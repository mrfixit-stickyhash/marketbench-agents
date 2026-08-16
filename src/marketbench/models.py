from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError(f"Timestamp must include a timezone: {value!r}")
    return result.astimezone(timezone.utc)


def iso_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class Bar:
    timestamp: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("Bar symbol cannot be empty")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("OHLC prices must be positive")
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close):
            raise ValueError("Invalid OHLC range")
        if self.volume < 0:
            raise ValueError("Volume cannot be negative")
        object.__setattr__(self, "timestamp", parse_timestamp(self.timestamp))

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["timestamp"] = iso_timestamp(self.timestamp)
        return row


@dataclass(frozen=True, slots=True)
class NewsEvent:
    event_id: str
    published_at: datetime
    available_at: datetime
    source: str
    headline: str
    body: str = ""
    symbols: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "published_at", parse_timestamp(self.published_at))
        object.__setattr__(self, "available_at", parse_timestamp(self.available_at))
        if self.available_at < self.published_at:
            raise ValueError("available_at cannot precede published_at")

    def to_dict(self, include_body: bool = False) -> dict[str, Any]:
        result = {
            "event_id": self.event_id,
            "published_at": iso_timestamp(self.published_at),
            "available_at": iso_timestamp(self.available_at),
            "source": self.source,
            "headline": self.headline,
            "symbols": list(self.symbols),
        }
        if include_body:
            result["body"] = self.body
        return result


@dataclass(slots=True)
class Decision:
    target_weights: dict[str, float]
    rationale: str = ""
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Trade:
    timestamp: datetime
    symbol: str
    side: str
    quantity: float
    price: float
    notional: float
    fee: float
    slippage_bps: float

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["timestamp"] = iso_timestamp(self.timestamp)
        return row


@dataclass(slots=True)
class BacktestResult:
    name: str
    metrics: dict[str, float | int | str]
    equity_curve: list[tuple[datetime, float]]
    trades: list[Trade]
    violations: list[str]
    output_dir: str = ""

