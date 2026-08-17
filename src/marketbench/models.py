from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import math
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
class OpportunityForecast:
    """A point-in-time, machine-scoreable forecast for one tradable asset."""

    score: float
    probability_outperform: float
    expected_return: float
    horizon_bars: int = 5
    expected_event_bars: int | None = None
    target_price: float | None = None
    invalidation_price: float | None = None

    def __post_init__(self) -> None:
        score = float(self.score)
        probability = float(self.probability_outperform)
        expected_return = float(self.expected_return)
        if not all(math.isfinite(value) for value in (score, probability, expected_return)):
            raise ValueError("Forecast score, probability and expected_return must be finite")
        self.score = max(-1.0, min(1.0, score))
        self.probability_outperform = max(0.0, min(1.0, probability))
        self.expected_return = expected_return
        self.horizon_bars = max(1, int(self.horizon_bars))
        if self.expected_event_bars is None:
            self.expected_event_bars = self.horizon_bars
        else:
            self.expected_event_bars = max(1, int(self.expected_event_bars))
        if self.target_price is not None:
            self.target_price = float(self.target_price)
            if not math.isfinite(self.target_price) or self.target_price <= 0:
                raise ValueError("target_price must be positive")
        if self.invalidation_price is not None:
            self.invalidation_price = float(self.invalidation_price)
            if not math.isfinite(self.invalidation_price) or self.invalidation_price <= 0:
                raise ValueError("invalidation_price must be positive")

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "OpportunityForecast":
        return cls(
            score=float(value.get("score", 0.0)),
            probability_outperform=float(value.get("probability_outperform", 0.5)),
            expected_return=float(value.get("expected_return", 0.0)),
            horizon_bars=int(value.get("horizon_bars", 5)),
            expected_event_bars=value.get("expected_event_bars"),
            target_price=value.get("target_price"),
            invalidation_price=value.get("invalidation_price"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Decision:
    target_weights: dict[str, float]
    rationale: str = ""
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)
    forecasts: dict[str, OpportunityForecast] = field(default_factory=dict)

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


@dataclass(frozen=True, slots=True)
class PositionEpisode:
    symbol: str
    opened_at: datetime
    closed_at: datetime
    holding_bars: int
    entry_price: float
    exit_price: float
    net_roi: float
    time_underwater_bars: int
    max_adverse_excursion: float
    max_favorable_excursion: float
    marked_open_at_end: bool = False

    def to_dict(self) -> dict[str, Any]:
        row = asdict(self)
        row["opened_at"] = iso_timestamp(self.opened_at)
        row["closed_at"] = iso_timestamp(self.closed_at)
        return row


@dataclass(slots=True)
class BacktestResult:
    name: str
    metrics: dict[str, float | int | str]
    equity_curve: list[tuple[datetime, float]]
    trades: list[Trade]
    violations: list[str]
    output_dir: str = ""
    position_episodes: list[PositionEpisode] = field(default_factory=list)
    forecast_evaluations: list[dict[str, Any]] = field(default_factory=list)
