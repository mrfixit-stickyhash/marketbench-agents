# Research objective

Improve the candidate agent's median hidden-window Rank IC while preserving portfolio safety and inference-budget parity.

## You may change

- Agent prompts and role coordination in `src/marketbench/agents.py`.
- Candidate-only declarative strategy configuration explicitly mounted by the controller.
- Point-in-time features that can be computed entirely from the supplied observation.

## You may not change

- Evaluation or metric implementations.
- Data, timestamps, hidden-window selection or benchmark results.
- Execution timing, fees, slippage or risk limits.
- Tests, schemas, Git history outside the candidate branch or this policy.
- Model-call/token/time budgets.

## Experiment discipline

Make one auditable hypothesis per candidate. Run the fixed experiment command supplied by the controller. Keep the candidate only if the frozen evaluator reports a higher score and every hard gate passes. Log failures as well as successes. Do not infer hidden labels from filenames, absolute dates or external network access.
