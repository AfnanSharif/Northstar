from __future__ import annotations

import re
from dataclasses import replace

from .agentic import LangChainMultiAgent
from .memory import Memory
from .models import AgentResponse, Intent
from .portfolio import analyze_portfolio, historical_risk_trends, mitigation_strategies, position_analysis, scenario_projection, stress_test
from .providers import AdviceProvider, OfflineAdvisor
from .sources import PortfolioSource

DISCLAIMER = "Educational analysis only—not individualized investment, tax, or legal advice. Inputs may be stale; verify them with a qualified professional."


def detect_intent(question: str) -> Intent:
    text = question.lower()
    if any(term in text for term in ("risk", "volatile", "stress", "downturn", "loss")):
        return Intent.RISK
    if any(term in text for term in ("allocation", "divers", "concentrat", "weight")):
        return Intent.ALLOCATION
    if any(term in text for term in ("goal", "retire", "project", "future", "plan")):
        return Intent.PLANNING
    if any(term in text for term in ("performance", "gain", "return", "worth", "value")):
        return Intent.PERFORMANCE
    return Intent.GENERAL


class WealthAgent:
    def __init__(self, source: PortfolioSource, memory: Memory, provider: AdviceProvider | None = None, orchestrator: LangChainMultiAgent | None = None) -> None:
        self.source, self.memory, self.provider, self.orchestrator = source, memory, provider or OfflineAdvisor(), orchestrator

    @staticmethod
    def _preference_updates(question: str, supplied: dict[str, str] | None) -> dict[str, str]:
        updates = dict(supplied or {})
        match = re.search(r"(?:risk (?:tolerance|profile) (?:is|to)|I am)\s+(conservative|moderate|aggressive)\b", question, re.IGNORECASE)
        if match:
            updates["risk_tolerance"] = match.group(1).lower()
        allowed = {"risk_tolerance", "goal", "exclusions", "liquidity_needs", "currency"}
        if any(key not in allowed for key in updates):
            raise ValueError(f"preference keys must be one of: {', '.join(sorted(allowed))}")
        cleaned: dict[str, str] = {}
        for key, value in updates.items():
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > 200:
                raise ValueError("preference values must contain 1–200 characters")
            cleaned[key] = re.sub(r"\s+", " ", value).strip()
        if "risk_tolerance" in cleaned and cleaned["risk_tolerance"].lower() not in {"conservative", "moderate", "aggressive"}:
            raise ValueError("risk_tolerance must be conservative, moderate, or aggressive")
        return cleaned

    def ask(self, user_id: str, question: str, preference_updates: dict[str, str] | None = None) -> AgentResponse:
        if not isinstance(user_id, str) or not user_id.strip() or len(user_id) > 100:
            raise ValueError("user_id must be between 1 and 100 characters")
        if not isinstance(question, str):
            raise ValueError("question must be a string")
        clean = re.sub(r"\s+", " ", question).strip()
        if not clean:
            raise ValueError("question cannot be empty")
        if len(clean) > 2_000:
            raise ValueError("question cannot exceed 2,000 characters")
        user_id = user_id.strip()
        updates = self._preference_updates(clean, preference_updates)
        for key, value in updates.items():
            self.memory.set_preference(user_id, key, value.lower() if key == "risk_tolerance" else value)
        preferences = self.memory.preferences(user_id)
        intent = detect_intent(clean)
        tools = ["load_portfolio"]
        portfolio = self.source.load(user_id)
        if preferences.get("risk_tolerance"):
            portfolio = replace(portfolio, risk_tolerance=preferences["risk_tolerance"])
        analysis = analyze_portfolio(portfolio)
        history = self.memory.contextual(user_id, clean)
        if self.orchestrator:
            execution = self.orchestrator.execute(clean, portfolio, history, preferences)
            tools.extend(execution.tools_used)
            results = execution.tool_results
            answer = execution.answer
            engine = self.orchestrator.name
        else:
            results: dict[str, object] = {"position_analysis": position_analysis(portfolio)}
            tools.append("position_analysis_agent")
            if intent == Intent.RISK:
                results["stress_test"] = stress_test(analysis)
                results["historical_risk_trends"] = historical_risk_trends(portfolio)
                tools.append("risk_analysis_agent")
            if intent in {Intent.PLANNING, Intent.ALLOCATION, Intent.RISK}:
                results["mitigation"] = mitigation_strategies(portfolio, analysis, preferences)
                tools.append("risk_mitigation_agent")
            if intent == Intent.PLANNING:
                results["projection"] = scenario_projection(analysis.total_value, analysis.expected_return, portfolio.horizon_years)
                tools.append("investment_planning_agent")
            answer = self.provider.explain(clean, intent, portfolio, analysis, history, results)
            engine = "local-multi-agent"
        self.memory.remember(user_id, clean, answer)
        return AgentResponse(answer, intent, tools, analysis, DISCLAIMER, results, preferences, engine)
