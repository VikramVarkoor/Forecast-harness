"""Domain B: European electricity day-ahead load, same rolling-origin backtest as the ride-hail work.

    python -m src.elec_run dev        # development year only. Pick the best baseline here.
    python -m src.elec_run final      # the last 4 weeks. RUN ONCE. Refuses a second run unless --force.

Models: four simple baselines, the grid operators' own published day-ahead forecast (benchmark),
and one global LightGBM. Origins are midnight UTC, horizon 24 hours, expanding window.
The operator forecast was issued about half a day before our origin and uses weather forecasts my
model does not have, so it is a reference line, not a like-for-like opponent.
"""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from src.analyze import block_bootstrap
from src.backtest import run_backtest, summarize
from src.baselines import BASELINES
from src.elec_features import ElecLGBM, tso_forecaster
from src.metrics import interval_coverage, interval_width

ROOT = Path(__file__).resolve().parent.parent
HOLDOUT_DAYS, DEV_DAYS = 28, 364
TSO = "operator_forecast"


def split(wide):
    """Cut = midnight that leaves exactly 28 full origin days at the end. Dev data is everything before it."""
    last_origin = (wide.index[-1] + pd.Timedelta(hours=1) - pd.Timedelta(hours=24)).normalize()
    cut = last_origin - pd.Timedelta(days=HOLDOUT_DAYS - 1)
    return cut, last_origin


def evaluate(wide, tso, origins, features=None, run_q=True, rounds=None, log=print):
    runs = {}

    def go(name, f):
        t = time.time(); runs[name] = run_backtest(wide, f, origins); log(f"  {name}: {time.time() - t:.0f}s")

    for n, f in BASELINES.items():
        go(n, f)
    go(TSO, tso_forecaster(tso))
    models = {"lgbm": ElecLGBM(features=features)}
    if run_q:
        models["lgbm_q10"] = ElecLGBM("quantile", alpha=0.1, features=features)
        models["lgbm_q90"] = ElecLGBM("quantile", alpha=0.9, features=features)
    for n, m in models.items():
        if rounds:
            m.rounds = rounds
        go(n, m)
    keys = ["origin", "ts", "zone", "y"]
    pred = runs["lgbm"][keys + ["scale"]].copy()
    for n, bt in runs.items():
        assert bt[keys].equals(pred[keys]), f"{n} rows do not line up with the others"
        pred[n] = bt["yhat"].to_numpy()
    n0 = len(pred)
    pred = pred[pred[TSO].notna()].reset_index(drop=True)     # hours with no operator forecast are out for every model
    pred.attrs["dropped_rows"] = n0 - len(pred)
    if run_q:
        pred["q10"] = np.minimum(pred["lgbm_q10"], pred["lgbm_q90"]); pred["q90"] = np.maximum(pred["lgbm_q10"], pred["lgbm_q90"])
    return pred


def score(pred, name):
    d = pred.assign(yhat=pred[name])
    s = summarize(d)
    e = (d["yhat"] - d["y"]).abs()
    s["wMAPE_pct"] = 100 * e.sum() / d["y"].sum()
    s["MAPE_pct"] = 100 * float((e / d["y"]).mean())
    return s


def table(pred, names):
    return pd.DataFrame({n: score(pred, n) for n in names}).T


def by_country(pred, names):
    rows = []
    for cc, g in pred.groupby("zone"):
        for n in names:
            e = (g[n] - g["y"]).abs()
            rows.append(dict(country=cc, model=n, MAE=e.mean(), MAPE_pct=100 * float((e / g["y"]).mean()), mean_load=g["y"].mean()))
    return pd.DataFrame(rows)


def daily(pred, col, pct=False):
    e = (pred[col] - pred["y"]).abs()
    if pct:
        e = e / pred["y"]
    return e.groupby(pred["origin"]).mean().sort_index()


def paired(pred, a, b):
    """a vs b on daily error. Gain is b minus a, so positive means a is better. Blocks of 7 days."""
    rows = []
    for label, pct in (("MAE (MW)", False), ("MAPE (%)", True)):
        da, db = daily(pred, a, pct), daily(pred, b, pct)
        diff = (db - da) * (100 if pct else 1)
        m, lo, hi = block_bootstrap(diff)
        rows.append(dict(model=a, versus=b, metric=label, gain=m, ci95_lo=lo, ci95_hi=hi, win_rate=float((da < db).mean()), n_days=len(da)))
    return pd.DataFrame(rows)


def load():
    act = pd.read_parquet(ROOT / "data" / "opsd" / "elec_actual.parquet")
    tso = pd.read_parquet(ROOT / "data" / "opsd" / "elec_tso.parquet")
    return act, tso


