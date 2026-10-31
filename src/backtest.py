"""Rolling-origin backtest, expanding window, 24-hour horizon.

A forecaster is f(hist, origin) -> DataFrame (24 rows, zones as columns). The harness slices
`hist` to rows strictly before the origin, so a forecaster cannot see the future by construction.
Every model and baseline goes through run_backtest unchanged. Domain B reuses it as is.
"""
import numpy as np
import pandas as pd

from src.metrics import mae, rmse, bias, seasonal_naive_scale

H = 24


def to_wide(long_df, value="trips", time="ts", key="zone"):
    return long_df.pivot(index=time, columns=key, values=value).sort_index()


def make_origins(index, min_history_hours=168 * 4, step_days=1, end=None):
    """Midnight origins with enough history behind them and a full horizon ahead."""
    first = index[0].normalize() + pd.Timedelta(hours=min_history_hours)
    first = first.normalize() + pd.Timedelta(days=1) if first != first.normalize() else first
    last_ok = (end or index[-1] + pd.Timedelta(hours=1)) - pd.Timedelta(hours=H)
    return list(pd.date_range(first, last_ok, freq=f"{step_days}D"))


def run_backtest(wide, forecaster, origins):
    """Returns a long frame: origin, ts, zone, y, yhat, and the per-origin-zone MASE scale."""
    rows = []
    for o in origins:
        hist = wide.loc[wide.index < o]
        actual = wide.loc[o : o + pd.Timedelta(hours=H - 1)]
        if len(actual) < H:
            continue
        pred = forecaster(hist)
        pred = pred.reindex(actual.index)
        scale = pd.Series({z: seasonal_naive_scale(hist[z].values[-168 * 4 :]) for z in hist.columns})
        long = pd.DataFrame(
            {
                "origin": o,
                "ts": np.repeat(actual.index.values, actual.shape[1]),
                "zone": np.tile(actual.columns.values, H),
                "y": actual.values.ravel(),
                "yhat": pred.values.ravel(),
            }
        )
        long["scale"] = long["zone"].map(scale)
        rows.append(long)
    return pd.concat(rows, ignore_index=True)


def summarize(bt):
    """One row of metrics for a backtest frame. MASE is the mean of per-zone MASE, so every
    zone counts equally and quiet zones are not drowned out."""
    per_zone = bt.groupby("zone").apply(
        lambda g: pd.Series({"mae": mae(g.y, g.yhat), "scale": g["scale"].mean()}), include_groups=False
    )
    per_zone["mase"] = per_zone["mae"] / per_zone["scale"].replace(0, np.nan)
    return pd.Series(
        {
            "MAE": mae(bt.y, bt.yhat),
            "RMSE": rmse(bt.y, bt.yhat),
            "bias": bias(bt.y, bt.yhat),
            "MASE": float(per_zone["mase"].mean()),
            "n_origins": bt["origin"].nunique(),
        }
    )
