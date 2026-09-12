from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from angel_market.domain.company import Company
from angel_market.domain.periods import YearMonth
from angel_market.domain.scenario import DecisionConstraints, HiringAction, Scenario
from angel_market.engine.reverse_stress import maximum_receipts_decline, maximum_receipts_delay
from angel_market.engine.scenarios import run_scenario
from angel_market.ingestion.csv_parser import parse_financial_csv
from angel_market.reports.memo import DecisionMemoInput, generate_decision_memo
from angel_market.storage.sqlite import Database


ROOT = Path(__file__).resolve().parents[1]


def run(db_path: Path, memo_path: Path) -> None:
    database = Database(db_path)
    company = database.create_company(Company("SaaS B2B Demo"))
    validation = parse_financial_csv((ROOT / "data/synthetic/saas_b2b_demo.csv").read_bytes())
    if not validation.valid:
        raise RuntimeError("dataset sintetico invalido")
    baseline = database.publish_import(company.id, validation.parsed).baseline
    constraints = DecisionConstraints(YearMonth.parse("2026-09"), 50_000_00)
    base = Scenario(company.id, "Baseline", baseline, 9, constraints)
    hire_now = HiringAction(1, YearMonth.parse("2026-01"), 12_000_00)
    alternative_a = replace(base, name="Alternative A — contratar M1", actions=(hire_now,))
    hire_later = HiringAction(1, YearMonth.parse("2026-08"), 12_000_00)
    alternative_b = replace(base, name="Alternative B — contratar M8", actions=(hire_later,))

    results = []
    run_ids = []
    for scenario in (base, alternative_a, alternative_b):
        scenario = replace(scenario, id=_new_id(), created_at=_now())
        database.save_scenario(scenario)
        result = run_scenario(scenario)
        results.append(result)
        run_ids.append(database.save_run(result))

    delay_limit = maximum_receipts_delay(results[0].scenario)
    decline_limit = maximum_receipts_decline(results[2].scenario)
    database.save_stress_run(results[0].scenario, delay_limit, {"maximum_months": 9})
    database.save_stress_run(results[2].scenario, decline_limit, {"maximum_fraction": "1"})
    decision_id = database.save_decision(
        company_id=company.id,
        run_id=run_ids[2],
        scenario_id=results[2].scenario.id,
        objective="Chegar ao mes 9 com reserva minima de BRL 50.000",
        rationale="Viavel no cenario central, mas com pequena margem para deterioracao.",
        responsible="Founder Demo",
        next_review_date="2026-02-01",
    )
    database.record_action_event(decision_id, "planned", "2026-08-01", "1 contratacao", "")
    database.record_outcome(decision_id, "2026-01", "cash", "275000", "observed")
    memo = generate_decision_memo(
        DecisionMemoInput(
            company=company,
            objective="Chegar ao mes 9 preservando BRL 50.000",
            chosen_decision="Revisar a contratacao de M8 apos confirmar recebimentos.",
            next_review_date="2026-02-01",
            results=(results[2], results[0], results[1]),
            rationale="A alternativa M8 cabe por BRL 1.000 no caso central.",
            stress_limits=(decline_limit, delay_limit),
        )
    )
    memo_path.parent.mkdir(parents=True, exist_ok=True)
    memo_path.write_text(memo, encoding="utf-8")
    database.close()
    print(f"walkthrough_ok db={db_path} memo={memo_path}")


def _new_id() -> str:
    from uuid import uuid4

    return str(uuid4())


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=ROOT / "data/private/walkthrough.db")
    parser.add_argument("--memo", type=Path, default=ROOT / "data/private/decision_memo_demo.html")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    if args.db.exists():
        if not args.replace:
            raise SystemExit("o banco ja existe; use --replace para recriar somente este arquivo")
        args.db.unlink()
    run(args.db, args.memo)


if __name__ == "__main__":
    main()

