from __future__ import annotations

from dataclasses import replace

from angel_market.domain.scenario import FinancialPeriod
from angel_market.engine.scenarios import run_scenario


def test_reference_cashflow_reaches_zero_in_month_10(baseline_factory, scenario_factory):
    baseline = baseline_factory(months=10)
    result = run_scenario(scenario_factory(baseline))

    assert result.projection.rows[0].cash_end_cents == 90_000_00
    assert result.projection.rows[9].cash_end_cents == 0
    assert result.metrics.projected_cash_out_month == "2026-10"
    assert result.metrics.projected_runway_complete_months == 9


def test_cash_without_movements_is_constant(baseline_factory, scenario_factory):
    baseline = baseline_factory(months=3, receipts=0, personnel=0, marketing=0)
    result = run_scenario(scenario_factory(baseline))
    assert [row.cash_end_cents for row in result.projection.rows] == [100_000_00] * 3
    assert result.metrics.static_runway_months is None


def test_revenue_without_receipt_does_not_increase_cash(baseline_factory, scenario_factory):
    baseline = baseline_factory(months=1, receipts=0, personnel=10_000_00, marketing=0, revenue=40_000_00)
    row = run_scenario(scenario_factory(baseline)).projection.rows[0]
    assert row.revenue_recognized_cents == 40_000_00
    assert row.cash_end_cents == 90_000_00


def test_receipt_without_revenue_increases_cash(baseline_factory, scenario_factory):
    baseline = baseline_factory(months=1, receipts=20_000_00, personnel=0, marketing=0, revenue=None)
    row = run_scenario(scenario_factory(baseline)).projection.rows[0]
    assert row.revenue_recognized_cents is None
    assert row.cash_end_cents == 120_000_00


def test_single_expense_only_affects_one_month(baseline_factory, scenario_factory):
    baseline = baseline_factory(months=3, receipts=0, personnel=0, marketing=0)
    periods = list(baseline.periods)
    periods[1] = replace(periods[1], capex_cents=7_000_00)
    baseline = replace(baseline, periods=tuple(periods))
    values = [row.cash_end_cents for row in run_scenario(scenario_factory(baseline)).projection.rows]
    assert values == [100_000_00, 93_000_00, 93_000_00]


def test_negative_burn_has_no_static_runway(baseline_factory, scenario_factory):
    baseline = baseline_factory(months=2, receipts=30_000_00, personnel=10_000_00, marketing=0)
    result = run_scenario(scenario_factory(baseline))
    assert result.metrics.average_net_operating_burn_cents == -20_000_00
    assert result.metrics.static_runway_months is None


def test_zero_initial_cash_is_immediate_insufficiency(baseline_factory, scenario_factory):
    baseline = baseline_factory(months=1, initial_cash=0, receipts=0, personnel=0, marketing=0)
    result = run_scenario(scenario_factory(baseline))
    assert result.metrics.projected_cash_out_month == "2026-01"
    assert result.metrics.projected_runway_complete_months == 0


def test_no_cash_out_is_reported_as_absent(baseline_factory, scenario_factory):
    baseline = baseline_factory(months=4, receipts=10_000_00, personnel=0, marketing=0)
    result = run_scenario(scenario_factory(baseline))
    assert result.metrics.projected_cash_out_month is None
    assert result.metrics.projected_runway_complete_months is None


def test_reserve_is_violated_before_cash_zero(baseline_factory, scenario_factory):
    baseline = baseline_factory(months=10)
    result = run_scenario(scenario_factory(baseline, reserve=50_000_00))
    assert result.metrics.minimum_reserve_violation_month == "2026-06"
    assert result.metrics.projected_cash_out_month == "2026-10"


def test_financing_is_cash_inflow_not_operating_receipt(baseline_factory, scenario_factory):
    baseline = baseline_factory(months=1, receipts=0, personnel=0, marketing=0, financing=30_000_00)
    row = run_scenario(scenario_factory(baseline)).projection.rows[0]
    assert row.operating_receipts_cents == 0
    assert row.net_operating_burn_cents == 0
    assert row.cash_end_cents == 130_000_00

