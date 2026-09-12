from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from angel_market.domain.scenario import (
    DelayHiringAction,
    HiringAction,
    MrrGrowthAssumption,
    OpexAdjustment,
    ReceiptsAssumption,
    Scenario,
)

from .cashflow import CashFlowProjection, project_cashflow
from .constraints import FeasibilityResult, evaluate_feasibility
from .metrics import FinancialMetrics, calculate_metrics


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    scenario: Scenario
    projection: CashFlowProjection
    metrics: FinancialMetrics
    feasibility: FeasibilityResult
    limitations: tuple[str, ...] = (
        "A analise e mensal e nao identifica falta de caixa dentro do mes.",
        "Os resultados dependem integralmente das premissas declaradas.",
        "MRR e ARR run-rate nao representam receita realizada nem recebimento.",
        "Viabilidade financeira nao implica sucesso do marco operacional.",
    )


@dataclass(frozen=True, slots=True)
class ScenarioComparison:
    results: tuple[ScenarioResult, ...]
    baseline_difference_warning: str | None = None


def run_scenario(scenario: Scenario) -> ScenarioResult:
    periods = scenario.baseline.periods[: scenario.horizon]
    receipts = [period.operating_receipts_cents for period in periods]
    personnel = [period.personnel_cents for period in periods]
    marketing = [period.marketing_cents for period in periods]
    other_opex = [period.other_opex_cents for period in periods]
    incremental_cost = [0] * scenario.horizon
    mrr_growth: list[Decimal | None] = [None] * scenario.horizon

    operational_violations = _validate_allowed_actions(scenario)
    hires = {action.id: action for action in scenario.actions if isinstance(action, HiringAction)}
    delayed_starts = {
        action.hiring_action_id: action.new_start_month
        for action in scenario.actions
        if isinstance(action, DelayHiringAction)
    }
    unknown_delays = set(delayed_starts) - set(hires)
    if unknown_delays:
        raise ValueError("adiamento referencia uma contratacao inexistente no cenario")

    for action in scenario.actions:
        if isinstance(action, HiringAction):
            start_month = delayed_starts.get(action.id, action.start_month)
            for index, period in enumerate(periods):
                if period.month >= start_month:
                    cost = action.monthly_cost_total_cents
                    if period.month == start_month:
                        cost += action.initial_cost_total_cents
                    personnel[index] += cost
                    incremental_cost[index] += cost
        elif isinstance(action, OpexAdjustment):
            target = marketing if action.category == "marketing" else other_opex
            for index, period in enumerate(periods):
                if period.month >= action.start_month and (
                    action.end_month is None or period.month <= action.end_month
                ):
                    target[index] += action.amount_cents
                    incremental_cost[index] += action.amount_cents

    for assumption in scenario.assumptions:
        if isinstance(assumption, ReceiptsAssumption):
            receipts = _apply_receipts_assumption(receipts, periods, assumption)
        elif isinstance(assumption, MrrGrowthAssumption):
            start = assumption.start_month or periods[0].month
            for index, period in enumerate(periods):
                if period.month >= start:
                    mrr_growth[index] = assumption.monthly_growth

    operational_violations += _validate_operational_floors(
        scenario, periods, personnel, marketing, other_opex
    )
    baseline_projection = project_cashflow(
        periods,
        currency=scenario.baseline.currency,
        initial_cash_cents=scenario.baseline.initial_cash_cents,
        initial_mrr_cents=scenario.baseline.initial_mrr_cents,
    )
    projection = project_cashflow(
        periods,
        currency=scenario.baseline.currency,
        initial_cash_cents=scenario.baseline.initial_cash_cents,
        initial_mrr_cents=scenario.baseline.initial_mrr_cents,
        receipts_cents=receipts,
        personnel_cents=personnel,
        marketing_cents=marketing,
        other_opex_cents=other_opex,
        incremental_cost_cents=incremental_cost,
        mrr_growth_overrides=mrr_growth,
    )
    feasibility = evaluate_feasibility(
        projection, scenario.constraints, tuple(operational_violations)
    )
    metrics = calculate_metrics(
        projection,
        milestone_month=scenario.constraints.milestone_month,
        minimum_reserve_cents=scenario.constraints.minimum_cash_reserve_cents,
        baseline_projection=baseline_projection,
    )
    return ScenarioResult(scenario, projection, metrics, feasibility)


def compare_scenarios(
    scenarios: tuple[Scenario, ...], *, allow_different_baseline: bool = False
) -> ScenarioComparison:
    if len(scenarios) < 2:
        raise ValueError("selecione pelo menos dois cenarios")
    base_months = {scenario.baseline.base_month for scenario in scenarios}
    horizons = {scenario.horizon for scenario in scenarios}
    versions = {scenario.baseline_version for scenario in scenarios}
    if len(base_months) > 1 or len(horizons) > 1:
        raise ValueError("comparacao exige a mesma data-base e o mesmo horizonte")
    warning = None
    if len(versions) > 1:
        if not allow_different_baseline:
            raise ValueError("baselines diferentes exigem confirmacao explicita")
        warning = "Comparacao usa versoes diferentes de baseline; deltas nao sao diretamente equivalentes."
    return ScenarioComparison(tuple(run_scenario(scenario) for scenario in scenarios), warning)


def _apply_receipts_assumption(receipts, periods, assumption: ReceiptsAssumption) -> list[int]:
    adjusted = [0] * len(receipts)
    start = assumption.start_month or periods[0].month
    factor = Decimal("1") + assumption.shock_fraction
    for index, (amount, period) in enumerate(zip(receipts, periods)):
        if period.month < start:
            adjusted[index] += amount
            continue
        shifted_index = index + assumption.delay_months
        if shifted_index < len(adjusted):
            adjusted[shifted_index] += int(
                (Decimal(amount) * factor).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
    return adjusted


def _validate_allowed_actions(scenario: Scenario) -> list[str]:
    allowed = set(scenario.constraints.allowed_actions)
    return [
        f"acao '{action.kind}' nao esta entre as acoes permitidas"
        for action in scenario.actions
        if action.kind not in allowed
    ]


def _validate_operational_floors(scenario, periods, personnel, marketing, other_opex) -> list[str]:
    series = {
        "personnel": personnel,
        "marketing": marketing,
        "other_opex": other_opex,
    }
    violations: list[str] = []
    for category, floor in scenario.constraints.protected_costs_cents.items():
        if category not in series:
            violations.append(f"categoria protegida desconhecida: {category}")
            continue
        for period, value in zip(periods, series[category]):
            if period.month <= scenario.constraints.milestone_month and value < floor:
                violations.append(
                    f"{category} abaixo do custo protegido em {period.month}"
                )
                break
    return violations

