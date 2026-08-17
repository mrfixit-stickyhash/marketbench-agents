from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

from .benchmark import export_sft_dataset, model_matrix_factories, run_suite, strategy_factories, timestamped_output
from .config import DEFAULT_CONFIG, load_config
from .data import MarketDataset
from .engine import EngineConfig
from .integrations.runebench import convert_runebench
from .portfolio import ExecutionConfig, RiskConfig
from .providers import build_provider
from .research_eval import evaluate_research_suites, write_research_evaluation
from .synthetic import generate_synthetic_dataset


def _dataset_from_config(config: dict[str, Any]) -> tuple[MarketDataset, dict[str, str]]:
    data = config["data"]
    if data.get("kind") == "synthetic":
        dataset = generate_synthetic_dataset(
            bars=int(data.get("bars", 420)),
            symbols=tuple(str(item) for item in data.get("symbols", DEFAULT_CONFIG["data"]["symbols"])),
            seed=int(data.get("seed", 7)),
        )
    elif data.get("kind") == "csv":
        if not data.get("bars_path"):
            raise ValueError("data.bars_path is required for CSV datasets")
        dataset = MarketDataset.from_csv(data["bars_path"], data.get("news_path"), data.get("name"))
    else:
        raise ValueError(f"Unknown data kind: {data.get('kind')}")
    if bool(data.get("anonymize_symbols", False)):
        return dataset.anonymized()
    return dataset, {}


def _print_results(results) -> None:
    print("\nMarketBench results")
    print(
        f"{'strategy':24} {'score':>9} {'return':>9} {'sharpe':>9} "
        f"{'rank IC':>9} {'brier':>9} {'drawdown':>9}"
    )
    for result in sorted(results, key=lambda item: float(item.metrics["score"]), reverse=True):
        has_forecasts = int(result.metrics.get("forecast_count", 0)) > 0
        rank_ic = f"{float(result.metrics.get('rank_ic_mean', 0.0)):.3f}" if has_forecasts else "n/a"
        brier = f"{float(result.metrics.get('forecast_brier_score', 0.0)):.3f}" if has_forecasts else "n/a"
        print(
            f"{result.name:24} {float(result.metrics['score']):9.3f} "
            f"{float(result.metrics['total_return']):9.2%} {float(result.metrics['sharpe']):9.3f} "
            f"{rank_ic:>9} {brier:>9} {float(result.metrics['max_drawdown']):9.2%}"
        )


def command_demo(args: argparse.Namespace) -> int:
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["run"]["strategies"] = [
        "cash",
        "equal_weight",
        "momentum",
        "safe_program",
        "direct_agent",
        "agent_swarm",
        "program_author_agent",
    ]
    dataset, symbol_mapping = _dataset_from_config(config)
    root = timestamped_output(args.output, "offline-demo")
    factories = strategy_factories(config["run"]["strategies"], config["provider"])
    results = run_suite(
        dataset,
        factories,
        root,
        EngineConfig(**config["engine"]),
        ExecutionConfig(**config["execution"]),
        RiskConfig(**config["risk"]),
        manifest={"mode": "offline_demo", "dataset": dataset.summary(), "symbol_mapping": symbol_mapping},
    )
    _print_results(results)
    print(f"\nReport: {root / 'comparison.html'}")
    return 0


def command_run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if args.strategy:
        config["run"]["strategies"] = args.strategy
    dataset, symbol_mapping = _dataset_from_config(config)
    root = timestamped_output(args.output or config["run"]["output_root"], config["run"]["name"])
    if config.get("providers"):
        matrix = config.get("matrix", {})
        baseline_names = list(matrix.get("baselines", ["cash", "equal_weight", "momentum"]))
        agent_names = list(matrix.get("agent_strategies", ["direct_agent", "agent_swarm", "program_author_agent"]))
        factories = model_matrix_factories(baseline_names, agent_names, config["providers"])
    else:
        factories = strategy_factories(list(config["run"]["strategies"]), config["provider"])
    public_config = copy.deepcopy(config)
    public_config.pop("_config_path", None)
    if public_config.get("provider", {}).get("api_key"):
        public_config["provider"]["api_key"] = "<redacted>"
    results = run_suite(
        dataset,
        factories,
        root,
        EngineConfig(**config["engine"]),
        ExecutionConfig(**config["execution"]),
        RiskConfig(**config["risk"]),
        manifest={"config": public_config, "dataset": dataset.summary(), "symbol_mapping": symbol_mapping},
    )
    _print_results(results)
    print(f"\nReport: {root / 'comparison.html'}")
    return 0


