# Day-ahead forecasting, two domains

Two forecasting projects built with the same discipline: forecasts made from the night before, a held-out period scored once, simple baselines beside every model, and results reported whatever they came out as. Decisions were written before code (`DECISIONS*.md`).

## A. NYC ride-hail day-ahead demand forecast

Hourly pickups per taxi zone for the next 24 hours, forecast at midnight, scored by one rolling-origin harness.
Data: NYC TLC High Volume For-Hire Vehicle trips, 30 zones (20 busiest, 5 mid, 5 quiet, chosen on development data only).
Every number below is written by `python -m src.make_readme` from files in `results/`.

### Findings

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

### Limits

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

### Method

1. TLC HVFHV trips aggregated to hourly pickups per zone in DuckDB (`src/sql/hourly.sql`), complete (hour, zone) grid.
2. Rolling-origin backtest, expanding window, daily midnight origins, 24-hour horizon. Forecasters only see rows before the origin.
3. Four baselines, exponential smoothing, one global Poisson LightGBM (lag 24, lag 168, rolling means, hour, weekday, holiday, zone), an average of LightGBM and the best baseline, and 10%/90% quantile LightGBM.
4. MAE, RMSE, bias and MASE (scaled by lag-168 seasonal naive). No MAPE.
5. The leak test recomputes features from raw history and is shown to fail on three planted leaks (`tests/test_leakage.py`).
6. Decisions were written before code: see `DECISIONS.md`.

### Reproduce

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

### Data and credit

NYC Taxi and Limousine Commission, TLC Trip Record Data (HVFHV). Zone names from the TLC Taxi Zone Lookup Table (`app/taxi_zone_lookup.csv`). Holidays from the `holidays` package. The TLC terms of use were not
verified in this project; check them before redistributing derived data. Raw data is not in this repository.

## B. European electricity day-ahead load forecast

Hourly national load for 10 countries, forecast at midnight for the next 24 hours, scored by the same rolling-origin harness idea as Domain A.
Every number in this section is computed from `results/elec_*` files by `src/make_site_elec.py`.

### Findings

- The model beat the simple guess on 27 of 28 days.
- Grid operators publish a day-ahead demand forecast that traders and plant schedulers lean on. I built the same kind of forecast for 10 European countries and tested it honestly. I hid the last 28 days, then made the model forecast each one from the night before. It was off by about 423 MW per country per hour. A simple guess was off by 759. That is 44% fewer misses overall, and a lower percentage error in every one of the 10 countries.
- I also compared it with the grid operators' own forecast, which was off by 468 MW. In megawatts the difference is small and the 95% range runs from -20 to +94 MW a day, so I cannot say the model is ahead. In percent the model was 0.45 points better, with a 95% range of 0.11 to 0.74.
- The operators beat the model in Italy, Spain, Finland, and the model beat them in Germany, France, Poland, Belgium. In Netherlands, Switzerland, Austria the operator forecast is more than 4% away from measured load every year, so those comparisons are not fair. The operators use weather forecasts and my model does not, so weather is the first thing I would add. I did test that on a separate window (see Weather test below).
- 75% of actual hours fell inside the 10% to 90% range. It should be about 80%. The range is a little too narrow, so treat it as optimistic.

Held-out (28 days, scored once; lower is better):

| model | MAE MW | MAPE % | MASE |
|---|---|---|---|
| LightGBM (mine) | 422.6 | 2.29 | 0.616 |
| repeat the same hour from a week earlier (simple guess) | 759.2 | 3.73 | 0.984 |
| Operator day-ahead forecast (not like for like) | 468.0 | 2.74 | 0.744 |

By country (MAPE):

| country | mean load MW | model MAPE % | simple guess MAPE % | operator MAPE % | operator series flagged |
|---|---|---|---|---|---|
| Germany | 52372 | 1.59 | 2.27 | 2.05 |  |
| France | 44303 | 1.60 | 2.84 | 1.62 |  |
| Italy | 33516 | 2.09 | 5.09 | 1.88 |  |
| Spain | 27044 | 1.64 | 4.03 | 0.88 |  |
| Poland | 18590 | 1.41 | 2.09 | 2.20 |  |
| Netherlands | 12678 | 5.16 | 7.67 | 5.89 | yes |
| Belgium | 9001 | 2.18 | 2.63 | 2.29 |  |
| Finland | 8057 | 1.78 | 2.86 | 1.55 |  |
| Switzerland | 6475 | 4.19 | 5.96 | 7.01 | yes |
| Austria | 6396 | 1.28 | 1.85 | 2.05 | yes |

