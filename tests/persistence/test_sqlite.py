from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from angel_market.domain.company import Company
from angel_market.domain.periods import YearMonth
from angel_market.domain.scenario import HiringAction
from angel_market.engine.scenarios import run_scenario
from angel_market.ingestion.csv_parser import parse_financial_csv
from angel_market.storage.sqlite import Database


HEADER = (
    "month,starting_cash,operating_receipts,personnel,marketing,other_opex,"
    "capex,debt_service,financing_inflows,mrr\n"
)


def csv_with_receipts(value: int) -> bytes:
    return (
        HEADER
        + f"2026-01,100000,{value},25000,5000,0,0,0,0,20000\n"
        + f"2026-02,,{value},25000,5000,0,0,0,0,\n"
    ).encode()


def test_repeated_import_is_idempotent_and_correction_creates_revision(tmp_path):
    database = Database(tmp_path / "angel.db")
    company = database.create_company(Company("Synthetic Co"))
    first_parsed = parse_financial_csv(csv_with_receipts(20_000)).parsed
    first = database.publish_import(company.id, first_parsed)
    duplicate = database.publish_import(company.id, first_parsed)
    correction = database.publish_import(
        company.id, parse_financial_csv(csv_with_receipts(25_000)).parsed
    )

    assert first.created
    assert not duplicate.created
    assert duplicate.baseline.version == first.baseline.version
    assert correction.baseline.version != first.baseline.version
    revisions = database.connection.execute(
        "SELECT month, MAX(revision) AS revision FROM financial_periods GROUP BY month ORDER BY month"
    ).fetchall()
    assert [row["revision"] for row in revisions] == [2, 2]
    assert len(database.list_scenarios(company.id)) == 6
    database.close()


def test_old_scenario_remains_reproducible_after_new_import(tmp_path):
    database = Database(tmp_path / "angel.db")
    company = database.create_company(Company("Synthetic Co"))
    first = database.publish_import(
        company.id, parse_financial_csv(csv_with_receipts(20_000)).parsed
    ).baseline
    hire = HiringAction(1, YearMonth.parse("2026-01"), 5_000_00)
    default = database.get_scenario(database.list_scenarios(company.id)[0]["id"])
    old_scenario = replace(
        default,
        id=str(uuid4()),
        created_at=datetime.now(UTC).isoformat(),
        name="Hiring",
        actions=(hire,),
    )
    database.save_scenario(old_scenario)
    old_result = run_scenario(old_scenario)
    run_id = database.save_run(old_result)

    database.publish_import(company.id, parse_financial_csv(csv_with_receipts(30_000)).parsed)
    restored = database.get_scenario(old_scenario.id)
    restored_result = run_scenario(restored)

    assert restored.baseline.version == first.version
    assert restored_result.projection.rows == old_result.projection.rows
    assert database.get_run(run_id)["input_hash"]
    database.close()


def test_decision_action_and_outcome_are_separate_records(tmp_path):
    database = Database(tmp_path / "angel.db")
    company = database.create_company(Company("Synthetic Co"))
    database.publish_import(company.id, parse_financial_csv(csv_with_receipts(20_000)).parsed)
    scenario = database.get_scenario(database.list_scenarios(company.id)[0]["id"])
    run_id = database.save_run(run_scenario(scenario))
    decision_id = database.save_decision(
        company_id=company.id,
        run_id=run_id,
        scenario_id=scenario.id,
        objective="Chegar ao marco",
        rationale="Preserva a reserva",
        responsible="Founder",
        next_review_date="2026-03-01",
    )
    database.record_action_event(decision_id, "executed", "2026-02-01", "1 hire", "")
    database.record_outcome(decision_id, "2026-03", "cash", "85000", "observed")

    assert len(database.list_decisions(company.id)) == 1
    assert len(database.list_action_events(company.id)) == 1
    assert len(database.list_outcomes(company.id)) == 1
    database.close()


def test_backup_is_consistent_and_refuses_overwrite(tmp_path):
    database = Database(tmp_path / "source.db")
    database.create_company(Company("Backup Co"))
    destination = database.backup(tmp_path / "backup.db")
    restored = Database(destination)
    assert restored.list_companies()[0]["name"] == "Backup Co"
    restored.close()
    try:
        database.backup(destination)
    except FileExistsError:
        pass
    else:
        raise AssertionError("backup nao deve sobrescrever arquivo existente")
    database.close()
