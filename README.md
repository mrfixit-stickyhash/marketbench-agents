# MarketBench Agents

MarketBench is a runnable, point-in-time benchmark for local market agents, coding agents, and agent swarms. It replays historical or synthetic bars through a paper portfolio, gives each agent only information available at the current replay step, executes approved decisions on the **next** bar, records the complete trajectory, and produces a comparison report plus a conversational dataset for later distillation.

The project is intentionally safe by default:

- no brokerage or wallet is connected;
- model-generated actions pass through a deterministic risk gate;
- model-authored programs use a constrained strategy language instead of arbitrary Python;
- timestamps and symbols can be hidden to reduce historical-memory contamination;
- secrets are read from environment variables and never included in prompts;
- the included Hyperliquid boundary only exports unsigned testnet intents.

## What already works

- Deterministic multi-asset replay with next-bar execution
- Cash, equal-weight, momentum, and safe-program baselines
- Direct model agent, three-role swarm, and program-author agent
- Local Qwen through any OpenAI-compatible endpoint (vLLM, LM Studio, Ollama-compatible bridge)
- Generic frontier-model comparison through the same endpoint contract
- Fees, slippage, cash, positions, concentration, gross exposure, and turnover limits
- Point-in-time news using separate `published_at` and `available_at` timestamps
- Full observation/model/decision/fill/reward trajectory logging
- Versioned per-asset opportunity forecasts with declared horizon, target, invalidation and conviction
- Rank IC, conviction calibration, target accuracy, timing error and opportunity-capture evaluation
- Position-episode ROI, holding time, time-underwater and adverse/favorable excursion analytics
- Frozen AutoResearch evaluator across one or more hidden walk-forward suites
- HTML reports and machine-readable metrics
- RuneBench result conversion
- Distillation-ready JSONL export
- Optional QLoRA training entry point

## Fastest start — no GPU and no API key

From this folder:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -e .
marketbench demo
```

Git Bash:

```bash
source .venv/Scripts/activate
pip install -e .
marketbench demo
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -e .
marketbench demo
```

The command creates a timestamped directory under `runs/`. Open `comparison.html` to view the results. The offline scripted model exercises the exact same swarm, logging, risk, execution, and report path used by Qwen.

## Connect local Qwen

Start a Qwen model behind an OpenAI-compatible `/v1/chat/completions` endpoint. A vLLM compose template is included:

```bash
docker compose -f docker-compose.qwen.yml up
marketbench doctor --config configs/qwen-local.toml
marketbench run --config configs/qwen-local.toml
```

`Qwen/Qwen3.6-27B` at full precision requires substantially more memory than a single 24 GB consumer GPU. Set `QWEN_MODEL_ID` to a compatible quantized checkpoint when serving on smaller hardware, or point `MARKETBENCH_BASE_URL` at a rented GPU endpoint.

You can override the endpoint without editing the config:

```bash
export MARKETBENCH_BASE_URL=http://192.168.1.50:8000/v1
export MARKETBENCH_MODEL=Qwen/Qwen3.6-27B
export MARKETBENCH_API_KEY=
marketbench run --config configs/qwen-local.toml
```

To compare local Qwen and a frontier endpoint in the same replay, copy
`configs/model-matrix.example.toml`, fill in the frontier endpoint/model, set
the two API-key environment variables, and run that config. Baselines run once;
each agent mode runs once per named provider under identical market data.

## Use real data

MarketBench accepts long-form CSV files. Generate an exact example first:

```bash
marketbench generate-data --output data/example
```

Then copy `configs/real-csv.example.toml`, point it at your licensed dataset, and run it. See [docs/DATA_CONTRACT.md](docs/DATA_CONTRACT.md).

Do not use `yfinance` for twenty years of minute data: its intraday history is limited. The benchmark deliberately separates the replay engine from the data vendor so a licensed point-in-time source can be added without rewriting agent logic.

## Build a distillation dataset

After running teacher models:

```bash
marketbench export-sft --runs runs --output datasets/marketbench-sft.jsonl --min-score 0.0
```

The exporter selects logged model interactions from qualifying runs and writes conversational `messages` records with the run score and risk metrics attached. Inspect and filter this data before training.

Optional QLoRA training:

```bash
pip install -e ".[train]"
python training/train_qlora.py \
  --dataset datasets/marketbench-sft.jsonl \
  --model Qwen/Qwen3.6-27B \
  --output checkpoints/marketbench-qwen-lora
```

Training a 27B model requires a suitable CUDA GPU and careful memory settings. Start on a small checkpoint to validate the data pipeline.

## Import published RuneBench trajectories

```bash
marketbench import-runebench \
  --input codex53.json \
  --output datasets/runebench-codex53.jsonl
```

This normalizes the published RuneBench trajectory array but does not claim access to private live-server bot logs. See [docs/RUNEBENCH.md](docs/RUNEBENCH.md).

## Project boundaries

This MVP builds the complete experimental loop. It does not include copyrighted news archives, licensed twenty-year minute data, a production brokerage, or autonomous control of real funds. Those are external data and execution boundaries—not missing replay logic.

Before any live experiment, use Hyperliquid testnet, keep the signer outside the model process, enforce absolute notional/leverage/daily-loss limits, and require a human-controlled kill switch. See [docs/HYPERLIQUID.md](docs/HYPERLIQUID.md).

## Test

```bash
python -m unittest discover -s tests -v
```

## Main output files

Each strategy directory contains:

- `trajectory.jsonl` — observation, model, decision, risk and fill events
- `metrics.json` — risk-adjusted score and performance metrics
- `equity.csv` — timestamped paper-equity curve
- `trades.csv` — simulated fills
- `violations.json` — deterministic risk interventions
- `forecast-evaluations.json` — realized Rank IC, timing, target, calibration and excursion inputs
- `position-episodes.json` — completed and end-marked position episodes with ROI and holding analytics
- `report.html` — self-contained visual report

The suite root also contains `comparison.html`, `comparison.json`, and `manifest.json`.

## Objective research metrics

MarketBench now separates two questions that should not be collapsed into one score:

1. **Did the agent understand which opportunities were best?** Rank IC, Brier calibration, target error, target timing, adverse excursion and opportunity capture evaluate the declared forecasts.
2. **Could the agent turn that understanding into portfolio performance?** Net return, drawdown, per-position ROI, holding duration, time underwater, turnover, fees and violations evaluate execution.

Agent strategies can attach a forecast to every decision:

```json
{
  "forecasts": {
    "ASSET_001": {
      "score": 0.8,
      "probability_outperform": 0.72,
      "expected_return": 0.10,
      "horizon_bars": 10,
      "expected_event_bars": 7,
      "target_price": 115.0,
      "invalidation_price": 94.0
    }
  }
}
```

See [docs/METRICS.md](docs/METRICS.md) and [schemas/opportunity-forecast-v1.schema.json](schemas/opportunity-forecast-v1.schema.json).

## AutoResearch evaluation

Run the candidate through multiple timestamped suites, then reduce the hidden-window results to one reproducible scalar:

```bash
marketbench evaluate-research \
  --runs runs/research-windows \
  --strategy agent_swarm \
  --benchmark equal_weight \
  --primary-metric rank_ic_mean \
  --max-drawdown 0.25 \
  --output research-evaluation.json
```

The evaluator uses hard eligibility gates instead of hiding unacceptable drawdown or agent failures inside arbitrary score weights. The research agent must not be allowed to edit the evaluator, test windows, schemas or tests. See [docs/AUTORESEARCH.md](docs/AUTORESEARCH.md).
