from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Any, Iterable

from .data import MarketDataset
from .models import OpportunityForecast, iso_timestamp


@dataclass(frozen=True, slots=True)
class ForecastRecord:
    decision_step: int
    forecasts: dict[str, OpportunityForecast]


def _average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor + 1
        while end < len(order) and values[order[end]] == values[order[cursor]]:
            end += 1
        average = (cursor + 1 + end) / 2.0
        for position in range(cursor, end):
            ranks[order[position]] = average
        cursor = end
    return ranks


def spearman_rank_correlation(left: Iterable[float], right: Iterable[float]) -> float | None:
    left_values = [float(value) for value in left]
    right_values = [float(value) for value in right]
    if len(left_values) != len(right_values) or len(left_values) < 2:
        return None
    left_ranks = _average_ranks(left_values)
    right_ranks = _average_ranks(right_values)
    left_mean = statistics.fmean(left_ranks)
    right_mean = statistics.fmean(right_ranks)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left_ranks, right_ranks))
    left_scale = math.sqrt(sum((value - left_mean) ** 2 for value in left_ranks))
    right_scale = math.sqrt(sum((value - right_mean) ** 2 for value in right_ranks))
    if left_scale <= 0 or right_scale <= 0:
        return None
    return numerator / (left_scale * right_scale)


