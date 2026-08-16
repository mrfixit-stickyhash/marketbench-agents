from __future__ import annotations

import json
import time
from typing import Any

from .models import Decision
from .providers import ProviderResult
from .strategies import MarketSnapshot, ProgramSpec, SafeProgramStrategy
from .trajectory import TrajectoryLogger


def parse_json_object(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        if candidate.startswith("json"):
            candidate = candidate[4:].lstrip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("Model did not return a JSON object")
        value = json.loads(candidate[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("Model response must be a JSON object")
    return value


class AgentBase:
    def __init__(self, provider: Any, logger: TrajectoryLogger, name: str):
        self.provider = provider
        self.logger = logger
        self.name = name

    def _call(self, role: str, system: str, payload: dict[str, Any], timestamp) -> dict[str, Any]:
        user = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        started = time.perf_counter()
        result: ProviderResult = self.provider.complete(system, user, json_mode=True)
        elapsed = time.perf_counter() - started
        self.logger.emit(
            "model_response",
            {
                "role": role,
                "model": result.model,
                "system": system,
                "user": user,
                "assistant": result.text,
                "usage": result.usage,
                "latency_seconds": elapsed,
            },
            timestamp,
        )
        return parse_json_object(result.text)


def _decision_from_mapping(value: dict[str, Any]) -> Decision:
    weights = value.get("target_weights", {})
    if not isinstance(weights, dict):
        raise ValueError("target_weights must be an object")
    return Decision(
        target_weights={str(symbol): float(weight) for symbol, weight in weights.items()},
        rationale=str(value.get("rationale", ""))[:1000],
        confidence=max(0.0, min(1.0, float(value.get("confidence", 0.5)))),
    )


class DirectAgentStrategy(AgentBase):
    name = "direct_agent"

    def __init__(self, provider: Any, logger: TrajectoryLogger):
        super().__init__(provider, logger, self.name)

    def decide(self, snapshot: MarketSnapshot) -> Decision:
        system = (
            "You are a portfolio strategist in a historical replay. Use only the supplied point-in-time data. "
            "Return JSON with target_weights, rationale, and confidence. Do not claim access to future data. "
            "Weights are portfolio fractions; omit an asset to allocate zero. Keep at least 5% cash."
        )
        value = self._call("strategist", system, snapshot.to_agent_payload(), snapshot.timestamp)
        return _decision_from_mapping(value)


class SwarmAgentStrategy(AgentBase):
    name = "agent_swarm"

    def __init__(self, provider: Any, logger: TrajectoryLogger):
        super().__init__(provider, logger, self.name)

    def decide(self, snapshot: MarketSnapshot) -> Decision:
        base = snapshot.to_agent_payload()
        research = self._call(
            "researcher",
            "You are the market researcher in an agent swarm. Use only supplied point-in-time data. Return JSON with regime, summary, and risks. Give a concise decision summary, not hidden reasoning.",
            base,
            snapshot.timestamp,
        )
        proposal = self._call(
            "strategist",
            "You are the portfolio strategist in an agent swarm. Return JSON with target_weights, rationale, and confidence. Keep at least 5% cash and never use information outside the payload.",
            {**base, "research": research},
            snapshot.timestamp,
        )
        reviewed = self._call(
            "risk_reviewer",
            "You are the risk reviewer in an agent swarm. Return JSON with approved target_weights, rationale, and confidence. Reduce concentration or exposure when necessary. A deterministic risk gate will enforce final limits.",
            {**base, "research": research, "proposal": proposal},
            snapshot.timestamp,
        )
        decision = _decision_from_mapping(reviewed)
        decision.metadata.update({"research": research, "original_proposal": proposal})
        return decision


class ProgramAuthorAgent(AgentBase):
    name = "program_author_agent"

    def __init__(self, provider: Any, logger: TrajectoryLogger):
        super().__init__(provider, logger, self.name)
        self.program: SafeProgramStrategy | None = None

    def decide(self, snapshot: MarketSnapshot) -> Decision:
        if self.program is None:
            system = (
                "You are a coding agent authoring a safe declarative trading program. Return JSON only with: "
                "signal (momentum, mean_reversion, volatility_adjusted_momentum, or equal_weight), lookback "
                "(2-60), top_k, max_weight (<=0.35), cash_buffer (>=0.05), and minimum_signal. "
                "Use only supplied point-in-time observations."
            )
            value = self._call("program_author", system, snapshot.to_agent_payload(), snapshot.timestamp)
            spec = ProgramSpec.from_mapping(value)
            self.program = SafeProgramStrategy(spec, name="authored_safe_program")
            self.logger.emit("program_compiled", {"program": spec.to_dict()}, snapshot.timestamp)
        return self.program.decide(snapshot)

