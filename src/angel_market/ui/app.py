from __future__ import annotations

import os
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from angel_market.domain.company import Company
from angel_market.domain.money import to_cents
from angel_market.domain.periods import YearMonth
from angel_market.domain.scenario import (
    DecisionConstraints,
    DelayHiringAction,
    HiringAction,
    MrrGrowthAssumption,
    OpexAdjustment,
    ReceiptsAssumption,
    Scenario,
)
from angel_market.engine.reverse_stress import (
    StressLimit,
    earliest_feasible_hiring_month,
    maximum_hiring_cost,
    maximum_opex_increase,
    maximum_receipts_decline,
    maximum_receipts_delay,
)
from angel_market.engine.scenarios import compare_scenarios, run_scenario
from angel_market.ingestion.csv_parser import parse_financial_csv
from angel_market.reports.memo import DecisionMemoInput, generate_decision_memo
from angel_market.storage.sqlite import Database


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB = ROOT / "data" / "private" / "angel_market.db"
PAGES = ("Company", "Import", "Scenario Builder", "Compare", "Stress", "Decision Memo", "History")


@st.cache_resource
def _database(path: str) -> Database:
    return Database(path)


def main() -> None:
    st.set_page_config(page_title="Angel Market", page_icon="📐", layout="wide")
    database = _database(os.getenv("ANGEL_MARKET_DB", str(DEFAULT_DB)))
    st.sidebar.title("Angel Market")
    page = st.sidebar.radio("Navegacao", PAGES)
    company = _company_selector(database)
    if page == "Company":
        _company_page(database, company)
        return
    if company is None:
        st.info("Cadastre e selecione uma empresa na tela Company.")
        return
    {
        "Import": _import_page,
        "Scenario Builder": _scenario_page,
        "Compare": _compare_page,
        "Stress": _stress_page,
        "Decision Memo": _memo_page,
        "History": _history_page,
    }[page](database, company)


def _company_selector(database: Database) -> Company | None:
    companies = database.list_companies()
    if not companies:
        st.sidebar.caption("Nenhuma empresa cadastrada")
        return None
    ids = [item["id"] for item in companies]
    names = {item["id"]: item["name"] for item in companies}
    selected = st.sidebar.selectbox(
        "Empresa",
        ids,
        format_func=lambda company_id: names[company_id],
        key="selected_company_id",
    )
    return database.get_company(selected)


def _company_page(database: Database, company: Company | None) -> None:
    st.title("Company")
    st.caption("Cadastro local e resumo financeiro da empresa selecionada.")
    with st.form("create_company", clear_on_submit=True):
        columns = st.columns(4)
        name = columns[0].text_input("Nome")
        currency = columns[1].text_input("Moeda ISO", "BRL", max_chars=3)
        sector = columns[2].text_input("Setor", "SaaS B2B")
        stage = columns[3].text_input("Estagio", "early-stage")
        if st.form_submit_button("Cadastrar empresa"):
            try:
                created = database.create_company(Company(name, currency, sector, stage))
                st.session_state["selected_company_id"] = created.id
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    if company is None:
        return
    st.subheader(company.name)
    st.write(f"{company.sector} · {company.stage} · {company.currency}")
    try:
        baseline = database.get_current_baseline(company.id)
    except KeyError:
        st.info("Ainda nao ha baseline. Use Import para incluir o primeiro plano.")
        return
    scenario = Scenario(
        company_id=company.id,
        name="Baseline atual",
        baseline=baseline,
        horizon=len(baseline.periods),
        constraints=DecisionConstraints(baseline.periods[-1].month, 0),
    )
    result = run_scenario(scenario)
    _metric_cards(result)
    st.line_chart(
        pd.DataFrame(
            {"Caixa": [_units(row.cash_end_cents) for row in result.projection.rows]},
            index=[str(row.month) for row in result.projection.rows],
        )
    )


