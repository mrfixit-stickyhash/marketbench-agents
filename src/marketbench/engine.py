from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .data import MarketDataset
from .metrics import calculate_metrics
from .models import BacktestResult, Decision, iso_timestamp
from .portfolio import ExecutionConfig, Portfolio, RiskGate
from .strategies import MarketSnapshot, Strategy, build_features
from .trajectory import TrajectoryLogger


@dataclass(slots=True)
class EngineConfig:
    initial_cash: float = 100_000.0
    warmup_bars: int = 60
    decision_every: int = 5
    history_bars: int = 80
    bars_per_year: int = 252
    expose_timestamps: bool = False
    include_news_body: bool = False


class BacktestEngine:
    def __init__(
        self,
        dataset: MarketDataset,
        strategy: Strategy,
        risk_gate: RiskGate,
        logger: TrajectoryLogger,
        engine_config: EngineConfig,
        execution_config: ExecutionConfig,
    ):
        self.dataset = dataset
        self.strategy = strategy
        self.risk_gate = risk_gate
        self.logger = logger
        self.config = engine_config
        self.execution_config = execution_config

    def run(self) -> BacktestResult:
        if self.config.warmup_bars >= len(self.dataset.times) - 1:
            raise ValueError("warmup_bars must leave at least one decision and execution bar")
        portfolio = Portfolio(self.config.initial_cash)
        histories: dict[str, list[float]] = {symbol: [] for symbol in self.dataset.symbols}
        marks: dict[str, float] = {}
        pending: Decision | None = None
        equity_curve: list[tuple[datetime, float]] = []
        violations: list[str] = []
        last_decision_time: datetime | None = None
        agent_errors = 0
        decision_count = 0

        self.logger.emit(
            "run_started",
            {
                "strategy": self.strategy.name,
                "dataset": self.dataset.summary(),
                "engine": self.config,
                "execution": self.execution_config,
            },
        )

        for step, timestamp in enumerate(self.dataset.times):
            bars = self.dataset.bars_at(timestamp)
            open_marks = dict(marks)
            open_marks.update({symbol: bar.open for symbol, bar in bars.items()})

            if pending is not None:
                fills = portfolio.execute_targets(timestamp, open_marks, pending.target_weights, self.execution_config)
                for fill in fills:
                    self.logger.emit("fill", fill.to_dict(), timestamp)
                pending = None

            for symbol, bar in bars.items():
                histories.setdefault(symbol, []).append(bar.close)
                if len(histories[symbol]) > self.config.history_bars:
                    histories[symbol] = histories[symbol][-self.config.history_bars :]
                marks[symbol] = bar.close

            equity = portfolio.value(marks)
            equity_curve.append((timestamp, equity))

            decision_due = step >= self.config.warmup_bars and (step - self.config.warmup_bars) % self.config.decision_every == 0
            if not decision_due:
                continue
            decision_count += 1

            available_news = self.dataset.news_between(last_decision_time, timestamp)
            news_payload = []
            for item in available_news:
                rendered = item.to_dict(include_body=self.config.include_news_body)
                if not self.config.expose_timestamps:
                    rendered.pop("published_at", None)
                    rendered.pop("available_at", None)
                    rendered["available_step"] = f"step_{step:06d}"
                news_payload.append(rendered)
            features = build_features(histories)
            snapshot = MarketSnapshot(
                timestamp=timestamp,
                step=step,
                timestamp_label=iso_timestamp(timestamp) if self.config.expose_timestamps else f"step_{step:06d}",
                symbols=self.dataset.symbols,
                prices=dict(marks),
                features=features,
                portfolio_value=equity,
                cash=portfolio.cash,
                current_weights=portfolio.weights(marks),
                news=news_payload,
            )
            self.logger.emit("observation", snapshot.to_agent_payload(), timestamp)
            try:
                proposed = self.strategy.decide(snapshot)
            except Exception as exc:  # Agent/provider errors should be visible without corrupting the replay.
                agent_errors += 1
                self.logger.emit("agent_error", {"type": type(exc).__name__, "message": str(exc)}, timestamp)
                proposed = Decision(dict(snapshot.current_weights), "Agent error; preserve current holdings.", 0.0)

            risk = self.risk_gate.sanitize(proposed.target_weights, snapshot.current_weights)
            violations.extend(risk.violations)
            pending = Decision(risk.target_weights, proposed.rationale, proposed.confidence, proposed.metadata)
            self.logger.emit(
                "decision",
                {
                    "proposed": proposed.to_dict(),
                    "approved_target_weights": risk.target_weights,
                    "risk_violations": risk.violations,
                    "executes_no_earlier_than_step": step + 1,
                },
                timestamp,
            )
            last_decision_time = timestamp

        metrics = calculate_metrics(
            equity_curve,
            bars_per_year=self.config.bars_per_year,
            turnover=portfolio.normalized_turnover,
            fees_paid=portfolio.fees_paid,
            trade_count=len(portfolio.trades),
            violation_count=len(violations),
            decision_count=decision_count,
        )
        metrics["agent_error_count"] = agent_errors
        self.logger.emit("run_finished", {"metrics": metrics, "violations": violations})
        return BacktestResult(self.strategy.name, metrics, equity_curve, portfolio.trades, violations, str(self.logger.output_dir))
