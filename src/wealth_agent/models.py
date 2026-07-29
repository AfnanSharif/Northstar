from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class Intent(StrEnum):
    RISK = "risk_analysis"
    ALLOCATION = "allocation"
    PERFORMANCE = "performance"
    PLANNING = "investment_planning"
    GENERAL = "general"


@dataclass(slots=True)
class Holding:
    symbol: str
    name: str
    asset_class: str
    quantity: float
    price: float
    cost_basis: float
    annual_volatility: float
    expected_return: float
    return_history: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        for attribute in ("symbol", "name", "asset_class"):
            value = getattr(self, attribute)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"holding {attribute} must be a non-empty string")
            setattr(self, attribute, value.strip())
        for attribute in ("quantity", "price", "cost_basis", "annual_volatility", "expected_return"):
            value = getattr(self, attribute)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"holding {attribute} must be a finite number")
            setattr(self, attribute, float(value))
        if self.quantity < 0 or self.price < 0 or self.cost_basis < 0 or self.annual_volatility < 0:
            raise ValueError("holding quantity, price, cost_basis, and annual_volatility cannot be negative")
        if self.quantity > 1e12 or self.price > 1e12 or self.cost_basis > 1e12:
            raise ValueError("holding quantity, price, and cost_basis cannot exceed 1e12")
        if self.annual_volatility > 10:
            raise ValueError("holding annual_volatility cannot exceed 10")
        if not -1 < self.expected_return <= 10:
            raise ValueError("holding expected_return must be greater than -1 and no more than 10")
        if not isinstance(self.return_history, list) or len(self.return_history) > 1_000:
            raise ValueError("holding return_history must be a list with at most 1,000 observations")
        validated_history: list[float] = []
        for value in self.return_history:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not -1 <= value <= 10:
                raise ValueError("holding return_history values must be finite numbers between -1 and 10")
            validated_history.append(float(value))
        self.return_history = validated_history

    @property
    def market_value(self) -> float:
        return self.quantity * self.price

    @property
    def gain_loss(self) -> float:
        return self.quantity * (self.price - self.cost_basis)


@dataclass(slots=True)
class Portfolio:
    user_id: str
    risk_tolerance: str
    horizon_years: int
    holdings: list[Holding]

    def __post_init__(self) -> None:
        if not isinstance(self.user_id, str) or not self.user_id.strip():
            raise ValueError("portfolio user_id must be a non-empty string")
        if not isinstance(self.risk_tolerance, str) or not self.risk_tolerance.strip():
            raise ValueError("risk_tolerance must be a non-empty string")
        if isinstance(self.horizon_years, bool) or not isinstance(self.horizon_years, int) or not 0 <= self.horizon_years <= 200:
            raise ValueError("horizon_years must be an integer between 0 and 200")
        if not isinstance(self.holdings, list) or any(not isinstance(item, Holding) for item in self.holdings):
            raise ValueError("holdings must be a list of Holding objects")
        self.user_id = self.user_id.strip()
        self.risk_tolerance = self.risk_tolerance.strip()


@dataclass(slots=True)
class PortfolioAnalysis:
    total_value: float
    total_gain_loss: float
    expected_return: float
    estimated_volatility: float
    diversification_score: float
    concentration_index: float
    largest_position: str
    largest_weight: float
    allocations: dict[str, float]
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AgentResponse:
    answer: str
    intent: Intent
    tools_used: list[str]
    analysis: PortfolioAnalysis | None
    disclaimer: str
    tool_results: dict[str, Any] = field(default_factory=dict)
    preferences: dict[str, str] = field(default_factory=dict)
    engine: str = "local-agent"

    def to_dict(self) -> dict[str, Any]:
        values = asdict(self)
        values["intent"] = self.intent.value
        return values
