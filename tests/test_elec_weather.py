import numpy as np
import pandas as pd
import pytest

from src import elec_features as ef, elec_weather_run as ew, opsd_weather
from src.baselines import BASELINES


def synth(days=500, seed=2, cols=("DE", "FR", "FI")):
    """Load that really depends on temperature, so a model given temperature should do better."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2017-01-01", periods=days * 24, freq="h")
    doy = idx.day_of_year.values; h = idx.hour.values
    temp = pd.DataFrame({c: 10 + 12 * np.cos((doy - 200) / 365 * 2 * np.pi) + 5 * np.sin((h - 9) / 24 * 2 * np.pi) + rng.normal(0, 4, len(idx)) for c in cols}, index=idx)
    load = pd.DataFrame({c: (i + 1) * 10000 * (1 + 0.2 * np.sin((h - 6) / 24 * 2 * np.pi)) + (i + 1) * 500 * np.maximum(0, 15 - temp[c].values) + rng.normal(0, 100, len(idx)) for i, c in enumerate(cols)}, index=idx)
    return load, temp


def test_weather_features_read_the_target_hour_and_nothing_else():
    load, temp = synth(days=60)
    f = ef.build_features(load, temp)
    ts = load.index[1000]
    row = f.loc[(ts, "FR")]
    assert row["temp"] == pytest.approx(temp.loc[ts, "FR"])
    assert row["hdd"] == pytest.approx(max(0, 15 - temp.loc[ts, "FR"]))
    assert row["cdd"] == pytest.approx(max(0, temp.loc[ts, "FR"] - 22))
    assert row["temp_24"] == pytest.approx(temp["FR"].iloc[1000 - 23: 1001].mean())
    assert "temp" not in ef.build_features(load).columns


def test_model_with_temperature_beats_the_same_model_without_it_when_load_depends_on_temperature():
    load, temp = synth()
    origins = list(pd.date_range(load.index[-1].normalize() - pd.Timedelta(days=9), periods=6, freq="D"))
    tso = load * 1.0
    class Fast(ef.ElecLGBM):
        def __init__(self, *a, **k):
            super().__init__(*a, **k); self.rounds = 80
    ew.ElecLGBM, saved = Fast, ew.ElecLGBM
    try:
        pred = ew.run(load, tso, temp, origins, "same_hour_last_week", log=lambda *_: None)
    finally:
        ew.ElecLGBM = saved
    mae = lambda c: (pred[c] - pred["y"]).abs().mean()
    assert mae("lgbm_weather") < mae("lgbm")
    assert np.isfinite(pred[["lgbm", "lgbm_weather"]].to_numpy()).all()


def test_window_must_sit_before_the_development_days():
    idx = pd.date_range("2015-01-01", "2020-09-30 23:00", freq="h")
    act = pd.DataFrame({"DE": 1.0}, index=idx)
    ew.check_window(act, ew.window())                      # Nov 2018 is fine
    late = list(pd.date_range("2020-02-01", periods=28, freq="D"))
    with pytest.raises(SystemExit):
        ew.check_window(act, late)


def test_weather_csv_is_read_by_name(tmp_path):
    p = tmp_path / "w.csv"
    pd.DataFrame({"utc_timestamp": ["2018-11-01T00:00:00Z", "2018-11-01T01:00:00Z", "2018-11-01T03:00:00Z"], "DE_temperature": [4.0, 3.5, 3.0],
                  "FR_temperature": [8, 8, 7], "DE_radiation_direct_horizontal": [0, 0, 0]}).to_csv(p, index=False)
    w = opsd_weather.load(p, ["DE", "FR"])
    assert list(w.columns) == ["DE", "FR"] and w.index.tz is None and len(w) == 4 and w["DE"].isna().sum() == 1
    with pytest.raises(SystemExit):
        opsd_weather.load(p, ["DE", "ZZ"])