def command_generate_data(args: argparse.Namespace) -> int:
    symbols = tuple(part.strip().upper() for part in args.symbols.split(",") if part.strip())
    dataset = generate_synthetic_dataset(args.bars, symbols, args.seed)
    bars_path, news_path = dataset.write_csv(args.output)
    print(json.dumps({"bars": str(bars_path), "news": str(news_path), "summary": dataset.summary()}, indent=2))
    return 0


def command_import_runebench(args: argparse.Namespace) -> int:
    count = convert_runebench(args.input, args.output)
    print(f"Converted {count} RuneBench trajectory events to {args.output}")
    return 0


def command_export_sft(args: argparse.Namespace) -> int:
    count = export_sft_dataset(args.runs, args.output, args.min_score)
    print(f"Exported {count} model interactions to {args.output}")
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    provider = build_provider(config["provider"])
    result = provider.complete(
        "Return a JSON object containing status and model_role.",
        json.dumps({"request": "MarketBench endpoint health check"}),
        json_mode=True,
    )
    print(json.dumps({"model": result.model, "usage": result.usage, "response": result.text}, indent=2))
    return 0


def command_evaluate_research(args: argparse.Namespace) -> int:
    result = evaluate_research_suites(
        runs_root=args.runs,
        strategy=args.strategy,
        benchmark=args.benchmark,
        primary_metric=args.primary_metric,
        max_drawdown=args.max_drawdown,
        min_forecast_groups=args.min_forecast_groups,
    )
    if args.output:
        write_research_evaluation(result, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if int(result["eligible_window_count"]) > 0 else 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="marketbench", description="Deterministic market benchmark for coding agents")
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("demo", help="Run the complete offline benchmark with a scripted agent swarm")
    demo.add_argument("--output", default="runs", help="Parent directory for the timestamped run")
    demo.set_defaults(func=command_demo)

    run = subparsers.add_parser("run", help="Run a TOML-configured benchmark")
    run.add_argument("--config", required=True)
    run.add_argument("--output", help="Override the configured output root")
    run.add_argument("--strategy", action="append", help="Strategy to run; repeat for several")
    run.set_defaults(func=command_run)

    generate = subparsers.add_parser("generate-data", help="Create a synthetic multi-regime CSV dataset")
    generate.add_argument("--output", default="data/synthetic")
    generate.add_argument("--bars", type=int, default=420)
    generate.add_argument("--seed", type=int, default=7)
    generate.add_argument("--symbols", default="ALPHA,BETA,GAMMA,DELTA,EPSILON,ZETA")
    generate.set_defaults(func=command_generate_data)

    importer = subparsers.add_parser("import-runebench", help="Normalize a published RuneBench result JSON")
    importer.add_argument("--input", required=True)
    importer.add_argument("--output", required=True)
    importer.set_defaults(func=command_import_runebench)

    exporter = subparsers.add_parser("export-sft", help="Create a conversational SFT dataset from benchmark trajectories")
    exporter.add_argument("--runs", required=True)
    exporter.add_argument("--output", required=True)
    exporter.add_argument("--min-score", type=float, default=float("-inf"))
    exporter.set_defaults(func=command_export_sft)

    doctor = subparsers.add_parser("doctor", help="Check a configured model endpoint")
    doctor.add_argument("--config", required=True)
    doctor.set_defaults(func=command_doctor)

    evaluator = subparsers.add_parser(
        "evaluate-research",
        help="Produce one frozen AutoResearch score across completed hidden-window suites",
    )
    evaluator.add_argument("--runs", required=True, help="Suite directory or parent containing several suites")
    evaluator.add_argument("--strategy", required=True, help="Candidate strategy name in comparison.json")
    evaluator.add_argument("--benchmark", default="equal_weight", help="Frozen benchmark strategy name")
    evaluator.add_argument(
        "--primary-metric",
        choices=("rank_ic_mean", "rank_ic_median", "net_excess_return"),
        default="rank_ic_mean",
    )
    evaluator.add_argument("--max-drawdown", type=float, default=0.25)
    evaluator.add_argument("--min-forecast-groups", type=int, default=3)
    evaluator.add_argument("--output", help="Optional JSON output path")
    evaluator.set_defaults(func=command_evaluate_research)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        raise SystemExit(args.func(args))
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
