from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


class ProviderError(RuntimeError):
    pass


@dataclass(slots=True)
class ProviderResult:
    text: str
    model: str
    usage: dict[str, int | float] = field(default_factory=dict)


class OpenAICompatibleProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout_seconds: float = 120.0,
        temperature: float = 0.1,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature

    def complete(self, system: str, user: str, json_mode: bool = True) -> ProviderResult:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ProviderError(f"Model endpoint failed: {exc}") from exc
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"Unexpected model response: {payload}") from exc
        if isinstance(content, list):
            content = "".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in content)
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        return ProviderResult(str(content), str(payload.get("model", self.model)), usage)


class ScriptedProvider:
    """Offline model substitute that exercises the complete agent pipeline."""

    model = "scripted-market-agent-v1"

    def complete(self, system: str, user: str, json_mode: bool = True) -> ProviderResult:
        try:
            payload = json.loads(user)
        except json.JSONDecodeError:
            payload = {}
        system_lower = system.lower()
        market = payload.get("market", {})
        if "researcher" in system_lower:
            returns = [float(item.get("return_20", 0.0)) for item in market.values()]
            average = sum(returns) / len(returns) if returns else 0.0
            regime = "risk_on" if average > 0.01 else "risk_off" if average < -0.01 else "mixed"
            result = {"regime": regime, "summary": f"Average 20-period return is {average:.4f}.", "risks": []}
        elif "risk reviewer" in system_lower:
            proposal = payload.get("proposal", {})
            result = {
                "target_weights": proposal.get("target_weights", {}),
                "rationale": "Proposal passed to the deterministic risk gate.",
                "confidence": min(0.85, float(proposal.get("confidence", 0.6))),
            }
        elif "program author" in system_lower:
            result = {
                "signal": "volatility_adjusted_momentum",
                "lookback": 20,
                "top_k": 3,
                "max_weight": 0.30,
                "cash_buffer": 0.10,
                "minimum_signal": 0.0,
            }
        else:
            ranked = sorted(
                ((float(item.get("return_20", 0.0)), symbol) for symbol, item in market.items()),
                reverse=True,
            )
            selected = [symbol for score, symbol in ranked[:3] if score > 0]
            weight = 0.30 if selected else 0.0
            result = {
                "target_weights": {symbol: weight for symbol in selected},
                "rationale": "Selected assets with positive observed momentum.",
                "confidence": 0.72,
            }
        return ProviderResult(json.dumps(result), self.model, {"input_tokens": 0, "output_tokens": 0})


def build_provider(config: dict[str, Any]):
    kind = str(config.get("kind", "scripted"))
    if kind == "scripted":
        return ScriptedProvider()
    if kind != "openai_compatible":
        raise ValueError(f"Unknown provider kind: {kind}")
    base_url = os.getenv(str(config.get("base_url_env", "MARKETBENCH_BASE_URL")), str(config.get("base_url", "http://127.0.0.1:8000/v1")))
    model = os.getenv(str(config.get("model_env", "MARKETBENCH_MODEL")), str(config.get("model", "Qwen/Qwen3.6-27B")))
    api_key = os.getenv(str(config.get("api_key_env", "MARKETBENCH_API_KEY")), "")
    return OpenAICompatibleProvider(
        base_url=base_url,
        model=model,
        api_key=api_key,
        timeout_seconds=float(config.get("timeout_seconds", 120.0)),
        temperature=float(config.get("temperature", 0.1)),
    )

