import unittest

from wealth_agent.models import Holding, Intent, Portfolio
from wealth_agent.portfolio import analyze_portfolio, scenario_projection, stress_test
from wealth_agent.service import detect_intent


def portfolio() -> Portfolio:
    return Portfolio("test", "moderate", 10, [
        Holding("AAA", "Equity", "US Equity", 8, 100, 80, .20, .08),
        Holding("BBB", "Bond", "Bonds", 2, 100, 100, .05, .03),
    ])


class PortfolioTests(unittest.TestCase):
    def test_analysis_weights_and_totals(self) -> None:
        result = analyze_portfolio(portfolio())
        self.assertAlmostEqual(result.total_value, 1000)
        self.assertAlmostEqual(result.allocations["US Equity"], .8)
        self.assertAlmostEqual(result.total_gain_loss, 160)
        self.assertGreater(result.estimated_volatility, 0)
        self.assertLess(result.estimated_volatility, .2)

    def test_projection_compounds(self) -> None:
        values = scenario_projection(1000, .10, 2, 100)
        self.assertAlmostEqual(values[-1]["value"], 1420)

    def test_stress_and_intent(self) -> None:
        stressed = stress_test(analyze_portfolio(portfolio()), -.25)
        self.assertLess(stressed["stressed_value"], 1000)
        self.assertEqual(detect_intent("How concentrated am I?"), Intent.ALLOCATION)
        self.assertEqual(detect_intent("Stress test a downturn"), Intent.RISK)

    def test_financial_inputs_are_bounded(self) -> None:
        with self.assertRaises(ValueError):
            Holding("BAD", "Invalid", "US Equity", -1, 10, 10, .2, .1)
        with self.assertRaises(ValueError):
            analyze_portfolio(Portfolio("test", "moderate", 10, [
                Holding("A", "A", "Equity", 1, 10, 10, .2, .1),
                Holding("B", "B", "Equity", 1, 10, 10, .2, .1),
                Holding("C", "C", "Equity", 1, 10, 10, .2, .1),
            ]), correlation=-0.75)
        with self.assertRaises(ValueError):
            scenario_projection(1000, -1, 10)


if __name__ == "__main__":
    unittest.main()
