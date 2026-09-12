from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from html import escape

from angel_market.domain.company import Company
from angel_market.domain.scenario import (
    DelayHiringAction,
    HiringAction,
    MrrGrowthAssumption,
    OpexAdjustment,
    ReceiptsAssumption,
)
from angel_market.engine.reverse_stress import StressLimit
from angel_market.engine.scenarios import ScenarioResult


@dataclass(frozen=True, slots=True)
class DecisionMemoInput:
    company: Company
    objective: str
    chosen_decision: str
    next_review_date: str
    results: tuple[ScenarioResult, ...]
    rationale: str = ""
    stress_limits: tuple[StressLimit, ...] = ()


def generate_decision_memo(data: DecisionMemoInput) -> str:
    if not data.results:
        raise ValueError("memo precisa de pelo menos um resultado")
    central = data.results[0]
    scenario_rows = "".join(_scenario_row(result) for result in data.results)
    actions = _list_items(
        [_describe_action(action, data.company.currency) for action in central.scenario.actions],
        "Nenhuma acao incremental.",
    )
    assumptions = _list_items(
        [_describe_assumption(item) for item in central.scenario.assumptions],
        "Sem alteracoes adicionais; fluxos do baseline declarado.",
    )
    stress = _list_items(
        [_describe_stress(item, data.company.currency) for item in data.stress_limits],
        "Nenhum limite reverso anexado a este memo.",
    )
    limitations = _list_items(list(central.limitations), "")
    feasibility = "Viavel" if central.feasibility.feasible else "Inviavel"
    invalidation = (
        "A primeira violacao ocorre em " + central.feasibility.violation_month
        if central.feasibility.violation_month
        else "O plano deixa de ser viavel quando o caixa mensal cai abaixo da reserva ou uma restricao operacional e violada."
    )
    first_row = central.projection.rows[0]
    runway_text = (
        "nao aplicavel"
        if central.metrics.static_runway_months is None
        else f"{central.metrics.static_runway_months} meses (aproximacao estatica)"
    )
    reserve = central.scenario.constraints.minimum_cash_reserve_cents
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Decision Memo — {escape(data.company.name)}</title>
<style>
body {{ font: 15px/1.45 Arial, sans-serif; color: #18212f; max-width: 900px; margin: 36px auto; }}
h1, h2 {{ color: #14213d; }} h2 {{ margin-top: 28px; border-bottom: 1px solid #d9dee7; }}
table {{ border-collapse: collapse; width: 100%; }} th, td {{ border: 1px solid #d9dee7; padding: 8px; text-align: left; }}
.meta {{ color: #526072; }} .result {{ padding: 12px; border-left: 5px solid #315caa; background: #f4f7fb; }}
@media print {{ body {{ margin: 12mm; }} }}
</style>
</head>
<body>
<h1>Decision Memo</h1>
<p class="meta"><strong>Empresa:</strong> {escape(data.company.name)}<br>
<strong>Data-base:</strong> {central.scenario.baseline.base_month}<br>
<strong>Horizonte:</strong> {central.scenario.horizon} meses<br>
<strong>Objetivo:</strong> {escape(data.objective)}<br>
<strong>Restricao:</strong> manter ao menos {_money(reserve, data.company.currency)} ate {central.scenario.constraints.milestone_month}</p>

<h2>Estado atual</h2>
<ul>
<li>Caixa inicial: {_money(central.projection.initial_cash_cents, data.company.currency)}</li>
<li>MRR de referencia: {_money(first_row.mrr_cents, data.company.currency) if first_row.mrr_cents is not None else "nao informado"}</li>
<li>Burn operacional liquido medio: {_money(central.metrics.average_net_operating_burn_cents, data.company.currency)}/mes</li>
<li>Runway: {runway_text}</li>
</ul>

<h2>Decisao avaliada</h2>{actions}
<h2>Cenarios</h2>
<table><thead><tr><th>Cenario</th><th>Caixa final</th><th>Caixa minimo</th><th>Cash-out</th><th>Custo incremental</th><th>Reserva</th><th>Resultado</th></tr></thead>
<tbody>{scenario_rows}</tbody></table>

<h2>Resultado central</h2>
<p class="result"><strong>{feasibility}.</strong> Margem minima contra a reserva: {_money(central.feasibility.minimum_margin_cents, data.company.currency)}.</p>

<h2>Limites / stress</h2>{stress}
<h2>Principais premissas</h2>{assumptions}
<h2>Condicao que invalida o plano</h2><p>{escape(invalidation)}</p>
<h2>Decisao escolhida</h2><p>{escape(data.chosen_decision)}</p>
<p><strong>Racional registrado:</strong> {escape(data.rationale) if data.rationale else "nao informado"}</p>
<p><strong>Data da proxima revisao:</strong> {escape(data.next_review_date)}</p>
<h2>Limitacoes</h2>{limitations}
</body></html>"""


def _scenario_row(result: ScenarioResult) -> str:
    metrics = result.metrics
    currency = result.scenario.baseline.currency
    cash_out = metrics.projected_cash_out_month or "nao ocorre no horizonte"
    status = "viavel" if result.feasibility.feasible else "inviavel"
    return (
        "<tr>"
        f"<td>{escape(result.scenario.name)}</td>"
        f"<td>{_money(metrics.ending_cash_cents, currency)}</td>"
        f"<td>{_money(metrics.minimum_cash_cents, currency)}</td>"
        f"<td>{escape(cash_out)}</td>"
        f"<td>{_money(metrics.total_incremental_cost_cents, currency)}</td>"
        f"<td>{_money(result.scenario.constraints.minimum_cash_reserve_cents, currency)}</td>"
        f"<td>{status}</td></tr>"
    )


def _describe_action(action, currency: str) -> str:
    if isinstance(action, HiringAction):
        return (
            f"Contratar {action.quantity} pessoa(s) em {action.start_month}, "
            f"a {_money(action.monthly_cost_per_person_cents, currency)} por pessoa/mes, "
            f"mais {_money(action.initial_cost_total_cents, currency)} inicial."
        )
    if isinstance(action, DelayHiringAction):
        return f"Adiar a contratacao {action.hiring_action_id} para {action.new_start_month}."
    if isinstance(action, OpexAdjustment):
        recurrence = "recorrente" if action.end_month is None else f"ate {action.end_month}"
        return (
            f"Ajustar {action.category} em {_money(action.amount_cents, currency)} "
            f"desde {action.start_month}, {recurrence}."
        )
    return "Acao nao reconhecida."


def _describe_assumption(assumption) -> str:
    if isinstance(assumption, ReceiptsAssumption):
        percent = (assumption.shock_fraction * 100).quantize(Decimal("0.01"))
        return (
            f"Recebimentos com choque de {percent}% e atraso de {assumption.delay_months} mes(es)"
            + (f" desde {assumption.start_month}." if assumption.start_month else ".")
        )
    if isinstance(assumption, MrrGrowthAssumption):
        percent = (assumption.monthly_growth * 100).quantize(Decimal("0.01"))
        return f"Crescimento liquido mensal de MRR: {percent}%."
    return "Premissa nao reconhecida."


def _describe_stress(limit: StressLimit, currency: str) -> str:
    value = "sem solucao" if limit.value is None else str(limit.value)
    if "centavos" in limit.unit and limit.value is not None:
        value = _money(int(Decimal(str(limit.value))), currency)
    bounded = "limite encontrado" if limit.bounded else "limite nao atingido no intervalo testado"
    tolerance = "" if limit.tolerance is None else f"; tolerancia {limit.tolerance}"
    return f"{limit.factor}: {value} ({bounded}; metodo {limit.method}{tolerance})."


def _list_items(items: list[str], empty_message: str) -> str:
    if not items:
        return f"<p>{escape(empty_message)}</p>"
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"


def _money(cents: int | None, currency: str) -> str:
    if cents is None:
        return "nao informado"
    amount = Decimal(cents) / 100
    return f"{currency} {amount:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
