from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

from .models import BacktestResult


def _format_metric(name: str, value: float | int | str) -> str:
    if isinstance(value, float):
        if name in {"total_return", "annualized_return", "annualized_volatility", "max_drawdown"}:
            return f"{value:.2%}"
        if name in {"initial_equity", "final_equity", "fees_paid"}:
            return f"${value:,.2f}"
        return f"{value:.4f}"
    return str(value)


def _polyline(curve: list[tuple[datetime, float]], width: int = 900, height: int = 280) -> str:
    if not curve:
        return ""
    values = [value / curve[0][1] * 100.0 for _, value in curve]
    low, high = min(values), max(values)
    span = max(high - low, 1e-9)
    points = []
    for index, value in enumerate(values):
        x = 20 + index / max(1, len(values) - 1) * (width - 40)
        y = 15 + (high - value) / span * (height - 35)
        points.append(f"{x:.2f},{y:.2f}")
    return " ".join(points)


def write_run_report(result: BacktestResult, path: str | Path) -> Path:
    destination = Path(path)
    rows = "".join(
        f"<tr><th>{html.escape(key.replace('_', ' ').title())}</th><td>{html.escape(_format_metric(key, value))}</td></tr>"
        for key, value in result.metrics.items()
    )
    svg = _polyline(result.equity_curve)
    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MarketBench — {html.escape(result.name)}</title>
<style>body{{font:15px system-ui;background:#0b1020;color:#e8eefc;margin:0;padding:32px}}main{{max-width:1000px;margin:auto}}.card{{background:#151d33;border:1px solid #2a3658;border-radius:14px;padding:22px;margin:18px 0}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;padding:9px;border-bottom:1px solid #2a3658}}th{{color:#9fb1d9}}svg{{width:100%;height:auto;background:#0e162a;border-radius:10px}}.muted{{color:#9fb1d9}}</style>
</head><body><main><h1>MarketBench: {html.escape(result.name)}</h1><p class="muted">Deterministic replay report. Orders execute no earlier than the bar after each decision.</p>
<section class="card"><h2>Normalized equity</h2><svg viewBox="0 0 900 280" role="img" aria-label="Normalized equity curve"><polyline points="{svg}" fill="none" stroke="#6ee7b7" stroke-width="3"/></svg></section>
<section class="card"><h2>Metrics</h2><table>{rows}</table></section>
<section class="card"><h2>Audit</h2><p>{len(result.trades)} fills · {len(result.violations)} risk-gate interventions</p></section>
</main></body></html>"""
    destination.write_text(body, encoding="utf-8")
    return destination


def write_comparison_report(results: list[BacktestResult], path: str | Path) -> Path:
    destination = Path(path)
    metric_names = ("score", "total_return", "sharpe", "max_drawdown", "turnover", "fees_paid", "trade_count", "violation_count")
    header = "".join(f"<th>{name.replace('_', ' ').title()}</th>" for name in metric_names)
    rows = ""
    for result in sorted(results, key=lambda item: float(item.metrics.get("score", 0.0)), reverse=True):
        cells = "".join(f"<td>{html.escape(_format_metric(name, result.metrics.get(name, 0)))}</td>" for name in metric_names)
        rows += f"<tr><th>{html.escape(result.name)}</th>{cells}</tr>"
    body = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MarketBench comparison</title>
<style>body{{font:15px system-ui;background:#0b1020;color:#e8eefc;padding:32px}}main{{max-width:1200px;margin:auto}}table{{border-collapse:collapse;width:100%;background:#151d33}}th,td{{padding:10px;border:1px solid #2a3658;text-align:right}}th:first-child{{text-align:left}}thead th{{color:#9fb1d9}}</style></head>
<body><main><h1>MarketBench comparison</h1><p>Higher score is better. Score combines Sharpe, drawdown, turnover and risk violations.</p><table><thead><tr><th>Strategy</th>{header}</tr></thead><tbody>{rows}</tbody></table></main></body></html>"""
    destination.write_text(body, encoding="utf-8")
    return destination

