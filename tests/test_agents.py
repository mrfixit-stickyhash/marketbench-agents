from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone

from marketbench.agents import ProgramAuthorAgent, SwarmAgentStrategy, parse_json_object
from marketbench.providers import ScriptedProvider
from marketbench.strategies import MarketSnapshot
from marketbench.trajectory import TrajectoryLogger


def snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        step=50,
        timestamp_label="step_000050",
        symbols=("AAA", "BBB"),
        prices={"AAA": 110, "BBB": 90},
        features={
            "AAA": {"price": 110, "return_20": 0.10, "volatility_20": 0.02},
            "BBB": {"price": 90, "return_20": -0.05, "volatility_20": 0.03},
        },
        portfolio_value=100_000,
        cash=100_000,
        current_weights={},
        news=[],
    )


class AgentTests(unittest.TestCase):
    def test_json_fence_parser(self) -> None:
        self.assertEqual(parse_json_object("```json\n{\"x\":1}\n```"), {"x": 1})

    def test_scripted_swarm_returns_weights(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            strategy = SwarmAgentStrategy(ScriptedProvider(), TrajectoryLogger(directory, "swarm"))
            decision = strategy.decide(snapshot())
            self.assertEqual(decision.target_weights, {"AAA": 0.3})
            self.assertEqual(set(decision.forecasts), {"AAA", "BBB"})

    def test_program_author_compiles_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            strategy = ProgramAuthorAgent(ScriptedProvider(), TrajectoryLogger(directory, "program"))
            first = strategy.decide(snapshot())
            second = strategy.decide(snapshot())
            self.assertEqual(first.metadata["program"], second.metadata["program"])
            lines = (strategy.logger.path).read_text(encoding="utf-8").splitlines()
            calls = [json.loads(line) for line in lines if json.loads(line)["kind"] == "model_response"]
            self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
