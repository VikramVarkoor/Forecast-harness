"""Features for the day-ahead model. Every feature for target hour t uses only data from
t-24 or earlier, so it is known at the midnight origin for any t in the origin day.

    lag_24         y[t-24]
    lag_168        y[t-168]
    roll24_l24     mean of y[t-47 .. t-24]
    roll4w_sh      mean of y[t-168], y[t-336], y[t-504], y[t-672]
    hour, dow
    holiday        US federal or New York state holiday on that calendar date (known in advance)
    zone_id        the zone, as a categorical with a fixed category list
"""
from functools import lru_cache

import pandas as pd

NUMERIC = ["lag_24", "lag_168", "roll24_l24", "roll4w_sh"]
FEATURES = NUMERIC + ["hour", "dow", "holiday", "zone_id"]


@lru_cache(maxsize=8)
def _calendar(first_year: int, last_year: int) -> pd.DatetimeIndex:
    import holidays

    cal = holidays.country_holidays("US", subdiv="NY", years=range(first_year, last_year + 1))
    return pd.DatetimeIndex(sorted(pd.Timestamp(d) for d in cal.keys()))


def holiday_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return _calendar(index.min().year - 1, index.max().year + 1)


def build_features(wide: pd.DataFrame) -> pd.DataFrame:
    """Vectorised pipeline over the whole wide frame. Returns long (ts, zone) rows."""
    f = {
        "lag_24": wide.shift(24),
        "lag_168": wide.shift(168),
        "roll24_l24": wide.shift(24).rolling(24).mean(),
        "roll4w_sh": sum(wide.shift(168 * k) for k in range(1, 5)) / 4.0,
    }
    long = pd.concat({k: v.stack(future_stack=True) for k, v in f.items()}, axis=1)
    long.index.names = ["ts", "zone"]
    ts = long.index.get_level_values("ts")
    long["hour"] = ts.hour
    long["dow"] = ts.day_of_week
    long["holiday"] = ts.normalize().isin(holiday_dates(wide.index)).astype("int8")
    zone = long.index.get_level_values("zone")
    long["zone_id"] = pd.Categorical(zone, categories=sorted(wide.columns))
    return long


def features_from_raw(wide: pd.DataFrame, ts, zone) -> dict:
    """Independent, slow recomputation for one (ts, zone) from raw values by timestamp lookup.
    Deliberately shares no code with build_features."""
    s = wide[zone]
    h = pd.Timedelta(hours=1)

    def at(k):
        t = ts - k * h
        return s.get(t, float("nan"))

    return {
        "lag_24": at(24),
        "lag_168": at(168),
        "roll24_l24": sum(at(k) for k in range(24, 48)) / 24.0,
        "roll4w_sh": sum(at(168 * k) for k in range(1, 5)) / 4.0,
    }
