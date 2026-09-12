from dataclasses import replace

from angel_market.domain.periods import YearMonth
from angel_market.domain.scenario import DelayHiringAction, HiringAction, OpexAdjustment
from angel_market.engine.scenarios import run_scenario


def test_hiring_in_month_one_is_incremental_once(baseline_factory, scenario_factory):
    baseline = baseline_factory(months=2, receipts=0, personnel=10_000_00, marketing=0)
    action = HiringAction(2, YearMonth.parse("2026-01"), 3_000_00, 1_000_00)
    scenario = replace(scenario_factory(baseline), actions=(action,))
    result = run_scenario(scenario)
    assert result.projection.rows[0].personnel_cents == 17_000_00
    assert result.projection.rows[1].personnel_cents == 16_000_00
    assert result.metrics.total_incremental_cost_cents == 13_000_00


def test_delay_hiring_changes_only_affected_months(baseline_factory, scenario_factory):
    baseline = baseline_factory(months=3, receipts=0, personnel=0, marketing=0)
    hire = HiringAction(1, YearMonth.parse("2026-01"), 5_000_00)
    delay = DelayHiringAction(hire.id, YearMonth.parse("2026-03"))
    scenario = replace(scenario_factory(baseline), actions=(hire, delay))
    rows = run_scenario(scenario).projection.rows
    assert [row.personnel_cents for row in rows] == [0, 0, 5_000_00]


def test_opex_cut_cannot_cross_protected_floor(baseline_factory, scenario_factory):
    baseline = baseline_factory(months=2, marketing=5_000_00)
    action = OpexAdjustment("marketing", -4_000_00, YearMonth.parse("2026-01"))
    base_scenario = scenario_factory(baseline)
    constraints = replace(base_scenario.constraints, protected_costs_cents={"marketing": 2_000_00})
    result = run_scenario(replace(base_scenario, constraints=constraints, actions=(action,)))
    assert not result.feasibility.feasible
    assert "marketing abaixo" in result.feasibility.operational_violations[0]


def test_changed_scenario_does_not_mutate_frozen_baseline(baseline_factory, scenario_factory):
    baseline = baseline_factory(months=1)
    original = baseline.periods[0].personnel_cents
    action = HiringAction(1, YearMonth.parse("2026-01"), 5_000_00)
    run_scenario(replace(scenario_factory(baseline), actions=(action,)))
    assert baseline.periods[0].personnel_cents == original

