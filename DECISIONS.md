# DECISIONS

Written before the code for each step. Newest at the bottom. Status is one of: planned, done, changed.

## D0. Problem framing (planned)

Given everything known at midnight, forecast hourly demand for the next 24 hours so a team could position supply (cars or generation) before it is needed.

- Domain A: pickups per NYC taxi zone per hour, TLC High Volume For-Hire Vehicle trips (Uber, Lyft, Via, Juno).
- Domain B (phase two): actual load per country per hour, Open Power System Data.
- Everything below follows from that sentence. If a choice does not serve it, it gets cut.

## D1. Target, horizon, origin (planned)

- Target: count of trips per `(pickup hour, PULocationID)`, grouped on `pickup_datetime`.
- Origin: every day at 00:00 local time. Horizon: the 24 hours of that day.
- Reason: matches the decision in D0 and matches the operator day-ahead convention for Domain B.
- Timestamps: `pickup_datetime` is local NYC wall time. DST creates a missing hour in March and a repeated hour in November. Decision: keep local wall time, aggregate on the local hour, and write down the two DST days in the audit. Check what the TLC data dictionary says before trusting this.

## D2. Period (planned)

- The most recent 12 published months, all after 5 January 2025 (congestion relief charge start, `cbd_congestion_fee` column present).
- Reason: a level shift in Manhattan zones would distort a model trained across the boundary.
- Cut-scope fallback: 6 months, if session 1 runs 50 percent over.
- Final 4 weeks of data are the held-out set. Not touched until the very end.

## D3. Zones (planned)

- 20 busiest, 5 mid-volume, 5 quiet, ranked by total pickups on the development period only (not the held-out weeks).
- Zones under 1,000 total trips are excluded before ranking, so a dead zone is not passed off as quiet. Mid is the 5 zones around the median rank below the top 20. Quiet is the 5 lowest above the floor.
- Reason: shows how error behaves at different scales.
- Cut-scope fallback: fewer zones.

## D4. Data layer (planned)

- DuckDB reads parquet directly, aggregation is plain SQL in `src/sql/hourly.sql`, output is one parquet file `data/hourly.parquet`.
- Reason: SQL stays visible, no multi-million row frames in pandas.
- Grid completion: every `(hour, zone)` pair in range gets a row, with 0 where no trips. A missing row and a zero are different things only if the data has a gap, so the audit separates them.

## D5. Baselines (planned)

Four, all scored by exactly the same backtest function as any model:

1. Naive: last observed hour at the origin, held flat for 24 hours.
2. Same hour yesterday.
3. Same hour last week.
4. Mean of the same hour over the last 4 weeks.

## D6. Backtest (done in code, tested on synthetic data only)

- Rolling origin, expanding window, 24-hour horizon, midnight origins.
- Deviation from the playbook: it says a new origin every week. A weekly step always lands on the same weekday, so the model would never be scored on the other six. Default is a new origin every day (`--step-days 1`). Weekly is one flag away if needed for speed.
- Every forecaster takes `hist`, which the harness slices to rows strictly before the origin. A forecaster cannot see the future by construction, and a test spies on this.
- Domain B reuses `run_backtest` and `summarize` unchanged.

## D7. Metrics (done in code, tested on hand-made series)

- MAE, RMSE, bias (mean of forecast minus actual), MASE scaled by the seasonal naive (lag 168) in-sample error.
- Scale window: the 4 weeks of history before each origin, per zone. MASE in the summary is the mean of per-zone MASE so quiet zones count as much as busy ones.
- No MAPE. Quiet zones have near-zero hours.

## D8. Leak test (done in code)

- Two independent checks. (1) Truncation invariance: features for the origin day must not change when all data at or after the origin is removed. (2) Recompute every lag and rolling feature from raw history by timestamp lookup, sharing no code with the pipeline, and compare.
- Proof it works: tests plant a lag-23 leak, a centered rolling window and the target as a feature, and assert each is caught.

## D9. Models, session 3 (planned)

