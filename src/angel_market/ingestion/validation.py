from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    row: int | None
    field: str
    message: str

    def display(self) -> str:
        location = "cabecalho" if self.row is None else f"linha {self.row}"
        return f"{location}, {self.field}: {self.message}"

