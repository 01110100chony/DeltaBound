from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable


def next_mrr_cents(current_mrr_cents: int, net_growth: Decimal) -> int:
    if net_growth < Decimal("-1"):
        raise ValueError("crescimento liquido nao pode produzir MRR negativo")
    return int(
        (Decimal(current_mrr_cents) * (Decimal("1") + net_growth)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


def project_mrr(initial_mrr_cents: int, net_growth_rates: Iterable[Decimal]) -> tuple[int, ...]:
    values: list[int] = []
    current = initial_mrr_cents
    for rate in net_growth_rates:
        current = next_mrr_cents(current, rate)
        values.append(current)
    return tuple(values)

