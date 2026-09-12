from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, order=True, slots=True)
class YearMonth:
    year: int
    month: int

    def __post_init__(self) -> None:
        if self.year < 1900 or not 1 <= self.month <= 12:
            raise ValueError("mes deve estar no formato YYYY-MM")

    @classmethod
    def parse(cls, value: str) -> "YearMonth":
        try:
            parsed = date.fromisoformat(f"{value}-01")
        except (TypeError, ValueError) as exc:
            raise ValueError("mes deve estar no formato YYYY-MM") from exc
        if value != parsed.strftime("%Y-%m"):
            raise ValueError("mes deve estar no formato YYYY-MM")
        return cls(parsed.year, parsed.month)

    def add(self, months: int) -> "YearMonth":
        position = self.year * 12 + self.month - 1 + months
        year, zero_based_month = divmod(position, 12)
        return YearMonth(year, zero_based_month + 1)

    def months_until(self, other: "YearMonth") -> int:
        return (other.year - self.year) * 12 + other.month - self.month

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

