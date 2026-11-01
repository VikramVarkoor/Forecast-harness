"""Domain B, extension: does weather help? One scored run on a window nobody has tuned on.

    python -m src.elec_weather_run            # RUN ONCE. Refuses a second run unless --force (after a crash only).

Set up before any weather result exists:
  * Window: the 28 origin days 3 to 30 November 2018. Heating season, before COVID, no national holiday in it.
    The weather file ends in 2019, so the September 2020 held-out days cannot be used. The run checks that the
    window sits wholly before the development days used earlier, so no baseline pick or look at them touched it.
  * Models, all given the same window and the same fixed settings, nothing tuned: the best simple baseline (read from
    the development result), the grid operators' forecast, the existing LightGBM, and the same LightGBM plus four
    temperature features (temperature at the target hour, its 24 h mean, heating degrees below 15 C, cooling degrees
    above 22 C).
  * The temperature handed to the weather model is what was MEASURED at the target hour. A real forecast would be
    wrong by a degree or two, so this shows the most weather could add, not what a deployed model would get.
"""
import argparse
import json
from datetime import datetime, timezone

import pandas as pd

from src.backtest import run_backtest
from src.baselines import BASELINES
from src.elec_features import FEATURES, WX, ElecLGBM, tso_forecaster
from src.elec_run import DEV_DAYS, ROOT, TSO, by_country, load, paired, split, table

WINDOW_START, WINDOW_DAYS = "2018-11-03", 28


def window():
    s = pd.Timestamp(WINDOW_START)
    return list(pd.date_range(s, periods=WINDOW_DAYS, freq="D"))


def check_window(act, origins):
    cut, _ = split(act)
    dev_start = cut - pd.Timedelta(days=DEV_DAYS)
    if origins[-1] >= dev_start:
        raise SystemExit(f"The test window ends {origins[-1].date()}, but the development days start {dev_start.date()}. It must be wholly earlier.")


def run(act, tso, wx, origins, best, log=print):
    models = {best: BASELINES[best], TSO: tso_forecaster(tso), "lgbm": ElecLGBM(), "lgbm_weather": ElecLGBM(features=FEATURES + WX, weather=wx)}
    runs = {}
    for n, f in models.items():
        runs[n] = run_backtest(act, f, origins); log(f"  {n} done")
    keys = ["origin", "ts", "zone", "y"]
    pred = runs["lgbm"][keys + ["scale"]].copy()
    for n, bt in runs.items():
        assert bt[keys].equals(pred[keys]), f"{n} rows do not line up"
        pred[n] = bt["yhat"].to_numpy()
    n0 = len(pred)
    pred = pred[pred[TSO].notna()].reset_index(drop=True)
    pred.attrs["dropped_rows"] = n0 - len(pred)
    return pred


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    out = ROOT / "results"
    act, tso = load()
    wx = pd.read_parquet(ROOT / "data" / "opsd" / "weather_temp.parquet")
    origins = window()
    check_window(act, origins)
    end = origins[-1] + pd.Timedelta(hours=23)
    gone = [c for c in act.columns if c not in wx.columns]
    if gone or wx.reindex(columns=act.columns).loc[act.index.min():end].isna().any().any():
        raise SystemExit("Weather has gaps or missing countries over the training span. Run python -m src.opsd_weather and read its report.")
    best = (out / "elec_dev_best.txt").read_text().strip()
    path = out / "elec_weather_run.json"
    prior = json.loads(path.read_text()) if path.exists() else {"runs": []}
    if prior["runs"] and not a.force:
        raise SystemExit(f"The weather window was already scored (see {path}). Use --force only after a crash.")
    prior["runs"].append({"started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "window": [str(origins[0].date()), str(origins[-1].date())], "best_baseline": best, "status": "started"})
    path.write_text(json.dumps(prior, indent=2))
    print(f"WEATHER WINDOW: {len(origins)} origins {origins[0].date()} to {origins[-1].date()}, best baseline fixed at {best}", flush=True)
    wide = act.loc[act.index <= end]
    pred = run(wide, tso, wx, origins, best)
    names = [best, TSO, "lgbm", "lgbm_weather"]
    res = table(pred, names); res.to_csv(out / "elec_weather_models.csv")
    pred.to_parquet(out / "elec_weather_predictions.parquet", index=False)
    cc = by_country(pred, names); cc.to_csv(out / "elec_weather_by_country.csv", index=False)
    pr = pd.concat([paired(pred, "lgbm_weather", "lgbm"), paired(pred, "lgbm_weather", best), paired(pred, "lgbm_weather", TSO)])
    pr.to_csv(out / "elec_weather_paired.csv", index=False)
    print(f"Rows left out because the operator forecast was missing: {pred.attrs['dropped_rows']}")
    print("\nWEATHER-WINDOW result (lower is better):"); print(res[["MAE", "MASE", "wMAPE_pct", "MAPE_pct", "bias"]].sort_values("MASE").round(3).to_string())
    print("\nMAPE (%) by country:"); print(cc.pivot(index="country", columns="model", values="MAPE_pct")[names].round(2).to_string())
    print("\nPaired on daily error (gain positive favours the weather model; 4 weekly blocks, so the interval is crude):"); print(pr.round(3).to_string(index=False))
    j = json.loads(path.read_text()); j["runs"][-1]["status"] = "done"; path.write_text(json.dumps(j, indent=2))
    print(f"\nrecorded in {path}. Do not run this again.")


if __name__ == "__main__":
    main()
