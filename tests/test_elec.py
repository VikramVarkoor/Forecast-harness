import numpy as np
import pandas as pd
import pytest

from src import elec_data, elec_features as ef, elec_run
from src.leakcheck import matches_raw, truncation_invariance

COLS = ["lag_24", "lag_168", "roll24_l24", "roll4w_sh", "lvl"]


def make_wide(days=900, seed=1, cols=("DE", "FR", "FI", "ES")):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2018-01-01", periods=days * 24, freq="h")
    d = {}
    for i, c in enumerate(cols):
        h = idx.hour.values; dw = idx.day_of_week.values; doy = idx.day_of_year.values
        base = (1 + i) * 10000 * (1 + 0.25 * np.sin((h - 6) / 24 * 2 * np.pi) + 0.2 * np.cos(doy / 365 * 2 * np.pi) - 0.1 * (dw >= 5))
        d[c] = base + rng.normal(0, 150, len(idx))
    return pd.DataFrame(d, index=idx)


def test_features_match_independent_recomputation():
    w = make_wide(days=120)
    pairs = [(w.index[i], c) for i in (1500, 2000, 2500) for c in ("DE", "FI")]
    assert matches_raw(ef.build_features, ef.features_from_raw, w, pairs, COLS, tol=1e-9) == []


def test_features_do_not_peek_forward():
    w = make_wide(days=120)
    origins = [w.index[0] + pd.Timedelta(days=d) for d in (80, 90)]
    assert truncation_invariance(ef.build_features, w, origins, COLS) == []


def test_a_planted_leak_is_caught():
    def leaky(w):
        f = ef.build_features(w)
        f["lag_24"] = (w.shift(-24) / w.shift(24).rolling(ef.LVL, min_periods=ef.LVL).mean()).stack(future_stack=True).to_numpy()
        return f
    w = make_wide(days=120)
    assert truncation_invariance(leaky, w, [w.index[0] + pd.Timedelta(days=85)], ["lag_24"]) != []


def test_local_clock_follows_daylight_saving():
    # 12:00 UTC is 13:00 local in winter and 14:00 in summer in Berlin; Helsinki is one hour further on
    idx = pd.DatetimeIndex(["2019-01-15 12:00", "2019-07-15 12:00"])
    assert list(ef.local_fields(idx, "DE")["hour"]) == [13, 14]
    assert list(ef.local_fields(idx, "FI")["hour"]) == [14, 15]


def test_holiday_flag_uses_the_country_calendar():
    idx = pd.date_range("2019-12-25 10:00", periods=1, freq="h")
    assert ef.local_fields(idx, "DE")["holiday"][0] == 1
    assert ef.local_fields(pd.date_range("2019-11-13 10:00", periods=1, freq="h"), "DE")["holiday"][0] == 0


def test_split_leaves_28_origin_days():
    w = make_wide(days=100)
    w = w.iloc[:-1]  # data ends at 22:00, like the real file
    cut, last = elec_run.split(w)
    assert len(pd.date_range(cut, last, freq="D")) == 28
    assert last + pd.Timedelta(hours=23) <= w.index[-1]


def test_country_rule_and_cleaning():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2015-01-01", periods=24 * 400, freq="h", tz="UTC")
    d = {}
    for cc, mean in (("AA", 9e4), ("BB", 5e4), ("CC", 8e4), ("DD", 7e4)):
        d[f"{cc}_actual"] = mean + rng.normal(0, 500, len(idx)); d[f"{cc}_tso"] = mean + rng.normal(0, 500, len(idx))
    df = pd.DataFrame(d, index=idx)
    df.loc[df.index[100:105], "AA_actual"] = np.nan          # short gap, fine
    df.loc[df.index[200:260], "CC_actual"] = np.nan          # 60 h gap, ineligible
    df.loc[df.index[:3], "AA_tso"] = np.nan                      # leading gap in the operator forecast
    df.loc[df.index[-2:], "DD_tso"] = np.nan                     # trailing gap
    df.loc[df.index[300:310], "DD_tso"] = np.nan                  # 10 h hole in the operator forecast: still eligible, left unfilled
    chosen, t = elec_data.pick(df, n=2)
    assert chosen == ["AA", "DD"]                              # CC dropped for the gap, BB too small
    act, tso, filled = elec_data.clean(df, chosen)
    assert act.index[0] == df.index[3].tz_localize(None) and act.index[-1] == df.index[-3].tz_localize(None)
    assert tso["DD"].isna().sum() == 10 and filled["tso_left_missing"] == 10
    assert filled["actual"] == 5 and not act.isna().any().any() and act.index.tz is None


def test_end_to_end_runs_and_operator_row_is_untouched():
    w = make_wide(days=900)
    tso = w * 1.01
    origins = list(pd.date_range(w.index[-1].normalize() - pd.Timedelta(days=4), periods=3, freq="D"))
    tso.loc[origins[1]: origins[1] + pd.Timedelta(hours=3), "DE"] = np.nan   # 4 operator hours missing inside the scored days
    pred = elec_run.evaluate(w, tso, origins, run_q=True, rounds=25, log=lambda *_: None)
    assert len(pred) == 3 * 24 * w.shape[1] - 4 and pred.attrs["dropped_rows"] == 4
    assert np.allclose(pred[elec_run.TSO], pred["y"] * 1.01, rtol=1e-9)
    res = elec_run.table(pred, list(elec_run.BASELINES) + [elec_run.TSO, "lgbm"])
    assert res.loc["lgbm", "MAE"] < res.loc["naive_last_hour", "MAE"] * 3 and np.isfinite(res.values).all()
