# Objective research metrics

MarketBench reports portfolio performance and forecast intelligence separately. A strong backtest does not prove that the model ranked opportunities correctly, and a good ranking does not prove it can be converted into a safe portfolio.

## Forecast contract

At decision time, before any future bar is visible, a strategy may publish one forecast per asset:

| Field | Meaning |
| --- | --- |
| `score` | Relative opportunity score from -1 (most bearish) to +1 (most bullish) |
| `probability_outperform` | Probability that the asset beats the equal-weight universe over the declared horizon |
| `expected_return` | Predicted decimal return over the horizon |
| `horizon_bars` | Evaluation horizon |
| `expected_event_bars` | Expected bars until the target event or price realization |
| `target_price` | Optional declared price target |
| `invalidation_price` | Optional price that invalidates the thesis |

Forecasts execute conceptually from the next bar open, matching the paper portfolio's no-lookahead execution boundary.

## Opportunity understanding

- **Rank IC:** Spearman correlation between the agent's asset scores and realized returns. It tests whether the agent ordered the future winners above the losers.
- **Rank IC IR:** Mean Rank IC divided by its variability. It is diagnostic on short samples and is not treated as proof of alpha.
- **Brier score:** Mean squared error of `probability_outperform` against the realized outperform/not-outperform outcome. Lower is better.
- **Expected-return error:** Absolute difference between declared and realized return.
- **Target hit rate:** Fraction of declared targets touched during the horizon.
- **Target timing error:** Absolute difference between declared event timing and first target touch.
- **Time underwater:** Bars moving against the declared direction relative to the next-open entry.
- **Maximum adverse/favorable excursion:** Worst and best directional movement during the forecast horizon.
- **Opportunity capture:** Fraction of maximum favorable movement retained at the declared horizon, capped from 0 to 1.

## Portfolio conversion

- **Net return:** Paper-portfolio return after modeled fees and slippage.
- **Position ROI:** Episode cash proceeds minus cash cost, divided by cash cost. Positions still open at the end are marked at the final close.
- **Holding bars:** Bars from first buy to full close or final mark.
- **Position time underwater:** Bars whose close is below the episode's first entry price.
- **Position adverse/favorable excursion:** Worst and best price path relative to first entry.
- **Drawdown, turnover and violations:** Existing portfolio and deterministic risk-gate measurements.

## Interpreting the metrics

Do not optimize a large weighted composite. For autonomous research, select one primary measurement and enforce the rest as frozen eligibility gates. Recommended first pass:

1. Optimize median hidden-window Rank IC.
2. Require a maximum drawdown limit and zero agent errors.
3. Confirm positive median net excess return against a frozen benchmark.
4. Reserve a final test period that the research loop never observes.

Sixty days is enough to validate the pipeline or study a specific episode. It is not enough to claim a strategy generalizes.
