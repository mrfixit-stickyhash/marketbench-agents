# Project state

## Current release

Version 0.2.0 is a runnable local benchmark, not a live trading system.

Working:

- deterministic multi-asset replay and next-bar execution;
- point-in-time news availability;
- local/frontier OpenAI-compatible providers;
- direct, swarm and constrained program-author agents;
- deterministic portfolio risk gate;
- trajectory, trade, equity and report artifacts;
- forecast Rank IC, conviction, price-target, timing and excursion analytics;
- position ROI, holding duration and time-underwater analytics;
- multi-window AutoResearch evaluator;
- distillation export and optional QLoRA entry point.

External work still required:

- licensed historical price data;
- permissioned, anonymized Discord export and chronological rolling-memory adapter;
- production API/worker/viewer containers;
- real Qwen endpoint and fixed inference-budget experiments;
- multiple walk-forward regimes plus one untouched final test;
- any testnet execution beyond unsigned intents.

## Safe next milestone

Use daily data for a small fixed portfolio universe. Replay permissioned Discord/news context chronologically, compare price-only, news-only and community-context agents, and score all three under identical model/risk budgets.
