from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from .models import Trade


@dataclass(slots=True)
class ExecutionConfig:
    fee_bps: float = 1.0
    slippage_bps: float = 2.0


@dataclass(slots=True)
class Portfolio:
    initial_cash: float
    cash: float = field(init=False)
    positions: dict[str, float] = field(default_factory=dict)
    trades: list[Trade] = field(default_factory=list)
    fees_paid: float = 0.0
    traded_notional: float = 0.0
    normalized_turnover: float = 0.0

    def __post_init__(self) -> None:
        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        self.cash = float(self.initial_cash)

    def value(self, prices: Mapping[str, float]) -> float:
        return self.cash + sum(quantity * prices.get(symbol, 0.0) for symbol, quantity in self.positions.items())

    def weights(self, prices: Mapping[str, float]) -> dict[str, float]:
        total = self.value(prices)
        if total <= 0:
            return {}
        return {
            symbol: quantity * prices[symbol] / total
            for symbol, quantity in self.positions.items()
            if symbol in prices and abs(quantity) > 1e-12
        }

    def execute_targets(
        self,
        timestamp: datetime,
        open_prices: Mapping[str, float],
        target_weights: Mapping[str, float],
        config: ExecutionConfig,
    ) -> list[Trade]:
        portfolio_value = self.value(open_prices)
        if portfolio_value <= 0:
            return []
        deltas: dict[str, float] = {}
        symbols = set(self.positions) | set(target_weights)
        for symbol in symbols:
            price = open_prices.get(symbol)
            if not price or price <= 0:
                continue
            current_notional = self.positions.get(symbol, 0.0) * price
            target_notional = portfolio_value * max(0.0, float(target_weights.get(symbol, 0.0)))
            deltas[symbol] = target_notional - current_notional

        new_trades: list[Trade] = []
        for symbol, delta in sorted(deltas.items(), key=lambda item: item[1]):
            if delta >= -1e-8:
                continue
            market_price = open_prices[symbol]
            execution_price = market_price * (1.0 - config.slippage_bps / 10_000.0)
            held = self.positions.get(symbol, 0.0)
            quantity = min(held, -delta / market_price)
            if quantity <= 1e-12:
                continue
            notional = quantity * execution_price
            fee = notional * config.fee_bps / 10_000.0
            self.positions[symbol] = held - quantity
            if self.positions[symbol] <= 1e-12:
                self.positions.pop(symbol, None)
            self.cash += notional - fee
            trade = Trade(timestamp, symbol, "sell", quantity, execution_price, notional, fee, config.slippage_bps)
            self._record_trade(trade, portfolio_value)
            new_trades.append(trade)

        desired_buys = {symbol: delta for symbol, delta in deltas.items() if delta > 1e-8}
        total_required = sum(
            delta * (1.0 + config.slippage_bps / 10_000.0) * (1.0 + config.fee_bps / 10_000.0)
            for delta in desired_buys.values()
        )
        buy_scale = min(1.0, self.cash / total_required) if total_required > 0 else 0.0

        for symbol, delta in sorted(desired_buys.items()):
            market_price = open_prices[symbol]
            execution_price = market_price * (1.0 + config.slippage_bps / 10_000.0)
            target_notional = delta * buy_scale
            quantity = target_notional / market_price
            notional = quantity * execution_price
            fee = notional * config.fee_bps / 10_000.0
            required = notional + fee
            if required > self.cash:
                quantity *= self.cash / required
                notional = quantity * execution_price
                fee = notional * config.fee_bps / 10_000.0
                required = notional + fee
            if quantity <= 1e-12:
                continue
            self.cash -= required
            self.positions[symbol] = self.positions.get(symbol, 0.0) + quantity
            trade = Trade(timestamp, symbol, "buy", quantity, execution_price, notional, fee, config.slippage_bps)
            self._record_trade(trade, portfolio_value)
            new_trades.append(trade)

        return new_trades

    def _record_trade(self, trade: Trade, portfolio_value: float) -> None:
        self.trades.append(trade)
        self.fees_paid += trade.fee
        self.traded_notional += abs(trade.notional)
        if portfolio_value > 0:
            self.normalized_turnover += abs(trade.notional) / portfolio_value


@dataclass(slots=True)
class RiskConfig:
    long_only: bool = True
    max_position_weight: float = 0.35
    max_gross_exposure: float = 0.95
    min_cash_weight: float = 0.05
    max_turnover_per_decision: float = 0.65


@dataclass(slots=True)
class RiskResult:
    target_weights: dict[str, float]
    violations: list[str]


class RiskGate:
    def __init__(self, config: RiskConfig, allowed_symbols: set[str]):
        self.config = config
        self.allowed_symbols = allowed_symbols

    def sanitize(
        self,
        proposed: Mapping[str, float],
        current: Mapping[str, float],
    ) -> RiskResult:
        clean: dict[str, float] = {}
        violations: list[str] = []
        for symbol, raw_weight in proposed.items():
            if symbol not in self.allowed_symbols:
                violations.append(f"unknown_symbol:{symbol}")
                continue
            try:
                weight = float(raw_weight)
            except (TypeError, ValueError):
                violations.append(f"invalid_weight:{symbol}")
                continue
            if weight != weight or weight in (float("inf"), float("-inf")):
                violations.append(f"non_finite_weight:{symbol}")
                continue
            if self.config.long_only and weight < 0:
                violations.append(f"short_blocked:{symbol}")
                weight = 0.0
            if weight > self.config.max_position_weight:
                violations.append(f"position_clamped:{symbol}")
                weight = self.config.max_position_weight
            if weight > 1e-10:
                clean[symbol] = weight

        gross_limit = min(self.config.max_gross_exposure, 1.0 - self.config.min_cash_weight)
        gross = sum(abs(value) for value in clean.values())
        if gross > gross_limit and gross > 0:
            violations.append("gross_exposure_scaled")
            scale = gross_limit / gross
            clean = {symbol: value * scale for symbol, value in clean.items()}

        all_symbols = set(clean) | set(current)
        turnover = sum(abs(clean.get(symbol, 0.0) - current.get(symbol, 0.0)) for symbol in all_symbols)
        if turnover > self.config.max_turnover_per_decision and turnover > 0:
            violations.append("turnover_scaled")
            alpha = self.config.max_turnover_per_decision / turnover
            adjusted = {
                symbol: current.get(symbol, 0.0) + alpha * (clean.get(symbol, 0.0) - current.get(symbol, 0.0))
                for symbol in all_symbols
            }
            clean = {symbol: max(0.0, value) for symbol, value in adjusted.items() if value > 1e-10}

        return RiskResult(clean, violations)

