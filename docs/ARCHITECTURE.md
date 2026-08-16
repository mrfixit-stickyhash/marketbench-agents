# Architecture

## Event order

For timestamp `t`, MarketBench performs operations in this order:

1. Execute the previous decision using timestamp `t` opening prices.
2. Reveal timestamp `t` closing bars to the strategy.
3. Release news whose `available_at` is no later than `t`.
4. Mark the portfolio using timestamp `t` closing prices.
5. Ask the strategy or agent for target portfolio weights when a decision is due.
6. Pass the proposal through the deterministic risk gate.
7. Queue the approved weights for the next timestamp.

This prevents an agent from observing a bar close and receiving a fill at an earlier price from the same bar.

## Components

- `MarketDataset`: validated, UTC-normalized bars and news.
- `BacktestEngine`: deterministic market clock and point-in-time observation boundary.
- `Portfolio`: cash, positions, next-bar fills, fees and slippage.
- `RiskGate`: symbol allowlist, long-only enforcement, concentration, gross exposure, cash and turnover limits.
- `Strategy`: deterministic baseline or agent-facing policy.
- `Provider`: scripted offline model or OpenAI-compatible endpoint.
- `TrajectoryLogger`: append-only audit events.
- `BenchmarkSuite`: repeated identical episodes across strategies/models.
- `SFT exporter`: converts qualifying model calls into conversational training records.

## Agent modes

### Direct agent

One model call receives compact point-in-time features, current holdings, and newly available news. It returns target weights, confidence, and a concise rationale.

### Swarm

Three model roles operate sequentially:

1. Researcher classifies the observed regime and risks.
2. Strategist proposes portfolio weights.
3. Risk reviewer modifies the proposal.

The deterministic risk gate remains authoritative. An LLM risk reviewer can never bypass hard limits.

### Program author

The model authors a constrained declarative program selecting a signal, lookback, number of positions, cash buffer and concentration. The compiled program then processes bars without another model call at every timestamp. This mirrors RuneBench's coding-agent pattern while avoiding arbitrary host code execution.

## Historical contamination controls

- Set `anonymize_symbols = true` for real data.
- Keep `expose_timestamps = false` so the model receives a replay step rather than a historical calendar date.
- Never reveal future news or end-of-episode metadata.
- Hold out entire regimes and run live-forward episodes.
- Treat historical-news experiments as contaminated unless the model's training cutoff and memorization risk are controlled.

## Extension points

- Add a licensed dataset by converting it to the documented CSV contract or implementing another `MarketDataset` loader.
- Add a provider by implementing `complete(system, user, json_mode)`.
- Add a strategy by implementing `decide(snapshot)`.
- Add testnet execution after the risk gate, with signing in a separate process.

