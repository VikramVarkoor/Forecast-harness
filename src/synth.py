"""SYNTHETIC trips in the HVFHV parquet schema. For tests and dry runs only.
Never report numbers from this data as results."""
from pathlib import Path

import numpy as np
import pandas as pd


def make_month_files(out_dir: Path, start="2025-02-01", days=70, n_zones=12, seed=0):
    rng = np.random.default_rng(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    hours = pd.date_range(start, periods=days * 24, freq="h")
    scale = np.geomspace(3, 120, n_zones)
    frames = []
    for z, s in enumerate(scale, start=1):
        h = hours.hour.values
        dow = hours.day_of_week.values
        daily = 1 + 0.6 * np.sin((h - 14) / 24 * 2 * np.pi) + 0.3 * (h >= 17) * (h <= 21)
        weekly = np.where(dow >= 5, 1.25, 1.0)
        lam = s * daily * weekly
        n = rng.poisson(lam)
        ts = np.repeat(hours.values, n)
        zone = np.full(len(ts), z)
        frames.append(pd.DataFrame({"pickup_datetime": ts, "PULocationID": zone}))
    df = pd.concat(frames, ignore_index=True)
    df["pickup_datetime"] = df["pickup_datetime"] + pd.to_timedelta(rng.integers(0, 3600, len(df)), unit="s")
    df["hvfhs_license_num"] = rng.choice(["HV0003", "HV0005", "HV0004", "HV0002"], len(df), p=[.7, .2, .07, .03])
    df["dropoff_datetime"] = df["pickup_datetime"] + pd.Timedelta(minutes=15)
    df["DOLocationID"] = rng.integers(1, n_zones + 1, len(df))
    df["trip_miles"] = rng.uniform(0.5, 10, len(df)).round(2)
    df["month"] = df["pickup_datetime"].dt.strftime("%Y-%m")
    paths = []
    for ym, g in df.groupby("month"):
        p = out_dir / f"fhvhv_tripdata_{ym}.parquet"
        g.drop(columns="month").to_parquet(p, index=False)
        paths.append(p)
    return paths
