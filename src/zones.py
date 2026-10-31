"""Zone selection: 20 busiest, 5 mid-volume, 5 quiet, ranked on TRAINING hours only."""
import pandas as pd


def select_zones(hourly: pd.DataFrame, train_end, n_top=20, n_mid=5, n_quiet=5, min_total=1000):
    tr = hourly[hourly["ts"] < train_end]
    tot = tr.groupby("zone")["trips"].sum().sort_values(ascending=False)
    tot = tot[tot >= min_total]  # a zone with almost no trips is a data curiosity, not a quiet zone
    top = list(tot.index[:n_top])
    rest = tot.iloc[n_top:]
    quiet = list(rest.index[-n_quiet:])
    mid_pool = rest.iloc[: len(rest) - n_quiet]
    c = len(mid_pool) // 2
    mid = list(mid_pool.index[max(0, c - n_mid // 2) : max(0, c - n_mid // 2) + n_mid])
    return pd.DataFrame(
        [(z, "top") for z in top] + [(z, "mid") for z in mid] + [(z, "quiet") for z in quiet],
        columns=["zone", "tier"],
    ).merge(tot.rename("total_trips").reset_index(), on="zone")
