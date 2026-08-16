# Point-in-time data contract

All timestamps must include a timezone. MarketBench normalizes them to UTC.

## Bars

Long-form `bars.csv` columns:

| Column | Meaning |
| --- | --- |
| `timestamp` | Bar close/event timestamp in ISO 8601 with timezone |
| `symbol` | Point-in-time symbol identifier |
| `open` | Positive opening price |
| `high` | High price |
| `low` | Low price |
| `close` | Positive closing price |
| `volume` | Non-negative volume |

There must be no duplicate `(timestamp, symbol)` pair.

## News and events

`news.csv` columns:

| Column | Meaning |
| --- | --- |
| `event_id` | Stable identifier |
| `published_at` | Publisher timestamp |
| `available_at` | Earliest timestamp the simulated agent could consume it |
| `source` | Source/provider |
| `headline` | Headline or event title |
| `body` | Optional licensed body text |
| `symbols` | Pipe-separated symbols, such as `AAPL|MSFT` |

`available_at` must not precede `published_at`. The replay boundary uses `available_at`.

## Real-equity requirements

A credible twenty-year equity benchmark also needs point-in-time index membership, delisted securities, corporate actions, symbol changes and exchange calendars. A file containing only today's S&P 500 members creates survivorship bias.

SPX itself is not directly tradable. Start with SPY/QQQ/sector ETFs, or model futures contracts and rolls explicitly.

## Resolution

The engine is resolution-independent. Set `bars_per_year` correctly for annualized metrics:

- daily US equities: approximately `252`
- hourly US equities: approximately `1638`
- five-minute regular-hours US equities: approximately `19656`
- one-minute regular-hours US equities: approximately `98280`