def _mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def evaluate_forecasts(
    dataset: MarketDataset,
    records: Iterable[ForecastRecord],
) -> tuple[dict[str, float | int], list[dict[str, Any]]]:
    """Score point-in-time forecasts only after their declared horizons have elapsed."""

    times = dataset.times
    evaluations: list[dict[str, Any]] = []
    rank_ics: list[float] = []

    for record in records:
        entry_step = record.decision_step + 1
        if entry_step >= len(times):
            continue
        grouped_scores: dict[int, list[tuple[float, float]]] = {}

        for symbol, forecast in sorted(record.forecasts.items()):
            exit_step = entry_step + forecast.horizon_bars - 1
            if exit_step >= len(times):
                continue
            entry_bar = dataset.bars_at(times[entry_step]).get(symbol)
            exit_bar = dataset.bars_at(times[exit_step]).get(symbol)
            if entry_bar is None or exit_bar is None:
                continue

            comparable_returns: list[float] = []
            for candidate in dataset.symbols:
                candidate_entry = dataset.bars_at(times[entry_step]).get(candidate)
                candidate_exit = dataset.bars_at(times[exit_step]).get(candidate)
                if candidate_entry is not None and candidate_exit is not None and candidate_entry.open > 0:
                    comparable_returns.append(candidate_exit.close / candidate_entry.open - 1.0)
            benchmark_return = _mean(comparable_returns)
            realized_return = exit_bar.close / entry_bar.open - 1.0
            excess_return = realized_return - benchmark_return
            success = 1.0 if excess_return > 0 else 0.0

            path = [dataset.bars_at(times[index]).get(symbol) for index in range(entry_step, exit_step + 1)]
            path = [bar for bar in path if bar is not None]
            bullish = forecast.score >= 0
            if bullish:
                maximum_favorable = max((bar.high / entry_bar.open - 1.0 for bar in path), default=0.0)
                maximum_adverse = max((1.0 - bar.low / entry_bar.open for bar in path), default=0.0)
                underwater = sum(1 for bar in path if bar.close < entry_bar.open)
            else:
                maximum_favorable = max((1.0 - bar.low / entry_bar.open for bar in path), default=0.0)
                maximum_adverse = max((bar.high / entry_bar.open - 1.0 for bar in path), default=0.0)
                underwater = sum(1 for bar in path if bar.close > entry_bar.open)

            target_hit_step: int | None = None
            if forecast.target_price is not None:
                target_is_above = forecast.target_price >= entry_bar.open
                for offset, bar in enumerate(path, 1):
                    if (target_is_above and bar.high >= forecast.target_price) or (
                        not target_is_above and bar.low <= forecast.target_price
                    ):
                        target_hit_step = offset
                        break
            invalidation_hit = False
            if forecast.invalidation_price is not None:
                invalidation_is_above = forecast.invalidation_price >= entry_bar.open
                invalidation_hit = any(
                    (invalidation_is_above and bar.high >= forecast.invalidation_price)
                    or (not invalidation_is_above and bar.low <= forecast.invalidation_price)
                    for bar in path
                )

            directional_return = realized_return if bullish else -realized_return
            capture = max(0.0, directional_return) / maximum_favorable if maximum_favorable > 1e-12 else 0.0
            capture = max(0.0, min(1.0, capture))
            target_error = (
                abs(forecast.target_price - exit_bar.close) / entry_bar.open
                if forecast.target_price is not None
                else None
            )
            timing_error = (
                abs(target_hit_step - int(forecast.expected_event_bars or forecast.horizon_bars))
                if target_hit_step is not None
                else None
            )
            evaluation = {
                "decision_step": record.decision_step,
                "entry_step": entry_step,
                "exit_step": exit_step,
                "entry_at": iso_timestamp(times[entry_step]),
                "exit_at": iso_timestamp(times[exit_step]),
                "symbol": symbol,
                "score": forecast.score,
                "probability_outperform": forecast.probability_outperform,
                "expected_return": forecast.expected_return,
                "horizon_bars": forecast.horizon_bars,
                "expected_event_bars": forecast.expected_event_bars,
                "target_price": forecast.target_price,
                "invalidation_price": forecast.invalidation_price,
                "entry_price": entry_bar.open,
                "exit_price": exit_bar.close,
                "realized_return": realized_return,
                "benchmark_return": benchmark_return,
                "excess_return": excess_return,
                "outperformed": bool(success),
                "brier_loss": (forecast.probability_outperform - success) ** 2,
                "expected_return_error": abs(forecast.expected_return - realized_return),
                "target_hit": target_hit_step is not None,
                "time_to_target_bars": target_hit_step,
                "target_timing_error_bars": timing_error,
                "target_error": target_error,
                "invalidation_hit": invalidation_hit,
                "time_underwater_bars": underwater,
                "max_adverse_excursion": max(0.0, maximum_adverse),
                "max_favorable_excursion": max(0.0, maximum_favorable),
                "opportunity_capture": capture,
            }
            evaluations.append(evaluation)
            grouped_scores.setdefault(forecast.horizon_bars, []).append((forecast.score, realized_return))

        for pairs in grouped_scores.values():
            correlation = spearman_rank_correlation(
                [score for score, _ in pairs],
                [realized for _, realized in pairs],
            )
            if correlation is not None:
                rank_ics.append(correlation)

    brier = [float(item["brier_loss"]) for item in evaluations]
    excess = [float(item["excess_return"]) for item in evaluations]
    target_errors = [float(item["target_error"]) for item in evaluations if item["target_error"] is not None]
    timing_errors = [
        float(item["target_timing_error_bars"])
        for item in evaluations
        if item["target_timing_error_bars"] is not None
    ]
    time_to_target = [
        float(item["time_to_target_bars"])
        for item in evaluations
        if item["time_to_target_bars"] is not None
    ]
    underwater = [float(item["time_underwater_bars"]) for item in evaluations]
    adverse = [float(item["max_adverse_excursion"]) for item in evaluations]
    favorable = [float(item["max_favorable_excursion"]) for item in evaluations]
    capture = [float(item["opportunity_capture"]) for item in evaluations]
    return_errors = [float(item["expected_return_error"]) for item in evaluations]
    rank_ic_std = statistics.stdev(rank_ics) if len(rank_ics) > 1 else 0.0

    metrics: dict[str, float | int] = {
        "forecast_count": len(evaluations),
        "forecast_group_count": len(rank_ics),
        "rank_ic_mean": _mean(rank_ics),
        "rank_ic_median": _median(rank_ics),
        "rank_ic_ir": _mean(rank_ics) / rank_ic_std if rank_ic_std > 0 else 0.0,
        "forecast_brier_score": _mean(brier),
        "forecast_hit_rate": _mean([1.0 if item["outperformed"] else 0.0 for item in evaluations]),
        "forecast_excess_return_mean": _mean(excess),
        "expected_return_error_mean": _mean(return_errors),
        "target_count": len(target_errors),
        "target_hit_rate": _mean([1.0 if item["target_hit"] else 0.0 for item in evaluations if item["target_price"] is not None]),
        "target_error_mean": _mean(target_errors),
        "target_timing_error_mean_bars": _mean(timing_errors),
        "time_to_target_mean_bars": _mean(time_to_target),
        "forecast_time_underwater_mean_bars": _mean(underwater),
        "forecast_max_adverse_excursion_mean": _mean(adverse),
        "forecast_max_favorable_excursion_mean": _mean(favorable),
        "opportunity_capture_mean": _mean(capture),
        "invalidation_hit_rate": _mean(
            [1.0 if item["invalidation_hit"] else 0.0 for item in evaluations if item["invalidation_price"] is not None]
        ),
    }
    return metrics, evaluations
