from __future__ import annotations

import json
from typing import Protocol

from .models import Intent, Portfolio, PortfolioAnalysis


class AdviceProvider(Protocol):
    name: str
    def explain(self, question: str, intent: Intent, portfolio: Portfolio, analysis: PortfolioAnalysis, context: list[tuple[str, str]], tool_results: dict[str, object]) -> str: ...


class OfflineAdvisor:
    name = "offline-rules"

    def explain(self, question: str, intent: Intent, portfolio: Portfolio, analysis: PortfolioAnalysis, context: list[tuple[str, str]], tool_results: dict[str, object]) -> str:
        if intent == Intent.RISK:
            trends = tool_results.get("historical_risk_trends", [])
            rising = [item["symbol"] for item in trends if item.get("direction") == "rising"] if isinstance(trends, list) else []
            trend_note = f" Realized volatility is rising in the supplied history for {', '.join(rising)}." if rising else " No supplied return series shows a material rise under the 10% trend threshold."
            return f"Estimated annual volatility is {analysis.estimated_volatility:.1%}; the largest position is {analysis.largest_position} at {analysis.largest_weight:.1%}." + trend_note + " " + " ".join(analysis.recommendations)
        if intent == Intent.ALLOCATION:
            allocation = ", ".join(f"{name}: {weight:.1%}" for name, weight in analysis.allocations.items())
            return f"Current allocation is {allocation}. Diversification score: {analysis.diversification_score:.0f}/100. " + " ".join(analysis.recommendations)
        if intent == Intent.PERFORMANCE:
            return f"The portfolio is worth ${analysis.total_value:,.2f} with an unrealized gain/loss of ${analysis.total_gain_loss:,.2f}. Its assumption-based expected annual return is {analysis.expected_return:.1%}."
        if intent == Intent.PLANNING and "projection" in tool_results:
            final = tool_results["projection"][-1]
            mitigation = tool_results.get("mitigation", {}).get("options", []) if isinstance(tool_results.get("mitigation"), dict) else []
            option = f" One option to review: {mitigation[0]['idea']}" if mitigation else ""
            return f"Under the selected constant-return scenario, the projected year-{final['year']} value is ${final['value']:,.2f}. This is a scenario, not a forecast." + option
        return "I can analyze allocation, concentration, volatility, performance, stress scenarios, and goal projections. Ask a specific portfolio question for an auditable tool result."


class LangChainAdvisor:
    name = "langchain-openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required")
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI

        prompt = ChatPromptTemplate.from_messages([
            ("system", "Explain supplied portfolio calculations in plain language. Do not invent prices, guarantee returns, or prescribe trades. State that assumptions and user circumstances matter. Keep it under 180 words."),
            ("human", "QUESTION: {question}\nINTENT: {intent}\nPORTFOLIO: {portfolio}\nANALYSIS: {analysis}\nTOOLS: {tools}\nPRIOR CONTEXT: {context}"),
        ])
        self.chain = prompt | ChatOpenAI(api_key=api_key, model=model, temperature=0.15) | StrOutputParser()

    def explain(self, question: str, intent: Intent, portfolio: Portfolio, analysis: PortfolioAnalysis, context: list[tuple[str, str]], tool_results: dict[str, object]) -> str:
        return self.chain.invoke({"question": question, "intent": intent.value, "portfolio": portfolio, "analysis": json.dumps(analysis.to_dict()), "tools": json.dumps(tool_results), "context": context[-3:]})
