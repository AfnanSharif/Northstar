from __future__ import annotations

import math
import statistics
from collections import defaultdict

from .models import Holding, Portfolio, PortfolioAnalysis


def analyze_portfolio(portfolio: Portfolio, correlation: float = 0.25) -> PortfolioAnalysis:
    if not portfolio.holdings:
        raise ValueError("portfolio must contain at least one holding")
    if isinstance(correlation, bool) or not isinstance(correlation, (int, float)) or not math.isfinite(correlation):
        raise ValueError("correlation must be a finite number")
    if not -1 <= correlation <= 1:
        raise ValueError("correlation must be between -1 and 1")
    if len(portfolio.holdings) > 1 and correlation < -1 / (len(portfolio.holdings) - 1):
        raise ValueError("correlation is not valid for the number of holdings")
    total = sum(item.market_value for item in portfolio.holdings)
    if not math.isfinite(total) or total <= 0:
        raise ValueError("portfolio market value must be positive")
    weights = [item.market_value / total for item in portfolio.holdings]
    expected = sum(weight * item.expected_return for weight, item in zip(weights, portfolio.holdings))
    volatility_exposures = [weight * item.annual_volatility for weight, item in zip(weights, portfolio.holdings)]
    squared_exposure = sum(value * value for value in volatility_exposures)
    variance = (1 - correlation) * squared_exposure + correlation * sum(volatility_exposures) ** 2
    allocations: defaultdict[str, float] = defaultdict(float)
    for weight, item in zip(weights, portfolio.holdings):
        allocations[item.asset_class] += weight
    hhi = sum(weight * weight for weight in allocations.values())
    effective_assets = 1 / hhi if hhi else 0
    diversification = min(100.0, (effective_assets / max(4, len(allocations))) * 100)
    largest_index = max(range(len(weights)), key=weights.__getitem__)
    largest_weight = weights[largest_index]
    recommendations: list[str] = []
    if largest_weight > 0.35:
        recommendations.append(f"Review concentration in {portfolio.holdings[largest_index].symbol} ({largest_weight:.1%} of the portfolio).")
    if allocations.get("Cash", 0) < 0.03:
        recommendations.append("Confirm that a separate emergency reserve covers near-term liquidity needs.")
    equity_weight = sum(value for key, value in allocations.items() if "Equity" in key)
    if portfolio.risk_tolerance.lower() == "conservative" and equity_weight > 0.55:
        recommendations.append("Equity exposure appears high relative to the stated conservative tolerance; review with a fiduciary adviser.")
    if portfolio.horizon_years < 3 and equity_weight > 0.5:
        recommendations.append("A short horizon and high equity allocation can create sequence risk; consider liability-matched assets.")
    if not recommendations:
        recommendations.append("No simple threshold alert fired; review allocation, fees, taxes, and goals periodically.")
    return PortfolioAnalysis(
        total_value=total,
        total_gain_loss=sum(item.gain_loss for item in portfolio.holdings),
        expected_return=expected,
        estimated_volatility=math.sqrt(max(variance, 0)),
        diversification_score=diversification,
        concentration_index=hhi,
        largest_position=portfolio.holdings[largest_index].symbol,
        largest_weight=largest_weight,
        allocations=dict(sorted(allocations.items())),
        recommendations=recommendations,
    )


def scenario_projection(starting_value: float, annual_return: float, years: int, annual_contribution: float = 0) -> list[dict[str, float]]:
    numeric_values = (starting_value, annual_return, annual_contribution)
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in numeric_values):
        raise ValueError("scenario values must be finite numbers")
    if isinstance(years, bool) or not isinstance(years, int) or not 0 <= years <= 200:
        raise ValueError("years must be an integer between 0 and 200")
    if starting_value < 0 or annual_contribution < 0 or not -1 < annual_return <= 10:
        raise ValueError("values cannot be negative and annual_return must be greater than -1 and no more than 10")
    value, results = starting_value, [{"year": 0, "value": round(starting_value, 2)}]
    for year in range(1, years + 1):
        value = value * (1 + annual_return) + annual_contribution
        if not math.isfinite(value):
            raise ValueError("scenario values overflowed the supported numeric range")
        results.append({"year": year, "value": round(value, 2)})
    return results


