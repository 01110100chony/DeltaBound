from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class Company:
    name: str
    currency: str = "BRL"
    sector: str = "SaaS B2B"
    stage: str = "early-stage"
    id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("nome da empresa e obrigatorio")
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise ValueError("currency deve usar um codigo ISO de 3 letras")
        object.__setattr__(self, "currency", self.currency.upper())

