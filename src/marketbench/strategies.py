from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from .models import Decision, OpportunityForecast


@dataclass(slots=True)
class MarketSnapshot:
    timestamp: datetime
    step: int
    timestamp_label: str
    symbols: tuple[str, ...]
    prices: dict[str, float]
    features: dict[str, dict[str, float]]
    portfolio_value: float
    cash: float
    current_weights: dict[str, float]
    news: list[dict[str, Any]] = field(default_factory=list)

    def to_agent_payload(self) -> dict[str, Any]:
        return {
            "as_of": self.timestamp_label,
            "step": self.step,
            "market": self.features,
            "portfolio": {
                "value": round(self.portfolio_value, 4),
                "cash": round(self.cash, 4),
                "current_weights": {key: round(value, 6) for key, value in self.current_weights.items()},
            },
            "news_available_now": self.news,
        }


class Strategy(Protocol):
    name: str

    def decide(self, snapshot: MarketSnapshot) -> Decision:
        ...


class CashStrategy:
    name = "cash"

    def decide(self, snapshot: MarketSnapshot) -> Decision:
        return Decision({}, "Remain in cash.", 1.0)


class EqualWeightStrategy:
    name = "equal_weight"

    def decide(self, snapshot: MarketSnapshot) -> Decision:
        if not snapshot.symbols:
            return Decision({}, "No tradable symbols.", 1.0)
        weight = 0.95 / len(snapshot.symbols)
        return Decision({symbol: weight for symbol in snapshot.symbols}, "Equal-weight baseline.", 1.0)


class MomentumStrategy:
    name = "momentum_20"

    def __init__(self, top_k: int = 3):
        self.top_k = top_k

    def decide(self, snapshot: MarketSnapshot) -> Decision:
        ranked = sorted(
            ((feature.get("return_20", 0.0), symbol) for symbol, feature in snapshot.features.items()),
            reverse=True,
        )
        selected = [symbol for score, symbol in ranked[: self.top_k] if score > 0]
        forecasts = build_opportunity_forecasts(snapshot, {symbol: score for score, symbol in ranked})
        if not selected:
            return Decision({}, "No positive 20-period momentum; hold cash.", 0.7, forecasts=forecasts)
        weight = min(0.30, 0.90 / len(selected))
        return Decision(
            {symbol: weight for symbol in selected},
            "Deterministic 20-period momentum baseline.",
            0.8,
            forecasts=forecasts,
        )


@dataclass(slots=True)
class ProgramSpec:
    signal: str = "momentum"
    lookback: int = 20
    top_k: int = 3
    max_weight: float = 0.30
    cash_buffer: float = 0.10
    minimum_signal: float = 0.0

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "ProgramSpec":
        signal = str(value.get("signal", "momentum"))
        if signal not in {"momentum", "mean_reversion", "volatility_adjusted_momentum", "equal_weight"}:
            signal = "momentum"
        return cls(
            signal=signal,
            lookback=max(2, min(60, int(value.get("lookback", 20)))),
            top_k=max(1, min(10, int(value.get("top_k", 3)))),
            max_weight=max(0.02, min(0.35, float(value.get("max_weight", 0.30)))),
            cash_buffer=max(0.05, min(0.80, float(value.get("cash_buffer", 0.10)))),
            minimum_signal=float(value.get("minimum_signal", 0.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal": self.signal,
            "lookback": self.lookback,
            "top_k": self.top_k,
            "max_weight": self.max_weight,
            "cash_buffer": self.cash_buffer,
            "minimum_signal": self.minimum_signal,
        }


class SafeProgramStrategy:
    """Executes a small declarative strategy language instead of arbitrary model code."""

    def __init__(self, spec: ProgramSpec, name: str = "safe_program"):
        self.spec = spec
        self.name = name

    def decide(self, snapshot: MarketSnapshot) -> Decision:
        if self.spec.signal == "equal_weight":
            candidates = [(1.0, symbol) for symbol in snapshot.symbols]
        else:
            return_key = f"return_{self.spec.lookback}"
            candidates = []
            for symbol, feature in snapshot.features.items():
                value = feature.get(return_key)
                if value is None:
                    value = feature.get("return_20", 0.0)
                if self.spec.signal == "mean_reversion":
                    score = -value
                elif self.spec.signal == "volatility_adjusted_momentum":
                    score = value / max(feature.get("volatility_20", 0.0), 1e-6)
                else:
                    score = value
                if math.isfinite(score):
                    candidates.append((score, symbol))
        candidates.sort(reverse=True)
        forecasts = build_opportunity_forecasts(snapshot, {symbol: score for score, symbol in candidates})
        selected = [symbol for score, symbol in candidates[: self.spec.top_k] if score >= self.spec.minimum_signal]
        if not selected:
            return Decision(
                {},
                f"Program {self.spec.signal} found no qualifying assets.",
                0.6,
                {"program": self.spec.to_dict()},
                forecasts,
            )
        investable = 1.0 - self.spec.cash_buffer
        weight = min(self.spec.max_weight, investable / len(selected))
        weights = {symbol: weight for symbol in selected}
        return Decision(
            weights,
            f"Executed safe {self.spec.signal} program.",
            0.8,
            {"program": self.spec.to_dict()},
            forecasts,
        )


def build_opportunity_forecasts(
    snapshot: MarketSnapshot,
    raw_scores: dict[str, float] | None = None,
    horizon_bars: int = 5,
) -> dict[str, OpportunityForecast]:
    """Create deterministic, fully declared forecasts for baseline comparison."""

    forecasts: dict[str, OpportunityForecast] = {}
    for symbol in snapshot.symbols:
        feature = snapshot.features.get(symbol, {})
        raw = float((raw_scores or {}).get(symbol, feature.get("return_20", 0.0)))
        score = max(-1.0, min(1.0, raw * 5.0))
        expected_return = score * 0.05
        price = float(snapshot.prices.get(symbol, feature.get("price", 0.0)))
        if price <= 0:
            continue
        forecasts[symbol] = OpportunityForecast(
            score=score,
            probability_outperform=max(0.05, min(0.95, 0.5 + score * 0.35)),
            expected_return=expected_return,
            horizon_bars=horizon_bars,
            expected_event_bars=horizon_bars,
            target_price=price * (1.0 + expected_return),
            invalidation_price=price * (0.96 if score >= 0 else 1.04),
        )
    return forecasts


def build_features(history: dict[str, list[float]]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for symbol, values in history.items():
        if not values:
            continue
        feature: dict[str, float] = {"price": values[-1]}
        for lookback in (1, 5, 10, 20, 60):
            if len(values) > lookback and values[-lookback - 1] > 0:
                feature[f"return_{lookback}"] = values[-1] / values[-lookback - 1] - 1.0
            else:
                feature[f"return_{lookback}"] = 0.0
        recent = values[-21:]
        period_returns = [recent[index] / recent[index - 1] - 1.0 for index in range(1, len(recent))]
        feature["volatility_20"] = statistics.stdev(period_returns) if len(period_returns) > 1 else 0.0
        result[symbol] = feature
    return result