def stress_test(analysis: PortfolioAnalysis, shock: float = -0.2) -> dict[str, float]:
    if isinstance(shock, bool) or not isinstance(shock, (int, float)) or not math.isfinite(shock) or not -1 <= shock <= 0:
        raise ValueError("shock must be a finite number between -1 and 0")
    equity_weight = sum(weight for asset, weight in analysis.allocations.items() if "Equity" in asset)
    estimated_loss = analysis.total_value * equity_weight * shock
    return {"equity_shock": shock, "equity_weight": equity_weight, "estimated_change": estimated_loss, "stressed_value": analysis.total_value + estimated_loss}


def position_analysis(portfolio: Portfolio) -> list[dict[str, float | str | None]]:
    """Return auditable per-position performance and risk/reward measures."""
    total = sum(item.market_value for item in portfolio.holdings)
    if total <= 0:
        raise ValueError("portfolio market value must be positive")
    positions: list[dict[str, float | str | None]] = []
    for item in portfolio.holdings:
        risk_reward = item.expected_return / item.annual_volatility if item.annual_volatility else None
        positions.append({
            "symbol": item.symbol,
            "asset_class": item.asset_class,
            "market_value": round(item.market_value, 2),
            "weight": item.market_value / total,
            "gain_loss": round(item.gain_loss, 2),
            "expected_return": item.expected_return,
            "annual_volatility": item.annual_volatility,
            "risk_reward_ratio": risk_reward,
        })
    return sorted(positions, key=lambda item: float(item["weight"]), reverse=True)


def historical_risk_trends(portfolio: Portfolio, periods_per_year: int = 12) -> list[dict[str, float | int | str]]:
    """Compare prior and recent realized volatility from supplied return histories."""
    if not 1 <= periods_per_year <= 365:
        raise ValueError("periods_per_year must be between 1 and 365")
    trends: list[dict[str, float | int | str]] = []
    for item in portfolio.holdings:
        values = item.return_history
        if len(values) < 4:
            trends.append({"symbol": item.symbol, "observations": len(values), "direction": "insufficient_history", "prior_volatility": 0.0, "recent_volatility": 0.0})
            continue
        midpoint = len(values) // 2
        prior = statistics.stdev(values[:midpoint]) * math.sqrt(periods_per_year) if midpoint > 1 else 0.0
        recent_values = values[midpoint:]
        recent = statistics.stdev(recent_values) * math.sqrt(periods_per_year) if len(recent_values) > 1 else 0.0
        relative_delta = (recent - prior) / prior if prior else (1.0 if recent else 0.0)
        direction = "rising" if relative_delta > 0.10 else "falling" if relative_delta < -0.10 else "stable"
        trends.append({
            "symbol": item.symbol,
            "observations": len(values),
            "direction": direction,
            "prior_volatility": prior,
            "recent_volatility": recent,
        })
    return trends


def mitigation_strategies(portfolio: Portfolio, analysis: PortfolioAnalysis, preferences: dict[str, str] | None = None) -> dict[str, object]:
    """Generate non-transactional mitigation options from verified portfolio metrics."""
    preferences = preferences or {}
    tolerance = preferences.get("risk_tolerance", portfolio.risk_tolerance).lower()
    max_weight = {"conservative": 0.20, "moderate": 0.30, "aggressive": 0.40}.get(tolerance, 0.30)
    positions = position_analysis(portfolio)
    largest = positions[0]
    excess = max(0.0, float(largest["weight"]) - max_weight)
    options: list[dict[str, str]] = []
    if excess > 0:
        options.append({
            "type": "reallocation",
            "idea": f"Review reducing {largest['symbol']} by about {excess:.1%} of portfolio value and spreading exposure across underweight asset classes.",
            "caveat": "A qualified professional should evaluate taxes, fees, liquidity, and suitability before any transaction.",
        })
    equity_weight = sum(weight for name, weight in analysis.allocations.items() if "equity" in name.lower())
    if equity_weight > 0.50:
        options.append({
            "type": "hedging",
            "idea": "Compare a smaller equity allocation, high-quality fixed income, and a limited-cost protective hedge under the same stress scenario.",
            "caveat": "Derivatives can expire worthless, add complexity, and are not suitable for every investor.",
        })
    if len(analysis.allocations) < 4:
        options.append({
            "type": "alternative_diversifier",
            "idea": "Research whether a low-cost diversifier with genuinely different risk drivers fits the plan rather than adding another correlated fund.",
            "caveat": "Alternatives can be illiquid, opaque, expensive, and still lose value.",
        })
    if not options:
        options.append({"type": "monitor", "idea": "Rebalance against a documented target band and review risk after material life or market changes.", "caveat": "Model inputs and goals require periodic verification."})
    return {"risk_tolerance_used": tolerance, "largest_position": largest["symbol"], "largest_weight": largest["weight"], "options": options}
