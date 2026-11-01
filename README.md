# NYC ride-hail day-ahead demand forecast

Hourly pickups per taxi zone for the next 24 hours, forecast at midnight, scored by one rolling-origin harness.
Data: NYC TLC High Volume For-Hire Vehicle trips, 30 zones (20 busiest, 5 mid, 5 quiet, chosen on development data only).
Every number below is written by `python -m src.make_readme` from files in `results/`.

## Findings

- **Held-out, 4 weeks scored once:** LightGBM MAE 31.38 against 36.37 for the best baseline (mean of same hour, last 4 weeks), 13.7% lower. MASE 0.843 against 0.954. Paired daily gain 4.99 trips per zone-hour (95% interval 3.53 to 6.56), better on 93% of 28 days.
- **Development, rolling backtest:** LightGBM MAE 34.43 against 38.39 for the best baseline (mean of same hour, last 4 weeks), 10.3% lower. MASE 0.784 against 0.853. Paired daily gain 3.96 trips per zone-hour (95% interval 2.10 to 6.49), better on 70% of 281 days.
- Exponential smoothing ranks 5 of 7 on held-out MASE (1.234), behind the 4-week mean (0.954). It did not earn its place.
- Averaging LightGBM with the best baseline gave MAE 33.18 against 31.38 for LightGBM alone, so the combination did not help.
- Ablation (pre-registered in DECISIONS D18): dropping the two short-lag features moved development MASE from 0.784 to 0.860.
- The 10% to 90% interval covered 82% of held-out hours after rounding edges outward to whole trips (raw 75%). In quiet zones the raw interval covers 59% because counts are integers, so rounded coverage there (96%) mostly reflects zero-heavy hours.
- Held-out bias (forecast minus actual, trips per zone-hour) was negative for 5 of 7 models; LightGBM -8.0. Demand ran above what the history implied; the cause was not investigated.

Held-out result table (lower is better; MASE under 1 beats the seasonal naive of lag 168):

| model | MAE | RMSE | bias | MASE |
|---|---|---|---|---|
| LightGBM | 31.380 | 57.358 | -8.009 | 0.843 |
| LightGBM + mean same hour 4w | 33.177 | 60.378 | -10.797 | 0.882 |
| Mean of same hour, last 4 weeks | 36.374 | 66.198 | -13.586 | 0.954 |
| Same hour last week | 39.478 | 74.794 | -5.416 | 1.044 |
| Exponential smoothing (weekly) | 48.900 | 81.936 | 3.316 | 1.234 |
| Same hour yesterday | 58.976 | 116.941 | -0.680 | 1.489 |
| Last hour held flat | 140.794 | 227.134 | 76.792 | 3.269 |

Held-out MAE by zone tier:

| tier | baseline MAE | LightGBM MAE |
|---|---|---|
| top | 51.25 | 43.96 |
| mid | 12.07 | 11.33 |
| quiet | 1.18 | 1.12 |

Development result table (rolling backtest on every day before the held-out weeks):

| model | MAE | RMSE | bias | MASE |
|---|---|---|---|---|
| LightGBM | 34.433 | 67.303 | 1.311 | 0.784 |
| LightGBM + mean same hour 4w | 35.208 | 68.475 | 1.231 | 0.795 |
| Mean of same hour, last 4 weeks | 38.395 | 74.898 | 1.152 | 0.853 |
| Same hour last week | 44.809 | 89.475 | 0.220 | 0.999 |
| Exponential smoothing (weekly) | 50.324 | 89.522 | 1.685 | 1.067 |
| Same hour yesterday | 60.466 | 118.082 | -0.020 | 1.300 |
| Last hour held flat | 140.590 | 225.134 | 77.955 | 2.740 |

## Limits

- The held-out set is 28 days in one month. The paired interval uses only 4 weekly blocks, so treat it as crude.
- The held-out weeks were scored 1 time(s) (`results/heldout_run.json`). Nothing was tuned on them.
- Only 30 zones are modelled. Results say nothing about the other zones.
- The data covers one year, so each holiday appears once. Holiday handling is a flag, not a learned effect.
- Shock days dominate the error. The ten worst development days:

| date | weekday | model_abs_err | forecast_minus_actual | cause |
|---|---|---|---|---|
| 2026-01-25 | Sunday | 106657 | 104150 | Major winter storm; city digging out on this Sunday (snowfall total not read from the source) ([source](https://abc7ny.com/live-updates/winter-storm-weekend-nyc-area-northeast-prepare-potential-snow-extreme-cold/18443469/entry/18471362/)) |
| 2026-02-23 | Monday | 98738 | 98676 | Blizzard; citywide travel ban 9 pm Sunday to noon Monday; about 15 inches in Central Park by 7 am ([source](https://www.claimsjournal.com/news/national/2026/02/23/335841.htm)) |
| 2026-01-01 | Thursday | 87647 | -38967 | holiday: New Year's Day |
| 2025-11-27 | Thursday | 74743 | 37389 | holiday: Thanksgiving Day |
| 2025-11-28 | Friday | 58154 | 46377 | day after Thanksgiving Day |
| 2026-02-08 | Sunday | 55894 | -45512 | unexplained: check weather and events (not verified) |
| 2025-11-29 | Saturday | 55310 | 34337 | unexplained: check weather and events (not verified) |
| 2026-02-22 | Sunday | 55235 | 27275 | Evening of the citywide travel ban that began 9 pm this Sunday (blizzard) ([source](https://www.claimsjournal.com/news/national/2026/02/23/335841.htm)) |
| 2026-01-10 | Saturday | 55068 | -42788 | unexplained: check weather and events (not verified) |
| 2026-02-24 | Tuesday | 52059 | -34662 | unexplained: check weather and events (not verified) |

  Causes are stated only where a source was read. "Not verified" means the calendar label is a guess and no cause was checked.
- Timestamps are local wall time. The two daylight saving days contain a missing and a repeated hour, so they are data artifacts.
- No weather feature is used. Storms are not anticipated by the model.
- TLC says it did not create the trip data and cannot guarantee its accuracy.

## Method

1. TLC HVFHV trips aggregated to hourly pickups per zone in DuckDB (`src/sql/hourly.sql`), complete (hour, zone) grid.
2. Rolling-origin backtest, expanding window, daily midnight origins, 24-hour horizon. Forecasters only see rows before the origin.
3. Four baselines, exponential smoothing, one global Poisson LightGBM (lag 24, lag 168, rolling means, hour, weekday, holiday, zone), an average of LightGBM and the best baseline, and 10%/90% quantile LightGBM.
4. MAE, RMSE, bias and MASE (scaled by lag-168 seasonal naive). No MAPE.
5. The leak test recomputes features from raw history and is shown to fail on three planted leaks (`tests/test_leakage.py`).
6. Decisions were written before code: see `DECISIONS.md`.

## Reproduce

```
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
python -m src.download --from YYYY-MM --to YYYY-MM
python -m src.build_hourly
python -m pytest -q
python -m src.run_models && python -m src.analyze && python -m src.ablation
python -m src.final_eval        # once
python -m src.make_readme
streamlit run app/app.py
```

## Data and credit

NYC Taxi and Limousine Commission, TLC Trip Record Data (HVFHV). Zone names from the TLC Taxi Zone Lookup Table (`app/taxi_zone_lookup.csv`). Holidays from the `holidays` package. The TLC terms of use were not
verified in this project; check them before redistributing derived data. Raw data is not in this repository.

Built with AI assistance (Claude) for code and drafting; the decisions log, runs and checks are mine to explain.
