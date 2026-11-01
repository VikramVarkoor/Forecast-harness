"""Write README.md from the results files, so every number in it was produced by code.

    python -m src.make_readme

Reads results/*.csv and docs/day_reasons.csv. Prose that states a fact about the data is built from
the numbers; fixed prose only describes method and limits. Nothing here is a model run.
"""
import json
import re
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


def elec_section():
    """Domain B text, every number from results/elec_* via make_site_elec.build. Empty if that run has not happened."""
    if not (R / "elec_heldout_predictions.parquet").exists():
        return ""
    from src.make_site_elec import build
    d = build(R)
    c, w = d["compare"], d.get("weather")
    strip = lambda t: re.sub(r"<[^>]+>", "", t)
    cty = pd.DataFrame([{"country": x["name"], "mean load MW": x["mean_load"], "model MAPE %": x["mape_model"],
                         "simple guess MAPE %": x["mape_base"], "operator MAPE %": x["mape_op"],
                         "operator series flagged": "yes" if x["flagged"] else ""} for x in d["countries"]])
    f1, f2, f3 = (lambda v: f"{v:.1f}"), (lambda v: f"{v:.2f}"), (lambda v: f"{v:.3f}")
    tbl = pd.DataFrame([["LightGBM (mine)", f1(c["model_mae"]), f2(c["model_mape"]), f3(c["model_mase"])],
                        [c["base_label"] + " (simple guess)", f1(c["base_mae"]), f2(c["base_mape"]), f3(c["base_mase"])],
                        ["Operator day-ahead forecast (not like for like)", f1(c["op_mae"]), f2(c["op_mape"]), f3(c["op_mase"])]],
                       columns=["model", "MAE MW", "MAPE %", "MASE"])
    wx = ""
    if w:
        wx = (f"\n### Weather test\n\nSeparate window, {w['window']} ({w['n_days']} days), run once (`results/elec_weather_run.json`).\n\n"
              + "\n\n".join(strip(t) for t in w["plain"]) + "\n\nCaveats:\n\n" + "\n".join(f"- {t}" for t in w["caveats"]) + "\n")
    return f"""## B. European electricity day-ahead load forecast

Hourly national load for {len(d['countries'])} countries, forecast at midnight for the next 24 hours, scored by the same rolling-origin harness idea as Domain A.
Every number in this section is computed from `results/elec_*` files by `src/make_site_elec.py`.

### Findings

- {d['verdict']}
{chr(10).join('- ' + strip(t).replace(' on a separate window, in the Weather tab.', ' on a separate window (see Weather test below).') for t in d['plain'])}
- {d['findings'][2]['big']} of actual hours fell inside the 10% to 90% range. {d['findings'][2]['sub']}

Held-out ({c['n_days']} days, scored once; lower is better):

{md(tbl)}

By country (MAPE):

{md(cty, 2)}
{wx}
### Limits

{chr(10).join('- ' + t for t in d['limits'])}

### Method

{chr(10).join(f'{i}. {t}' for i, t in enumerate(d['method'], 1))}

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

{d['data_note']} Cite as: Open Power System Data. 2020. Data Package Time series. Version 2020-10-06. https://doi.org/10.25832/time_series/2020-10-06.
Weather: Open Power System Data. 2020. Data Package Weather Data. Version 2020-09-16. https://doi.org/10.25832/weather_data/2020-09-16.
The OPSD pages I read do not state a licence in the page text. I did not verify one, so check the data package metadata before redistributing derived data. Raw data is not in this repository.
"""


def bias_finding():
    """Sentence on the held-out bias, written from results/bias_check.json (python -m src.bias_check).
    Returns None if that file does not exist, and the README then says the cause was not investigated."""
    f = R / "bias_check.json"
    if not f.exists():
        return None
    b = json.loads(f.read_text())
    names = {}
    lk = ROOT / "app" / "taxi_zone_lookup.csv"
    if lk.exists():
        lkp = pd.read_csv(lk)
        names = dict(zip(lkp["LocationID"].astype(str), lkp["Zone"]))
    worst = ", ".join(names.get(w["zone"], f"zone {w['zone']}") for w in b["worst_zones"])
    rise = 100 * (b["mean_actual_ratio_held_to_dev"] - 1)
    hrs = b["bias_by_hour"]; lo = min(hrs, key=lambda h: abs(hrs[h])); hi = min(hrs, key=lambda h: hrs[h])
    bm = b["bias_held_by_model"]
    order = [("mean_same_hour_4w", "4-week mean"), ("lgbm", "LightGBM"), ("same_hour_last_week", "same hour last week"), ("same_hour_yesterday", "same hour yesterday")]
    pairs = ", ".join(f"{lab} {bm[k]:.1f}" for k, lab in order if k in bm)
    mae_note = ""
    if b.get("mae_held"):
        mae_note = f" The bias is about {100 * abs(b['bias_held']) / b['mae_held']:.0f}% of LightGBM's MAE, so most of the miss is not bias."
    return (f" Development days were {b['bias_dev']:+.1f}. Mean demand in the held-out weeks ran {rise:.1f}% above the development average. "
            f"The shortfall was spread out ({b['zones_negative']} of {b['zones_total']} zones and {b['days_negative']} of {b['days_total']} days were negative), "
            f"but the 5 worst zones carry {b['top5_share_of_total_shortfall_pct']:.0f}% of it ({worst}). By hour it is largest at {hi}:00 ({hrs[hi]:.1f}) and smallest at {lo}:00 ({hrs[lo]:+.1f}). "
            f"Held-out bias by model: {pairs}. That fits demand running above the recent history, but why (season, events, weather) was not tested.{mae_note}")


