from __future__ import annotations

import csv
import json
import threading
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .models import Trade, iso_timestamp


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return iso_timestamp(value)
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"Cannot encode {type(value).__name__}")


class TrajectoryLogger:
    schema_version = "marketbench.trajectory.v1"

    def __init__(self, output_dir: str | Path, run_id: str):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.output_dir / "trajectory.jsonl"
        self.run_id = run_id
        self._lock = threading.Lock()
        self._sequence = 0

    def emit(self, kind: str, payload: dict[str, Any], timestamp: datetime | None = None) -> None:
        with self._lock:
            self._sequence += 1
            event = {
                "schema": self.schema_version,
                "run_id": self.run_id,
                "sequence": self._sequence,
                "kind": kind,
                "timestamp": iso_timestamp(timestamp) if timestamp else None,
                "payload": payload,
            }
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, default=_json_default, separators=(",", ":")) + "\n")

    def write_json(self, filename: str, payload: Any) -> Path:
        path = self.output_dir / filename
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, default=_json_default, indent=2, sort_keys=True)
            handle.write("\n")
        return path

    def write_equity(self, rows: Iterable[tuple[datetime, float]]) -> Path:
        path = self.output_dir / "equity.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(("timestamp", "equity"))
            for timestamp, equity in rows:
                writer.writerow((iso_timestamp(timestamp), f"{equity:.8f}"))
        return path

    def write_trades(self, trades: Iterable[Trade]) -> Path:
        path = self.output_dir / "trades.csv"
        fields = ("timestamp", "symbol", "side", "quantity", "price", "notional", "fee", "slippage_bps")
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for trade in trades:
                writer.writerow(trade.to_dict())
        return path