def guard(out, force, args):
    out.mkdir(parents=True, exist_ok=True)
    path = out / "elec_heldout_run.json"
    prior = json.loads(path.read_text()) if path.exists() else {"runs": []}
    if prior["runs"] and not force:
        raise SystemExit(f"The held-out weeks were already scored (see {path}). Use --force only to rerun after a crash or a bug fix.")
    prior["runs"].append({"started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "args": args,
                          "forced": bool(force and prior["runs"]), "status": "started"})
    path.write_text(json.dumps(prior, indent=2))
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["dev", "final"])
    ap.add_argument("--best-baseline", default=None, help="final stage: fixed from the dev result, never re-picked on held-out days")
    ap.add_argument("--step-days", type=int, default=1)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    out = ROOT / "results"
    act, tso = load()
    cut, last_origin = split(act)
    base_names = list(BASELINES)
    if a.stage == "dev":
        wide = act.loc[act.index < cut]
        origins = list(pd.date_range(cut - pd.Timedelta(days=DEV_DAYS), cut - pd.Timedelta(days=1), freq=f"{a.step_days}D"))
        print(f"DEV: {len(origins)} origins {origins[0].date()} to {origins[-1].date()}, {wide.shape[1]} countries, held-out starts {cut.date()} and is not read", flush=True)
        pred = evaluate(wide, tso, origins)
        names = base_names + [TSO, "lgbm"]
        res = table(pred, names)
        best = min(base_names, key=lambda n: res.loc[n, "MASE"])
        res.to_csv(out / "elec_dev_models.csv"); pred.to_parquet(out / "elec_dev_predictions.parquet", index=False)
        (out / "elec_dev_best.txt").write_text(best)
        print(f"Rows left out because the operator forecast was missing: {pred.attrs['dropped_rows']}")
        print("\nDevelopment result (lower is better; MASE under 1 beats seasonal naive):")
        print(res[["MAE", "MASE", "wMAPE_pct", "MAPE_pct", "bias"]].sort_values("MASE").round(3).to_string())
        print(f"\nBest simple baseline on development days: {best}  (this is the fixed comparison for the final run)")
        print(by_country(pred, ["lgbm", best, TSO]).pivot(index="country", columns="model", values="MAPE_pct").round(2).to_string())
        print(paired(pred, "lgbm", best).round(3).to_string(index=False))
        print(paired(pred, "lgbm", TSO).round(3).to_string(index=False))
        print(f"\nQuantile band coverage (target about 0.80): {interval_coverage(pred['y'], pred['q10'], pred['q90']):.3f}, mean width {interval_width(pred['q10'], pred['q90']):.0f} MW")
        return
    best = a.best_baseline or (out / "elec_dev_best.txt").read_text().strip()
    marker = guard(out, a.force, {"best_baseline": best})
    origins = list(pd.date_range(cut, last_origin, freq="D"))
    print(f"HELD-OUT: {len(origins)} origins {origins[0].date()} to {origins[-1].date()}, {act.shape[1]} countries, best baseline fixed at {best}", flush=True)
    pred = evaluate(act, tso, origins)
    names = base_names + [TSO, "lgbm"]
    res = table(pred, names)
    res.to_csv(out / "elec_heldout.csv"); pred.to_parquet(out / "elec_heldout_predictions.parquet", index=False)
    cc = by_country(pred, names); cc.to_csv(out / "elec_heldout_by_country.csv", index=False)
    pr = pd.concat([paired(pred, "lgbm", best), paired(pred, "lgbm", TSO)]); pr.to_csv(out / "elec_heldout_paired.csv", index=False)
    cov = dict(coverage=interval_coverage(pred["y"], pred["q10"], pred["q90"]), width_mw=interval_width(pred["q10"], pred["q90"]), rows_left_out_no_operator_forecast=pred.attrs["dropped_rows"])
    (out / "elec_heldout_band.json").write_text(json.dumps(cov))
    print("\nHELD-OUT result (lower is better):")
    print(res[["MAE", "MASE", "wMAPE_pct", "MAPE_pct", "bias"]].sort_values("MASE").round(3).to_string())
    print("\nMAPE (%) by country:"); print(cc.pivot(index="country", columns="model", values="MAPE_pct")[["lgbm", best, TSO]].round(2).to_string())
    print("\nPaired on daily error (gain positive favours LightGBM; 4 weekly blocks, so the interval is crude):"); print(pr.round(3).to_string(index=False))
    print(f"\nBand coverage {cov['coverage']:.3f} (target about 0.80)")
    j = json.loads(marker.read_text()); j["runs"][-1]["status"] = "done"; marker.write_text(json.dumps(j, indent=2))
    print(f"\nrecorded in {marker}. Do not run this again.")


if __name__ == "__main__":
    main()
