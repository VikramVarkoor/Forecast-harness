"""Features and model for the electricity day-ahead task (Domain B).

Same idea as the ride-hail features: for target hour t, every feature uses data from t-24 or
earlier, so it is known at the midnight (UTC) origin for any hour in that day. Differences:
  * the index is UTC and regular; hour, weekday, month and holidays are read off each country's
    own local clock, so daylight saving moves the daily shape the way it really does
  * holidays come from each country's national calendar (regional holidays are not included)
  * countries differ hugely in size, so the model predicts load relative to a recent level
    (lvl = mean of the 672 hours ending 24 hours before the target) and the answer is scaled back
"""
from functools import lru_cache

import lightgbm as lgb
import numpy as np
import pandas as pd

H = 24
TZ = {"FI": "Europe/Helsinki", "GR": "Europe/Athens", "BG": "Europe/Sofia", "RO": "Europe/Bucharest", "LV": "Europe/Riga",
      "LT": "Europe/Vilnius", "EE": "Europe/Tallinn", "PT": "Europe/Lisbon", "IE": "Europe/Dublin", "GB": "Europe/London"}
RATIO = ["lag_24", "lag_168", "roll24_l24", "roll4w_sh"]
FEATURES = RATIO + ["hour", "dow", "month", "doy", "holiday", "zone_id"]
WX = ["temp", "temp_24", "hdd", "cdd"]      # weather add-on: temperature at the target hour, its 24 h mean, heating and cooling degrees
HDD_BASE, CDD_BASE = 15.0, 22.0
LVL = 672


def tz_of(cc):
    return TZ.get(cc, "Europe/Berlin")


@lru_cache(maxsize=64)
def _hol(cc, y0, y1):
    import holidays
    return pd.DatetimeIndex(sorted(pd.Timestamp(d) for d in holidays.country_holidays(cc, years=range(y0, y1 + 1)).keys()))


def local_fields(index, cc):
    """hour, dow, month, doy, holiday flag on the country's local clock, for a UTC naive index."""
    loc = index.tz_localize("UTC").tz_convert(tz_of(cc))
    day = loc.tz_localize(None).normalize()
    hol = day.isin(_hol(cc, index.min().year - 1, index.max().year + 1))
    return dict(hour=loc.hour, dow=loc.day_of_week, month=loc.month, doy=loc.day_of_year, holiday=hol.astype("int8"))


def build_features(wide, weather=None):
    """Long (ts, zone) frame with ratio features, the level, and calendar fields. With `weather` (hourly temperature,
    same columns), also the WX columns: the temperature measured at the target hour itself, so a model using them is
    handed a perfect weather forecast."""
    lvl = wide.shift(24).rolling(LVL, min_periods=LVL).mean()
    f = {"lag_24": wide.shift(24), "lag_168": wide.shift(168), "roll24_l24": wide.shift(24).rolling(24).mean(),
         "roll4w_sh": sum(wide.shift(168 * k) for k in range(1, 5)) / 4.0}
    long = pd.concat({k: (v / lvl).stack(future_stack=True) for k, v in f.items()}, axis=1)
    long["lvl"] = lvl.stack(future_stack=True)
    long.index.names = ["ts", "zone"]
    ts = long.index.get_level_values("ts"); zone = long.index.get_level_values("zone")
    cal = {c: np.empty(len(long), dtype=float) for c in ("hour", "dow", "month", "doy", "holiday")}
    for cc in wide.columns:
        m = np.asarray(zone == cc)
        lf = local_fields(pd.DatetimeIndex(ts[m]), cc)
        for k in cal:
            cal[k][m] = np.asarray(lf[k])
    for k, v in cal.items():
        long[k] = v.astype("int16") if k != "holiday" else v.astype("int8")
    long["zone_id"] = pd.Categorical(zone, categories=sorted(wide.columns))
    if weather is not None:
        w = weather.reindex(index=wide.index, columns=wide.columns)
        t24 = w.rolling(24, min_periods=1).mean()
        for k, v in (("temp", w), ("temp_24", t24), ("hdd", (HDD_BASE - w).clip(lower=0)), ("cdd", (w - CDD_BASE).clip(lower=0))):
            long[k] = v.stack(future_stack=True).to_numpy(float)
    return long


def features_from_raw(wide, ts, zone):
    """Independent slow recomputation for one (ts, zone), sharing no code with build_features."""
    s = wide[zone]; h = pd.Timedelta(hours=1)
    at = lambda k: s.get(ts - k * h, float("nan"))
    lvl = sum(at(k) for k in range(24, 24 + LVL)) / LVL
    return {"lag_24": at(24) / lvl, "lag_168": at(168) / lvl,
            "roll24_l24": (sum(at(k) for k in range(24, 48)) / 24.0) / lvl,
            "roll4w_sh": (sum(at(168 * k) for k in range(1, 5)) / 4.0) / lvl, "lvl": lvl}


class ElecLGBM:
    """One global LightGBM across countries on load relative to the recent level. Refit every
    `refit_days` days on all rows whose target is before the origin. Parameters are fixed in
    advance, not tuned on the backtest. objective='quantile' with alpha gives an interval edge."""

    def __init__(self, objective="regression", alpha=None, refit_days=7, features=None, weather=None):
        self.objective, self.alpha, self.refit_days, self.weather = objective, alpha, refit_days, weather
        self.features = list(features) if features else list(FEATURES)
        self.params = dict(learning_rate=0.05, num_leaves=63, min_data_in_leaf=50, bagging_fraction=0.8, bagging_freq=1,
                           feature_fraction=0.9, seed=0, deterministic=True, force_row_wise=True, verbose=-1)
        self.rounds, self.model, self.last_fit, self.n_fits = 300, None, None, 0

    def _fit(self, hist):
        feats = build_features(hist, self.weather)
        y = hist.stack(future_stack=True).to_numpy(float)
        assert len(y) == len(feats)
        feats["y"] = y / feats["lvl"].to_numpy(float)
        df = feats.dropna(subset=RATIO + ["y"])
        kw = dict(self.params, objective=self.objective)
        if self.alpha is not None:
            kw["alpha"] = self.alpha
        self.model = lgb.train(kw, lgb.Dataset(df[self.features], label=df["y"]), num_boost_round=self.rounds)
        self.n_fits += 1

    def __call__(self, hist):
        origin = hist.index[-1] + pd.Timedelta(hours=1)
        if self.model is None or origin - self.last_fit >= pd.Timedelta(days=self.refit_days):
            self._fit(hist); self.last_fit = origin
        horizon = pd.date_range(origin, periods=H, freq="h")
        ext = hist.reindex(pd.date_range(hist.index[0], horizon[-1], freq="h"))
        feats = build_features(ext, self.weather)
        sel = feats.loc[feats.index.get_level_values("ts").isin(horizon)]
        pred = pd.Series(self.model.predict(sel[self.features]) * sel["lvl"].to_numpy(float), index=sel.index).unstack("zone")
        return pred.reindex(index=horizon, columns=hist.columns).clip(lower=0)


def tso_forecaster(tso):
    """The grid operators' published day-ahead forecast as a forecaster. It reads the horizon rows of
    a table that was published before the day, so it is a benchmark, not something the harness slices."""
    def f(hist):
        origin = hist.index[-1] + pd.Timedelta(hours=1)
        return tso.loc[origin: origin + pd.Timedelta(hours=H - 1), hist.columns]
    return f
