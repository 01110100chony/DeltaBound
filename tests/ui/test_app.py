from pathlib import Path

from streamlit.testing.v1 import AppTest

from angel_market.domain.company import Company
from angel_market.ingestion.csv_parser import parse_financial_csv
from angel_market.storage.sqlite import Database


ROOT = Path(__file__).resolve().parents[2]


def test_all_pages_render_with_a_baseline(tmp_path, monkeypatch):
    db_path = tmp_path / "ui.db"
    database = Database(db_path)
    company = database.create_company(Company("UI Demo"))
    parsed = parse_financial_csv((ROOT / "data/synthetic/saas_b2b_demo.csv").read_bytes()).parsed
    database.publish_import(company.id, parsed)
    database.close()
    monkeypatch.setenv("ANGEL_MARKET_DB", str(db_path))

    app = AppTest.from_file(str(ROOT / "src/angel_market/ui/app.py"))
    app.run(timeout=20)
    assert not app.exception
    for page in ("Import", "Scenario Builder", "Compare", "Stress", "Decision Memo", "History"):
        app.sidebar.radio[0].set_value(page).run(timeout=20)
        assert not app.exception, page

