from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from angel_market.domain.company import Company
from angel_market.domain.scenario import (
    BaselineSnapshot,
    DecisionConstraints,
    FinancialPeriod,
    Scenario,
)
from angel_market.engine.scenarios import ScenarioResult
from angel_market.engine.reverse_stress import StressLimit
from angel_market.ingestion.csv_parser import ParsedCsvImport

from .snapshots import canonical_json, snapshot_hash


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    currency TEXT NOT NULL,
    sector TEXT NOT NULL,
    stage TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS import_batches (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id),
    content_hash TEXT NOT NULL,
    baseline_version TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    UNIQUE(company_id, content_hash)
);

CREATE TABLE IF NOT EXISTS financial_periods (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id),
    month TEXT NOT NULL,
    revision INTEGER NOT NULL,
    baseline_version TEXT NOT NULL REFERENCES import_batches(baseline_version),
    origin TEXT NOT NULL,
    data_json TEXT NOT NULL,
    is_current INTEGER NOT NULL,
    available_at TEXT NOT NULL,
    previous_revision_id TEXT REFERENCES financial_periods(id),
    created_at TEXT NOT NULL,
    UNIQUE(company_id, month, revision)
);
CREATE INDEX IF NOT EXISTS idx_financial_current ON financial_periods(company_id, is_current);

