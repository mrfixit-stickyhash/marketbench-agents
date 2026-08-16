from __future__ import annotations

import copy
import tomllib
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "run": {
        "name": "marketbench",
        "strategies": ["cash", "equal_weight", "momentum", "agent_swarm"],
        "output_root": "runs",
    },
    "data": {
        "kind": "synthetic",
        "bars": 420,
        "seed": 7,
        "symbols": ["ALPHA", "BETA", "GAMMA", "DELTA", "EPSILON", "ZETA"],
        "anonymize_symbols": False,
    },
    "engine": {
        "initial_cash": 100_000.0,
        "warmup_bars": 60,
        "decision_every": 5,
        "history_bars": 80,
        "bars_per_year": 252,
        "expose_timestamps": False,
        "include_news_body": False,
    },
    "execution": {"fee_bps": 1.0, "slippage_bps": 2.0},
    "risk": {
        "long_only": True,
        "max_position_weight": 0.35,
        "max_gross_exposure": 0.95,
        "min_cash_weight": 0.05,
        "max_turnover_per_decision": 0.65,
    },
    "provider": {
        "kind": "scripted",
        "base_url": "http://127.0.0.1:8000/v1",
        "model": "Qwen/Qwen3.6-27B",
        "api_key_env": "MARKETBENCH_API_KEY",
        "timeout_seconds": 120,
        "temperature": 0.1,
    },
}


def _deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).resolve()
    with config_path.open("rb") as handle:
        loaded = tomllib.load(handle)
    config = _deep_merge(DEFAULT_CONFIG, loaded)
    data = config["data"]
    for field in ("bars_path", "news_path"):
        if data.get(field):
            candidate = Path(str(data[field]))
            if not candidate.is_absolute():
                data[field] = str((config_path.parent / candidate).resolve())
    output_root = Path(str(config["run"].get("output_root", "runs")))
    if not output_root.is_absolute():
        config["run"]["output_root"] = str((config_path.parent.parent / output_root).resolve())
    config["_config_path"] = str(config_path)
    return config