def _import_page(database: Database, company: Company) -> None:
    st.title("Import")
    st.caption("Valide e revise a previa antes da confirmacao. Campos vazios nao sao convertidos em zero.")
    csv_tab, form_tab = st.tabs(("CSV", "Formulario"))
    with csv_tab:
        upload = st.file_uploader("CSV no schema V0", type="csv")
        if upload is not None:
            st.session_state["import_candidate"] = (company.id, upload.getvalue())
    with form_tab:
        with st.form("manual_import"):
            base_date = st.date_input("Primeiro mes", date.today().replace(day=1))
            horizon = st.number_input("Horizonte em meses", 1, 60, 12)
            columns = st.columns(4)
            initial_cash = columns[0].number_input("Caixa inicial", value=300_000.0)
            receipts = columns[1].number_input("Recebimentos mensais", value=20_000.0)
            personnel = columns[2].number_input("Pessoal mensal", value=40_000.0)
            marketing = columns[3].number_input("Marketing mensal", value=5_000.0)
            columns = st.columns(4)
            other_opex = columns[0].number_input("Outros OPEX", value=0.0)
            capex = columns[1].number_input("Capex", value=0.0)
            debt = columns[2].number_input("Servico da divida", value=0.0)
            financing = columns[3].number_input("Financiamento no 1o mes", value=0.0)
            mrr = st.number_input("MRR atual", value=20_000.0)
            growth = st.number_input("Crescimento liquido mensal de MRR (%)", value=0.0)
            origin = st.selectbox("Origem", ("declared", "observed"))
            if st.form_submit_button("Gerar previa"):
                frame = _manual_frame(
                    YearMonth(base_date.year, base_date.month),
                    int(horizon),
                    initial_cash,
                    receipts,
                    personnel,
                    marketing,
                    other_opex,
                    capex,
                    debt,
                    financing,
                    mrr,
                    growth,
                    origin,
                )
                st.session_state["import_candidate"] = (
                    company.id,
                    frame.to_csv(index=False).encode("utf-8"),
                )
    candidate = st.session_state.get("import_candidate")
    if candidate is None or candidate[0] != company.id:
        return
    validation = parse_financial_csv(candidate[1])
    if validation.preview:
        st.subheader("Previa normalizada")
        st.dataframe(pd.DataFrame(validation.preview), use_container_width=True, hide_index=True)
    if validation.issues:
        for issue in validation.issues:
            st.error(issue.display())
        return
    st.success("Arquivo valido. Confirme para criar uma nova versao do baseline.")
    if st.button("Confirmar importacao", type="primary"):
        publication = database.publish_import(company.id, validation.parsed)
        if publication.created:
            st.success(f"Baseline {publication.baseline.version[:8]} publicado.")
        else:
            st.info("Este mesmo arquivo ja foi publicado; nenhum periodo foi duplicado.")


