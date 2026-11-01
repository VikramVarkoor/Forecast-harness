import numpy as np
import pandas as pd
from src import opsd_download as o


def _csv(tmp_path):
    ts = pd.date_range("2015-01-01", periods=24 * 30, freq="h", tz="UTC")
    rng = np.random.default_rng(0)
    d = pd.DataFrame({"utc_timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "AT_load_actual_entsoe_transparency": 5000 + rng.normal(0, 100, len(ts)),
                      "AT_load_forecast_entsoe_transparency": 5000 + rng.normal(0, 100, len(ts)),
                      "DE_50hertz_load_actual_entsoe_transparency": 1.0,      # sub-area, must be ignored
                      "FR_load_actual_entsoe_transparency": 4e4 + rng.normal(0, 1e3, len(ts)),
                      "FR_load_forecast_entsoe_transparency": np.nan,
                      "AT_solar_generation_actual": 1.0})
    d.loc[10:15, "AT_load_actual_entsoe_transparency"] = np.nan
    p = tmp_path / "x.csv"; d.to_csv(p, index=False); return p


def test_load_keeps_only_national_load(tmp_path):
    df = o.load(_csv(tmp_path))
    assert sorted(df.columns) == ["AT_actual", "AT_tso", "FR_actual", "FR_tso"]
    assert str(df.index.tz) == "UTC" and df.index.is_monotonic_increasing


def test_coverage_counts_gap_and_missing(tmp_path):
    cov = o.coverage(o.load(_csv(tmp_path))).set_index("country")
    assert cov.loc["AT", "longest_gap_hours"] == 6
    assert abs(cov.loc["AT", "missing_actual_pct"] - 100 * 6 / (24 * 30)) < 0.01
    assert cov.loc["FR", "hours_with_both"] == 0 and cov.loc["FR", "tso_missing_pct"] == 100.0