- Exponential smoothing (statsmodels), LightGBM with lag 24, lag 168, rolling means, hour, day of week, holiday flag, zone. Simple average of LightGBM and best baseline. Quantile LightGBM at 10 and 90 percent.
- No deep learning.

## D10. Held-out weeks (done in code)

- The last 4 weeks are dropped inside `load_dev` in `src/run_baselines.py` and nowhere else. Anything that scores models goes through that function. The final evaluation will be one explicit call that reads them once.

## Open items (not verified)

- TLC file URL pattern, file sizes, row counts and exact months available: run `python src/download.py --probe` on a machine with internet.
- Whether `pickup_datetime` is local wall time in the current files: check the TLC data dictionary and the audit DST lines on the real data.
- Holiday package, weather source and its terms.
- Whether OPSD has a package newer than 2020-10-06.

## D11. Timestamps are local wall time (done, verified on real data)

- Evidence on the real files: 2026-03-08 02:00 has 85 trips against about 30,000 on either side (that hour does not exist in local time), and 2025-11-02 01:00 has 75,292, about double its neighbours (the repeated hour, both passes in one bucket). No hour in the year has zero city trips, so there are no real data gaps.
- Decision: keep wall time. Every hour then sits exactly 168 rows after the same hour of the previous week, so lag 168 and the weekly baselines stay aligned all year.
- Cost: two hours a year are artifacts. They inflate or deflate that hour in the forecasts for up to 4 weeks afterwards, because the 4-week mean and the lag features reuse them. Small, not corrected, goes in the README limits.
- Audit fix: the old gap check could never fail, because build_hourly fills a complete grid with zeros. Gap detection is now a near-zero city total, and the DST hours are printed explicitly.

## D12. Evaluation origins and warm-up (changed from D6)

- All models are scored on the same origins, which now start 8 weeks into the data (`--min-history-weeks 8`) so LightGBM has enough history to train. This shrinks the origin set slightly, so the baseline numbers move a little from the session 2 run. Compare models only within one run_models output.

## D13. Models (done in code, development backtest only)

- Statistical model: additive Holt-Winters (statsmodels), weekly season of 168 hours, no trend, one fit per zone on the last 6 weeks. If a fit fails it falls back to same-hour-last-week and the count is printed.
- LightGBM: one global model across zones, features lag 24, lag 168, mean of the previous 24 hours ending at lag 24, mean of the same hour over the previous 4 weeks, hour, day of week, holiday flag (US federal and New York state calendar), zone as a categorical.
- Point objective is Poisson, because counts span 0 to 1,500 across zones and Poisson handles that scale spread. Chosen before seeing any model result.
- Parameters are fixed in advance (300 rounds, learning rate 0.05, 63 leaves, 50 rows per leaf) and are not tuned on the backtest. Tuning, if done later, happens on development origins only.
- Refit weekly on all rows whose target is strictly before the origin (expanding window), not at every origin. Between refits the model is reused and only the features move. This is a cost decision: daily refits would triple the run time for little expected change.
- Native LightGBM API, no scikit-learn dependency.
- Features for the forecast day are built from history extended with empty horizon rows, so a feature bug cannot read the future. A test scrambles all data from the origin onward and checks the forecasts do not change.

## D14. Combination and intervals (done in code)

- Combination: simple average of LightGBM and the best baseline by development MASE (chosen by the code, printed in the output).
- Intervals: two more LightGBM models with the quantile objective at 0.1 and 0.9. Lower and upper edges are sorted per row so they cannot cross. Reported: share of actuals inside the band (target about 0.80) and mean width, overall and by zone tier. Low-count zones give integer actuals, so coverage there will be lumpy.
- Pinned requirements now match the versions the code was run with.

## D15. Intervals on integer counts (changed from D14)

- A quantile model outputs real-valued edges. For a quiet zone with a mean near 1 trip an hour, a lower edge of 0.4 excludes an actual of 0 even though 0 is the most common outcome, so raw coverage is understated there. The first run showed 0.558 in quiet zones for this reason.
- Decision: report both. Raw edges, and edges rounded outward (lower down, upper up) to whole trips. Rounded is the headline for counts. Rounding only ever widens a band, so it can only raise coverage, which is why both numbers are shown.

## D16. One weekday is not a backtest (process note)

- A first quick pass used `--step-days 7`, which puts every origin on the same weekday (Wednesday). Its results were discarded and are not used anywhere. `run_models` now prints a warning whenever the origins cover fewer than 7 weekdays.
- The holiday calendar is built once per year range and cached, instead of on every feature call.

## D17. How the development results are judged (analysis protocol)

- Head-to-head claims use a paired comparison against the best baseline on daily MAE, with a 95% interval from a bootstrap that resamples whole 7-day blocks. Neighbouring days are not independent, so resampling single days would make the interval look tighter than it is. A gain only counts as real if the interval excludes zero. Reported overall and by zone tier.
- The ten worst days are picked by total absolute error across the 30 zones. Calendar reasons (holiday names, the day before or after one, daylight saving days) are attached by code. Anything else is printed as "unexplained" and stays that way until someone checks weather and news. No reason is written from a guess.
- Feature importance comes from one fit on all development data, as share of total gain. It describes that fit, not causation.
- All of this reads development predictions only. The held-out 4 weeks stay unread until the single final evaluation.

## D18. Feature ablation, rule fixed before the result (planned)

- Question: do the short-lag features (lag_24 and the 24-hour mean ending at lag 24) help or hurt? On the development backtest the full model did worse than the baseline on 24 Feb 2026, the day after a collapse in demand, which fits a one-day lag carrying a shock forward. That is a hypothesis, and this ablation tests it.
- Candidate B: the same LightGBM without lag_24 and roll24_l24. Nothing else changes, and no other variants are tried.
- Rule, written before running it: switch to B only if B's paired daily-MAE gain over the full model is positive with a 95% interval (weekly block bootstrap) that excludes zero overall. Otherwise keep the full model.
- Whichever model the rule picks is frozen. No further modelling choices are made after the held-out weeks are scored.

## D19. Held-out evaluation protocol (done in code)

- `src/final_eval.py` scores the last 4 weeks, 28 daily origins, once. It records every run in `results/heldout_run.json` and refuses a second run unless forced. A forced rerun is marked in that file and gets disclosed in the README.
- Zones and the cut come from development data. The baseline used in the combination is fixed from the development result, not re-picked on these weeks.
- Expanding window as in production: each origin sees everything before its own midnight, including earlier held-out days. LightGBM refits weekly, so it refits at the held-out origins too.
- With 28 days there are only 4 weekly blocks, so the paired interval is crude. The held-out headline is the point estimate next to the development result.

## D21. App polish (done)

- Zone dropdown shows "ID: Borough, Zone" from `app/taxi_zone_lookup.csv` (TLC zone lookup, downloaded by the user, committed so the deployed app has it). If the file is missing the app shows bare IDs.
- Chart: legend moved below the plot, hour-only axis labels, smaller fonts.

## D22. App and README polish (done)

- headline held-out metrics at the top of the app, Forecast and About tabs, interval toggle, TLC zone lookup credit in the README generator.

## D23. App redesign (done)

- Dark theme in `.streamlit/config.toml`. Colors: amber for LightGBM, blue for the baseline, light gray for actuals; amber and blue checked with the dataviz validator against the dark surface.
- Interactive Altair charts with hover. New "Where it fails" tab: daily error over time with verified-cause days circled (from `docs/day_reasons.csv`), and an hour-by-weekday heatmap of where LightGBM beats the baseline.

## D24. App identity (done)

- Light "cab" look: taxi-yellow hero band with one large black number, cream surface, ink-black actuals, cobalt for LightGBM, neutral gray dashed for the baseline, taxi-yellow for the interval band and held-out period, orange for verified-cause days. Cobalt and orange pass the dataviz validator on the cream surface; the gray baseline is a deliberate neutral.
- Font: Archivo, loaded from Google Fonts by CSS import with Arial Narrow and system fallbacks.
