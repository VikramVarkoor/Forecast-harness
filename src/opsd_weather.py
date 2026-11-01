"""Domain B, weather step: hourly temperature per country from Open Power System Data (MERRA-2 reanalysis).

    python -m src.opsd_weather                  # download weather_data.csv once (about 220 MB), keep temperature for our countries
    python -m src.opsd_weather --no-download

Temperature is a population-weighted mean over each country, in degrees Celsius, hourly UTC, 1980 to 2019.
Writes data/opsd/weather_temp.parquet and results/opsd_weather_report.json. Needs data/opsd/elec_actual.parquet first
(it takes its country list and date span from there). The weather file ends in 2019, so it cannot cover the
September 2020 held-out days; the weather test uses an earlier window (see src/elec_weather_run.py).
"""
import argparse
import json
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "opsd" / "raw"
URL = "https://data.open-power-system-data.org/weather_data/2020-09-16/weather_data.csv"
CSV = RAW / "weather_data.csv"


def fetch(force=False):
    if CSV.exists() and not force:
        print(f"Using existing {CSV}")
        return
    RAW.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {URL}")
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (forecast-harness)"})
    with urllib.request.urlopen(req, timeout=120) as r, open(CSV, "wb") as f:
        total = int(r.headers.get("Content-Length", 0)); got = 0
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b); got += len(b)
            if total:
                print(f"\r  {got / 1e6:6.1f} / {total / 1e6:.1f} MB", end="", flush=True)
    print()


def load(path, countries):
    head = pd.read_csv(path, nrows=0)
    need = [f"{c}_temperature" for c in countries]
    missing = [c for c in need if c not in head.columns]
    if "utc_timestamp" not in head.columns or missing:
        raise SystemExit(f"Weather file is missing columns {missing or ['utc_timestamp']}. Open the CSV header and tell me what the temperature columns are called.")
    df = pd.read_csv(path, usecols=["utc_timestamp"] + need)
    df["utc_timestamp"] = pd.to_datetime(df["utc_timestamp"], utc=True).dt.tz_convert("UTC").dt.tz_localize(None)
    df = df.set_index("utc_timestamp").sort_index()
    df.index.name = "ts"
    df.columns = [c.replace("_temperature", "") for c in df.columns]
    return df.reindex(pd.date_range(df.index.min(), df.index.max(), freq="h"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true")
    a = ap.parse_args()
    act = pd.read_parquet(ROOT / "data" / "opsd" / "elec_actual.parquet")
    countries = list(act.columns)
    if not a.no_download:
        fetch()
    wx = load(CSV, countries)
    span = wx.loc[(wx.index >= act.index.min()) & (wx.index <= act.index.max())]
    rep = dict(countries=countries, first=str(wx.index.min()), last=str(wx.index.max()), hours_missing_in_load_span=int(span.isna().sum().sum()),
               temp_min_c=float(wx.min().min()), temp_max_c=float(wx.max().max()))
    wx.to_parquet(ROOT / "data" / "opsd" / "weather_temp.parquet")
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "opsd_weather_report.json").write_text(json.dumps(rep, indent=2))
    print(json.dumps(rep, indent=2))
    if wx.index.max() < pd.Timestamp("2018-12-01"):
        raise SystemExit("Weather ends before the test window (Nov 2018). Check the file.")


if __name__ == "__main__":
    main()
