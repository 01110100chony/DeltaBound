from __future__ import annotations

from dataclasses import dataclass

from angel_market.domain.scenario import DecisionConstraints

from .cashflow import CashFlowProjection


@dataclass(frozen=True, slots=True)
class FeasibilityResult:
    feasible: bool
    minimum_margin_cents: int
    violation_month: str | None
    operational_violations: tuple[str, ...] = ()


def evaluate_feasibility(
    projection: CashFlowProjection,
    constraints: DecisionConstraints,
    operational_violations: tuple[str, ...] = (),
) -> FeasibilityResult:
    relevant = [row for row in projection.rows if row.month <= constraints.milestone_month]
    if not relevant:
        raise ValueError("marco nao esta contido na projecao")
    margins = [row.cash_end_cents - constraints.minimum_cash_reserve_cents for row in relevant]
    violation = next((row.month for row, margin in zip(relevant, margins) if margin < 0), None)
    return FeasibilityResult(
        feasible=violation is None and not operational_violations,
        minimum_margin_cents=min(margins),
        violation_month=None if violation is None else str(violation),
        operational_violations=operational_violations,
    )