def _scenario_page(database: Database, company: Company) -> None:
    st.title("Scenario Builder")
    try:
        baseline = database.get_current_baseline(company.id)
    except KeyError as exc:
        st.info(str(exc))
        return
    months = [str(period.month) for period in baseline.periods]
    with st.form("scenario_builder"):
        name = st.text_input("Nome do novo cenario", "Alternative A")
        horizon = st.slider("Horizonte", 1, len(months), len(months))
        eligible_months = months[:horizon]
        columns = st.columns(2)
        milestone = columns[0].selectbox("Marco-alvo", eligible_months, index=len(eligible_months) - 1)
        reserve = columns[1].number_input("Reserva minima", min_value=0.0, value=50_000.0)
        allowed = st.multiselect(
            "Acoes permitidas",
            ("hiring", "delay_hiring", "opex_adjustment"),
            default=("hiring", "delay_hiring", "opex_adjustment"),
        )
        st.markdown("#### Contratacao")
        hire_enabled = st.checkbox("Incluir contratacao")
        columns = st.columns(4)
        hire_quantity = columns[0].number_input("Quantidade", 1, 100, 1)
        hire_start = columns[1].selectbox("Inicio", eligible_months, key="hire_start")
        hire_cost = columns[2].number_input("Custo/pessoa/mes", min_value=0.0, value=12_000.0)
        hire_initial = columns[3].number_input("Custo inicial total", min_value=0.0, value=0.0)
        delay_enabled = st.checkbox("Adicionar adiamento explicito")
        delay_start = st.selectbox("Novo inicio", eligible_months, index=len(eligible_months) - 1)
        st.markdown("#### Ajuste de OPEX")
        opex_enabled = st.checkbox("Incluir ajuste de OPEX")
        columns = st.columns(4)
        opex_category = columns[0].selectbox("Categoria", ("marketing", "other_opex"))
        opex_amount = columns[1].number_input("Ajuste mensal (+/-)", value=0.0)
        opex_start = columns[2].selectbox("Inicio do ajuste", eligible_months)
        opex_end = columns[3].selectbox("Fim", ("recorrente", *eligible_months))
        st.markdown("#### Premissas explicitas")
        columns = st.columns(4)
        receipts_shock = columns[0].number_input("Choque recebimentos (%)", -100.0, 500.0, 0.0)
        receipts_delay = columns[1].number_input("Atraso recebimentos (meses)", 0, horizon, 0)
        mrr_growth = columns[2].number_input("Crescimento liquido MRR (%)", -100.0, 500.0, 0.0)
        apply_mrr = columns[3].checkbox("Substituir crescimento MRR")
        st.markdown("#### Custos mensais protegidos")
        columns = st.columns(3)
        protected_personnel = columns[0].number_input("Pessoal protegido", min_value=0.0, value=0.0)
        protected_marketing = columns[1].number_input("Marketing protegido", min_value=0.0, value=0.0)
        protected_other = columns[2].number_input("Outros OPEX protegidos", min_value=0.0, value=0.0)
        submitted = st.form_submit_button("Salvar e executar", type="primary")
    if not submitted:
        return
    try:
        actions = []
        if hire_enabled:
            hiring = HiringAction(
                int(hire_quantity),
                YearMonth.parse(hire_start),
                to_cents(hire_cost),
                to_cents(hire_initial),
            )
            actions.append(hiring)
            if delay_enabled:
                actions.append(DelayHiringAction(hiring.id, YearMonth.parse(delay_start)))
        if opex_enabled:
            actions.append(
                OpexAdjustment(
                    opex_category,
                    to_cents(opex_amount),
                    YearMonth.parse(opex_start),
                    None if opex_end == "recorrente" else YearMonth.parse(opex_end),
                )
            )
        assumptions = []
        if receipts_shock or receipts_delay:
            assumptions.append(
                ReceiptsAssumption(
                    Decimal(str(receipts_shock)) / 100,
                    int(receipts_delay),
                )
            )
        if apply_mrr:
            assumptions.append(MrrGrowthAssumption(Decimal(str(mrr_growth)) / 100))
        protected = {
            key: to_cents(value)
            for key, value in {
                "personnel": protected_personnel,
                "marketing": protected_marketing,
                "other_opex": protected_other,
            }.items()
            if value > 0
        }
        scenario = Scenario(
            company_id=company.id,
            name=name,
            baseline=baseline,
            horizon=horizon,
            constraints=DecisionConstraints(
                YearMonth.parse(milestone), to_cents(reserve), protected, tuple(allowed)
            ),
            actions=tuple(actions),
            assumptions=tuple(assumptions),
        )
        result = run_scenario(scenario)
        database.save_scenario(scenario)
        run_id = database.save_run(result)
        st.session_state["last_run_id"] = run_id
        st.success(f"Cenario congelado e execucao {run_id[:8]} registrada.")
        _metric_cards(result)
        if result.feasibility.operational_violations:
            st.warning("; ".join(result.feasibility.operational_violations))
    except (ValueError, KeyError) as exc:
        st.error(str(exc))


def _compare_page(database: Database, company: Company) -> None:
    st.title("Compare")
    items = database.list_scenarios(company.id)
    if len(items) < 2:
        st.info("Crie pelo menos dois cenarios.")
        return
    labels = {
        item["id"]: f"{item['name']} · base {item['baseline_version'][:8]} · H{item['horizon']}"
        for item in items
    }
    selected = st.multiselect(
        "Cenarios (2 ou 3)",
        list(labels),
        default=list(labels)[: min(3, len(labels))],
        max_selections=3,
        format_func=lambda scenario_id: labels[scenario_id],
    )
    allow_difference = st.checkbox("Confirmo comparacao entre baselines diferentes")
    if st.button("Comparar", type="primary"):
        try:
            comparison = compare_scenarios(
                tuple(database.get_scenario(item) for item in selected),
                allow_different_baseline=allow_difference,
            )
            for result in comparison.results:
                database.save_run(result)
            if comparison.baseline_difference_warning:
                st.warning(comparison.baseline_difference_warning)
            st.dataframe(
                pd.DataFrame([_comparison_row(result) for result in comparison.results]),
                use_container_width=True,
                hide_index=True,
            )
            st.line_chart(
                pd.DataFrame(
                    {
                        result.scenario.name: [_units(row.cash_end_cents) for row in result.projection.rows]
                        for result in comparison.results
                    },
                    index=[str(row.month) for row in comparison.results[0].projection.rows],
                )
            )
        except ValueError as exc:
            st.error(str(exc))


