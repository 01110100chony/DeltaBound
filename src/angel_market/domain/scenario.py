from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, TypeAlias
from uuid import uuid4

from .periods import YearMonth


DataOrigin = Literal["observed", "declared", "assumed", "simulated"]


@dataclass(frozen=True, slots=True)
class FinancialPeriod:
    month: YearMonth
    operating_receipts_cents: int
    personnel_cents: int
    marketing_cents: int
    other_opex_cents: int
    capex_cents: int
    debt_service_cents: int
    financing_inflows_cents: int
    other_net_cash_movements_cents: int = 0
    cash_cogs_cents: int = 0
    operating_taxes_cents: int = 0
    starting_cash_cents: int | None = None
    revenue_recognized_cents: int | None = None
    mrr_cents: int | None = None
    net_mrr_growth: Decimal = Decimal("0")
    origin: DataOrigin = "declared"

    @property
    def operating_payments_cents(self) -> int:
        return (
            self.personnel_cents
            + self.marketing_cents
            + self.other_opex_cents
            + self.cash_cogs_cents
            + self.operating_taxes_cents
        )

    def to_dict(self) -> dict[str, Any]:
        result = {name: getattr(self, name) for name in self.__dataclass_fields__}
        result["month"] = str(self.month)
        result["net_mrr_growth"] = str(self.net_mrr_growth)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FinancialPeriod":
        values = dict(data)
        values["month"] = YearMonth.parse(values["month"])
        values["net_mrr_growth"] = Decimal(str(values.get("net_mrr_growth", "0")))
        return cls(**values)


