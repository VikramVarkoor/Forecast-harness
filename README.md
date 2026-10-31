# NYC ride-hail day-ahead demand forecast

> Status: harness built and tested on synthetic data. No real-data results yet.
> This README gets rewritten once the code has produced numbers. Findings go first.

## Findings and limits

_Not yet produced._

## Method

1. TLC HVFHV trips aggregated to hourly pickups per zone in DuckDB (`src/sql/hourly.sql`).
2. Rolling-origin backtest, expanding window, 24-hour horizon from a midnight origin.
3. Four baselines, then a statistical model, LightGBM, and a combination, all through the same harness.
4. MASE, MAE, RMSE and bias. Last 4 weeks held out and scored once.
5. Leak test recomputes features from raw history and is shown to fail on planted leaks.

## Reproduce

```
make setup
python src/download.py --probe
python src/download.py --from YYYY-MM --to YYYY-MM
python src/build_hourly.py --from YYYY-MM-01 --to YYYY-MM-01
make audit plots baselines test
```

## Data

NYC TLC High Volume For-Hire Vehicle trip records. TLC does not guarantee accuracy, the schema can change and files arrive about two months late. Attribution and licence notes to be completed after checking the TLC terms.
