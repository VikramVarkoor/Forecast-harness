"""Domain B step 1: download the Open Power System Data hourly time series and report what is usable.

    python -m src.opsd_download                  # download (about 100 MB, once), clean, print the report
    python -m src.opsd_download --no-download    # reuse the file already in data/opsd/raw
    python -m src.opsd_download --countries DE FR ES IT GB PL NL

It keeps only national load series: the measured load and the grid operators' own day-ahead forecast
(both from ENTSO-E). The operator forecast becomes a strong extra benchmark later. Nothing is
modelled here. The report tells us which countries have enough clean history, so the data picks the
country list, not me. Run it on a machine with normal internet.

Writes: data/opsd/load_hourly.parquet (UTC hourly index, columns <CC>_actual and <CC>_tso)
        results/opsd_coverage.csv     (one row per country, what the report prints)
"""
import argparse
import re
import sys
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "opsd" / "raw"
URL = "https://data.open-power-system-data.org/time_series/latest/time_series_60min_singleindex.csv"
CSV = RAW / "time_series_60min_singleindex.csv"
COL = re.compile(r"^([A-Z]{2})_load_(actual|forecast)_entsoe_transparency$")  # national series only, no sub-areas


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


def load(path=CSV):
    """Read only the national load columns. Returns an hourly UTC table with <CC>_actual and <CC>_tso."""
    head = pd.read_csv(path, nrows=0)
    keep = {c: COL.match(c) for c in head.columns if COL.match(c)}
    if "utc_timestamp" not in head.columns or not keep:
        raise SystemExit("Unexpected file layout: no utc_timestamp or no <CC>_load_*_entsoe_transparency columns. "
                         "Open the CSV header and tell me what the columns are called.")
    df = pd.read_csv(path, usecols=["utc_timestamp"] + list(keep), parse_dates=["utc_timestamp"])
    df["utc_timestamp"] = pd.to_datetime(df["utc_timestamp"], utc=True)
    df = df.set_index("utc_timestamp").sort_index()
    df.index.name = "ts"
    df = df.rename(columns={c: f"{m.group(1)}_{'actual' if m.group(2) == 'actual' else 'tso'}" for c, m in keep.items()})
    return df[~df.index.duplicated(keep="first")]


def coverage(df, since="2015-01-01"):
    """One row per country: first and last hour with an actual, share missing since `since`, longest gap."""
    rows = []
    for cc in sorted({c.split("_")[0] for c in df.columns}):
        if f"{cc}_actual" not in df.columns or f"{cc}_tso" not in df.columns:
            continue
        a, t = df[f"{cc}_actual"], df[f"{cc}_tso"]
        a_s = a[a.index >= pd.Timestamp(since, tz="UTC")]
        if a.dropna().empty:
            continue
        isna = a_s.isna().astype(int)
        run = isna.groupby((isna != isna.shift()).cumsum()).cumsum()
        both = pd.concat([a_s, t[t.index >= pd.Timestamp(since, tz="UTC")]], axis=1).dropna()
        rows.append(dict(country=cc, first=a.first_valid_index(), last=a.last_valid_index(),
                         hours_since=len(a_s), missing_actual_pct=round(100 * isna.mean(), 2),
                         longest_gap_hours=int(run.max()) if len(run) else 0,
                         tso_missing_pct=round(100 * t[t.index >= pd.Timestamp(since, tz="UTC")].isna().mean(), 2),
                         hours_with_both=len(both)))
    return pd.DataFrame(rows).sort_values("missing_actual_pct").reset_index(drop=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-download", action="store_true")
    ap.add_argument("--force", action="store_true", help="download again even if the file exists")
    ap.add_argument("--countries", nargs="*", help="keep only these two-letter codes in the parquet")
    ap.add_argument("--since", default="2015-01-01")
    a = ap.parse_args()
    if not a.no_download:
        fetch(a.force)
    df = load()
    cov = coverage(df, a.since)
    pd.set_option("display.width", 200); pd.set_option("display.max_columns", 20)
    print(f"\nFile covers {df.index.min()} to {df.index.max()}  ({len(df):,} hourly rows)")
    print(f"\nCoverage since {a.since} (missing share is of hours in the window):\n")
    print(cov.to_string(index=False))
    if a.countries:
        keep = [c for c in df.columns if c.split("_")[0] in set(a.countries)]
        df = df[keep]
    (ROOT / "results").mkdir(exist_ok=True); (ROOT / "data" / "opsd").mkdir(parents=True, exist_ok=True)
    cov.to_csv(ROOT / "results" / "opsd_coverage.csv", index=False)
    df.to_parquet(ROOT / "data" / "opsd" / "load_hourly.parquet")
    print(f"\nWrote data/opsd/load_hourly.parquet ({df.shape[1]} columns) and results/opsd_coverage.csv")
    print("Paste the table above back to me and I will pick the countries and the held-out weeks from it.")


if __name__ == "__main__":
    sys.exit(main())
