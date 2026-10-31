"""Final held-out evaluation. RUN ONCE, after every modelling decision is frozen.

    python -m src.final_eval                                   # full model
    python -m src.final_eval --drop-features lag_24,roll24_l24  # only if D18 said switch

Scores the last 4 weeks, which no earlier script reads. Refuses a second run unless --force, and
records every run in results/heldout_run.json so the README can state exactly how many times
these weeks were scored. Nothing is chosen on the held-out weeks: zones and the cut come from
development data, and the baseline used in the combination is fixed from the development result.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.analyze import compare
from src.backtest import to_wide
from src.features import FEATURES
from src.run_baselines import load_dev
from src.run_models import evaluate, report

ROOT = Path(__file__).resolve().parent.parent
MARKER = "heldout_run.json"


def guard(results_dir: Path, force: bool, args: dict) -> Path:
    """Record this run, and refuse if the held-out weeks were already scored."""
    results_dir.mkdir(parents=True, exist_ok=True)
    path = results_dir / MARKER
    prior = json.loads(path.read_text()) if path.exists() else {"runs": []}
    if prior["runs"] and not force:
        raise SystemExit(
            f"The held-out weeks were already scored (see {path}). Scoring them again after seeing "
            "the result is how a test set stops being a test set. Use --force only to rerun after a "
            "crash or a bug fix, and the README will have to say so."
        )
    prior["runs"].append({"started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "args": args, "forced": bool(force and prior["runs"]), "status": "started"})
    path.write_text(json.dumps(prior, indent=2))
    return path


def finish(path: Path):
    prior = json.loads(path.read_text())
    prior["runs"][-1]["status"] = "done"
    path.write_text(json.dumps(prior, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hourly", default=str(ROOT / "data" / "hourly.parquet"))
    ap.add_argument("--results-dir", default=str(ROOT / "results"))
    ap.add_argument("--drop-features", default="")
    ap.add_argument("--best-baseline", default="mean_same_hour_4w",
                    help="fixed from the development result, never re-picked on held-out weeks")
    ap.add_argument("--no-ets", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    drop = [f for f in a.drop_features.split(",") if f]
    unknown = set(drop) - set(FEATURES)
    if unknown:
        raise SystemExit(f"unknown features: {sorted(unknown)}")
    feats = [f for f in FEATURES if f not in drop]
    out = Path(a.results_dir)
    marker = guard(out, a.force, {"drop_features": drop, "best_baseline": a.best_baseline})

    dev, zones, cut = load_dev(a.hourly)           # zones and the cut come from development data only
    hourly = pd.read_parquet(a.hourly)
    full = hourly[hourly["zone"].isin(zones["zone"])]
    wide = to_wide(full)
    last = wide.index[-1] + pd.Timedelta(hours=1) - pd.Timedelta(hours=24)
    origins = list(pd.date_range(cut, last, freq="D"))
    print(f"HELD-OUT: {len(origins)} daily origins from {origins[0]} to {origins[-1]}, "
          f"{len(zones)} zones, LightGBM features {feats}", flush=True)

    tier = zones.set_index("zone")["tier"]
    r = evaluate(wide, origins, tier, features=feats, run_ets=not a.no_ets, best_baseline=a.best_baseline)
    r["res"].to_csv(out / "heldout.csv")
    r["cov"].to_csv(out / "heldout_intervals.csv", index=False)
    r["pred"].to_parquet(out / "heldout_predictions.parquet", index=False)
    report(r, "HELD-OUT result")

    cmp = compare(r["pred"], "lgbm", a.best_baseline, tier)
    cmp.to_csv(out / "heldout_paired.csv", index=False)
    print(f"\nPaired comparison, lgbm vs {a.best_baseline} on {len(origins)} held-out days "
          "(mae_gain positive favours LightGBM; only 4 weekly blocks, so the interval is crude):")
    print(cmp.round(3).to_string(index=False))
    finish(marker)
    print(f"\nrecorded in {marker}. Do not run this again.")


if __name__ == "__main__":
    main()
