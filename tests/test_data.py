from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from marketbench.data import MarketDataset
from marketbench.models import Bar, NewsEvent


class DataTests(unittest.TestCase):
    def test_news_is_released_by_available_at(self) -> None:
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        bars = [Bar(start + timedelta(days=i), "AAA", 100, 101, 99, 100, 1000) for i in range(3)]
        event = NewsEvent("n1", start, start + timedelta(days=2), "wire", "Delayed event")
        dataset = MarketDataset(bars, [event])
        self.assertEqual(dataset.news_between(None, start + timedelta(days=1)), [])
        self.assertEqual(dataset.news_between(None, start + timedelta(days=2))[0].event_id, "n1")

    def test_csv_round_trip(self) -> None:
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        dataset = MarketDataset(
            [Bar(start, "AAA", 100, 102, 99, 101, 1200)],
            [NewsEvent("n1", start, start, "wire", "Headline", "Body", ("AAA",))],
        )
        with tempfile.TemporaryDirectory() as directory:
            bars_path, news_path = dataset.write_csv(directory)
            loaded = MarketDataset.from_csv(bars_path, news_path)
            self.assertEqual(loaded.symbols, ("AAA",))
            self.assertEqual(loaded.news[0].headline, "Headline")

    def test_anonymization_is_consistent(self) -> None:
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        dataset = MarketDataset(
            [Bar(start, "AAPL", 100, 101, 99, 100, 1000)],
            [NewsEvent("n1", start, start, "wire", "AAPL event", symbols=("AAPL",))],
        )
        anonymous, mapping = dataset.anonymized()
        self.assertEqual(mapping["AAPL"], "ASSET_001")
        self.assertEqual(anonymous.news[0].symbols, ("ASSET_001",))
        self.assertNotIn("AAPL", anonymous.news[0].headline)


if __name__ == "__main__":
    unittest.main()
