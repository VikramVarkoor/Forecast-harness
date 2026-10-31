"""Plots for session 1: daily and weekly pattern for 3 zones (busy, mid, quiet)."""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.run_baselines import load_dev  # noqa: E402


def main(hourly=ROOT / "data" / "hourly.parquet"):
    dev, zones, _ = load_dev(hourly)
    pick = [zones[zones.tier == t].iloc[0]["zone"] for t in ("top", "mid", "quiet")]
    wide = dev.pivot(index="ts", columns="zone", values="trips")
    fig, ax = plt.subplots(3, 2, figsize=(12, 9))
    for i, z in enumerate(pick):
        s = wide[z]
        last = s.iloc[-24 * 14 :]
        ax[i, 0].plot(last.index, last.values, lw=0.9)
        ax[i, 0].set_title(f"Zone {z}: last 14 days")
        ax[i, 0].xaxis.set_major_locator(mdates.DayLocator(interval=3))
        ax[i, 0].xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        how = s.groupby([s.index.day_of_week, s.index.hour]).mean()
        ax[i, 1].plot(range(168), how.values, lw=0.9)
        ax[i, 1].set_title(f"Zone {z}: mean by hour of week (Mon 00:00 first)")
        ax[i, 1].set_xticks(range(0, 168, 24))
    fig.tight_layout()
    (ROOT / "results").mkdir(exist_ok=True)
    fig.savefig(ROOT / "results" / "weekly_pattern.png", dpi=130)
    print("wrote results/weekly_pattern.png")


if __name__ == "__main__":
    main()
