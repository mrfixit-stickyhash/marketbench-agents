from __future__ import annotations

import unittest

from marketbench.portfolio import RiskConfig, RiskGate


class RiskTests(unittest.TestCase):
    def test_gate_blocks_unknown_short_and_concentration(self) -> None:
        gate = RiskGate(
            RiskConfig(
                long_only=True,
                max_position_weight=0.35,
                max_gross_exposure=0.90,
                min_cash_weight=0.10,
                max_turnover_per_decision=2.0,
            ),
            {"AAA", "BBB"},
        )
        result = gate.sanitize({"AAA": 0.8, "BBB": -0.2, "EVIL": 0.5}, {})
        self.assertAlmostEqual(result.target_weights["AAA"], 0.35)
        self.assertNotIn("BBB", result.target_weights)
        self.assertNotIn("EVIL", result.target_weights)
        self.assertIn("position_clamped:AAA", result.violations)
        self.assertIn("short_blocked:BBB", result.violations)
        self.assertIn("unknown_symbol:EVIL", result.violations)

    def test_turnover_interpolates_from_current_weights(self) -> None:
        gate = RiskGate(RiskConfig(max_turnover_per_decision=0.20), {"AAA", "BBB"})
        result = gate.sanitize({"BBB": 0.35}, {"AAA": 0.35})
        turnover = abs(result.target_weights.get("AAA", 0) - 0.35) + abs(result.target_weights.get("BBB", 0) - 0)
        self.assertLessEqual(turnover, 0.2000001)
        self.assertIn("turnover_scaled", result.violations)


if __name__ == "__main__":
    unittest.main()

