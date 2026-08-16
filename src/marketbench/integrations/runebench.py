from __future__ import annotations

import json
from pathlib import Path


def convert_runebench(input_path: str | Path, output_path: str | Path) -> int:
    """Normalize published RuneBench trajectory arrays into JSONL events."""
    source = Path(input_path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    model = str(payload.get("model", "unknown"))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", encoding="utf-8") as handle:
        for task_name, task in payload.get("skills", {}).items():
            if not isinstance(task, dict):
                continue
            reward = task.get("peakXpRate", task.get("finalXp", 0))
            for sequence, item in enumerate(task.get("trajectory", []), 1):
                event = {
                    "schema": "marketbench.external-trajectory.v1",
                    "environment": "runebench",
                    "model": model,
                    "task": task_name,
                    "sequence": sequence,
                    "source": item.get("source"),
                    "text": item.get("text", ""),
                    "elapsed_seconds": item.get("ts"),
                    "episode_reward": reward,
                }
                handle.write(json.dumps(event, separators=(",", ":")) + "\n")
                count += 1
    return count

