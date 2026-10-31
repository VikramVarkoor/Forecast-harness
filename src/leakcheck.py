"""Leak checks, usable on any feature pipeline of the form wide_frame -> long feature frame.

1. truncation_invariance: features for the horizon rows of an origin must not change when
   everything at or after the origin is removed. A feature that peeks forward fails this.
2. matches_raw: pipeline output must equal an independent recomputation from raw history.
"""
import numpy as np
import pandas as pd

H = 24


def _future_frame(wide, origin):
    """History before origin plus empty (NaN) horizon rows, so the pipeline sees no future."""
    hist = wide.loc[wide.index < origin]
    idx = pd.date_range(hist.index[0], origin + pd.Timedelta(hours=H - 1), freq="h")
    return hist.reindex(idx)


def truncation_invariance(pipeline, wide, origins, cols):
    """Returns a list of (origin, column, max_abs_diff) violations. Empty means clean."""
    full = pipeline(wide)
    bad = []
    for o in origins:
        trunc = pipeline(_future_frame(wide, o))
        horizon = pd.date_range(o, periods=H, freq="h")
        a = full.loc[full.index.get_level_values("ts").isin(horizon), cols].sort_index()
        b = trunc.loc[trunc.index.get_level_values("ts").isin(horizon), cols].sort_index()
        both = a.notna().values & b.notna().values
        mismatch_na = (a.isna().values != b.isna().values).any(axis=0)
        diff = np.where(both, np.abs(a.values - b.values), 0.0).max(axis=0)
        for j, c in enumerate(cols):
            if diff[j] > 1e-9 or mismatch_na[j]:
                bad.append((o, c, float(diff[j])))
    return bad


def matches_raw(pipeline, raw_fn, wide, ts_zone_pairs, cols, tol=1e-9):
    """Compare pipeline features with an independent recomputation. Returns violations."""
    feats = pipeline(wide)
    bad = []
    for ts, z in ts_zone_pairs:
        want = raw_fn(wide, ts, z)
        got = feats.loc[(ts, z)]
        for c in cols:
            w, g = want[c], got[c]
            if (np.isnan(w) and np.isnan(g)) or abs(w - g) <= tol:
                continue
            bad.append((ts, z, c, float(w), float(g)))
    return bad