CREATE TABLE IF NOT EXISTS scenarios (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id),
    baseline_version TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    horizon INTEGER NOT NULL,
    engine_version TEXT NOT NULL,
    input_snapshot TEXT NOT NULL,
    input_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scenario_actions (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    kind TEXT NOT NULL,
    params_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scenario_assumptions (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    kind TEXT NOT NULL,
    params_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS simulation_runs (
    id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    input_snapshot TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    engine_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    result_summary TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_records (
    id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL REFERENCES companies(id),
    simulation_run_id TEXT NOT NULL REFERENCES simulation_runs(id),
    chosen_scenario_id TEXT NOT NULL REFERENCES scenarios(id),
    objective TEXT NOT NULL,
    rationale TEXT NOT NULL,
    responsible TEXT NOT NULL,
    next_review_date TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS action_events (
    id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL REFERENCES decision_records(id),
    status TEXT NOT NULL,
    effective_date TEXT,
    dose TEXT NOT NULL,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outcome_observations (
    id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL REFERENCES decision_records(id),
    observed_month TEXT NOT NULL,
    metric TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


@dataclass(frozen=True, slots=True)
class ImportPublication:
    baseline: BaselineSnapshot
    created: bool


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def backup(self, destination: str | Path) -> Path:
        target = Path(destination)
        if target.exists():
            raise FileExistsError("o destino do backup ja existe")
        target.parent.mkdir(parents=True, exist_ok=True)
        backup_connection = sqlite3.connect(target)
        try:
            self.connection.backup(backup_connection)
        finally:
            backup_connection.close()
        return target

    def create_company(self, company: Company) -> Company:
        self.connection.execute(
            "INSERT INTO companies VALUES (?, ?, ?, ?, ?, ?)",
            (
                company.id,
                company.name.strip(),
                company.currency,
                company.sector,
                company.stage,
                _now(),
            ),
        )
        self.connection.commit()
        return company

    def list_companies(self) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM companies ORDER BY name").fetchall()
        return [dict(row) for row in rows]

    def get_company(self, company_id: str) -> Company:
        row = self.connection.execute(
            "SELECT * FROM companies WHERE id = ?", (company_id,)
        ).fetchone()
        if row is None:
            raise KeyError("empresa nao encontrada")
        return Company(
            id=row["id"],
            name=row["name"],
            currency=row["currency"],
            sector=row["sector"],
            stage=row["stage"],
        )

    def publish_import(self, company_id: str, parsed: ParsedCsvImport) -> ImportPublication:
        company = self.get_company(company_id)
        existing = self.connection.execute(
            "SELECT baseline_version FROM import_batches WHERE company_id = ? AND content_hash = ?",
            (company_id, parsed.content_hash),
        ).fetchone()
        if existing is not None:
            return ImportPublication(self.get_baseline(existing["baseline_version"]), False)

        baseline_version = str(uuid4())
        batch_id = str(uuid4())
        created_at = _now()
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            self.connection.execute(
                "INSERT INTO import_batches VALUES (?, ?, ?, ?, ?)",
                (batch_id, company_id, parsed.content_hash, baseline_version, created_at),
            )
            for period in parsed.periods:
                previous = self.connection.execute(
                    """
                    SELECT id, revision FROM financial_periods
                    WHERE company_id = ? AND month = ? AND is_current = 1
                    """,
                    (company_id, str(period.month)),
                ).fetchone()
                revision = 1 if previous is None else int(previous["revision"]) + 1
                if previous is not None:
                    self.connection.execute(
                        "UPDATE financial_periods SET is_current = 0 WHERE id = ?",
                        (previous["id"],),
                    )
                self.connection.execute(
                    """
                    INSERT INTO financial_periods
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        company_id,
                        str(period.month),
                        revision,
                        baseline_version,
                        period.origin,
                        canonical_json(period.to_dict()),
                        created_at,
                        None if previous is None else previous["id"],
                        created_at,
                    ),
                )
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            raise
        baseline = BaselineSnapshot(
            company_id=company_id,
            currency=company.currency,
            version=baseline_version,
            periods=parsed.periods,
            initial_cash_cents=parsed.initial_cash_cents,
            initial_mrr_cents=parsed.initial_mrr_cents,
            base_month=parsed.periods[0].month,
            created_at=created_at,
        )
        self.ensure_default_scenarios(baseline)
        return ImportPublication(baseline, True)

    def get_baseline(self, baseline_version: str) -> BaselineSnapshot:
        batch = self.connection.execute(
            """
            SELECT b.*, c.currency FROM import_batches b
            JOIN companies c ON c.id = b.company_id
            WHERE b.baseline_version = ?
            """,
            (baseline_version,),
        ).fetchone()
        if batch is None:
            raise KeyError("baseline nao encontrado")
        rows = self.connection.execute(
            "SELECT data_json FROM financial_periods WHERE baseline_version = ? ORDER BY month",
            (baseline_version,),
        ).fetchall()
        periods = tuple(FinancialPeriod.from_dict(json.loads(row["data_json"])) for row in rows)
        return BaselineSnapshot(
            company_id=batch["company_id"],
            currency=batch["currency"],
            version=baseline_version,
            periods=periods,
            initial_cash_cents=periods[0].starting_cash_cents or 0,
            initial_mrr_cents=periods[0].mrr_cents,
            base_month=periods[0].month,
            created_at=batch["created_at"],
        )

    def get_current_baseline(self, company_id: str) -> BaselineSnapshot:
        row = self.connection.execute(
            """
            SELECT baseline_version FROM import_batches
            WHERE company_id = ? ORDER BY created_at DESC, rowid DESC LIMIT 1
            """,
            (company_id,),
        ).fetchone()
        if row is None:
            raise KeyError("empresa ainda nao possui baseline")
        return self.get_baseline(row["baseline_version"])

    def list_baselines(self, company_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT baseline_version, created_at, content_hash FROM import_batches
            WHERE company_id = ? ORDER BY created_at DESC, rowid DESC
            """,
            (company_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def ensure_default_scenarios(self, baseline: BaselineSnapshot) -> None:
        existing = self.connection.execute(
            "SELECT COUNT(*) AS count FROM scenarios WHERE baseline_version = ?",
            (baseline.version,),
        ).fetchone()["count"]
        if existing:
            return
        constraints = DecisionConstraints(
            milestone_month=baseline.periods[-1].month,
            minimum_cash_reserve_cents=0,
        )
        for name in ("Baseline", "Alternative A", "Alternative B"):
            self.save_scenario(
                Scenario(
                    company_id=baseline.company_id,
                    name=name,
                    baseline=baseline,
                    horizon=len(baseline.periods),
                    constraints=constraints,
                )
            )

    def save_scenario(self, scenario: Scenario) -> Scenario:
        snapshot = scenario.to_dict()
        with self.connection:
            self.connection.execute(
                "INSERT INTO scenarios VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    scenario.id,
                    scenario.company_id,
                    scenario.baseline_version,
                    scenario.name,
                    scenario.created_at,
                    scenario.horizon,
                    scenario.engine_version,
                    canonical_json(snapshot),
                    snapshot_hash(snapshot),
                ),
            )
            for action in snapshot["actions"]:
                self.connection.execute(
                    "INSERT INTO scenario_actions VALUES (?, ?, ?, ?)",
                    (action["id"], scenario.id, action["kind"], canonical_json(action)),
                )
            for assumption in snapshot["assumptions"]:
                self.connection.execute(
                    "INSERT INTO scenario_assumptions VALUES (?, ?, ?, ?)",
                    (assumption["id"], scenario.id, assumption["kind"], canonical_json(assumption)),
                )
        return scenario

    def get_scenario(self, scenario_id: str) -> Scenario:
        row = self.connection.execute(
            "SELECT input_snapshot FROM scenarios WHERE id = ?", (scenario_id,)
        ).fetchone()
        if row is None:
            raise KeyError("cenario nao encontrado")
        return Scenario.from_dict(json.loads(row["input_snapshot"]))

    def list_scenarios(self, company_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT id, name, baseline_version, horizon, engine_version, created_at
            FROM scenarios WHERE company_id = ? ORDER BY created_at DESC, rowid DESC
            """,
            (company_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def save_run(self, result: ScenarioResult) -> str:
        run_id = str(uuid4())
        snapshot = result.scenario.to_dict()
        summary = _result_summary(result)
        self.connection.execute(
            "INSERT INTO simulation_runs VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                result.scenario.id,
                canonical_json(snapshot),
                snapshot_hash(snapshot),
                result.scenario.engine_version,
                _now(),
                canonical_json(summary),
            ),
        )
        self.connection.commit()
        return run_id

    def save_stress_run(
        self, scenario: Scenario, limit: StressLimit, parameters: dict[str, Any]
    ) -> str:
        run_id = str(uuid4())
        input_snapshot = {"scenario": scenario.to_dict(), "stress_parameters": parameters}
        value = limit.value
        if not isinstance(value, (str, int, type(None))):
            value = str(value)
        summary = {
            "kind": "reverse_stress",
            "scenario_name": scenario.name,
            "baseline_version": scenario.baseline_version,
            "factor": limit.factor,
            "value": value,
            "unit": limit.unit,
            "method": limit.method,
            "tolerance": None if limit.tolerance is None else str(limit.tolerance),
            "bounded": limit.bounded,
            "base_feasible": limit.base_feasible,
            "failure_condition": limit.failure_condition,
        }
        self.connection.execute(
            "INSERT INTO simulation_runs VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                scenario.id,
                canonical_json(input_snapshot),
                snapshot_hash(input_snapshot),
                scenario.engine_version,
                _now(),
                canonical_json(summary),
            ),
        )
        self.connection.commit()
        return run_id

    def get_run(self, run_id: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM simulation_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if row is None:
            raise KeyError("execucao nao encontrada")
        result = dict(row)
        result["input_snapshot"] = json.loads(result["input_snapshot"])
        result["result_summary"] = json.loads(result["result_summary"])
        return result

    def list_runs(self, company_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT r.id, r.scenario_id, s.name AS scenario_name, r.engine_version, r.created_at,
                   r.result_summary
            FROM simulation_runs r JOIN scenarios s ON s.id = r.scenario_id
            WHERE s.company_id = ? ORDER BY r.created_at DESC, r.rowid DESC
            """,
            (company_id,),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["result_summary"] = json.loads(item["result_summary"])
            result.append(item)
        return result

    def save_decision(
        self,
        *,
        company_id: str,
        run_id: str,
        scenario_id: str,
        objective: str,
        rationale: str,
        responsible: str,
        next_review_date: str,
    ) -> str:
        decision_id = str(uuid4())
        self.connection.execute(
            "INSERT INTO decision_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                decision_id,
                company_id,
                run_id,
                scenario_id,
                objective.strip(),
                rationale.strip(),
                responsible.strip(),
                next_review_date,
                _now(),
            ),
        )
        self.connection.commit()
        return decision_id

    def record_action_event(
        self, decision_id: str, status: str, effective_date: str | None, dose: str, notes: str
    ) -> str:
        if status not in {"planned", "executed", "cancelled", "no_action"}:
            raise ValueError("status de acao invalido")
        event_id = str(uuid4())
        self.connection.execute(
            "INSERT INTO action_events VALUES (?, ?, ?, ?, ?, ?, ?)",
            (event_id, decision_id, status, effective_date, dose.strip(), notes.strip(), _now()),
        )
        self.connection.commit()
        return event_id

    def record_outcome(
        self, decision_id: str, observed_month: str, metric: str, value: str, source: str
    ) -> str:
        outcome_id = str(uuid4())
        self.connection.execute(
            "INSERT INTO outcome_observations VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                outcome_id,
                decision_id,
                observed_month,
                metric.strip(),
                value.strip(),
                source.strip(),
                _now(),
            ),
        )
        self.connection.commit()
        return outcome_id

    def list_decisions(self, company_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT d.*, s.name AS scenario_name FROM decision_records d
            JOIN scenarios s ON s.id = d.chosen_scenario_id
            WHERE d.company_id = ? ORDER BY d.created_at DESC, d.rowid DESC
            """,
            (company_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_action_events(self, company_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT e.* FROM action_events e JOIN decision_records d ON d.id = e.decision_id
            WHERE d.company_id = ? ORDER BY e.created_at DESC, e.rowid DESC
            """,
            (company_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def list_outcomes(self, company_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT o.* FROM outcome_observations o JOIN decision_records d ON d.id = o.decision_id
            WHERE d.company_id = ? ORDER BY o.created_at DESC, o.rowid DESC
            """,
            (company_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def _result_summary(result: ScenarioResult) -> dict[str, Any]:
    metrics = asdict(result.metrics)
    if metrics["static_runway_months"] is not None:
        metrics["static_runway_months"] = str(metrics["static_runway_months"])
    return {
        "kind": "scenario",
        "scenario_name": result.scenario.name,
        "baseline_version": result.scenario.baseline_version,
        "base_month": str(result.scenario.baseline.base_month),
        "horizon": result.scenario.horizon,
        "constraints": result.scenario.to_dict()["constraints"],
        "metrics": metrics,
        "feasibility": asdict(result.feasibility),
        "trajectory": [
            {
                "month": str(row.month),
                "cash_end_cents": row.cash_end_cents,
                "operating_receipts_cents": row.operating_receipts_cents,
                "operating_payments_cents": row.operating_payments_cents,
                "net_operating_burn_cents": row.net_operating_burn_cents,
                "mrr_cents": row.mrr_cents,
                "arr_run_rate_cents": row.arr_run_rate_cents,
            }
            for row in result.projection.rows
        ],
        "limitations": list(result.limitations),
    }


def _now() -> str:
    return datetime.now(UTC).isoformat()
