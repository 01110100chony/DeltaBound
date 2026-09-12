from dataclasses import replace
from decimal import Decimal

from angel_market.domain.periods import YearMonth
from angel_market.domain.scenario import HiringAction
from angel_market.engine.reverse_stress import (
    earliest_feasible_hiring_month,
    maximum_hiring_cost,
    maximum_opex_increase,
    maximum_receipts_decline,
    maximum_receipts_delay,
)


def robust_scenario(baseline_factory, scenario_factory):
    baseline = baseline_factory(
        months=9,
        initial_cash=300_000_00,
        receipts=20_000_00,
        personnel=40_000_00,
        marketing=5_000_00,
    )
    return scenario_factory(baseline, reserve=50_000_00)


def test_maximum_receipts_delay_is_one_month(baseline_factory, scenario_factory):
    limit = maximum_receipts_delay(robust_scenario(baseline_factory, scenario_factory))
    assert limit.value == 1
    assert limit.method == "grade_inteira_explicita"


def test_maximum_hiring_cost_uses_bisection(baseline_factory, scenario_factory):
    scenario = robust_scenario(baseline_factory, scenario_factory)
    hire = HiringAction(1, YearMonth.parse("2026-08"), 12_000_00)
    scenario = replace(scenario, actions=(hire,))
    limit = maximum_hiring_cost(
        scenario, hire.id, maximum_monthly_cost_per_person_cents=30_000_00, tolerance_cents=1
    )
    assert abs(int(limit.value) - 12_500_00) <= 1
    assert limit.method == "bissecao"


def test_earliest_hiring_month_is_month_eight(baseline_factory, scenario_factory):
    scenario = robust_scenario(baseline_factory, scenario_factory)
    hire = HiringAction(1, YearMonth.parse("2026-08"), 12_000_00)
    limit = earliest_feasible_hiring_month(replace(scenario, actions=(hire,)), hire.id)
    assert limit.value == "2026-08"


def test_receipts_decline_and_opex_limits_are_reproducible(baseline_factory, scenario_factory):
    scenario = robust_scenario(baseline_factory, scenario_factory)
    receipt_limit = maximum_receipts_decline(scenario, tolerance=Decimal("0.000001"))
    opex_limit = maximum_opex_increase(
        scenario,
        category="marketing",
        start_month=YearMonth.parse("2026-08"),
        maximum_monthly_cents=30_000_00,
        tolerance_cents=1,
    )
    assert abs(Decimal(receipt_limit.value) - Decimal("0.138888")) < Decimal("0.00001")
    assert abs(int(opex_limit.value) - 12_500_00) <= 1

