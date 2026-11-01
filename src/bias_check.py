"""Diagnose the taxi held-out bias. Read-only: it trains nothing, changes no model and no result.

    python -m src.bias_check

Reads results/predictions.parquet (development backtest) and results/heldout_predictions.parquet
(held-out weeks). This is a look at the held-out weeks after the fact, so what it finds goes in the
README as a finding. It is never used to tune or re-run anything.

Bias is forecast minus actual, trips per zone-hour. Negative means under-forecasting.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MODEL = "lgbm"


def bias(df, col=MODEL):
    return float((df[col] - df["y"]).mean())


def report(dev, held, model=MODEL, history_cols=("mean_same_hour_4w", "lag_168")):
    """Plain numbers answering: which zones, which hours, which days, and was demand higher
    than the history implied. dev/held are long frames with origin, ts, zone, y and model columns."""
    out = {"model": model}
    out["bias_dev"] = bias(dev, model)
    out["mae_held"] = float((held[model] - held["y"]).abs().mean())
    out["bias_held"] = bias(held, model)
    out["mean_actual_dev"] = float(dev["y"].mean())
    out["mean_actual_held"] = float(held["y"].mean())
    out["mean_actual_ratio_held_to_dev"] = out["mean_actual_held"] / out["mean_actual_dev"]
    out["bias_held_pct_of_actual"] = 100 * out["bias_held"] / out["mean_actual_held"]

    # was it the history-based baselines too? if every model under-forecasts, demand ran above history
    out["bias_held_by_model"] = {c: bias(held, c) for c in held.columns
                                 if c not in ("origin", "ts", "zone", "y", "scale", "q10", "q90", "q10_int", "q90_int")
                                 and pd.api.types.is_numeric_dtype(held[c]) and not c.startswith("lgbm_q")}

    # which zones: share of the total shortfall carried by the biggest ones
    z = held.assign(e=held[model] - held["y"]).groupby("zone").agg(bias=("e", "mean"), mean_y=("y", "mean"))
    z["total_miss"] = z["bias"] * (held.groupby("zone").size())
    z["pct_of_zone_demand"] = 100 * z["bias"] / z["mean_y"]
    z = z.sort_values("total_miss")
    tot = z["total_miss"].sum()
    out["zones_negative"] = int((z["bias"] < 0).sum())
    out["zones_total"] = int(len(z))
    out["top5_share_of_total_shortfall_pct"] = float(100 * z["total_miss"].head(5).sum() / tot) if tot else None
    out["worst_zones"] = [{"zone": str(i), "bias": round(float(r.bias), 2), "pct_of_zone_demand": round(float(r.pct_of_zone_demand), 1)}
                          for i, r in z.head(5).iterrows()]

    # which hours and which days
    h = held.assign(e=held[model] - held["y"], hour=pd.to_datetime(held["ts"]).dt.hour).groupby("hour")["e"].mean()
    out["bias_by_hour"] = {int(k): round(float(v), 2) for k, v in h.items()}
    d = held.assign(e=held[model] - held["y"]).groupby("origin")["e"].mean().sort_index()
    out["bias_by_day"] = {str(pd.Timestamp(k).date()): round(float(v), 2) for k, v in d.items()}
    out["days_negative"] = int((d < 0).sum())
    out["days_total"] = int(len(d))
    # demand drift: did actual demand rise through the held-out weeks?
    wk = held.assign(wk=(pd.to_datetime(held["origin"]) - pd.to_datetime(held["origin"]).min()).dt.days // 7).groupby("wk")["y"].mean()
    out["mean_actual_by_held_week"] = {int(k): round(float(v), 2) for k, v in wk.items()}
    return out


def main():
    res = ROOT / "results"
    dev = pd.read_parquet(res / "predictions.parquet")
    held = pd.read_parquet(res / "heldout_predictions.parquet")
    r = report(dev, held)
    (res / "bias_check.json").write_text(json.dumps(r, indent=2))
    print(f"bias, development days   : {r['bias_dev']:+.2f}")
    print(f"bias, held-out days      : {r['bias_held']:+.2f}  ({r['bias_held_pct_of_actual']:+.1f}% of mean demand)")
    print(f"mean actual trips/zone-hr: dev {r['mean_actual_dev']:.1f}, held-out {r['mean_actual_held']:.1f} (ratio {r['mean_actual_ratio_held_to_dev']:.2f})")
    print(f"zones with negative bias : {r['zones_negative']} of {r['zones_total']}")
    print(f"5 worst zones carry      : {r['top5_share_of_total_shortfall_pct']:.0f}% of the total shortfall")
    print("worst zones              :", r["worst_zones"])
    print(f"days with negative bias  : {r['days_negative']} of {r['days_total']}")
    print("bias by model, held-out  :", {k: round(v, 2) for k, v in r["bias_held_by_model"].items()})
    print("mean actual by held-out week:", r["mean_actual_by_held_week"])
    print("bias by hour             :", r["bias_by_hour"])
    print(f"wrote {res / 'bias_check.json'}")


if __name__ == "__main__":
    main()
