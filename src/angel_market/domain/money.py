from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


def to_cents(value: Decimal | str | int | float) -> int:
    amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(amount * 100)


@dataclass(frozen=True, slots=True)
class Money:
    cents: int
    currency: str

    def __post_init__(self) -> None:
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise ValueError("currency deve usar um codigo ISO de 3 letras")
        object.__setattr__(self, "currency", self.currency.upper())

    @classmethod
    def from_value(cls, value: Decimal | str | int | float, currency: str) -> "Money":
        return cls(to_cents(value), currency)

    @property
    def decimal(self) -> Decimal:
        return Decimal(self.cents) / 100

    def _same_currency(self, other: "Money") -> None:
        if self.currency != other.currency:
            raise ValueError("nao e permitido combinar moedas diferentes")

    def __add__(self, other: "Money") -> "Money":
        self._same_currency(other)
        return Money(self.cents + other.cents, self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._same_currency(other)
        return Money(self.cents - other.cents, self.currency)

