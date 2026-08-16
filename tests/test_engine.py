from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from marketbench.data import MarketDataset
from marketbench.engine import BacktestEngine, EngineConfig
from marketbench.models import Bar, Decision, NewsEvent
from marketbench.portfolio import ExecutionConfig, RiskConfig, RiskGate
from marketbench.trajectory import TrajectoryLogger


class AlwaysBuy:
    name = "always_buy"

    def decide(self, snapshot):
        return Decision({"AAA": 0.9}, "Buy after observing the current close.", 1.0)


class EngineTests(unittest.TestCase):
    def test_hidden_timestamp_is_removed_from_news_observation(self) -> None:
        import json

        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        bars = [Bar(start + timedelta(days=i), "AAA", 100, 102, 99, 101, 1000) for i in range(5)]
        dataset = MarketDataset(bars, [NewsEvent("n1", start, start, "wire", "Event")])
        with tempfile.TemporaryDirectory() as directory:
            logger = TrajectoryLogger(directory, "redacted-time")
            engine = BacktestEngine(
                dataset,
                AlwaysBuy(),
                RiskGate(RiskConfig(max_turnover_per_decision=2.0), {"AAA"}),
                logger,
                EngineConfig(warmup_bars=1, decision_every=1, history_bars=10, expose_timestamps=False),
                ExecutionConfig(),
            )
            engine.run()
            events = [json.loads(line) for line in logger.path.read_text(encoding="utf-8").splitlines()]
        observations = [event for event in events if event["kind"] == "observation"]
        news = observations[0]["payload"]["news_available_now"]
        self.assertTrue(news)
        self.assertNotIn("published_at", news[0])
        self.assertNotIn("available_at", news[0])
        self.assertEqual(news[0]["available_step"], "step_000001")
    def test_decision_executes_on_next_bar_open(self) -> None:
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        opens = [100.0, 110.0, 200.0, 205.0]
        closes = [105.0, 120.0, 202.0, 207.0]
        bars = [
            Bar(start + timedelta(days=i), "AAA", open_price, max(open_price, closes[i]) + 1, min(open_price, closes[i]) - 1, closes[i], 1000)
            for i, open_price in enumerate(opens)
        ]
        dataset = MarketDataset(bars)
        with tempfile.TemporaryDirectory() as directory:
            logger = TrajectoryLogger(directory, "next-bar")
            engine = BacktestEngine(
                dataset,
                AlwaysBuy(),
                RiskGate(RiskConfig(max_turnover_per_decision=2.0), {"AAA"}),
                logger,
                EngineConfig(warmup_bars=1, decision_every=1, history_bars=10, bars_per_year=252),
                ExecutionConfig(fee_bps=0.0, slippage_bps=0.0),
            )
            result = engine.run()
        self.assertTrue(result.trades)
        self.assertEqual(result.trades[0].timestamp, start + timedelta(days=2))
        self.assertEqual(result.trades[0].price, 200.0)

    def test_engine_records_metrics(self) -> None:
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        bars = [Bar(start + timedelta(days=i), "AAA", 100 + i, 102 + i, 99 + i, 101 + i, 1000) for i in range(10)]
        with tempfile.TemporaryDirectory() as directory:
            engine = BacktestEngine(
                MarketDataset(bars),
                AlwaysBuy(),
                RiskGate(RiskConfig(max_turnover_per_decision=2.0), {"AAA"}),
                TrajectoryLogger(directory, "metrics"),
                EngineConfig(warmup_bars=2, decision_every=2, history_bars=10, bars_per_year=252),
                ExecutionConfig(),
            )
            result = engine.run()
        self.assertIn("max_drawdown", result.metrics)
        self.assertIn("score", result.metrics)


if __name__ == "__main__":
    unittest.main()
