from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from wealth_agent.memory import ChromaMemory, SQLiteMemory
from wealth_agent.portfolio import analyze_portfolio
from wealth_agent.providers import LangChainAdvisor, OfflineAdvisor
from wealth_agent.service import WealthAgent
from wealth_agent.sources import JsonPortfolioSource, OneLakePortfolioSource

load_dotenv()
ROOT = Path(__file__).parent


def create_app() -> Flask:
    app = Flask(__name__)
    configured_portfolio = Path(os.getenv("WEALTH_PORTFOLIO_PATH", "data/sample_portfolio.json"))
    portfolio_path = configured_portfolio if configured_portfolio.is_absolute() else ROOT / configured_portfolio
    if os.getenv("FABRIC_WORKSPACE"):
        source = OneLakePortfolioSource(os.getenv("FABRIC_WORKSPACE", ""), os.getenv("FABRIC_LAKEHOUSE", ""), os.getenv("FABRIC_PORTFOLIO_PATH", "Files/portfolio.csv"))
    else:
        source = JsonPortfolioSource(portfolio_path)
    memory_backend = os.getenv("WEALTH_MEMORY_BACKEND", "sqlite").lower()
    if memory_backend not in {"sqlite", "chroma"}:
        raise ValueError("WEALTH_MEMORY_BACKEND must be sqlite or chroma")
    configured_db = Path(os.getenv("WEALTH_DB_PATH", "data/wealth_memory.sqlite3"))
    database_path = configured_db if configured_db.is_absolute() else ROOT / configured_db
    memory = ChromaMemory(str(ROOT / "chroma_data")) if memory_backend == "chroma" else SQLiteMemory(database_path)
    provider_name = os.getenv("WEALTH_PROVIDER", "offline").lower()
    if provider_name not in {"offline", "openai"}:
        raise ValueError("WEALTH_PROVIDER must be offline or openai")
    provider = LangChainAdvisor(os.getenv("OPENAI_API_KEY", ""), os.getenv("OPENAI_MODEL", "gpt-4o-mini")) if provider_name == "openai" else OfflineAdvisor()
    agent = WealthAgent(source, memory, provider)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "provider": provider.name, "source": type(source).__name__})

    @app.get("/api/portfolio/<user_id>")
    def portfolio(user_id: str):
        try:
            current = source.load(user_id)
            return jsonify(analyze_portfolio(current).to_dict())
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            app.logger.exception("Portfolio request failed")
            return jsonify({"error": "The portfolio service could not complete this request."}), 500

    @app.post("/api/chat")
    def chat():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            return jsonify({"error": "Request JSON must be an object."}), 400
        question, user_id = payload.get("question", ""), payload.get("user_id", "demo")
        if not isinstance(question, str) or not isinstance(user_id, str):
            return jsonify({"error": "question and user_id must be strings."}), 400
        try:
            return jsonify(agent.ask(user_id, question).to_dict())
        except (ValueError, LookupError) as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            app.logger.exception("Agent request failed")
            return jsonify({"error": "The analysis service could not complete this request."}), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
