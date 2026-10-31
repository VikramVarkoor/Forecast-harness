import datetime as dt

import numpy as np
import pandas as pd

from src.analyze import block_bootstrap, breakdown, compare, day_label, daily_mae, worst_days


def _pred(days=28, zones=(1, 2), better=True, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for d in range(days):
        o = pd.Timestamp("2026-01-05") + pd.Timedelta(days=d)
        for z in zones:
            for h in range(24):
                y = 50 + 20 * np.sin(h / 24 * 2 * np.pi) + rng.normal(0, 2)
                rows.append({"origin": o, "ts": o + pd.Timedelta(hours=h), "zone": z, "y": y,
                             "m": y + rng.normal(0, 1 if better else 6), "b": y + rng.normal(0, 4)})
    return pd.DataFrame(rows).rename(columns={"m": "lgbm", "b": "base"})


def test_bootstrap_interval_excludes_zero_for_a_real_gain_and_includes_it_for_none():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2026-01-01", periods=120)
    real = pd.Series(1.0 + rng.normal(0, 0.3, 120), index=idx)
    none = pd.Series(rng.normal(0, 1.0, 120), index=idx)
    m, lo, hi = block_bootstrap(real)
    assert lo > 0 and lo < m < hi
    m, lo, hi = block_bootstrap(none)
    assert lo < 0 < hi


def test_compare_sign_and_win_rate():
    p = _pred(better=True)
    c = compare(p, "lgbm", "base", {1: "top", 2: "mid"}).set_index("scope")
    assert c.loc["all", "mae_gain"] > 0 and c.loc["all", "win_rate"] > 0.9
    p = _pred(better=False)
    c = compare(p, "lgbm", "base", {1: "top", 2: "mid"}).set_index("scope")
    assert c.loc["all", "mae_gain"] < 0


def test_day_labels():
    cal = {dt.date(2026, 1, 1): "New Year's Day", dt.date(2026, 11, 26): "Thanksgiving"}
    dst = {dt.date(2026, 3, 8)}
    assert day_label(dt.date(2026, 1, 1), cal, dst) == "holiday: New Year's Day"
    assert day_label(dt.date(2025, 12, 31), cal, dst) == "day before New Year's Day"
    assert day_label(dt.date(2026, 11, 27), cal, dst) == "day after Thanksgiving"
    assert "daylight" in day_label(dt.date(2026, 3, 8), cal, dst)
    assert day_label(dt.date(2026, 2, 23), cal, dst).startswith("unexplained")


def test_worst_days_finds_the_planted_bad_day():
    p = _pred()
    bad = p["origin"] == pd.Timestamp("2026-01-12")
    p.loc[bad, "lgbm"] += 80
    top = worst_days(p, "lgbm", "base", k=3)
    assert top.index[0] == dt.date(2026, 1, 12)
    assert len(top) == 3 and "reason" in top.columns


def test_breakdown_shape_and_daily_mae_length():
    p = _pred()
    b = breakdown(p, p["ts"].dt.hour, "hour", "lgbm", "base")
    assert len(b) == 24 and {"model_mae", "baseline_mae", "model_over_baseline"} <= set(b.columns)
    assert len(daily_mae(p, "lgbm")) == 28
