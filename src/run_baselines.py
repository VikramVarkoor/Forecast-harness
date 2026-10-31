"""Session 2 deliverable: baselines ranked on the rolling-origin backtest.
Holds out the final 4 weeks; this script never reads them.

    python src/run_baselines.py [--hourly data/hourly.parquet]
"""
import argparse
from pathlib import Path

import pandas as pd

from src.backtest import make_origins, run_backtest, summarize, to_wide
from src.baselines import BASELINES
from src.zones import select_zones

ROOT = Path(__file__).resolve().parent.parent
HOLDOUT_WEEKS = 4


def load_dev(hourly_path):
    hourly = pd.read_parquet(hourly_path)
    cut = hourly["ts"].max() + pd.Timedelta(hours=1) - pd.Timedelta(weeks=HOLDOUT_WEEKS)
    dev = hourly[hourly["ts"] < cut]  # held-out weeks are dropped here, nowhere else
    zones = select_zones(dev, train_end=cut)
    return dev[dev["zone"].isin(zones["zone"])], zones, cut


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hourly", default=str(ROOT / "data" / "hourly.parquet"))
    ap.add_argument("--step-days", type=int, default=1)
    a = ap.parse_args()
    dev, zones, cut = load_dev(a.hourly)
    wide = to_wide(dev)
    origins = make_origins(wide.index, step_days=a.step_days, end=cut)
    print(f"{len(zones)} zones, {len(origins)} origins, development data ends {cut}")
    tier = zones.set_index("zone")["tier"]
    rows = []
    for name, f in BASELINES.items():
        bt = run_backtest(wide, f, origins)
        rows.append(summarize(bt).rename(name))
        for t in ("top", "mid", "quiet"):
            s = summarize(bt[bt["zone"].map(tier) == t]).rename(f"{name}|{t}")
            rows.append(s)
    res = pd.DataFrame(rows)
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    res.to_csv(out / "baselines.csv")
    overall = res[~res.index.str.contains(r"\|")].sort_values("MASE")
    print(overall.round(3).to_string())


if __name__ == "__main__":
    main()
