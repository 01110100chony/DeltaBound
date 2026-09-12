from __future__ import annotations

from decimal import Decimal

import pytest

from angel_market.domain.periods import YearMonth
from angel_market.domain.scenario import BaselineSnapshot, DecisionConstraints, FinancialPeriod, Scenario


def make_baseline(
    *,
    months: int = 12,
    initial_cash: int = 100_000_00,
    receipts: int = 20_000_00,
    personnel: int = 25_000_00,
    marketing: int = 5_000_00,
    revenue: int | None = None,
    mrr: int | None = 20_000_00,
    financing: int = 0,
) -> BaselineSnapshot:
    start = YearMonth.parse("2026-01")
    periods = tuple(
        FinancialPeriod(
            month=start.add(index),
            starting_cash_cents=initial_cash if index == 0 else None,
            operating_receipts_cents=receipts,
            revenue_recognized_cents=revenue,
            personnel_cents=personnel,
            marketing_cents=marketing,
            other_opex_cents=0,
            capex_cents=0,
            debt_service_cents=0,
            financing_inflows_cents=financing if index == 0 else 0,
            mrr_cents=mrr if index == 0 else None,
            net_mrr_growth=Decimal("0"),
        )
        for index in range(months)
    )
    return BaselineSnapshot(
        company_id="company-1",
        currency="BRL",
        version="baseline-1",
        periods=periods,
        initial_cash_cents=initial_cash,
        initial_mrr_cents=mrr,
        base_month=start,
    )


def make_scenario(baseline: BaselineSnapshot, *, reserve: int = 0, name: str = "Baseline") -> Scenario:
    return Scenario(
        company_id=baseline.company_id,
        name=name,
        baseline=baseline,
        horizon=len(baseline.periods),
        constraints=DecisionConstraints(
            milestone_month=baseline.periods[-1].month,
            minimum_cash_reserve_cents=reserve,
        ),
    )


@pytest.fixture
def baseline_factory():
    return make_baseline


@pytest.fixture
def scenario_factory():
    return make_scenario

