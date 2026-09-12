from decimal import Decimal

from angel_market.engine.revenue import project_mrr


def test_net_growth_already_includes_churn_once():
    assert project_mrr(100_000_00, [Decimal("-0.10"), Decimal("0")]) == (90_000_00, 90_000_00)

