from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Callable

from angel_market.domain.periods import YearMonth
from angel_market.domain.scenario import HiringAction, OpexAdjustment, ReceiptsAssumption, Scenario

from .scenarios import run_scenario


@dataclass(frozen=True, slots=True)
class StressLimit:
    factor: str
    value: Decimal | int | str | None
    unit: str
    method: str
    tolerance: Decimal | None
    bounded: bool
    base_feasible: bool
    failure_condition: str


def maximum_receipts_decline(
    scenario: Scenario,
    *,
    tolerance: Decimal = Decimal("0.0001"),
    maximum: Decimal = Decimal("1"),
) -> StressLimit:
    def feasible(value: Decimal) -> bool:
        stressed = replace(
            scenario,
            assumptions=scenario.assumptions + (ReceiptsAssumption(shock_fraction=-value),),
        )
        return run_scenario(stressed).feasibility.feasible

    return _bisect_limit(
        "queda de recebimentos", feasible, Decimal("0"), maximum, tolerance, "fracao"
    )


def maximum_receipts_delay(scenario: Scenario, *, maximum_months: int | None = None) -> StressLimit:
    upper = scenario.horizon if maximum_months is None else maximum_months
    values = []
    for delay in range(upper + 1):
        stressed = replace(
            scenario,
            assumptions=scenario.assumptions + (ReceiptsAssumption(delay_months=delay),),
        )
        values.append(run_scenario(stressed).feasibility.feasible)
    _assert_monotonic(values)
    last_feasible = max((index for index, value in enumerate(values) if value), default=None)
    return StressLimit(
        factor="atraso de recebimentos",
        value=last_feasible,
        unit="meses",
        method="grade_inteira_explicita",
        tolerance=None,
        bounded=last_feasible is not None and last_feasible < upper,
        base_feasible=values[0],
        failure_condition=_failure_message(last_feasible, "meses", upper),
    )


def maximum_hiring_cost(
    scenario: Scenario,
    hiring_action_id: str,
    *,
    maximum_monthly_cost_per_person_cents: int,
    tolerance_cents: int = 100,
) -> StressLimit:
    hiring = next(
        (
            action
            for action in scenario.actions
            if isinstance(action, HiringAction) and action.id == hiring_action_id
        ),
        None,
    )
    if hiring is None:
        raise ValueError("contratacao nao encontrada no cenario")

    def feasible(value: Decimal) -> bool:
        replacement = replace(hiring, monthly_cost_per_person_cents=int(value))
        actions = tuple(replacement if action.id == hiring.id else action for action in scenario.actions)
        return run_scenario(replace(scenario, actions=actions)).feasibility.feasible

    return _bisect_limit(
        "custo mensal por pessoa",
        feasible,
        Decimal("0"),
        Decimal(maximum_monthly_cost_per_person_cents),
        Decimal(tolerance_cents),
        "centavos/pessoa/mes",
    )


def maximum_opex_increase(
    scenario: Scenario,
    *,
    category: str,
    start_month: YearMonth,
    maximum_monthly_cents: int,
    tolerance_cents: int = 100,
) -> StressLimit:
    if category not in {"marketing", "other_opex"}:
        raise ValueError("categoria deve ser marketing ou other_opex")

    def feasible(value: Decimal) -> bool:
        action = OpexAdjustment(category, int(value), start_month)
        return run_scenario(replace(scenario, actions=scenario.actions + (action,))).feasibility.feasible

    return _bisect_limit(
        f"aumento de {category}",
        feasible,
        Decimal("0"),
        Decimal(maximum_monthly_cents),
        Decimal(tolerance_cents),
        "centavos/mes",
    )


def earliest_feasible_hiring_month(scenario: Scenario, hiring_action_id: str) -> StressLimit:
    hiring = next(
        (
            action
            for action in scenario.actions
            if isinstance(action, HiringAction) and action.id == hiring_action_id
        ),
        None,
    )
    if hiring is None:
        raise ValueError("contratacao nao encontrada no cenario")
    months = [period.month for period in scenario.baseline.periods[: scenario.horizon]]
    feasible_month = None
    values = []
    for month in months:
        replacement = replace(hiring, start_month=month)
        actions = tuple(replacement if action.id == hiring.id else action for action in scenario.actions)
        is_feasible = run_scenario(replace(scenario, actions=actions)).feasibility.feasible
        values.append(is_feasible)
        if is_feasible and feasible_month is None:
            feasible_month = month
    if any(values[index] and not values[index + 1] for index in range(len(values) - 1)):
        raise ValueError("relacao nao monotona; use uma grade explicita e reporte cada alternativa")
    return StressLimit(
        factor="primeiro mes viavel para contratar",
        value=None if feasible_month is None else str(feasible_month),
        unit="mes",
        method="grade_mensal_explicita",
        tolerance=None,
        bounded=feasible_month is not None,
        base_feasible=run_scenario(scenario).feasibility.feasible,
        failure_condition=(
            "nenhum mes do horizonte preserva a reserva"
            if feasible_month is None
            else f"meses anteriores a {feasible_month} violam a reserva ou restricoes"
        ),
    )


def _bisect_limit(
    factor: str,
    feasible: Callable[[Decimal], bool],
    lower: Decimal,
    upper: Decimal,
    tolerance: Decimal,
    unit: str,
) -> StressLimit:
    if tolerance <= 0 or upper < lower:
        raise ValueError("intervalo e tolerancia devem ser validos")
    samples = [lower + (upper - lower) * Decimal(index) / Decimal(4) for index in range(5)]
    sample_results = [feasible(value) for value in samples]
    _assert_monotonic(sample_results)
    base_feasible = sample_results[0]
    if not base_feasible:
        return StressLimit(
            factor, lower, unit, "bissecao", tolerance, True, False, "plano base ja e inviavel"
        )
    if sample_results[-1]:
        return StressLimit(
            factor,
            upper,
            unit,
            "bissecao",
            tolerance,
            False,
            True,
            "limite superior testado ainda e viavel",
        )
    low, high = lower, upper
    while high - low > tolerance:
        midpoint = (low + high) / Decimal(2)
        if feasible(midpoint):
            low = midpoint
        else:
            high = midpoint
    return StressLimit(
        factor,
        low,
        unit,
        "bissecao",
        tolerance,
        True,
        True,
        f"valores acima de aproximadamente {low} violam a reserva ou restricoes",
    )


def _assert_monotonic(values: list[bool]) -> None:
    seen_failure = False
    for value in values:
        if not value:
            seen_failure = True
        elif seen_failure:
            raise ValueError("relacao nao monotona; bissecao nao e apropriada")


def _failure_message(last_feasible: int | None, unit: str, upper: int) -> str:
    if last_feasible is None:
        return "plano base ja e inviavel"
    if last_feasible == upper:
        return "limite superior testado ainda e viavel"
    return f"acima de {last_feasible} {unit}, a reserva ou restricoes sao violadas"