### Weather test

Separate window, 3 Nov 2018 to 30 Nov 2018 (28 days), run once (`results/elec_weather_run.json`).

The first test asked whether the model could match the grid operators. This one asks what weather adds. I gave the same model four extra numbers: the temperature at the hour being forecast, its average over the day, and how far below 15 degrees or above 22 degrees it was. Then I forecast 28 days it had not seen (3 Nov 2018 to 30 Nov 2018), next to the same model without temperature, a simple guess and the operators.

Without weather the model missed by 579 MW per country per hour. With weather it missed by 497 MW, which is 14% lower. It was the better of the two on 20 of 28 days. The 95% range, 40 to 121 MW a day, stays on one side of zero. Against the grid operators' forecast (615 MW) the weather model (497 MW) is ahead, 19% lower in error.

Weather lowered the percentage error in all 10 countries. The temperature the model got is what was measured, not a forecast, so a real system would do worse than this. Read it as the most weather could add to this model, not as a result you could bank.

Caveats:

- Measured temperature stands in for a weather forecast. Real forecasts are wrong by a degree or two, so this is an upper bound on what weather would give.
- One window, 28 days, in autumn heating season. It says nothing about summer cooling or about holidays.
- The window was chosen before any weather result existed and sits wholly before the development days used for the first test. It is the only time it was scored.
- Settings were the same as the model without weather. Nothing was tuned for the weather version, so a tuned one could do better or worse.
- Temperature is a population-weighted country average from NASA's MERRA-2 reanalysis via Open Power System Data. Wind, cloud and sun are not included.

### Limits

- The held-out days are September 2020, right after the spring lockdowns, so demand was not behaving normally. One month of September says little about winter peaks.
- The data ends in 2020 and comes from one public source, so this shows the method, not what happens on today's grid.
- The main test has no weather input, and the operators' forecasts use weather. A second test on a different window added measured temperature; see the Weather tab.
- Holidays are national only. Regional holidays are not in the model.
- The operators' forecast was issued about half a day before my forecast and uses information mine does not have. It is a reference line, not a like-for-like opponent.
- For Netherlands, Switzerland, Austria the operator series looks like it measures something else, so I report the numbers but do not draw a conclusion from them.
- The 10% to 90% range covered 75% of hours against a target of 80%.
- The country list was chosen by a rule (complete data, then the largest average load). The rule was changed once after a first development run, and that is written down in the project notes. Countries with the most missing data were not used.

### Method

1. Pick a day. At midnight the model may only look at what happened before that moment.
2. It forecasts every hour of that day, in every country, using demand from the past day, week and four weeks, the hour, weekday, month and national holidays.
3. Countries differ hugely in size, so the model predicts demand relative to each country's recent level and scales the answer back.
4. The real numbers are revealed, the miss is scored, and the clock moves forward one day.
5. A test checks that every feature equals an independent recalculation from raw history, and that a deliberately planted leak is caught.
6. Choices were made on the 364 development days. The last 28 days were scored once.

### Reproduce

```
python -m src.opsd_download
python -m src.elec_data
python -m src.elec_run dev
python -m src.elec_run final      # once; a second run is refused
python -m src.opsd_weather && python -m src.elec_weather_run   # once
python -m src.make_site           # builds the static site, including elec.html
```

### Data and credit

Hourly load and operator forecasts from Open Power System Data (originally the ENTSO-E Transparency Platform), 2015-01-02 to 2020-09-30. Cite as: Open Power System Data. 2020. Data Package Time series. Version 2020-10-06. https://doi.org/10.25832/time_series/2020-10-06.
Weather: Open Power System Data. 2020. Data Package Weather Data. Version 2020-09-16. https://doi.org/10.25832/weather_data/2020-09-16.
The OPSD pages I read do not state a licence in the page text. I did not verify one, so check the data package metadata before redistributing derived data. Raw data is not in this repository.
