from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

from .models import Portfolio
from .portfolio import analyze_portfolio, historical_risk_trends, mitigation_strategies, position_analysis, scenario_projection, stress_test


@dataclass(slots=True)
class AgentTool:
    name: str
    description: str
    run: Callable[[str], str]


@dataclass(slots=True)
class AgentExecution:
    answer: str
    tools_used: list[str]
    tool_results: dict[str, object]


class LangChainMultiAgent:
    """A tool-calling supervisor over deterministic specialist financial agents."""

    name = "langchain-multi-agent"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", executor_factory=None) -> None:
        if not api_key.strip() and executor_factory is None:
            raise ValueError("OPENAI_API_KEY is required for the LangChain agent engine")
        self.api_key, self.model, self.executor_factory = api_key, model, executor_factory

    @staticmethod
    def tools(portfolio: Portfolio, preferences: dict[str, str]) -> list[AgentTool]:
        analysis = analyze_portfolio(portfolio)

        def positions(_: str = "") -> str:
            return json.dumps(position_analysis(portfolio))

        def risk(_: str = "") -> str:
            return json.dumps({"summary": analysis.to_dict(), "stress_test": stress_test(analysis), "historical_trends": historical_risk_trends(portfolio)})

        def strategy(_: str = "") -> str:
            return json.dumps(mitigation_strategies(portfolio, analysis, preferences))

        def planning(_: str = "") -> str:
            return json.dumps({"assumption": "constant expected return; not a forecast", "projection": scenario_projection(analysis.total_value, analysis.expected_return, portfolio.horizon_years)})

        return [
            AgentTool("position_analysis_agent", "Inspect stock positions, weights, performance, volatility, and per-asset risk/reward ratios.", positions),
            AgentTool("risk_analysis_agent", "Quantify allocation risk, diversification, historical volatility direction, and a bounded equity shock.", risk),
            AgentTool("risk_mitigation_agent", "Generate educational reallocation, hedging, and alternative-diversifier options aligned with stored preferences.", strategy),
            AgentTool("investment_planning_agent", "Calculate the assumption-based horizon projection for planning questions.", planning),
        ]

    def _production_executor(self, tools: list[AgentTool]):
        try:
            from langchain.agents import AgentExecutor, create_tool_calling_agent
            from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
            from langchain_core.tools import StructuredTool
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise RuntimeError("Install the AI profile with `pip install -r requirements-ai.txt`") from exc

        langchain_tools = [
            StructuredTool.from_function(name=tool.name, description=tool.description, func=tool.run)
            for tool in tools
        ]
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You supervise specialist wealth-analysis agents. Select the minimum relevant tools, but always call at least one. Use only tool outputs for numbers. Never claim to trade, guarantee returns, or give tax/legal advice. Explain assumptions, provide alternatives rather than directives, and keep the final answer under 220 words. Stored preferences are context, not proof of suitability."),
            ("human", "Question: {input}\nStored preferences: {preferences}\nRelevant prior conversations: {context}"),
            MessagesPlaceholder("agent_scratchpad"),
        ])
        agent = create_tool_calling_agent(ChatOpenAI(api_key=self.api_key, model=self.model, temperature=0), langchain_tools, prompt)
        return AgentExecutor(agent=agent, tools=langchain_tools, max_iterations=6, return_intermediate_steps=True, handle_parsing_errors=True)

    def execute(self, question: str, portfolio: Portfolio, context: list[tuple[str, str]], preferences: dict[str, str]) -> AgentExecution:
        tools = self.tools(portfolio, preferences)
        executor = self.executor_factory(tools) if self.executor_factory else self._production_executor(tools)
        result = executor.invoke({"input": question, "context": context[-5:], "preferences": preferences})
        answer = str(result.get("output", "")).strip()
        if not answer:
            raise ValueError("LangChain supervisor returned an empty answer")
        names: list[str] = []
        outputs: dict[str, object] = {}
        for action, observation in result.get("intermediate_steps", []):
            name = str(getattr(action, "tool", "unknown_tool"))
            if name not in names:
                names.append(name)
            try:
                outputs[name] = json.loads(observation) if isinstance(observation, str) else observation
            except json.JSONDecodeError:
                outputs[name] = observation
        if not names:
            raise ValueError("LangChain supervisor did not invoke a financial tool")
        return AgentExecution(answer, names, outputs)
