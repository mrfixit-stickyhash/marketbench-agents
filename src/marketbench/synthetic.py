from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

from .data import MarketDataset
from .models import Bar, NewsEvent


REGIMES = (
    ("expansion", 0.0010, 0.010),
    ("liquidity_shock", -0.0060, 0.035),
    ("recovery", 0.0024, 0.020),
    ("sideways_inflation", -0.0001, 0.014),
    ("technology_boom", 0.0015, 0.013),
)


def generate_synthetic_dataset(
    bars: int = 420,
    symbols: tuple[str, ...] = ("ALPHA", "BETA", "GAMMA", "DELTA", "EPSILON", "ZETA"),
    seed: int = 7,
    start: datetime | None = None,
) -> MarketDataset:
    if bars < 80:
        raise ValueError("Synthetic dataset needs at least 80 timestamps")
    rng = random.Random(seed)
    start = start or datetime(2099, 1, 5, 21, 0, tzinfo=timezone.utc)
    prices = {symbol: 80.0 + index * 12.0 for index, symbol in enumerate(symbols)}
    betas = {symbol: 0.65 + index * 0.18 for index, symbol in enumerate(symbols)}
    generated: list[Bar] = []
    news: list[NewsEvent] = []
    regime_length = max(1, bars // len(REGIMES))

    for step in range(bars):
        regime_index = min(step // regime_length, len(REGIMES) - 1)
        regime_name, drift, volatility = REGIMES[regime_index]
        timestamp = start + timedelta(days=step)
        factor = rng.gauss(drift, volatility)

        if step % regime_length == 0:
            news.append(
                NewsEvent(
                    event_id=f"regime-{regime_index}",
                    published_at=timestamp,
                    available_at=timestamp,
                    source="synthetic-wire",
                    headline=f"Macro conditions transition: {regime_name.replace('_', ' ')}",
                    body="Synthetic point-in-time event for the offline benchmark.",
                    symbols=symbols,
                )
            )

        for index, symbol in enumerate(symbols):
            tech_tilt = 0.0025 if regime_name == "technology_boom" and index < 2 else 0.0
            defensive_tilt = 0.0020 if regime_name == "liquidity_shock" and index >= len(symbols) - 2 else 0.0
            idiosyncratic = rng.gauss(0.0, volatility * 0.55)
            log_return = factor * betas[symbol] + idiosyncratic + tech_tilt + defensive_tilt
            previous_close = prices[symbol]
            close = max(1.0, previous_close * math.exp(log_return))
            open_price = max(1.0, previous_close * math.exp(rng.gauss(0.0, volatility * 0.12)))
            spread = abs(rng.gauss(volatility * 0.6, volatility * 0.25))
            high = max(open_price, close) * (1.0 + spread)
            low = max(0.01, min(open_price, close) * (1.0 - spread))
            volume = 800_000 * (1.0 + abs(factor) * 18.0) * (0.8 + rng.random() * 0.5)
            generated.append(Bar(timestamp, symbol, open_price, high, low, close, volume))
            prices[symbol] = close

    return MarketDataset(generated, news, name=f"synthetic-regimes-seed-{seed}")

