from __future__ import annotations

import csv
import hashlib
import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from angel_market.domain.money import to_cents
from angel_market.domain.periods import YearMonth
from angel_market.domain.scenario import BaselineSnapshot, FinancialPeriod

from .schema import MAX_CSV_BYTES, OPTIONAL_COLUMNS, REQUIRED_COLUMNS
from .validation import ValidationIssue


@dataclass(frozen=True, slots=True)
class ParsedCsvImport:
    periods: tuple[FinancialPeriod, ...]
    initial_cash_cents: int
    initial_mrr_cents: int | None
    content_hash: str

    def to_baseline(self, company_id: str, currency: str, version: str) -> BaselineSnapshot:
        return BaselineSnapshot(
            company_id=company_id,
            currency=currency,
            version=version,
            periods=self.periods,
            initial_cash_cents=self.initial_cash_cents,
            initial_mrr_cents=self.initial_mrr_cents,
            base_month=self.periods[0].month,
        )


@dataclass(frozen=True, slots=True)
class CsvValidationResult:
    parsed: ParsedCsvImport | None
    issues: tuple[ValidationIssue, ...]
    preview: tuple[dict[str, Any], ...]

    @property
    def valid(self) -> bool:
        return self.parsed is not None and not self.issues


def parse_financial_csv(content: bytes) -> CsvValidationResult:
    issues: list[ValidationIssue] = []
    if len(content) > MAX_CSV_BYTES:
        return CsvValidationResult(
            None,
            (ValidationIssue(None, "arquivo", "limite de 2 MB excedido"),),
            (),
        )
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return CsvValidationResult(
            None,
            (ValidationIssue(None, "arquivo", "use codificacao UTF-8"),),
            (),
        )

    reader = csv.DictReader(io.StringIO(text), strict=True)
    headers = tuple(reader.fieldnames or ())
    missing_headers = [column for column in REQUIRED_COLUMNS if column not in headers]
    unknown_headers = [
        column for column in headers if column not in REQUIRED_COLUMNS and column not in OPTIONAL_COLUMNS
    ]
    issues.extend(
        ValidationIssue(None, column, "coluna obrigatoria ausente") for column in missing_headers
    )
    issues.extend(
        ValidationIssue(None, column, "coluna nao suportada no schema V0") for column in unknown_headers
    )
    if missing_headers or unknown_headers:
        return CsvValidationResult(None, tuple(issues), ())

    rows: list[tuple[int, dict[str, str | None]]] = []
    try:
        rows = [(line, row) for line, row in enumerate(reader, start=2)]
    except csv.Error as exc:
        return CsvValidationResult(
            None,
            (ValidationIssue(None, "arquivo", f"CSV invalido: {exc}"),),
            (),
        )
    if not rows:
        return CsvValidationResult(
            None,
            (ValidationIssue(None, "arquivo", "inclua pelo menos um periodo"),),
            (),
        )

    parsed_rows: list[FinancialPeriod] = []
    preview: list[dict[str, Any]] = []
    seen_months: set[YearMonth] = set()
    for line, row in rows:
        period, row_issues = _parse_row(row, line)
        issues.extend(row_issues)
        if period is not None:
            if period.month in seen_months:
                issues.append(ValidationIssue(line, "month", "mes duplicado no arquivo"))
            seen_months.add(period.month)
            parsed_rows.append(period)
            preview.append(_preview_row(period))

    parsed_rows.sort(key=lambda period: period.month)
    if parsed_rows and parsed_rows[0].starting_cash_cents is None:
        issues.append(
            ValidationIssue(None, "starting_cash", "valor obrigatorio no primeiro mes; use 0 quando for zero")
        )
    if parsed_rows and parsed_rows[0].mrr_cents is None:
        issues.append(ValidationIssue(None, "mrr", "valor obrigatorio no primeiro mes; use 0 quando for zero"))
    for previous, current in zip(parsed_rows, parsed_rows[1:]):
        if previous.month.add(1) != current.month:
            issues.append(
                ValidationIssue(None, "month", f"lacuna entre {previous.month} e {current.month}")
            )
    if issues:
        return CsvValidationResult(None, tuple(issues), tuple(preview))

    first = parsed_rows[0]
    return CsvValidationResult(
        ParsedCsvImport(
            periods=tuple(parsed_rows),
            initial_cash_cents=first.starting_cash_cents or 0,
            initial_mrr_cents=first.mrr_cents,
            content_hash=hashlib.sha256(content).hexdigest(),
        ),
        (),
        tuple(preview),
    )


