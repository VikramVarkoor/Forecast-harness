"""Aggregate raw parquet to one tidy hourly table with DuckDB. Rerunnable.

    python src/build_hourly.py --from 2025-09-01 --to 2026-09-01
"""
import argparse
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SQL = (ROOT / "src" / "sql" / "hourly.sql").read_text()
BRANDS = {"uber": "HV0003", "lyft": "HV0005", "via": "HV0004", "juno": "HV0002"}


def build(raw_glob: str, start: str, end: str, brand: str | None = None) -> pd.DataFrame:
    bf = f"AND hvfhs_license_num = '{BRANDS[brand]}'" if brand else ""
    q = SQL.format(glob=raw_glob, start=start, end=end, brand_filter=bf)
    df = duckdb.sql(q).df()
    df["ts"] = pd.to_datetime(df["ts"])
    full = pd.date_range(start, pd.Timestamp(end) - pd.Timedelta(hours=1), freq="h")
    # Complete grid: absent (hour, zone) means zero trips. Real gaps are reported by audit.py.
    zones = sorted(df["zone"].unique())
    grid = pd.MultiIndex.from_product([full, zones], names=["ts", "zone"])
    out = df.set_index(["ts", "zone"]).reindex(grid, fill_value=0).reset_index()
    out["trips"] = out["trips"].astype("int32")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", required=True)
    ap.add_argument("--to", dest="end", required=True)
    ap.add_argument("--raw", default=str(ROOT / "data" / "raw" / "*.parquet"))
    ap.add_argument("--out", default=str(ROOT / "data" / "hourly.parquet"))
    ap.add_argument("--brand", choices=list(BRANDS))
    a = ap.parse_args()
    df = build(a.raw, a.start, a.end, a.brand)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(a.out, index=False)
    print(f"wrote {a.out}: {len(df):,} rows, {df['zone'].nunique()} zones, {df['ts'].min()} to {df['ts'].max()}")


if __name__ == "__main__":
    main()
