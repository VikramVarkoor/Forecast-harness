"""Step 4a: analysis of the development backtest. Reads results/predictions.parquet.

    python -m src.analyze [--baseline mean_same_hour_4w]

Everything here is development data only. The held-out weeks are never read.
"""
import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.audit import _nth_sunday
from src.backtest import to_wide
from src.features import holiday_dates
from src.models import LGBMForecaster
from src.run_baselines import load_dev

ROOT = Path(__file__).resolve().parent.parent
MODEL = "lgbm"


def abs_err(pred, col):
    return (pred[col] - pred["y"]).abs()


def daily_mae(pred, col):
    """Mean absolute error per origin day, over every zone and hour that day."""
    return abs_err(pred, col).groupby(pred["origin"]).mean().sort_index()


def block_bootstrap(diff: pd.Series, block=7, n_boot=2000, seed=0):
    """Mean of a daily paired difference with a 95% interval, resampling whole 7-day blocks so
    neighbouring days (which are not independent) stay together. Returns (mean, lo, hi)."""
    x = diff.sort_index().to_numpy(float)
    nb = int(np.ceil(len(x) / block))
    blocks = [x[i * block : (i + 1) * block] for i in range(nb)]
    rng = np.random.default_rng(seed)
    means = np.empty(n_boot)
    for i in range(n_boot):
        pick = rng.integers(0, nb, nb)
        means[i] = np.concatenate([blocks[j] for j in pick]).mean()
    return float(x.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def compare(pred, model, base, tier):
    """Paired comparison on daily MAE. Gain is baseline minus model, so positive means the model
    is better. win_rate is the share of days the model had the lower error."""
    rows = []
    for scope in ["all", "top", "mid", "quiet"]:
        d = pred if scope == "all" else pred[pred["zone"].map(tier) == scope]
        if len(d) == 0:
            continue
        dm, db = daily_mae(d, model), daily_mae(d, base)
        mean, lo, hi = block_bootstrap(db - dm)
        rows.append({"scope": scope, "baseline_mae": abs_err(d, base).mean(), "model_mae": abs_err(d, model).mean(),
                     "mae_gain": mean, "ci95_lo": lo, "ci95_hi": hi,
                     "win_rate": float((dm < db).mean()), "n_days": len(dm)})
    return pd.DataFrame(rows)


def dst_days(years):
    out = set()
    for y in years:
        out.add(_nth_sunday(y, 3, 2).date())
        out.add(_nth_sunday(y, 11, 1).date())
    return out


def day_label(d, cal, dst):
    """Reason we can state from the calendar alone. Anything else is flagged for a human check."""
    one = pd.Timedelta(days=1)
    if d in dst:
        return "daylight saving change day (data artifact)"
    if d in cal:
        return f"holiday: {cal.get(d)}"
    nxt, prv = cal.get((pd.Timestamp(d) + one).date()), cal.get((pd.Timestamp(d) - one).date())
    if nxt:
        return f"day before {nxt}"
    if prv:
        return f"day after {prv}"
    return "unexplained: check weather and events"


def worst_days(pred, model, base, k=10):
    import holidays

    years = range(pred["origin"].dt.year.min() - 1, pred["origin"].dt.year.max() + 2)
    cal = holidays.country_holidays("US", subdiv="NY", years=years)
    dst = dst_days(years)
    d = pred.assign(date=pred["origin"].dt.date, e=abs_err(pred, model), b=abs_err(pred, base))
    g = d.groupby("date").agg(model_abs_err=("e", "sum"), baseline_abs_err=("b", "sum"),
                              actual=("y", "sum"), forecast=(model, "sum"))
    g["forecast_minus_actual"] = g["forecast"] - g["actual"]
    top = g.sort_values("model_abs_err", ascending=False).head(k).copy()
    top["weekday"] = [pd.Timestamp(x).day_name() for x in top.index]
    top["reason"] = [day_label(x, cal, dst) for x in top.index]
    return top


def breakdown(pred, key, name, model, base):
    g = pred.assign(m=abs_err(pred, model), b=abs_err(pred, base)).groupby(key)[["m", "b"]].mean()
    g.columns = ["model_mae", "baseline_mae"]
    g["model_over_baseline"] = g["model_mae"] / g["baseline_mae"]
    g.index.name = name
    return g


def feature_importance(wide):
    f = LGBMForecaster()
    f._fit(wide)
    imp = pd.Series(f.model.feature_importance("gain"), index=f.model.feature_name())
    return (imp / imp.sum()).sort_values(ascending=False)


def figures(pred, zone, hourly_view, out):
    d = pred[(pred["zone"] == zone) & (pred["origin"] >= pred["origin"].max() - pd.Timedelta(days=6))].sort_values("ts")
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.fill_between(d["ts"], d["q10_int"], d["q90_int"], alpha=0.25, label="10% to 90% band")
    ax.plot(d["ts"], d["y"], lw=1.2, label="actual")
    ax.plot(d["ts"], d[MODEL], lw=1.2, label="LightGBM forecast")
    ax.set_title(f"Zone {zone}: last 7 forecast days of the development backtest")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "forecast_vs_actual.png", dpi=130)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(hourly_view.index, hourly_view["baseline_mae"], label="4-week same-hour mean")
    ax.plot(hourly_view.index, hourly_view["model_mae"], label="LightGBM")
    ax.set_xlabel("hour of day")
    ax.set_ylabel("MAE (trips per zone-hour)")
    ax.set_title("Error by hour of day")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "error_by_hour.png", dpi=130)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hourly", default=str(ROOT / "data" / "hourly.parquet"))
    ap.add_argument("--pred", default=str(ROOT / "results" / "predictions.parquet"))
    ap.add_argument("--baseline", default="mean_same_hour_4w")
    a = ap.parse_args()

    pred = pd.read_parquet(a.pred)
    dev, zones, _ = load_dev(a.hourly)
    tier = zones.set_index("zone")["tier"]
    out = ROOT / "results" / "analysis"
    out.mkdir(parents=True, exist_ok=True)
    pd.set_option("display.width", 200)

    cmp = compare(pred, MODEL, a.baseline, tier)
    print(f"\nPaired comparison, {MODEL} vs {a.baseline}. mae_gain is baseline minus model in trips per "
          "zone-hour, so positive favours the model. 95% interval from a weekly block bootstrap.")
    print(cmp.round(3).to_string(index=False))

    hod = breakdown(pred, pred["ts"].dt.hour, "hour", MODEL, a.baseline)
    dow = breakdown(pred, pred["ts"].dt.day_of_week, "weekday_0_is_monday", MODEL, a.baseline)
    hol = pred["ts"].dt.normalize().isin(holiday_dates(pred["ts"]))
    hday = breakdown(pred, np.where(hol, "holiday", "ordinary day"), "day_type", MODEL, a.baseline)
    print("\nError by hour of day:")
    print(hod.round(3).to_string())
    print("\nError by weekday:")
    print(dow.round(3).to_string())
    print("\nHolidays versus ordinary days:")
    print(hday.round(3).to_string())
    print(f"(holiday rows: {int(hol.sum()):,} of {len(pred):,})")

    wd = worst_days(pred, MODEL, a.baseline)
    print("\nTen worst days for the model, by total absolute error across the 30 zones:")
    print(wd.round(0).to_string())

    imp = feature_importance(to_wide(dev))
    print("\nLightGBM feature importance (share of total gain, one fit on all development data):")
    print(imp.round(3).to_string())

    cmp.to_csv(out / "paired_comparison.csv", index=False)
    hod.to_csv(out / "by_hour.csv")
    dow.to_csv(out / "by_weekday.csv")
    hday.to_csv(out / "by_day_type.csv")
    wd.to_csv(out / "worst_days.csv")
    imp.rename("gain_share").to_csv(out / "feature_importance.csv")
    zone = zones[zones["tier"] == "top"].iloc[0]["zone"]
    figures(pred, zone, hod, out)
    print(f"\nwrote tables and two figures to {out}")


if __name__ == "__main__":
    main()
