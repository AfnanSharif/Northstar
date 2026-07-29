import tempfile
import unittest
from pathlib import Path

from wealth_agent.memory import SQLiteMemory
from wealth_agent.service import WealthAgent
from wealth_agent.sources import JsonPortfolioSource


class ServiceTests(unittest.TestCase):
    def test_agent_uses_risk_tools(self) -> None:
        source = JsonPortfolioSource(Path(__file__).parents[1] / "data/sample_portfolio.json")
        with tempfile.TemporaryDirectory() as directory:
            agent = WealthAgent(source, SQLiteMemory(Path(directory) / "memory.sqlite3"))
            result = agent.ask("demo", "Please stress test my portfolio risk")
        self.assertIn("stress_test", result.tools_used)
        self.assertIsNotNone(result.analysis)
        self.assertIn("not individualized", result.disclaimer)

    def test_local_source_does_not_return_another_user_portfolio(self) -> None:
        source = JsonPortfolioSource(Path(__file__).parents[1] / "data/sample_portfolio.json")
        with self.assertRaises(LookupError):
            source.load("another-user")


if __name__ == "__main__":
    unittest.main()
