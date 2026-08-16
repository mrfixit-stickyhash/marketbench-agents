# RuneBench bridge

RuneBench is useful as Phase 0 because coding agents write and execute programs against an MMO environment. MarketBench applies the same pattern to market replay.

Recommended sequence:

1. Clone and run the open-source RS-SDK and RuneBench projects separately.
2. Serve the local model through the same OpenAI-compatible endpoint used by MarketBench.
3. Run one local-model episode and one frontier-model episode under identical tasks.
4. Preserve the original RuneBench result JSON.
5. Normalize public trajectory arrays using `marketbench import-runebench`.
6. Compare failure recovery, tool selection, program quality, latency, token use and score.

The converter handles the public result shape containing `model`, `skills`, per-task scores and `trajectory` arrays. It does not retrieve private live-server controller logs.

Market and RuneBench trajectories should remain labeled by environment. Do not combine them blindly: RuneBench tool-use records teach general agentic coding behavior, while MarketBench records teach the market-specific observation and action contract.

