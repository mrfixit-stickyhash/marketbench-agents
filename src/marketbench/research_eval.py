from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any


FAIL_SCORE = -1_000_000_000.0


def _suite_files(root: str | Path) -> list[Path]:
    candidate = Path(root)
    direct = candidate / "comparison.json"
    if direct.exists():
        return [direct]
    return sorted(candidate.rglob("comparison.json"))


def evaluate_research_suites(
    runs_root: str | Path,
    strategy: str,
    benchmark: str = "equal_weight",
    primary_metric: str = "rank_ic_mean",
    max_drawdown: float = 0.25,
    min_forecast_groups: int = 3,
) -> dict[str, Any]:
    if primary_metric not in {"rank_ic_mean", "rank_ic_median", "net_excess_return"}:
        raise ValueError("primary_metric must be rank_ic_mean, rank_ic_median or net_excess_return")
    windows: list[dict[str, Any]] = []

    for comparison_path in _suite_files(runs_root):
        comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
        if strategy not in comparison or benchmark not in comparison:
            continue
        candidate = comparison[strategy]
        baseline = comparison[benchmark]
        reasons: list[str] = []
        if float(candidate.get("max_drawdown", 1.0)) > max_drawdown:
            reasons.append("max_drawdown")
        if int(candidate.get("agent_error_count", 0)) > 0:
            reasons.append("agent_errors")
        if primary_metric.startswith("rank_ic_") and int(candidate.get("forecast_group_count", 0)) < min_forecast_groups:
            reasons.append("insufficient_forecast_groups")

        net_excess_return = float(candidate.get("total_return", 0.0)) - float(baseline.get("total_return", 0.0))
        rank_ic_mean = float(candidate.get("rank_ic_mean", 0.0))
        rank_ic_median = float(candidate.get("rank_ic_median", 0.0))
        eligible = not reasons
        if primary_metric == "rank_ic_mean":
            primary_value = rank_ic_mean
        elif primary_metric == "rank_ic_median":
            primary_value = rank_ic_median
        else:
            primary_value = net_excess_return
        windows.append(
            {
                "suite": str(comparison_path.parent),
                "eligible": eligible,
                "failure_reasons": reasons,
                "primary_value": primary_value if eligible else FAIL_SCORE,
                "rank_ic_mean": rank_ic_mean,
                "rank_ic_median": rank_ic_median,
                "net_excess_return": net_excess_return,
                "forecast_brier_score": float(candidate.get("forecast_brier_score", 0.0)),
                "max_drawdown": float(candidate.get("max_drawdown", 0.0)),
                "agent_error_count": int(candidate.get("agent_error_count", 0)),
                "forecast_group_count": int(candidate.get("forecast_group_count", 0)),
            }
        )

    eligible = [window for window in windows if window["eligible"]]
    score = statistics.median(float(window["primary_value"]) for window in eligible) if eligible else FAIL_SCORE
    result = {
        "schema": "marketbench.autoresearch-evaluation.v1",
        "strategy": strategy,
        "benchmark": benchmark,
        "primary_metric": primary_metric,
        "score": score,
        "eligible_window_count": len(eligible),
        "total_window_count": len(windows),
        "gates": {
            "max_drawdown": max_drawdown,
            "min_forecast_groups": min_forecast_groups,
            "agent_errors_allowed": 0,
        },
        "median_net_excess_return": (
            statistics.median(float(window["net_excess_return"]) for window in eligible) if eligible else 0.0
        ),
        "median_rank_ic": statistics.median(float(window["rank_ic_mean"]) for window in eligible) if eligible else 0.0,
        "mean_brier_score": (
            statistics.fmean(float(window["forecast_brier_score"]) for window in eligible) if eligible else 0.0
        ),
        "windows": windows,
    }
    return result


def write_research_evaluation(result: dict[str, Any], output: str | Path) -> Path:
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination
