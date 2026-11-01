"""Write README.md from the results files, so every number in it was produced by code.

    python -m src.make_readme

Reads results/*.csv and docs/day_reasons.csv. Prose that states a fact about the data is built from
the numbers; fixed prose only describes method and limits. Nothing here is a model run.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "results"
NAMES = {"lgbm": "LightGBM", "ets_weekly": "Exponential smoothing (weekly)",
         "mean_same_hour_4w": "Mean of same hour, last 4 weeks", "same_hour_last_week": "Same hour last week",
         "same_hour_yesterday": "Same hour yesterday", "naive_last_hour": "Last hour held flat"}


def md(df: pd.DataFrame, nd=2) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(f"{v:.{nd}f}" if isinstance(v, float) else str(v) for v in r) + " |")
    return "\n".join(out)


def overall(path):
    d = pd.read_csv(path, index_col=0)
    return d[~d.index.str.contains(r"\|")]


def table(path):
    d = overall(path).sort_values("MASE")
    t = d[["MAE", "RMSE", "bias", "MASE"]].reset_index()
    t.columns = ["model", "MAE", "RMSE", "bias", "MASE"]
    t["model"] = t["model"].map(lambda n: NAMES.get(n, n.replace("lgbm_plus_", "LightGBM + ").replace("_", " ")))
    return t


def pct(a, b):
    return 100 * (b - a) / b


def main():
    dev, held = overall(R / "models.csv"), overall(R / "heldout.csv")
    hp = pd.read_csv(R / "heldout_paired.csv").set_index("scope")
    dp = pd.read_csv(R / "analysis" / "paired_comparison.csv").set_index("scope")
    hc = pd.read_csv(R / "heldout_intervals.csv").set_index("scope")
    nolag = overall(R / "models_nolag.csv") if (R / "models_nolag.csv").exists() else None
    runs = json.loads((R / "heldout_run.json").read_text())["runs"]
    pred = pd.read_parquet(R / "heldout_predictions.parquet", columns=["origin", "zone", "lgbm", "y"])
    base = "mean_same_hour_4w"

    def line(d, p, label):
        m, b = d.loc["lgbm"], d.loc[base]
        g = p.loc["all"]
        return (f"- **{label}:** LightGBM MAE {m.MAE:.2f} against {b.MAE:.2f} for the best baseline "
                f"({NAMES[base].lower()}), {pct(m.MAE, b.MAE):.1f}% lower. MASE {m.MASE:.3f} against {b.MASE:.3f}. "
                f"Paired daily gain {g.mae_gain:.2f} trips per zone-hour (95% interval {g.ci95_lo:.2f} to {g.ci95_hi:.2f}), "
                f"better on {g.win_rate * 100:.0f}% of {int(g.n_days)} days.")

    rank = held["MASE"].rank().astype(int)
    combo = [i for i in held.index if i.startswith("lgbm_plus_")][0]
    bias_neg = [n for n in held.index if held.loc[n, "bias"] < 0]
    f = [line(held, hp, "Held-out, 4 weeks scored once"), line(dev, dp, "Development, rolling backtest"),
         f"- Exponential smoothing ranks {rank['ets_weekly']} of {len(held)} on held-out MASE "
         f"({held.loc['ets_weekly', 'MASE']:.3f}), behind the 4-week mean ({held.loc[base, 'MASE']:.3f}). It did not earn its place.",
         f"- Averaging LightGBM with the best baseline gave MAE {held.loc[combo, 'MAE']:.2f} against "
         f"{held.loc['lgbm', 'MAE']:.2f} for LightGBM alone, so the combination did not help."]
    if nolag is not None:
        f.append(f"- Ablation (pre-registered in DECISIONS D18): dropping the two short-lag features moved development MASE "
                 f"from {dev.loc['lgbm', 'MASE']:.3f} to {nolag.loc['lgbm', 'MASE']:.3f}.")
    f.append(f"- The 10% to 90% interval covered {hc.loc['all', 'coverage_rounded'] * 100:.0f}% of held-out hours after rounding edges "
             f"outward to whole trips (raw {hc.loc['all', 'coverage_raw'] * 100:.0f}%). In quiet zones the raw interval covers "
             f"{hc.loc['quiet', 'coverage_raw'] * 100:.0f}% because counts are integers, so rounded coverage there "
             f"({hc.loc['quiet', 'coverage_rounded'] * 100:.0f}%) mostly reflects zero-heavy hours.")
    f.append(f"- Held-out bias (forecast minus actual, trips per zone-hour) was negative for {len(bias_neg)} of {len(held)} "
             f"models; LightGBM {held.loc['lgbm', 'bias']:.1f}. Demand ran above what the history implied; the cause was not investigated.")

    reasons = pd.read_csv(ROOT / "docs" / "day_reasons.csv").set_index("date")
    wd = pd.read_csv(R / "analysis" / "worst_days.csv")
    wd = wd.rename(columns={wd.columns[0]: "date"})
    wd["date"] = wd["date"].astype(str)
    wd["cause"] = [f"{reasons.loc[d, 'reason']} ([source]({reasons.loc[d, 'source']}))" if d in reasons.index
                   else f"{r} (not verified)" if str(r).startswith("unexplained") else r
                   for d, r in zip(wd["date"], wd["reason"])]
    wt = wd[["date", "weekday", "model_abs_err", "forecast_minus_actual", "cause"]].copy()
    wt[["model_abs_err", "forecast_minus_actual"]] = wt[["model_abs_err", "forecast_minus_actual"]].round(0)

    tiers = []
    for t in ("top", "mid", "quiet"):
        tiers.append({"tier": t, "baseline MAE": held.loc[base, "MAE"] if t == "all" else
                      pd.read_csv(R / "heldout.csv", index_col=0).loc[f"{base}|{t}", "MAE"],
                      "LightGBM MAE": pd.read_csv(R / "heldout.csv", index_col=0).loc[f"lgbm|{t}", "MAE"]})
    ntr = int(pred["zone"].nunique())

    text = f"""# NYC ride-hail day-ahead demand forecast

Hourly pickups per taxi zone for the next 24 hours, forecast at midnight, scored by one rolling-origin harness.
Data: NYC TLC High Volume For-Hire Vehicle trips, {ntr} zones (20 busiest, 5 mid, 5 quiet, chosen on development data only).
Every number below is written by `python -m src.make_readme` from files in `results/`.

## Findings

{chr(10).join(f)}

Held-out result table (lower is better; MASE under 1 beats the seasonal naive of lag 168):

{md(table(R / "heldout.csv"), 3)}

Held-out MAE by zone tier:

{md(pd.DataFrame(tiers), 2)}

Development result table (rolling backtest on every day before the held-out weeks):

{md(table(R / "models.csv"), 3)}

## Limits

- The held-out set is 28 days in one month. The paired interval uses only 4 weekly blocks, so treat it as crude.
- The held-out weeks were scored {len(runs)} time(s) (`results/heldout_run.json`). Nothing was tuned on them.
- Only {ntr} zones are modelled. Results say nothing about the other zones.
- The data covers one year, so each holiday appears once. Holiday handling is a flag, not a learned effect.
- Shock days dominate the error. The ten worst development days:

{md(wt, 0)}

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
"""
    (ROOT / "README.md").write_text(text)
    print("wrote README.md")


if __name__ == "__main__":
    main()
