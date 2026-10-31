"""Session 3: every model through the same rolling-origin backtest, development weeks only.

    python -m src.run_models                    # full run
    python -m src.run_models --no-ets           # skip the slow statistical model
    python -m src.run_models --no-ets --drop-features lag_24,roll24_l24 --tag nolag   # ablation

Writes results/models*.csv, intervals*.csv and predictions*.parquet (suffix from --tag).
The held-out weeks are dropped inside load_dev and are never read here.
"""
import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src.backtest import make_origins, run_backtest, summarize, to_wide
from src.baselines import BASELINES
from src.features import FEATURES
from src.metrics import interval_coverage, interval_width, round_interval_outward
from src.models import ETSForecaster, LGBMForecaster
from src.run_baselines import load_dev

ROOT = Path(__file__).resolve().parent.parent
TIERS = ("top", "mid", "quiet")


def evaluate(wide, origins, tier, objective="poisson", refit_days=7, features=None,
             run_ets=True, best_baseline=None):
    """Run every model on `origins` and score it. Shared by the development run and the one-shot
    held-out run, so both go through identical code. If best_baseline is given it is used as is
    (the held-out run must not pick its own); otherwise it is chosen by MASE on these origins."""
    runs = {}

    def go(name, f):
        t = time.time()
        runs[name] = run_backtest(wide, f, origins)
        print(f"  {name}: {time.time() - t:.0f}s", flush=True)

    for n, f in BASELINES.items():
        go(n, f)
    ets = ETSForecaster()
    if run_ets:
        go("ets_weekly", ets)
    kw = dict(refit_days=refit_days, features=features)
    go("lgbm", LGBMForecaster(objective, **kw))
    go("lgbm_q10", LGBMForecaster("quantile", alpha=0.1, **kw))
    go("lgbm_q90", LGBMForecaster("quantile", alpha=0.9, **kw))

    keys = ["origin", "ts", "zone", "y"]
    pred = runs["lgbm"][keys + ["scale"]].copy()
    for n, bt in runs.items():
        assert bt[keys].equals(pred[keys]), f"{n} rows do not line up with the others"
        pred[n] = bt["yhat"].to_numpy()

    def score(df, name):
        return summarize(df.assign(yhat=df[name]))

    best = best_baseline or min(BASELINES, key=lambda n: score(pred, n)["MASE"])
    combo = f"lgbm_plus_{best}"
    pred[combo] = (pred["lgbm"] + pred[best]) / 2
    pred["q10"] = np.minimum(pred["lgbm_q10"], pred["lgbm_q90"])
    pred["q90"] = np.maximum(pred["lgbm_q10"], pred["lgbm_q90"])
    pred["q10_int"], pred["q90_int"] = round_interval_outward(pred["q10"], pred["q90"])

    models = list(BASELINES) + (["ets_weekly"] if run_ets else []) + ["lgbm", combo]
    rows = []
    for n in models:
        rows.append(score(pred, n).rename(n))
        for t in TIERS:
            rows.append(score(pred[pred["zone"].map(tier) == t], n).rename(f"{n}|{t}"))
    res = pd.DataFrame(rows)

    cov = []
    for scope, mask in [("all", slice(None))] + [(t, pred["zone"].map(tier) == t) for t in TIERS]:
        d = pred.loc[mask]
        cov.append({
            "scope": scope,
            "coverage_raw": interval_coverage(d["y"], d["q10"], d["q90"]),
            "coverage_rounded": interval_coverage(d["y"], d["q10_int"], d["q90_int"]),
            "width_raw": interval_width(d["q10"], d["q90"]),
            "width_rounded": interval_width(d["q10_int"], d["q90_int"]),
        })
    return dict(pred=pred, res=res, cov=pd.DataFrame(cov), best=best, combo=combo,
                models=models, ets=ets, run_ets=run_ets)


def report(r, title):
    res, cov, models = r["res"], r["cov"], r["models"]
    print(f"best baseline: {r['best']}")
    view = res[~res.index.str.contains(r"\|")][["MAE", "RMSE", "bias", "MASE"]].sort_values("MASE")
    print(f"\n{title} (lower is better, MASE under 1 beats seasonal naive):")
    print(view.round(3).to_string())
    for metric in ("MASE", "MAE"):
        print(f"\n{metric} by zone tier:")
        print(pd.DataFrame({t: res.loc[[f"{n}|{t}" for n in models], metric].values for t in TIERS},
                           index=models).round(3).to_string())
    print("\n10% to 90% interval check, target coverage about 0.80 "
          "(rounded = edges moved outward to whole trips):")
    print(cov.round(3).to_string(index=False))
    if r["run_ets"]:
        print(f"\nETS fits that fell back to last week's values: {r['ets'].fallbacks}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hourly", default=str(ROOT / "data" / "hourly.parquet"))
    ap.add_argument("--step-days", type=int, default=1)
    ap.add_argument("--min-history-weeks", type=int, default=8)
    ap.add_argument("--refit-days", type=int, default=7)
    ap.add_argument("--objective", default="poisson")
    ap.add_argument("--no-ets", action="store_true")
    ap.add_argument("--max-origins", type=int)
    ap.add_argument("--drop-features", default="", help="comma list of LightGBM features to leave out")
    ap.add_argument("--tag", default="", help="suffix for output files, e.g. nolag")
    a = ap.parse_args()

    drop = [f for f in a.drop_features.split(",") if f]
    unknown = set(drop) - set(FEATURES)
    if unknown:
        raise SystemExit(f"unknown features: {sorted(unknown)}; choose from {FEATURES}")
    feats = [f for f in FEATURES if f not in drop]

    dev, zones, cut = load_dev(a.hourly)
    wide = to_wide(dev)
    origins = make_origins(wide.index, min_history_hours=168 * a.min_history_weeks,
                           step_days=a.step_days, end=cut)
    if a.max_origins:
        origins = origins[: a.max_origins]
    weekdays = len({o.day_of_week for o in origins})
    if weekdays < 7:
        print(f"WARNING: origins cover only {weekdays} of 7 weekdays, so these results are not "
              "representative. Use --step-days 1 (not a multiple of 7) for any real comparison.")
    print(f"{len(zones)} zones, {len(origins)} origins from {origins[0]} to {origins[-1]}, "
          f"development data ends {cut}")
    print(f"LightGBM features: {feats}", flush=True)

    r = evaluate(wide, origins, zones.set_index("zone")["tier"], a.objective, a.refit_days,
                 feats, run_ets=not a.no_ets)
    suffix = f"_{a.tag}" if a.tag else ""
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    r["res"].to_csv(out / f"models{suffix}.csv")
    r["cov"].to_csv(out / f"intervals{suffix}.csv", index=False)
    r["pred"].to_parquet(out / f"predictions{suffix}.parquet", index=False)
    report(r, "Overall, development backtest")


if __name__ == "__main__":
    main()
