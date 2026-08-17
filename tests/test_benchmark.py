from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from marketbench.benchmark import export_sft_dataset, model_matrix_factories, run_suite, strategy_factories
from marketbench.engine import EngineConfig
from marketbench.portfolio import ExecutionConfig, RiskConfig
from marketbench.synthetic import generate_synthetic_dataset


class BenchmarkTests(unittest.TestCase):
    def test_model_matrix_names_each_agent_provider_pair(self) -> None:
        factories = model_matrix_factories(
            ["cash"],
            ["direct_agent", "agent_swarm"],
            {"local": {"kind": "scripted"}, "frontier": {"kind": "scripted"}},
        )
        self.assertEqual(
            set(factories),
            {"cash", "direct_agent__local", "agent_swarm__local", "direct_agent__frontier", "agent_swarm__frontier"},
        )

    def test_end_to_end_and_sft_export(self) -> None:
        dataset = generate_synthetic_dataset(bars=100, seed=3)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "suite"
            results = run_suite(
                dataset,
                strategy_factories(["cash", "direct_agent"], {"kind": "scripted"}),
                root,
                EngineConfig(warmup_bars=20, decision_every=10, history_bars=40, bars_per_year=252),
                ExecutionConfig(),
                RiskConfig(),
            )
            self.assertEqual(len(results), 2)
            self.assertTrue((root / "comparison.html").exists())
            self.assertTrue((root / "direct_agent" / "forecast-evaluations.json").exists())
            self.assertTrue((root / "direct_agent" / "position-episodes.json").exists())
            output = Path(directory) / "sft.jsonl"
            count = export_sft_dataset(root, output)
            self.assertGreater(count, 0)
            record = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(record["messages"][-1]["role"], "assistant")
            self.assertIn("run_score", record["metadata"])


if __name__ == "__main__":
    unittest.main()
