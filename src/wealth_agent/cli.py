from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .memory import SQLiteMemory
from .providers import LangChainAdvisor, OfflineAdvisor
from .service import WealthAgent
from .sources import JsonPortfolioSource


def main() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        pass
    else:
        load_dotenv()

    parser = argparse.ArgumentParser(description="Ask the explainable wealth agent")
    parser.add_argument("question", nargs="+")
    parser.add_argument("--portfolio", type=Path, default=Path(os.getenv("WEALTH_PORTFOLIO_PATH", "data/sample_portfolio.json")))
    parser.add_argument("--provider", choices=["offline", "openai"], default=os.getenv("WEALTH_PROVIDER", "offline"))
    parser.add_argument("--user-id", default="demo")
    args = parser.parse_args()
    provider = LangChainAdvisor(os.getenv("OPENAI_API_KEY", ""), os.getenv("OPENAI_MODEL", "gpt-4o-mini")) if args.provider == "openai" else OfflineAdvisor()
    agent = WealthAgent(JsonPortfolioSource(args.portfolio), SQLiteMemory(os.getenv("WEALTH_DB_PATH", "data/wealth_memory.sqlite3")), provider)
    print(json.dumps(agent.ask(args.user_id, " ".join(args.question)).to_dict(), indent=2))


if __name__ == "__main__":
    main()
