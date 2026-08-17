from __future__ import annotations

import statistics
from dataclasses import dataclass

from .data import MarketDataset
from .models import PositionEpisode, Trade


@dataclass(slots=True)
class _OpenEpisode:
    symbol: str
    opened_step: int
    first_entry_price: float
    quantity: float = 0.0
    cash_out: float = 0.0
    cash_in: float = 0.0


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def build_position_episodes(dataset: MarketDataset, trades: list[Trade]) -> list[PositionEpisode]:
    times = dataset.times
    time_index = {timestamp: index for index, timestamp in enumerate(times)}
    open_episodes: dict[str, _OpenEpisode] = {}
    completed: list[PositionEpisode] = []

    def finish(state: _OpenEpisode, closed_step: int, exit_price: float, marked_open: bool) -> None:
        path = [dataset.bars_at(times[index]).get(state.symbol) for index in range(state.opened_step, closed_step + 1)]
        path = [bar for bar in path if bar is not None]
        entry_price = state.first_entry_price
        underwater = sum(1 for bar in path if bar.close < entry_price)
        adverse = max((1.0 - bar.low / entry_price for bar in path), default=0.0)
        favorable = max((bar.high / entry_price - 1.0 for bar in path), default=0.0)
        net_roi = (state.cash_in - state.cash_out) / state.cash_out if state.cash_out > 0 else 0.0
        completed.append(
            PositionEpisode(
                symbol=state.symbol,
                opened_at=times[state.opened_step],
                closed_at=times[closed_step],
                holding_bars=closed_step - state.opened_step + 1,
                entry_price=entry_price,
                exit_price=exit_price,
                net_roi=net_roi,
                time_underwater_bars=underwater,
                max_adverse_excursion=max(0.0, adverse),
                max_favorable_excursion=max(0.0, favorable),
                marked_open_at_end=marked_open,
            )
        )

    for trade in sorted(trades, key=lambda item: (item.timestamp, 0 if item.side == "sell" else 1, item.symbol)):
        step = time_index.get(trade.timestamp)
        if step is None:
            continue
        state = open_episodes.get(trade.symbol)
        if trade.side == "buy":
            if state is None:
                state = _OpenEpisode(trade.symbol, step, trade.price)
                open_episodes[trade.symbol] = state
            state.quantity += trade.quantity
            state.cash_out += trade.notional + trade.fee
            continue
        if state is None:
            continue
        sold = min(state.quantity, trade.quantity)
        if sold <= 0:
            continue
        state.quantity -= sold
        proportional_notional = trade.notional * sold / trade.quantity
        proportional_fee = trade.fee * sold / trade.quantity
        state.cash_in += proportional_notional - proportional_fee
        if state.quantity <= 1e-9:
            finish(state, step, trade.price, False)
            open_episodes.pop(trade.symbol, None)

    final_step = len(times) - 1
    for symbol, state in sorted(open_episodes.items()):
        final_bar = dataset.bars_at(times[final_step]).get(symbol)
        if final_bar is None:
            continue
        state.cash_in += state.quantity * final_bar.close
        finish(state, final_step, final_bar.close, True)

    return completed


def calculate_position_metrics(episodes: list[PositionEpisode]) -> dict[str, float | int]:
    returns = [episode.net_roi for episode in episodes]
    holding = [float(episode.holding_bars) for episode in episodes]
    underwater = [float(episode.time_underwater_bars) for episode in episodes]
    adverse = [episode.max_adverse_excursion for episode in episodes]
    favorable = [episode.max_favorable_excursion for episode in episodes]
    return {
        "position_episode_count": len(episodes),
        "position_win_rate": _mean([1.0 if value > 0 else 0.0 for value in returns]),
        "mean_position_roi": _mean(returns),
        "median_position_roi": _median(returns),
        "mean_holding_bars": _mean(holding),
        "median_holding_bars": _median(holding),
        "mean_position_time_underwater_bars": _mean(underwater),
        "mean_position_max_adverse_excursion": _mean(adverse),
        "mean_position_max_favorable_excursion": _mean(favorable),
    }