def _stress_page(database: Database, company: Company) -> None:
    st.title("Stress")
    items = database.list_scenarios(company.id)
    if not items:
        st.info("Crie um cenario primeiro.")
        return
    labels = {item["id"]: item["name"] for item in items}
    scenario_id = st.selectbox("Cenario", list(labels), format_func=lambda item: labels[item])
    scenario = database.get_scenario(scenario_id)
    factor = st.selectbox(
        "Limite a calcular",
        (
            "Queda maxima de recebimentos",
            "Atraso maximo de recebimentos",
            "Custo maximo da contratacao",
            "Primeiro mes viavel para contratar",
            "Aumento maximo de OPEX",
        ),
    )
    limit: StressLimit | None = None
    parameters: dict[str, object] = {"factor": factor}
    try:
        if factor == "Queda maxima de recebimentos":
            tolerance_pct = st.number_input("Tolerancia (p.p.)", 0.0001, 10.0, 0.01, format="%.4f")
            if st.button("Executar stress", type="primary"):
                tolerance = Decimal(str(tolerance_pct)) / 100
                limit = maximum_receipts_decline(scenario, tolerance=tolerance)
                parameters["tolerance"] = str(tolerance)
        elif factor == "Atraso maximo de recebimentos":
            maximum = st.number_input("Atraso maximo a testar", 0, scenario.horizon, scenario.horizon)
            if st.button("Executar stress", type="primary"):
                limit = maximum_receipts_delay(scenario, maximum_months=int(maximum))
                parameters["maximum_months"] = int(maximum)
        elif factor in {"Custo maximo da contratacao", "Primeiro mes viavel para contratar"}:
            hires = [action for action in scenario.actions if isinstance(action, HiringAction)]
            if not hires:
                st.info("O cenario selecionado nao possui contratacao.")
                return
            hire = st.selectbox("Contratacao", hires, format_func=lambda item: f"{item.quantity} pessoa(s) em {item.start_month}")
            if factor == "Custo maximo da contratacao":
                maximum = st.number_input("Custo maximo por pessoa/mes a testar", min_value=0.0, value=50_000.0)
                tolerance = st.number_input("Tolerancia monetaria", min_value=0.01, value=1.0)
                if st.button("Executar stress", type="primary"):
                    limit = maximum_hiring_cost(
                        scenario,
                        hire.id,
                        maximum_monthly_cost_per_person_cents=to_cents(maximum),
                        tolerance_cents=to_cents(tolerance),
                    )
                    parameters.update(maximum=maximum, tolerance=tolerance, hiring_action_id=hire.id)
            elif st.button("Executar stress", type="primary"):
                limit = earliest_feasible_hiring_month(scenario, hire.id)
                parameters["hiring_action_id"] = hire.id
        else:
            category = st.selectbox("Categoria", ("marketing", "other_opex"))
            start = st.selectbox("Inicio", [str(period.month) for period in scenario.baseline.periods[: scenario.horizon]])
            maximum = st.number_input("Aumento mensal maximo a testar", min_value=0.0, value=50_000.0)
            tolerance = st.number_input("Tolerancia monetaria", min_value=0.01, value=1.0)
            if st.button("Executar stress", type="primary"):
                limit = maximum_opex_increase(
                    scenario,
                    category=category,
                    start_month=YearMonth.parse(start),
                    maximum_monthly_cents=to_cents(maximum),
                    tolerance_cents=to_cents(tolerance),
                )
                parameters.update(category=category, start=start, maximum=maximum, tolerance=tolerance)
    except ValueError as exc:
        st.error(str(exc))
        return
    if limit is not None:
        run_id = database.save_stress_run(scenario, limit, parameters)
        st.session_state["last_stress"] = (scenario.id, limit)
        st.success(f"{_stress_value(limit, company.currency)}")
        st.caption(
            f"Metodo: {limit.method}; tolerancia: {limit.tolerance or 'discreta'}; "
            f"execucao {run_id[:8]}. Limite nao e probabilidade."
        )
        st.write(limit.failure_condition)


