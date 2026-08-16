from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TestnetOrderIntent:
    symbol: str
    side: str
    quantity: float
    order_type: str = "market"
    reduce_only: bool = False


class TestnetIntentGateway:
    """A non-signing safety boundary for later Hyperliquid testnet execution."""

    def __init__(self, output_path: str | Path, api_url: str = "https://api.hyperliquid-testnet.xyz"):
        if "testnet" not in api_url:
            raise ValueError("MarketBench refuses non-testnet URLs in this adapter")
        self.output_path = Path(output_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.api_url = api_url

    def submit(self, intent: TestnetOrderIntent) -> None:
        if intent.side not in {"buy", "sell"} or intent.quantity <= 0:
            raise ValueError("Invalid testnet order intent")
        record = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "api_url": self.api_url,
            "intent": asdict(intent),
            "status": "awaiting_external_testnet_signer",
        }
        with self.output_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")