def _parse_row(
    row: dict[str, str | None], line: int
) -> tuple[FinancialPeriod | None, list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    try:
        month = YearMonth.parse((row.get("month") or "").strip())
    except ValueError as exc:
        issues.append(ValidationIssue(line, "month", str(exc)))
        return None, issues

    amounts: dict[str, int | None] = {}
    nonnegative = {
        "operating_receipts",
        "personnel",
        "marketing",
        "other_opex",
        "capex",
        "debt_service",
        "financing_inflows",
        "mrr",
        "revenue_recognized",
        "cash_cogs",
        "operating_taxes",
    }
    required_amounts = set(REQUIRED_COLUMNS) - {"month", "starting_cash", "mrr"}
    amount_columns = set(REQUIRED_COLUMNS + OPTIONAL_COLUMNS) - {
        "month",
        "net_mrr_growth",
        "origin",
    }
    for field in amount_columns:
        raw = (row.get(field) or "").strip()
        required = field in required_amounts
        if not raw:
            if required:
                issues.append(ValidationIssue(line, field, "valor ausente; use 0 quando for zero"))
            amounts[field] = None
            continue
        try:
            value = Decimal(raw)
            if not value.is_finite():
                raise InvalidOperation
            amounts[field] = to_cents(value)
        except (InvalidOperation, ValueError):
            issues.append(ValidationIssue(line, field, "numero invalido; use ponto decimal e sem formula"))
            amounts[field] = None
            continue
        if field in nonnegative and amounts[field] is not None and amounts[field] < 0:
            issues.append(ValidationIssue(line, field, "valor nao pode ser negativo"))

    growth = Decimal("0")
    raw_growth = (row.get("net_mrr_growth") or "").strip()
    if raw_growth:
        try:
            growth = Decimal(raw_growth)
            if not growth.is_finite() or growth < Decimal("-1"):
                raise InvalidOperation
        except InvalidOperation:
            issues.append(ValidationIssue(line, "net_mrr_growth", "taxa decimal deve ser >= -1"))

    origin = (row.get("origin") or "declared").strip().lower()
    if origin not in {"observed", "declared"}:
        issues.append(ValidationIssue(line, "origin", "use observed ou declared"))
    if issues:
        return None, issues
    return FinancialPeriod(
        month=month,
        starting_cash_cents=amounts["starting_cash"],
        operating_receipts_cents=amounts["operating_receipts"] or 0,
        personnel_cents=amounts["personnel"] or 0,
        marketing_cents=amounts["marketing"] or 0,
        other_opex_cents=amounts["other_opex"] or 0,
        capex_cents=amounts["capex"] or 0,
        debt_service_cents=amounts["debt_service"] or 0,
        financing_inflows_cents=amounts["financing_inflows"] or 0,
        other_net_cash_movements_cents=amounts.get("other_net_cash_movements") or 0,
        cash_cogs_cents=amounts.get("cash_cogs") or 0,
        operating_taxes_cents=amounts.get("operating_taxes") or 0,
        revenue_recognized_cents=amounts.get("revenue_recognized"),
        mrr_cents=amounts["mrr"],
        net_mrr_growth=growth,
        origin=origin,
    ), issues


def _preview_row(period: FinancialPeriod) -> dict[str, Any]:
    return {
        "month": str(period.month),
        "starting_cash": _amount(period.starting_cash_cents),
        "operating_receipts": _amount(period.operating_receipts_cents),
        "revenue_recognized": _amount(period.revenue_recognized_cents),
        "personnel": _amount(period.personnel_cents),
        "marketing": _amount(period.marketing_cents),
        "other_opex": _amount(period.other_opex_cents),
        "capex": _amount(period.capex_cents),
        "debt_service": _amount(period.debt_service_cents),
        "financing_inflows": _amount(period.financing_inflows_cents),
        "mrr": _amount(period.mrr_cents),
        "origin": period.origin,
    }


def _amount(cents: int | None) -> str | None:
    return None if cents is None else f"{Decimal(cents) / 100:.2f}"
