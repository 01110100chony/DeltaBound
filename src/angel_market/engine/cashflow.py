from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from angel_market.domain.periods import YearMonth
from angel_market.domain.scenario import FinancialPeriod

from .revenue import next_mrr_cents


@dataclass(frozen=True, slots=True)
class CashFlowRow:
    month: YearMonth
    cash_start_cents: int
    operating_receipts_cents: int
    personnel_cents: int
    marketing_cents: int
    other_opex_cents: int
    cash_cogs_cents: int
    operating_taxes_cents: int
    operating_payments_cents: int
    capex_cents: int
    debt_service_cents: int
    financing_inflows_cents: int
    other_net_cash_movements_cents: int
    gross_operating_burn_cents: int
    net_operating_burn_cents: int
    cash_end_cents: int
    revenue_recognized_cents: int | None
    mrr_cents: int | None
    arr_run_rate_cents: int | None
    incremental_action_cost_cents: int
    origin: str = "simulated"


@dataclass(frozen=True, slots=True)
class CashFlowProjection:
    currency: str
    initial_cash_cents: int
    rows: tuple[CashFlowRow, ...]


def project_cashflow(
    periods: Sequence[FinancialPeriod],
    *,
    currency: str,
    initial_cash_cents: int,
    initial_mrr_cents: int | None,
    receipts_cents: Sequence[int] | None = None,
    personnel_cents: Sequence[int] | None = None,
    marketing_cents: Sequence[int] | None = None,
    other_opex_cents: Sequence[int] | None = None,
    incremental_cost_cents: Sequence[int] | None = None,
    mrr_growth_overrides: Sequence[Decimal | None] | None = None,
) -> CashFlowProjection:
    size = len(periods)
    _check_length(size, receipts_cents, personnel_cents, marketing_cents, other_opex_cents)
    _check_length(size, incremental_cost_cents, mrr_growth_overrides)
    cash = initial_cash_cents
    mrr = initial_mrr_cents
    rows: list[CashFlowRow] = []

    for index, period in enumerate(periods):
        receipts = receipts_cents[index] if receipts_cents is not None else period.operating_receipts_cents
        personnel = personnel_cents[index] if personnel_cents is not None else period.personnel_cents
        marketing = marketing_cents[index] if marketing_cents is not None else period.marketing_cents
        other_opex = other_opex_cents[index] if other_opex_cents is not None else period.other_opex_cents
        values = (receipts, personnel, marketing, other_opex, period.cash_cogs_cents, period.operating_taxes_cents)
        if any(value < 0 for value in values):
            raise ValueError("recebimentos e componentes operacionais nao podem ser negativos")

        operating_payments = (
            personnel + marketing + other_opex + period.cash_cogs_cents + period.operating_taxes_cents
        )
        cash_start = cash
        cash = (
            cash_start
            + receipts
            - operating_payments
            - period.capex_cents
            - period.debt_service_cents
            + period.financing_inflows_cents
            + period.other_net_cash_movements_cents
        )

        growth_override = mrr_growth_overrides[index] if mrr_growth_overrides is not None else None
        if mrr is not None:
            if growth_override is not None:
                mrr = next_mrr_cents(mrr, growth_override)
            elif period.mrr_cents is not None:
                mrr = period.mrr_cents
            else:
                mrr = next_mrr_cents(mrr, period.net_mrr_growth)

        rows.append(
            CashFlowRow(
                month=period.month,
                cash_start_cents=cash_start,
                operating_receipts_cents=receipts,
                personnel_cents=personnel,
                marketing_cents=marketing,
                other_opex_cents=other_opex,
                cash_cogs_cents=period.cash_cogs_cents,
                operating_taxes_cents=period.operating_taxes_cents,
                operating_payments_cents=operating_payments,
                capex_cents=period.capex_cents,
                debt_service_cents=period.debt_service_cents,
                financing_inflows_cents=period.financing_inflows_cents,
                other_net_cash_movements_cents=period.other_net_cash_movements_cents,
                gross_operating_burn_cents=operating_payments,
                net_operating_burn_cents=operating_payments - receipts,
                cash_end_cents=cash,
                revenue_recognized_cents=period.revenue_recognized_cents,
                mrr_cents=mrr,
                arr_run_rate_cents=None if mrr is None else mrr * 12,
                incremental_action_cost_cents=(
                    incremental_cost_cents[index] if incremental_cost_cents is not None else 0
                ),
            )
        )
    return CashFlowProjection(currency=currency, initial_cash_cents=initial_cash_cents, rows=tuple(rows))


def _check_length(expected: int, *values: Sequence[object] | None) -> None:
    if any(value is not None and len(value) != expected for value in values):
        raise ValueError("series de entrada devem ter o mesmo tamanho dos periodos")

