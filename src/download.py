"""Download TLC HVFHV monthly parquet files. Run on a machine with normal internet.

    python src/download.py --probe                 # which recent months exist, with sizes
    python src/download.py --from 2025-09 --to 2026-08 --dry-run
    python src/download.py --from 2025-09 --to 2026-08

URL pattern is the one TLC has used for years; verify it on the TLC trip record page.
"""
import argparse
import sys
import urllib.request
from datetime import date
from pathlib import Path

BASE = "https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_{ym}.parquet"
DATA = Path(__file__).resolve().parent.parent / "data" / "raw"


def months(start: str, end: str):
    y, m = map(int, start.split("-"))
    ye, me = map(int, end.split("-"))
    while (y, m) <= (ye, me):
        yield f"{y:04d}-{m:02d}"
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def size(url: str):
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return int(r.headers.get("Content-Length", -1))
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start")
    ap.add_argument("--to", dest="end")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.probe:
        t = date.today()
        y, m = t.year, t.month
        recent = []
        for _ in range(16):
            recent.append(f"{y:04d}-{m:02d}")
            y, m = (y - 1, 12) if m == 1 else (y, m - 1)
        for ym in sorted(recent):
            s = size(BASE.format(ym=ym))
            print(ym, "missing" if s is None else f"{s / 1e6:.0f} MB")
        return
    if not (a.start and a.end):
        sys.exit("give --from and --to, or --probe")

    DATA.mkdir(parents=True, exist_ok=True)
    plan = [(ym, BASE.format(ym=ym)) for ym in months(a.start, a.end)]
    total = 0
    for ym, url in plan:
        s = size(url)
        if s is None:
            print(f"{ym}: not found, stopping (check --probe)")
            sys.exit(1)
        total += s
        print(f"{ym}: {s / 1e6:.0f} MB")
    print(f"total {total / 1e9:.2f} GB")
    if a.dry_run:
        return
    for ym, url in plan:
        out = DATA / f"fhvhv_tripdata_{ym}.parquet"
        if out.exists():
            print("skip", out.name)
            continue
        print("get ", out.name)
        urllib.request.urlretrieve(url, out)


if __name__ == "__main__":
    main()