def _memo_page(database: Database, company: Company) -> None:
    st.title("Decision Memo")
    runs = [run for run in database.list_runs(company.id) if run["result_summary"].get("kind") == "scenario"]
    if not runs:
        st.info("Execute ao menos um cenario antes de gerar o memo.")
        return
    labels = {run["id"]: f"{run['scenario_name']} · {run['created_at'][:19]}" for run in runs}
    with st.form("memo"):
        selected = st.multiselect(
            "Execucoes comparadas (a primeira e o resultado central)",
            list(labels),
            default=[next(iter(labels))],
            max_selections=3,
            format_func=lambda run_id: labels[run_id],
        )
        objective = st.text_input("Objetivo", "Chegar ao marco preservando a reserva minima")
        chosen = st.text_input("Decisao escolhida")
        rationale = st.text_area("Racional")
        responsible = st.text_input("Responsavel", "Founder")
        review_date = st.date_input("Proxima revisao")
        submitted = st.form_submit_button("Registrar decisao e gerar memo", type="primary")
    if submitted:
        if not selected or not chosen.strip():
            st.error("Selecione uma execucao e registre a decisao escolhida.")
            return
        results = []
        for run_id in selected:
            snapshot = database.get_run(run_id)["input_snapshot"]
            results.append(run_scenario(Scenario.from_dict(snapshot)))
        central = results[0]
        decision_id = database.save_decision(
            company_id=company.id,
            run_id=selected[0],
            scenario_id=central.scenario.id,
            objective=objective,
            rationale=rationale,
            responsible=responsible,
            next_review_date=review_date.isoformat(),
        )
        last_stress = st.session_state.get("last_stress")
        stress_limits = (
            (last_stress[1],) if last_stress and last_stress[0] == central.scenario.id else ()
        )
        html = generate_decision_memo(
            DecisionMemoInput(
                company,
                objective,
                chosen,
                review_date.isoformat(),
                tuple(results),
                rationale,
                stress_limits,
            )
        )
        st.session_state["memo_html"] = html
        st.success(f"Decisao {decision_id[:8]} registrada.")
    html = st.session_state.get("memo_html")
    if html:
        components.html(html, height=900, scrolling=True)
        st.download_button("Baixar HTML", html, "decision_memo.html", "text/html")
        st.caption("Abra o HTML no navegador e use Imprimir → Salvar como PDF.")


def _history_page(database: Database, company: Company) -> None:
    st.title("History")
    decisions = database.list_decisions(company.id)
    scenarios = database.list_scenarios(company.id)
    st.subheader("Cenarios congelados")
    st.dataframe(pd.DataFrame(scenarios), use_container_width=True, hide_index=True)
    st.subheader("Decisoes")
    st.dataframe(pd.DataFrame(decisions), use_container_width=True, hide_index=True)
    if decisions:
        labels = {item["id"]: f"{item['scenario_name']} · {item['created_at'][:10]}" for item in decisions}
        event_tab, outcome_tab = st.tabs(("Registrar acao", "Registrar realizado"))
        with event_tab, st.form("event"):
            decision_id = st.selectbox("Decisao", list(labels), format_func=lambda item: labels[item])
            status = st.selectbox("Status", ("planned", "executed", "cancelled", "no_action"))
            effective = st.date_input("Data efetiva")
            dose = st.text_input("Dose / acao agregada")
            notes = st.text_area("Notas sem dados pessoais")
            if st.form_submit_button("Registrar evento"):
                database.record_action_event(decision_id, status, effective.isoformat(), dose, notes)
                st.success("Evento registrado separadamente da decisao.")
        with outcome_tab, st.form("outcome"):
            decision_id = st.selectbox("Decisao", list(labels), format_func=lambda item: labels[item], key="outcome_decision")
            month = st.text_input("Mes observado (YYYY-MM)")
            metric = st.selectbox("Metrica", ("cash", "mrr", "operating_receipts", "other"))
            value = st.text_input("Valor observado na moeda da empresa")
            source = st.selectbox("Origem", ("observed", "declared"))
            if st.form_submit_button("Registrar realizado"):
                try:
                    YearMonth.parse(month)
                    Decimal(value)
                    database.record_outcome(decision_id, month, metric, value, source)
                    st.success("Realizado registrado sem alterar o cenario historico.")
                except (ValueError, ArithmeticError) as exc:
                    st.error(str(exc))
    events = database.list_action_events(company.id)
    outcomes = database.list_outcomes(company.id)
    st.subheader("Acoes executadas / canceladas")
    st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)
    st.subheader("Realizado posterior")
    st.dataframe(pd.DataFrame(outcomes), use_container_width=True, hide_index=True)
    comparison = _actual_vs_projected(database, decisions, outcomes, company.currency)
    if comparison:
        st.subheader("Realizado versus cenario congelado")
        st.dataframe(pd.DataFrame(comparison), use_container_width=True, hide_index=True)


