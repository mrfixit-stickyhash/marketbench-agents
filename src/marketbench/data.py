from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .models import Bar, NewsEvent, iso_timestamp, parse_timestamp


BAR_COLUMNS = ("timestamp", "symbol", "open", "high", "low", "close", "volume")
NEWS_COLUMNS = (
    "event_id",
    "published_at",
    "available_at",
    "source",
    "headline",
    "body",
    "symbols",
)


@dataclass(slots=True)
class MarketDataset:
    bars: list[Bar]
    news: list[NewsEvent] = field(default_factory=list)
    name: str = "dataset"
    _bars_by_time: dict[datetime, dict[str, Bar]] = field(init=False, repr=False)
    _times: list[datetime] = field(init=False, repr=False)
    _symbols: tuple[str, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.bars:
            raise ValueError("Dataset must contain at least one bar")
        self.bars.sort(key=lambda row: (row.timestamp, row.symbol))
        self.news.sort(key=lambda row: (row.available_at, row.event_id))
        grouped: dict[datetime, dict[str, Bar]] = defaultdict(dict)
        for bar in self.bars:
            if bar.symbol in grouped[bar.timestamp]:
                raise ValueError(f"Duplicate bar for {bar.symbol} at {bar.timestamp}")
            grouped[bar.timestamp][bar.symbol] = bar
        self._bars_by_time = dict(grouped)
        self._times = sorted(grouped)
        self._symbols = tuple(sorted({bar.symbol for bar in self.bars}))

    @property
    def times(self) -> list[datetime]:
        return list(self._times)

    @property
    def symbols(self) -> tuple[str, ...]:
        return self._symbols

    def bars_at(self, timestamp: datetime) -> dict[str, Bar]:
        return self._bars_by_time[timestamp]

    def news_between(self, after: datetime | None, through: datetime) -> list[NewsEvent]:
        return [
            item
            for item in self.news
            if (after is None or item.available_at > after) and item.available_at <= through
        ]

    def anonymized(self) -> tuple["MarketDataset", dict[str, str]]:
        mapping = {symbol: f"ASSET_{index:03d}" for index, symbol in enumerate(self.symbols, 1)}

        def redact_symbols(text: str) -> str:
            result = text
            for original in sorted(mapping, key=len, reverse=True):
                result = result.replace(original, mapping[original])
            return result

        bars = [
            Bar(
                timestamp=bar.timestamp,
                symbol=mapping[bar.symbol],
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
            )
            for bar in self.bars
        ]
        news = [
            NewsEvent(
                event_id=item.event_id,
                published_at=item.published_at,
                available_at=item.available_at,
                source=item.source,
                headline=redact_symbols(item.headline),
                body=redact_symbols(item.body),
                symbols=tuple(mapping[s] for s in item.symbols if s in mapping),
            )
            for item in self.news
        ]
        return MarketDataset(bars, news, f"{self.name}-anonymous"), mapping

    def summary(self) -> dict[str, object]:
        return {
            "name": self.name,
            "bar_count": len(self.bars),
            "timestamp_count": len(self._times),
            "news_count": len(self.news),
            "symbols": list(self.symbols),
            "start": iso_timestamp(self._times[0]),
            "end": iso_timestamp(self._times[-1]),
        }

    @classmethod
    def from_csv(
        cls,
        bars_path: str | Path,
        news_path: str | Path | None = None,
        name: str | None = None,
    ) -> "MarketDataset":
        bars_file = Path(bars_path)
        with bars_file.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            missing = set(BAR_COLUMNS) - set(reader.fieldnames or [])
            if missing:
                raise ValueError(f"Bars CSV is missing columns: {sorted(missing)}")
            bars = [
                Bar(
                    timestamp=parse_timestamp(row["timestamp"]),
                    symbol=row["symbol"].strip(),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                )
                for row in reader
            ]
        news: list[NewsEvent] = []
        if news_path:
            with Path(news_path).open("r", newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                missing = set(NEWS_COLUMNS) - set(reader.fieldnames or [])
                if missing:
                    raise ValueError(f"News CSV is missing columns: {sorted(missing)}")
                for row in reader:
                    news.append(
                        NewsEvent(
                            event_id=row["event_id"],
                            published_at=parse_timestamp(row["published_at"]),
                            available_at=parse_timestamp(row["available_at"]),
                            source=row["source"],
                            headline=row["headline"],
                            body=row["body"],
                            symbols=tuple(s.strip() for s in row["symbols"].split("|") if s.strip()),
                        )
                    )
        return cls(bars, news, name or bars_file.stem)

    def write_csv(self, directory: str | Path) -> tuple[Path, Path]:
        output = Path(directory)
        output.mkdir(parents=True, exist_ok=True)
        bars_path = output / "bars.csv"
        news_path = output / "news.csv"
        with bars_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=BAR_COLUMNS)
            writer.writeheader()
            writer.writerows(bar.to_dict() for bar in self.bars)
        with news_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=NEWS_COLUMNS)
            writer.writeheader()
            for item in self.news:
                row = item.to_dict(include_body=True)
                row["symbols"] = "|".join(item.symbols)
                writer.writerow(row)
        return bars_path, news_path


def require_monotonic(values: Iterable[datetime]) -> None:
    previous: datetime | None = None
    for value in values:
        if previous is not None and value <= previous:
            raise ValueError("Timestamps must be strictly increasing")
        previous = value
