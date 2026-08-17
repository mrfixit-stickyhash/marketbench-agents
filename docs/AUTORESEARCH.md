# AutoResearch boundary

MarketBench can supply the fixed experiment/evaluate/keep-or-revert loop used by an AutoResearch-style coding agent. The security and scientific boundary matters more than the loop itself.

## Frozen surface

The research agent must not modify:

- market data or chronological message/news inputs;
- `src/marketbench/research_metrics.py`;
- `src/marketbench/research_eval.py`;
- `src/marketbench/engine.py` no-lookahead and next-bar execution boundaries;
- `schemas/`;
- `tests/`;
- fees, slippage, risk limits, model-call budget or hidden window selection.

Enforce this with container filesystem permissions or an external controller. Instructions in Markdown alone are not a security boundary.

## Editable surface

A candidate research branch may modify a deliberately narrow surface, such as:

- agent prompts and role coordination in `src/marketbench/agents.py`;
- a candidate declarative program/configuration;
- feature construction that uses only point-in-time inputs;
- model endpoint choice when every candidate receives the same inference budget.

## Evaluation protocol

1. Run identical candidate and benchmark strategies through several walk-forward suites.
2. Keep hidden data mounted read-only outside the editable repository when possible.
3. Run `marketbench evaluate-research` to produce one scalar and a complete audit record.
4. Keep a candidate only when it improves the primary metric and passes every hard gate.
5. Count every attempted candidate. Repeatedly selecting the winner on the same windows overfits those windows.
6. Promote the final candidate once to a separate untouched test set.

Example:

```bash
marketbench evaluate-research \
  --runs /evaluation/hidden-window-runs \
  --strategy agent_swarm \
  --benchmark equal_weight \
  --primary-metric rank_ic_mean \
  --max-drawdown 0.25 \
  --min-forecast-groups 10 \
  --output research-evaluation.json
```

The command exits with code `3` if no window qualifies. Failed gates receive a sentinel score instead of a negotiable penalty.

## Discord and news replay

Messages must have a stable timestamp and an `available_at` boundary. Rolling summaries must be constructed forward in time from the previous summary plus newly available messages. Never summarize the full historical archive and inject that retrospective summary into earlier replay steps.
