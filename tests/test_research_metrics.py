from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from marketbench.data import MarketDataset
from marketbench.models import Bar, OpportunityForecast, Trade
from marketbench.position_metrics import build_position_episodes, calculate_position_metrics
from marketbench.research_eval import FAIL_SCORE, evaluate_research_suites
from marketbench.research_metrics import ForecastRecord, evaluate_forecasts, spearman_rank_correlation


def dataset() -> MarketDataset:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars: list[Bar] = []
    for step in range(8):
        timestamp = start + timedelta(days=step)
        aaa = 100.0 + step * 4.0
        bbb = 100.0 - step * 2.0
        bars.extend(
            [
                Bar(timestamp, "AAA", aaa, aaa + 2.0, aaa - 1.0, aaa + 1.0, 1000),
                Bar(timestamp, "BBB", bbb, bbb + 1.0, bbb - 2.0, bbb - 1.0, 1000),
            ]
        )
    return MarketDataset(bars)


class ResearchMetricTests(unittest.TestCase):
    def test_rank_ic_detects_correct_order(self) -> None:
        self.assertAlmostEqual(spearman_rank_correlation([2, 1, 0], [0.3, 0.2, -0.1]) or 0.0, 1.0)
        self.assertAlmostEqual(spearman_rank_correlation([2, 1, 0], [-0.1, 0.2, 0.3]) or 0.0, -1.0)

    def test_forecasts_measure_ranking_targets_and_calibration(self) -> None:
        records = [
            ForecastRecord(
                0,
                {
                    "AAA": OpportunityForecast(0.9, 0.9, 0.10, 3, 2, 110.0, 95.0),
                    "BBB": OpportunityForecast(-0.8, 0.1, -0.06, 3, 2, 94.0, 105.0),
                },
            )
        ]
        metrics, rows = evaluate_forecasts(dataset(), records)
        self.assertEqual(metrics["forecast_count"], 2)
        self.assertAlmostEqual(float(metrics["rank_ic_mean"]), 1.0)
        self.assertLess(float(metrics["forecast_brier_score"]), 0.02)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["target_hit"] for row in rows))

    def test_position_episode_records_roi_holding_and_excursion(self) -> None:
        data = dataset()
        times = data.times
        trades = [
            Trade(times[1], "AAA", "buy", 10.0, 104.0, 1040.0, 1.0, 0.0),
            Trade(times[4], "AAA", "sell", 10.0, 116.0, 1160.0, 1.0, 0.0),
        ]
        episodes = build_position_episodes(data, trades)
        metrics = calculate_position_metrics(episodes)
        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0].holding_bars, 4)
        self.assertGreater(episodes[0].net_roi, 0.10)
        self.assertEqual(metrics["position_win_rate"], 1.0)

    def test_autoresearch_evaluator_applies_hard_gates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            good = root / "window-good"
            bad = root / "window-bad"
            good.mkdir()
            bad.mkdir()
            base = {"total_return": 0.04, "max_drawdown": 0.10}
            candidate = {
                "total_return": 0.08,
                "max_drawdown": 0.15,
                "agent_error_count": 0,
                "forecast_group_count": 12,
                "rank_ic_mean": 0.2,
                "rank_ic_median": 0.2,
                "forecast_brier_score": 0.18,
            }
            (good / "comparison.json").write_text(
                json.dumps({"agent": candidate, "equal_weight": base}),
                encoding="utf-8",
            )
            failed = dict(candidate, max_drawdown=0.40)
            (bad / "comparison.json").write_text(
                json.dumps({"agent": failed, "equal_weight": base}),
                encoding="utf-8",
            )
            result = evaluate_research_suites(root, "agent", max_drawdown=0.25)
            self.assertEqual(result["eligible_window_count"], 1)
            self.assertAlmostEqual(float(result["score"]), 0.2)
            rejected = evaluate_research_suites(bad, "agent", max_drawdown=0.25)
            self.assertEqual(rejected["score"], FAIL_SCORE)


if __name__ == "__main__":
    unittest.main()