SOURCES = [
    ("A. Taxi", [("Held-out MAE, RMSE, bias, MASE", "heldout.csv"), ("Days won, paired gain and its range", "heldout_paired.csv"),
                 ("Development backtest table", "models.csv"), ("Interval coverage, raw and rounded", "heldout_intervals.csv"),
                 ("Held-out bias check", "bias_check.json"), ("Ablation without the short-lag features", "models_nolag.csv"),
                 ("How many times the held-out weeks were scored", "heldout_run.json")]),
    ("B. Electricity", [("Held-out table, MAE and MAPE per model", "elec_heldout.csv"), ("Per-country results", "elec_heldout_by_country.csv"),
                        ("Model against the baseline and the grid operators, paired", "elec_heldout_paired.csv"),
                        ("10% to 90% range coverage", "elec_heldout_band.json"), ("Data span, hours, gaps, chosen countries", "elec_data_report.json"),
                        ("Baseline chosen on development data", "elec_dev_best.txt"), ("Weather test, by model", "elec_weather_models.csv"),
                        ("Weather test, paired gain and its range", "elec_weather_paired.csv"),
                        ("How many times the held-out days were scored", "elec_heldout_run.json")]),
]


def sources_section():
    """Which results file backs which headline number. Lists only files that exist."""
    rows = []
    for dom, items in SOURCES:
        for what, name in items:
            if (R / name).exists():
                rows.append(f"| {dom} | {what} | `results/{name}` |")
    if not rows:
        return ""
    return ("## Where the numbers come from\n\nEvery figure above is read from one of these files, so it can be checked against the source.\n\n"
            "| Domain | Number | File |\n|---|---|---|\n" + "\n".join(rows) + "\n\n"
            "`app/app.py` is the original Streamlit dashboard for the taxi results (`streamlit run app/app.py`). "
            "The static site generator reuses its data code, so it stays in the repository.\n")


def combine(taxi):
    """Two domains in one README: Domain A headings demoted one level, Domain B appended."""
    a = re.sub(r"^## ", "### ", taxi, flags=re.M)
    a = a.replace("# NYC ride-hail day-ahead demand forecast", "## A. NYC ride-hail day-ahead demand forecast", 1)
    head = ("# Day-ahead forecasting, two domains\n\nTwo forecasting projects built with the same discipline: forecasts made from the night before, "
            "a held-out period scored once, simple baselines beside every model, and results reported whatever they came out as. "
            "Decisions are logged in `DECISIONS.md` and `docs/decisions/`.\n\n")
    return head + a.rstrip() + "\n\n" + elec_section() + "\n\n" + sources_section()


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
        f.append(f"- Ablation (rule in DECISIONS D18): dropping the two short-lag features moved development MASE "
                 f"from {dev.loc['lgbm', 'MASE']:.3f} to {nolag.loc['lgbm', 'MASE']:.3f}.")
    f.append(f"- The 10% to 90% interval is meant to cover 80% of hours. Raw coverage on held-out hours was {hc.loc['all', 'coverage_raw'] * 100:.0f}%. "
             f"After rounding the edges outward to whole trips it was {hc.loc['all', 'coverage_rounded'] * 100:.0f}%. That rounding is not a calibration, it only "
             f"reflects that trip counts are integers. In quiet zones raw coverage is {hc.loc['quiet', 'coverage_raw'] * 100:.0f}%, and the rounded figure there "
             f"({hc.loc['quiet', 'coverage_rounded'] * 100:.0f}%) mostly reflects zero-heavy hours.")
    f.append(f"- Held-out bias (forecast minus actual, trips per zone-hour) was negative for {len(bias_neg)} of {len(held)} "
             f"models; LightGBM {held.loc['lgbm', 'bias']:.1f}." + (bias_finding() or " Demand ran above what the history implied; the cause was not investigated."))

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
    catch = " Zone 265 is the TLC's catch-all for trips outside the city, not a neighbourhood." if 265 in set(pred["zone"].astype(int)) else ""

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
- Only {ntr} zones are modelled. Results say nothing about the other zones.{catch}
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
6. Decisions are logged in `DECISIONS.md` and `docs/decisions/`.

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

"""
    text = combine(text)
    (ROOT / "README.md").write_text(text)
    print("wrote README.md")


if __name__ == "__main__":
    main()
