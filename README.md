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
- `report.html` — self-contained visual report

The suite root also contains `comparison.html`, `comparison.json`, and `manifest.json`.
