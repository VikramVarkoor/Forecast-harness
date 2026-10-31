"""Data audit. Writes results/audit.md. Look at the output before trusting any number downstream.

    python src/audit.py [--raw 'data/raw/*.parquet'] [--hourly data/hourly.parquet]
"""
import argparse
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def _nth_sunday(year, month, n):
    first = pd.Timestamp(year=year, month=month, day=1)
    return first + pd.Timedelta(days=(6 - first.day_of_week) % 7 + 7 * (n - 1))


def dst_report(city: pd.Series) -> list[str]:
    """Timestamps are local wall time. Spring forward: 02:00 does not exist. Fall back: 01:00
    happens twice and both land in one bucket. Show each day's hour next to the same hour a week
    either side so the artifact is visible."""
    out = []
    for year in sorted(set(city.index.year)):
        for label, t in (("spring 02:00", _nth_sunday(year, 3, 2) + pd.Timedelta(hours=2)),
                         ("autumn 01:00", _nth_sunday(year, 11, 1) + pd.Timedelta(hours=1))):
            if t in city.index:
                wk = pd.Timedelta(days=7)
                before, after = city.get(t - wk), city.get(t + wk)
                out.append(f"  - {label} on {t.date()}: {int(city[t]):,} trips "
                           f"(same hour a week before: {before}, a week after: {after})")
    return out


def audit_hourly(hourly: pd.DataFrame) -> list[str]:
    out = []
    ts_min, ts_max = hourly["ts"].min(), hourly["ts"].max()
    expected = pd.date_range(ts_min, ts_max, freq="h")
    present = pd.DatetimeIndex(sorted(hourly["ts"].unique()))
    missing = expected.difference(present)
    out.append(f"- Range: {ts_min} to {ts_max}, {len(expected):,} expected hours, {len(present):,} present")
    out.append(f"- Hours with no row at all: {len(missing)}. Note: build_hourly fills a complete grid with "
               "zeros, so a real data gap shows up as a near-zero city total below, not here.")
    dup = hourly.duplicated(["ts", "zone"]).sum()
    out.append(f"- Duplicate (hour, zone) rows in the hourly table: {dup}")

    wide = hourly.pivot(index="ts", columns="zone", values="trips")
    city = wide.sum(axis=1)
    zero_share = (wide == 0).mean()
    out.append(f"- Zones: {wide.shape[1]}. Zones with trips in under 1% of hours: {(zero_share > 0.99).sum()}")
    out.append(f"- Zones with zero trips in the whole period: {(wide.sum() == 0).sum()}")
    out.append(f"- Hours where the whole city has zero trips: {(city == 0).sum()}")

    how = city.index.day_of_week * 24 + city.index.hour
    med = city.groupby(how).transform("median")
    low = city[city < 0.05 * med]
    out.append(f"- Gap candidates (city total under 5% of that hour-of-week median): {len(low)}")
    for t, v in low.head(10).items():
        out.append(f"  - {t}: {int(v)} trips against a median of {int(med[t])}")

    mad = (city - med).abs().groupby(how).transform("median").replace(0, 1)
    z = (city - med) / (1.4826 * mad)
    odd = z[z.abs() > 6].sort_values(key=abs, ascending=False)
    out.append(f"- City-level hours more than 6 robust sigmas from their hour-of-week median: {len(odd)}")
    for t, v in odd.head(10).items():
        out.append(f"  - {t}: city total {int(city[t])}, robust z {v:.1f}")

    out.append("- Daylight saving (local wall time, so one hour is nearly empty and one is doubled):")
    out += dst_report(city)
    return out


def audit_raw(raw_glob: str) -> list[str]:
    q = f"""
    SELECT COUNT(*) AS n,
           COUNT(*) - COUNT(DISTINCT (hvfhs_license_num, pickup_datetime, dropoff_datetime,
                                      PULocationID, DOLocationID, trip_miles)) AS dupes,
           COUNT(*) FILTER (WHERE pickup_datetime IS NULL) AS null_pickup,
           COUNT(*) FILTER (WHERE PULocationID IS NULL) AS null_zone,
           MIN(pickup_datetime) AS first, MAX(pickup_datetime) AS last
    FROM read_parquet('{raw_glob}')
    """
    r = duckdb.sql(q).df().iloc[0]
    return [
        f"- Raw trips: {int(r.n):,}, between {r['first']} and {r['last']}",
        f"- Exact duplicate rows (same brand, times, zones, miles): {int(r.dupes):,}",
        f"- Null pickup_datetime: {int(r.null_pickup)}, null PULocationID: {int(r.null_zone)}",
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=str(ROOT / "data" / "raw" / "*.parquet"))
    ap.add_argument("--hourly", default=str(ROOT / "data" / "hourly.parquet"))
    ap.add_argument("--skip-raw", action="store_true")
    a = ap.parse_args()
    lines = ["# Data audit", "", "## Hourly table"]
    lines += audit_hourly(pd.read_parquet(a.hourly))
    if not a.skip_raw:
        lines += ["", "## Raw files"] + audit_raw(a.raw)
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "audit.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