def _manual_frame(
    start: YearMonth,
    horizon: int,
    initial_cash: float,
    receipts: float,
    personnel: float,
    marketing: float,
    other_opex: float,
    capex: float,
    debt: float,
    financing: float,
    mrr: float,
    growth: float,
    origin: str,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "month": str(start.add(index)),
                "starting_cash": initial_cash if index == 0 else "",
                "operating_receipts": receipts,
                "personnel": personnel,
                "marketing": marketing,
                "other_opex": other_opex,
                "capex": capex,
                "debt_service": debt,
                "financing_inflows": financing if index == 0 else 0,
                "mrr": mrr if index == 0 else "",
                "net_mrr_growth": growth / 100,
                "origin": origin,
            }
            for index in range(horizon)
        ]
    )


def _metric_cards(result) -> None:
    metrics = result.metrics
    columns = st.columns(5)
    columns[0].metric("Caixa final", _money(metrics.ending_cash_cents, result.scenario.baseline.currency))
    columns[1].metric("Caixa minimo", _money(metrics.minimum_cash_cents, result.scenario.baseline.currency))
    columns[2].metric("Cash-out", metrics.projected_cash_out_month or "Nao ocorre em H")
    columns[3].metric("Reserva", "Viavel" if result.feasibility.feasible else "Violada")
    columns[4].metric("Capital adicional", _money(metrics.cash_required_to_sustain_plan_cents, result.scenario.baseline.currency))


def _comparison_row(result) -> dict[str, object]:
    metrics = result.metrics
    currency = result.scenario.baseline.currency
    return {
        "Cenario": result.scenario.name,
        "Caixa final": _money(metrics.ending_cash_cents, currency),
        "Caixa minimo": _money(metrics.minimum_cash_cents, currency),
        "Cash-out": metrics.projected_cash_out_month or "nao ocorre no horizonte",
        "Runway": metrics.projected_runway_complete_months,
        "Custo incremental": _money(metrics.total_incremental_cost_cents, currency),
        "Reserva": _money(result.scenario.constraints.minimum_cash_reserve_cents, currency),
        "Fragilidade (margem minima)": _money(result.feasibility.minimum_margin_cents, currency),
        "Resultado": "viavel" if result.feasibility.feasible else "inviavel",
    }


def _stress_value(limit: StressLimit, currency: str) -> str:
    if limit.value is None:
        return f"{limit.factor}: nenhuma alternativa viavel no intervalo."
    if limit.unit == "fracao":
        return f"{limit.factor}: aproximadamente {Decimal(limit.value) * 100:.2f}%."
    if "centavos" in limit.unit:
        return f"{limit.factor}: aproximadamente {_money(int(Decimal(limit.value)), currency)}."
    return f"{limit.factor}: {limit.value} {limit.unit}."


def _actual_vs_projected(database, decisions, outcomes, currency: str) -> list[dict[str, object]]:
    decisions_by_id = {item["id"]: item for item in decisions}
    rows = []
    for outcome in outcomes:
        if outcome["metric"] != "cash" or outcome["decision_id"] not in decisions_by_id:
            continue
        decision = decisions_by_id[outcome["decision_id"]]
        run = database.get_run(decision["simulation_run_id"])
        trajectory = run["result_summary"].get("trajectory", [])
        projected = next(
            (item.get("cash_end_cents") for item in trajectory if item.get("month") == outcome["observed_month"]),
            None,
        )
        if projected is not None:
            actual = to_cents(outcome["value"])
            rows.append(
                {
                    "Mes": outcome["observed_month"],
                    "Cenario": decision["scenario_name"],
                    "Projetado": _money(projected, currency),
                    "Realizado": _money(actual, currency),
                    "Delta": _money(actual - projected, currency),
                }
            )
    return rows


def _money(cents: int, currency: str) -> str:
    amount = Decimal(cents) / 100
    return f"{currency} {amount:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _units(cents: int) -> float:
    return float(Decimal(cents) / 100)


if __name__ == "__main__":
    main()
