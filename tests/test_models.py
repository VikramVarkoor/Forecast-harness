import numpy as np
import pandas as pd

from src.backtest import make_origins, run_backtest
from src.features import build_features, holiday_dates
from src.metrics import interval_coverage, interval_width, round_interval_outward
from src.models import ETSForecaster, LGBMForecaster

FAST = dict(n_estimators=20, num_leaves=15, min_data_in_leaf=10, num_threads=1)


def _hist(wide, day):
    o = wide.index[0].normalize() + pd.Timedelta(days=day)
    return o, wide.loc[wide.index < o]


def test_ets_recovers_a_clean_weekly_pattern():
    idx = pd.date_range("2025-02-01", periods=24 * 56, freq="h")
    shape = 50 + 40 * np.sin(np.arange(len(idx)) / 168 * 2 * np.pi * 7) + 10 * (idx.day_of_week.values >= 5)
    w = pd.DataFrame({1: shape, 2: shape * 0.5}, index=idx)
    o = idx[0].normalize() + pd.Timedelta(days=49)
    f = ETSForecaster()(w.loc[w.index < o])
    assert list(f.index) == list(pd.date_range(o, periods=24, freq="h"))
    assert (f >= 0).all().all()
    assert np.abs(f.values - w.loc[o : o + pd.Timedelta(hours=23)].values).mean() < 1.0


def test_lgbm_shape_index_and_nonnegative(wide):
    o, hist = _hist(wide, 50)
    f = LGBMForecaster(params=FAST)(hist)
    assert list(f.index) == list(pd.date_range(o, periods=24, freq="h"))
    assert list(f.columns) == list(wide.columns)
    assert (f >= 0).all().all() and f.notna().all().all()


def test_model_chain_ignores_the_future(wide):
    """Scramble everything from the origin day onward. Training, features and forecast must not
    change, because none of it is allowed to see those rows."""
    o, _ = _hist(wide, 50)
    scrambled = wide.copy()
    rng = np.random.default_rng(9)
    scrambled.loc[scrambled.index >= o] = rng.uniform(0, 500, scrambled.loc[scrambled.index >= o].shape)
    for make in (lambda: LGBMForecaster(params=FAST), lambda: ETSForecaster()):
        a = run_backtest(wide, make(), [o])["yhat"].to_numpy()
        b = run_backtest(scrambled, make(), [o])["yhat"].to_numpy()
        assert np.allclose(a, b, atol=1e-6)


def test_quantile_models_straddle_the_point_forecast_on_average(wide):
    o, hist = _hist(wide, 50)
    lo = LGBMForecaster("quantile", alpha=0.1, params=FAST)(hist).to_numpy().mean()
    hi = LGBMForecaster("quantile", alpha=0.9, params=FAST)(hist).to_numpy().mean()
    assert lo < hi


def test_refit_schedule_is_weekly(wide):
    f = LGBMForecaster(refit_days=7, params=FAST)
    origins = make_origins(wide.index, min_history_hours=168 * 5)[:15]
    run_backtest(wide, f, origins)
    assert f.n_fits == int(np.ceil(15 / 7))


def test_holiday_flag_marks_known_dates_only(wide):
    dates = holiday_dates(wide.index)
    assert pd.Timestamp("2025-02-17") in dates       # Presidents Day
    assert pd.Timestamp("2025-02-18") not in dates
    feats = build_features(wide)
    ts = feats.index.get_level_values("ts")
    flagged = set(ts[feats["holiday"].to_numpy() == 1].normalize().unique())
    assert pd.Timestamp("2025-02-17") in flagged and pd.Timestamp("2025-02-18") not in flagged


def test_interval_metrics_hand_checked():
    y, lo, hi = [1, 5, 9, 12], [0, 4, 10, 10], [2, 6, 11, 14]
    assert interval_coverage(y, lo, hi) == 0.75      # 9 is below its lower edge of 10
    assert interval_width(lo, hi) == 2.25            # widths 2, 2, 1, 4


def test_outward_rounding_fixes_integer_edge_artifact():
    y = [0, 0, 1, 2]
    lo, hi = [0.4] * 4, [1.2] * 4
    assert interval_coverage(y, lo, hi) == 0.25      # a real-valued edge excludes the zeros and the 2
    lo2, hi2 = round_interval_outward(lo, hi)
    assert list(lo2) == [0.0] * 4 and list(hi2) == [2.0] * 4
    assert interval_coverage(y, lo2, hi2) == 1.0


def test_holiday_calendar_is_cached():
    from src.features import _calendar
    _calendar.cache_clear()
    idx = pd.date_range("2025-10-01", periods=24, freq="h")
    holiday_dates(idx); holiday_dates(idx)
    assert _calendar.cache_info().hits >= 1
