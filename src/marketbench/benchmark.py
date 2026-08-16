from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agents import DirectAgentStrategy, ProgramAuthorAgent, SwarmAgentStrategy
from .data import MarketDataset
from .engine import BacktestEngine, EngineConfig
from .models import BacktestResult
from .portfolio import ExecutionConfig, RiskConfig, RiskGate
from .providers import build_provider
from .report import write_comparison_report, write_run_report
from .strategies import CashStrategy, EqualWeightStrategy, MomentumStrategy, ProgramSpec, SafeProgramStrategy, Strategy
from .trajectory import TrajectoryLogger


StrategyFactory = Callable[[TrajectoryLogger], Strategy]


def safe_name(value: str) -> str:
    result = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-")
    return result or "run"


def timestamped_output(root: str | Path, name: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    candidate = Path(root) / f"{safe_name(name)}-{stamp}"
    suffix = 1
    while candidate.exists():
        candidate = Path(root) / f"{safe_name(name)}-{stamp}-{suffix}"
        suffix += 1
    candidate.mkdir(parents=True)
    return candidate


def strategy_factories(names: list[str], provider_config: dict[str, Any]) -> dict[str, StrategyFactory]:
    provider = build_provider(provider_config)
    available: dict[str, StrategyFactory] = {
        "cash": lambda logger: CashStrategy(),
        "equal_weight": lambda logger: EqualWeightStrategy(),
        "momentum": lambda logger: MomentumStrategy(),
        "safe_program": lambda logger: SafeProgramStrategy(ProgramSpec()),
        "direct_agent": lambda logger: DirectAgentStrategy(provider, logger),
        "agent_swarm": lambda logger: SwarmAgentStrategy(provider, logger),
        "program_author_agent": lambda logger: ProgramAuthorAgent(provider, logger),
    }
    unknown = [name for name in names if name not in available]
    if unknown:
        raise ValueError(f"Unknown strategies: {unknown}. Available: {sorted(available)}")
    return {name: available[name] for name in names}


def model_matrix_factories(
    baseline_names: list[str],
    agent_names: list[str],
    providers: dict[str, dict[str, Any]],
) -> dict[str, StrategyFactory]:
    factories = strategy_factories(baseline_names, {"kind": "scripted"})
    for provider_name, provider_config in providers.items():
        provider_factories = strategy_factories(agent_names, provider_config)
        for agent_name, factory in provider_factories.items():
            factories[f"{agent_name}__{safe_name(provider_name)}"] = factory
    return factories


def run_suite(
    dataset: MarketDataset,
    factories: dict[str, StrategyFactory],
    output_dir: str | Path,
    engine_config: EngineConfig,
    execution_config: ExecutionConfig,
    risk_config: RiskConfig,
    manifest: dict[str, Any] | None = None,
) -> list[BacktestResult]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(json.dumps(manifest or {}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    results: list[BacktestResult] = []
    for requested_name, factory in factories.items():
        run_dir = root / safe_name(requested_name)
        logger = TrajectoryLogger(run_dir, requested_name)
        strategy = factory(logger)
        risk_gate = RiskGate(risk_config, set(dataset.symbols))
        engine = BacktestEngine(dataset, strategy, risk_gate, logger, engine_config, execution_config)
        result = engine.run()
        result.name = requested_name
        result.output_dir = str(run_dir)
        logger.write_json("metrics.json", result.metrics)
        logger.write_json("violations.json", result.violations)
        logger.write_equity(result.equity_curve)
        logger.write_trades(result.trades)
        write_run_report(result, run_dir / "report.html")
        results.append(result)
    write_comparison_report(results, root / "comparison.html")
    (root / "comparison.json").write_text(
        json.dumps({result.name: result.metrics for result in results}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return results


def export_sft_dataset(runs_root: str | Path, output_path: str | Path, min_score: float = float("-inf")) -> int:
    root = Path(runs_root)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with destination.open("w", encoding="utf-8") as output:
        for trajectory_path in sorted(root.rglob("trajectory.jsonl")):
            metrics_path = trajectory_path.parent / "metrics.json"
            if not metrics_path.exists():
                continue
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            score = float(metrics.get("score", 0.0))
            if score < min_score:
                continue
            for line in trajectory_path.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                if event.get("kind") != "model_response":
                    continue
                payload = event["payload"]
                record = {
                    "messages": [
                        {"role": "system", "content": payload["system"]},
                        {"role": "user", "content": payload["user"]},
                        {"role": "assistant", "content": payload["assistant"]},
                    ],
                    "metadata": {
                        "run_id": event.get("run_id"),
                        "role": payload.get("role"),
                        "teacher_model": payload.get("model"),
                        "run_score": score,
                        "total_return": metrics.get("total_return"),
                        "max_drawdown": metrics.get("max_drawdown"),
                    },
                }
                output.write(json.dumps(record, separators=(",", ":")) + "\n")
                count += 1
    return count
