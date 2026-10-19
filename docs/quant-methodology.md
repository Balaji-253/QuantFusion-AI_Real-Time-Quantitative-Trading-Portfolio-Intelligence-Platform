# Quant methodology notes

## Descriptive metrics

- Return is computed from the first and last observations in the selected window.
- Volatility is sample standard deviation of simple returns, in percent per observation.
- Maximum drawdown is the most negative peak-to-trough price return in the window.
- Metrics are not annualized and must not be interpreted as a calibrated risk estimate.

## Baseline momentum

Compares the latest five-observation mean to the latest twenty-observation mean. Thresholds create `BUY_BIAS`, `SELL_BIAS`, or `NEUTRAL`. It is a simple engineering baseline, not a validated alpha model.

## Research controls required

Use point-in-time universes, adjusted prices where appropriate, temporal train/validation/test splits, walk-forward validation, realistic fees and slippage, delisted assets when relevant, corporate-action handling, and robust statistical tests. Keep paper trading separate from live brokerage execution.
