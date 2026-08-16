from __future__ import annotations

import math
import statistics
from datetime import datetime


def calculate_metrics(
    equity_curve: list[tuple[datetime, float]],
    bars_per_year: int,
    turnover: float,
    fees_paid: float,
    trade_count: int,
    violation_count: int,
    decision_count: int,
) -> dict[str, float | int]:
    if len(equity_curve) < 2:
        raise ValueError("At least two equity observations are required")
    values = [value for _, value in equity_curve]
    returns = [values[index] / values[index - 1] - 1.0 for index in range(1, len(values)) if values[index - 1] > 0]
    total_return = values[-1] / values[0] - 1.0
    years = max((len(values) - 1) / max(1, bars_per_year), 1.0 / max(1, bars_per_year))
    annualized_return = (values[-1] / values[0]) ** (1.0 / years) - 1.0 if values[-1] > 0 else -1.0
    mean_return = statistics.fmean(returns) if returns else 0.0
    volatility = statistics.stdev(returns) * math.sqrt(bars_per_year) if len(returns) > 1 else 0.0
    sharpe = mean_return / statistics.stdev(returns) * math.sqrt(bars_per_year) if len(returns) > 1 and statistics.stdev(returns) > 0 else 0.0
    downside = [min(0.0, value) for value in returns]
    downside_dev = math.sqrt(statistics.fmean(value * value for value in downside)) if downside else 0.0
    sortino = mean_return / downside_dev * math.sqrt(bars_per_year) if downside_dev > 0 else 0.0

    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        drawdown = (peak - value) / peak if peak > 0 else 0.0
        max_drawdown = max(max_drawdown, drawdown)

    violation_rate = violation_count / max(1, decision_count)
    score = sharpe - 2.0 * max_drawdown - 0.02 * turnover - 0.10 * violation_rate
    return {
        "initial_equity": values[0],
        "final_equity": values[-1],
        "total_return": total_return,
        "annualized_return": annualized_return,
        "annualized_volatility": volatility,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_drawdown,
        "turnover": turnover,
        "fees_paid": fees_paid,
        "trade_count": trade_count,
        "decision_count": decision_count,
        "violation_count": violation_count,
        "violation_rate": violation_rate,
        "score": score,
    }
