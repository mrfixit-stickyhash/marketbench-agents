# Hyperliquid testnet boundary

MarketBench does not sign or submit orders. The included `TestnetIntentGateway` writes validated, unsigned intents to JSONL and rejects any URL that does not contain `testnet`.

For a later testnet adapter:

1. Run the exact trained strategy in shadow mode first.
2. Convert approved target weights into bounded order intents.
3. Send intents over a narrow local IPC channel to a separate signer.
4. Have the signer independently enforce an asset allowlist, maximum order notional, maximum leverage, maximum open exposure, daily loss limit, rate limit and kill switch.
5. Point the official SDK at `https://api.hyperliquid-testnet.xyz`.
6. Keep private keys out of configuration, logs, model prompts and model memory.
7. Require explicit human authorization before enabling any mainnet endpoint.

The model should never hold a seed phrase or signing key. A good model output is still only a proposal until deterministic controls approve it.

