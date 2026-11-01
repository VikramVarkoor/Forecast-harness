import numpy as np
import pandas as pd

from src.bias_check import report


def frame(n_days=14, shift=0.0, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for d in range(n_days):
        for h in range(24):
            for z in (1, 2, 3):
                y = 20 * z + rng.normal(0, 1)
                rows.append(dict(origin=pd.Timestamp("2025-01-01") + pd.Timedelta(days=d),
                                 ts=pd.Timestamp("2025-01-01") + pd.Timedelta(days=d, hours=h),
                                 zone=z, y=y, lgbm=y + shift, base=y + shift / 2))
    return pd.DataFrame(rows)


def test_report_recovers_planted_under_forecast():
    r = report(frame(shift=0.0), frame(shift=-8.0, seed=1))
    assert abs(r["bias_dev"]) < 0.2
    assert abs(r["bias_held"] + 8.0) < 0.2
    assert r["zones_negative"] == 3 and r["days_negative"] == r["days_total"]
    assert abs(r["bias_held_by_model"]["base"] + 4.0) < 0.2
    assert len(r["bias_by_hour"]) == 24


def test_report_handles_zero_bias():
    r = report(frame(), frame(seed=2))
    assert abs(r["bias_held"]) < 0.2
