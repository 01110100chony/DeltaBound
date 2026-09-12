from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from angel_market.domain.periods import YearMonth

from .cashflow import CashFlowProjection


@dataclass(frozen=True, slots=True)
class FinancialMetrics:
    ending_cash_cents: int
    minimum_cash_cents: int
    average_gross_operating_burn_cents: int
    average_net_operating_burn_cents: int
    static_runway_months: Decimal | None
    static_runway_reference_months: tuple[str, ...]
    projected_cash_out_month: str | None
    projected_runway_complete_months: int | None
    minimum_reserve_violation_month: str | None
    total_incremental_cost_cents: int
    cash_required_to_sustain_plan_cents: int
    ending_cash_delta_vs_baseline_cents: int


def calculate_metrics(
    projection: CashFlowProjection,
    *,
    milestone_month: YearMonth,
    minimum_reserve_cents: int,
    baseline_projection: CashFlowProjection | None = None,
) -> FinancialMetrics:
    rows = projection.rows
    if not rows:
        raise ValueError("projecao vazia")
    relevant = [row for row in rows if row.month <= milestone_month]
    if not relevant:
        raise ValueError("marco nao esta contido na projecao")

    reference = rows[-min(3, len(rows)) :]
    average_net = _rounded_average([row.net_operating_burn_cents for row in reference])
    average_gross = _rounded_average([row.gross_operating_burn_cents for row in rows])
    runway = None
    if projection.initial_cash_cents > 0 and average_net > 0:
        runway = (Decimal(projection.initial_cash_cents) / Decimal(average_net)).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )

    cash_out_row = next((row for row in rows if row.cash_end_cents <= 0), None)
    reserve_row = next(
        (row for row in relevant if row.cash_end_cents < minimum_reserve_cents), None
    )
    minimum_relevant_cash = min(row.cash_end_cents for row in relevant)
    baseline_ending = baseline_projection.rows[-1].cash_end_cents if baseline_projection else rows[-1].cash_end_cents

    return FinancialMetrics(
        ending_cash_cents=rows[-1].cash_end_cents,
        minimum_cash_cents=min(row.cash_end_cents for row in rows),
        average_gross_operating_burn_cents=average_gross,
        average_net_operating_burn_cents=_rounded_average(
            [row.net_operating_burn_cents for row in rows]
        ),
        static_runway_months=runway,
        static_runway_reference_months=tuple(str(row.month) for row in reference),
        projected_cash_out_month=None if cash_out_row is None else str(cash_out_row.month),
        projected_runway_complete_months=None if cash_out_row is None else rows.index(cash_out_row),
        minimum_reserve_violation_month=None if reserve_row is None else str(reserve_row.month),
        total_incremental_cost_cents=sum(row.incremental_action_cost_cents for row in rows),
        cash_required_to_sustain_plan_cents=max(0, minimum_reserve_cents - minimum_relevant_cash),
        ending_cash_delta_vs_baseline_cents=rows[-1].cash_end_cents - baseline_ending,
    )


def _rounded_average(values: list[int]) -> int:
    return int((Decimal(sum(values)) / Decimal(len(values))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
