from dataclasses import replace

from angel_market.domain.company import Company
from angel_market.reports.memo import DecisionMemoInput, generate_decision_memo
from angel_market.engine.scenarios import run_scenario


def test_memo_is_deterministic_html_with_required_sections(baseline_factory, scenario_factory):
    result = run_scenario(scenario_factory(baseline_factory(months=2), reserve=50_000_00))
    data = DecisionMemoInput(
        company=Company("Demo <script>"),
        objective="Preservar caixa",
        chosen_decision="Manter plano",
        next_review_date="2026-03-01",
        results=(result,),
    )
    first = generate_decision_memo(data)
    second = generate_decision_memo(data)

    assert first == second
    assert "Demo &lt;script&gt;" in first
    for section in (
        "Estado atual",
        "Decisao avaliada",
        "Cenarios",
        "Resultado central",
        "Limites / stress",
        "Principais premissas",
        "Condicao que invalida o plano",
        "Decisao escolhida",
        "Limitacoes",
    ):
        assert section in first

