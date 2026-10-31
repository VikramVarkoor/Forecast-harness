import pandas as pd

from src.baselines import (mean_same_hour_4w, naive_last_hour, same_hour_last_week,
                           same_hour_yesterday)
from src.backtest import make_origins, run_backtest, summarize


def _ramp():
    idx = pd.date_range("2025-03-01", periods=24 * 40, freq="h")
    return pd.DataFrame({1: range(len(idx))}, index=idx, dtype=float)  # value = hour counter


def test_baselines_pick_the_right_hours():
    w = _ramp()
    o = pd.Timestamp("2025-03-31")
    hist = w.loc[w.index < o]
    n = len(hist)  # value at index i is i
    assert (naive_last_hour(hist)[1] == n - 1).all()
    assert list(same_hour_yesterday(hist)[1]) == [n - 24 + h for h in range(24)]
    assert list(same_hour_last_week(hist)[1]) == [n - 168 + h for h in range(24)]
    want = [sum(n - 168 * k + h for k in range(1, 5)) / 4 for h in range(24)]
    assert list(mean_same_hour_4w(hist)[1]) == want
    assert same_hour_yesterday(hist).index[0] == o


def test_harness_gives_forecaster_no_future(wide):
    seen = []

    def spy(hist):
        seen.append(hist.index[-1])
        return same_hour_yesterday(hist)

    origins = make_origins(wide.index)[:5]
    run_backtest(wide, spy, origins)
    assert all(last < o for last, o in zip(seen, origins))
    assert all(last == o - pd.Timedelta(hours=1) for last, o in zip(seen, origins))


def test_weekly_baseline_beats_naive_on_weekly_data(wide):
    origins = make_origins(wide.index)
    res = {n: summarize(run_backtest(wide, f, origins)) for n, f in
           {"naive": naive_last_hour, "week": same_hour_last_week}.items()}
    assert res["week"]["MAE"] < res["naive"]["MAE"]