@dataclass(frozen=True, slots=True)
class BaselineSnapshot:
    company_id: str
    currency: str
    version: str
    periods: tuple[FinancialPeriod, ...]
    initial_cash_cents: int
    initial_mrr_cents: int | None
    base_month: YearMonth
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        if not self.periods:
            raise ValueError("baseline precisa de pelo menos um periodo")
        months = [period.month for period in self.periods]
        if months != sorted(months) or len(set(months)) != len(months):
            raise ValueError("periodos do baseline devem ser unicos e ordenados")
        if any(months[index].add(1) != months[index + 1] for index in range(len(months) - 1)):
            raise ValueError("periodos do baseline devem ser mensais e contiguos")

    def to_dict(self) -> dict[str, Any]:
        return {
            "company_id": self.company_id,
            "currency": self.currency,
            "version": self.version,
            "periods": [period.to_dict() for period in self.periods],
            "initial_cash_cents": self.initial_cash_cents,
            "initial_mrr_cents": self.initial_mrr_cents,
            "base_month": str(self.base_month),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BaselineSnapshot":
        return cls(
            company_id=data["company_id"],
            currency=data["currency"],
            version=data["version"],
            periods=tuple(FinancialPeriod.from_dict(item) for item in data["periods"]),
            initial_cash_cents=int(data["initial_cash_cents"]),
            initial_mrr_cents=data.get("initial_mrr_cents"),
            base_month=YearMonth.parse(data["base_month"]),
            created_at=data["created_at"],
        )


@dataclass(frozen=True, slots=True)
class HiringAction:
    quantity: int
    start_month: YearMonth
    monthly_cost_per_person_cents: int
    initial_cost_total_cents: int = 0
    id: str = field(default_factory=lambda: str(uuid4()))
    kind: Literal["hiring"] = "hiring"
    origin: DataOrigin = "declared"

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError("quantidade da contratacao deve ser positiva")
        if self.monthly_cost_per_person_cents < 0 or self.initial_cost_total_cents < 0:
            raise ValueError("custos de contratacao nao podem ser negativos")

    @property
    def monthly_cost_total_cents(self) -> int:
        return self.quantity * self.monthly_cost_per_person_cents


@dataclass(frozen=True, slots=True)
class DelayHiringAction:
    hiring_action_id: str
    new_start_month: YearMonth
    id: str = field(default_factory=lambda: str(uuid4()))
    kind: Literal["delay_hiring"] = "delay_hiring"
    origin: DataOrigin = "declared"


@dataclass(frozen=True, slots=True)
class OpexAdjustment:
    category: Literal["marketing", "other_opex"]
    amount_cents: int
    start_month: YearMonth
    end_month: YearMonth | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    kind: Literal["opex_adjustment"] = "opex_adjustment"
    origin: DataOrigin = "declared"

    def __post_init__(self) -> None:
        if self.end_month is not None and self.end_month < self.start_month:
            raise ValueError("fim do ajuste nao pode ser anterior ao inicio")


@dataclass(frozen=True, slots=True)
class ReceiptsAssumption:
    shock_fraction: Decimal = Decimal("0")
    delay_months: int = 0
    start_month: YearMonth | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    kind: Literal["receipts"] = "receipts"
    origin: DataOrigin = "assumed"

    def __post_init__(self) -> None:
        if self.shock_fraction < Decimal("-1"):
            raise ValueError("choque nao pode reduzir recebimentos abaixo de zero")
        if self.delay_months < 0:
            raise ValueError("atraso nao pode ser negativo")


@dataclass(frozen=True, slots=True)
class MrrGrowthAssumption:
    monthly_growth: Decimal
    start_month: YearMonth | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    kind: Literal["mrr_growth"] = "mrr_growth"
    origin: DataOrigin = "assumed"

    def __post_init__(self) -> None:
        if self.monthly_growth < Decimal("-1"):
            raise ValueError("crescimento de MRR nao pode levar MRR abaixo de zero")


ScenarioAction: TypeAlias = HiringAction | DelayHiringAction | OpexAdjustment
ScenarioAssumption: TypeAlias = ReceiptsAssumption | MrrGrowthAssumption


@dataclass(frozen=True, slots=True)
class DecisionConstraints:
    milestone_month: YearMonth
    minimum_cash_reserve_cents: int
    protected_costs_cents: dict[str, int] = field(default_factory=dict)
    allowed_actions: tuple[str, ...] = ("hiring", "delay_hiring", "opex_adjustment")

    def __post_init__(self) -> None:
        if self.minimum_cash_reserve_cents < 0:
            raise ValueError("reserva minima nao pode ser negativa")
        if any(value < 0 for value in self.protected_costs_cents.values()):
            raise ValueError("custos protegidos nao podem ser negativos")


@dataclass(frozen=True, slots=True)
class Scenario:
    company_id: str
    name: str
    baseline: BaselineSnapshot
    horizon: int
    constraints: DecisionConstraints
    actions: tuple[ScenarioAction, ...] = ()
    assumptions: tuple[ScenarioAssumption, ...] = ()
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    engine_version: str = "0.1.0"

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("nome do cenario e obrigatorio")
        if self.company_id != self.baseline.company_id:
            raise ValueError("cenario e baseline pertencem a empresas diferentes")
        if not 1 <= self.horizon <= len(self.baseline.periods):
            raise ValueError("horizonte fora dos periodos disponiveis no baseline")
        last_month = self.baseline.periods[self.horizon - 1].month
        if not self.baseline.base_month <= self.constraints.milestone_month <= last_month:
            raise ValueError("marco deve estar dentro do horizonte")
        hires = {action.id: action for action in self.actions if isinstance(action, HiringAction)}
        for action in self.actions:
            if isinstance(action, DelayHiringAction):
                hiring = hires.get(action.hiring_action_id)
                if hiring is None:
                    raise ValueError("adiamento referencia uma contratacao inexistente")
                if action.new_start_month < hiring.start_month:
                    raise ValueError("nova data deve efetivamente adiar a contratacao")

    @property
    def baseline_version(self) -> str:
        return self.baseline.version

    def to_dict(self) -> dict[str, Any]:
        return {
            "company_id": self.company_id,
            "name": self.name,
            "baseline": self.baseline.to_dict(),
            "horizon": self.horizon,
            "constraints": {
                "milestone_month": str(self.constraints.milestone_month),
                "minimum_cash_reserve_cents": self.constraints.minimum_cash_reserve_cents,
                "protected_costs_cents": self.constraints.protected_costs_cents,
                "allowed_actions": list(self.constraints.allowed_actions),
            },
            "actions": [_action_to_dict(action) for action in self.actions],
            "assumptions": [_assumption_to_dict(item) for item in self.assumptions],
            "id": self.id,
            "created_at": self.created_at,
            "engine_version": self.engine_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Scenario":
        constraints = data["constraints"]
        return cls(
            company_id=data["company_id"],
            name=data["name"],
            baseline=BaselineSnapshot.from_dict(data["baseline"]),
            horizon=int(data["horizon"]),
            constraints=DecisionConstraints(
                milestone_month=YearMonth.parse(constraints["milestone_month"]),
                minimum_cash_reserve_cents=int(constraints["minimum_cash_reserve_cents"]),
                protected_costs_cents={
                    key: int(value) for key, value in constraints.get("protected_costs_cents", {}).items()
                },
                allowed_actions=tuple(constraints.get("allowed_actions", ())),
            ),
            actions=tuple(_action_from_dict(item) for item in data.get("actions", [])),
            assumptions=tuple(_assumption_from_dict(item) for item in data.get("assumptions", [])),
            id=data["id"],
            created_at=data["created_at"],
            engine_version=data.get("engine_version", "0.1.0"),
        )


def _action_to_dict(action: ScenarioAction) -> dict[str, Any]:
    data = {name: getattr(action, name) for name in action.__dataclass_fields__}
    for field_name in ("start_month", "end_month", "new_start_month"):
        if field_name in data and data[field_name] is not None:
            data[field_name] = str(data[field_name])
    return data


def _action_from_dict(data: dict[str, Any]) -> ScenarioAction:
    values = dict(data)
    kind = values.pop("kind")
    if kind == "hiring":
        values["start_month"] = YearMonth.parse(values["start_month"])
        return HiringAction(**values)
    if kind == "delay_hiring":
        values["new_start_month"] = YearMonth.parse(values["new_start_month"])
        return DelayHiringAction(**values)
    if kind == "opex_adjustment":
        values["start_month"] = YearMonth.parse(values["start_month"])
        if values.get("end_month") is not None:
            values["end_month"] = YearMonth.parse(values["end_month"])
        return OpexAdjustment(**values)
    raise ValueError(f"tipo de acao desconhecido: {kind}")


def _assumption_to_dict(assumption: ScenarioAssumption) -> dict[str, Any]:
    data = {name: getattr(assumption, name) for name in assumption.__dataclass_fields__}
    if data.get("start_month") is not None:
        data["start_month"] = str(data["start_month"])
    for field_name in ("shock_fraction", "monthly_growth"):
        if field_name in data:
            data[field_name] = str(data[field_name])
    return data


def _assumption_from_dict(data: dict[str, Any]) -> ScenarioAssumption:
    values = dict(data)
    kind = values.pop("kind")
    if values.get("start_month") is not None:
        values["start_month"] = YearMonth.parse(values["start_month"])
    if kind == "receipts":
        values["shock_fraction"] = Decimal(values["shock_fraction"])
        return ReceiptsAssumption(**values)
    if kind == "mrr_growth":
        values["monthly_growth"] = Decimal(values["monthly_growth"])
        return MrrGrowthAssumption(**values)
    raise ValueError(f"tipo de premissa desconhecido: {kind}")
