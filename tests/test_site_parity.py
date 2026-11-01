"""The browser's compare-zones sentence must equal the Python one for every day. Skipped when Playwright is not installed."""
import functools
import http.server
import json
import sys
import threading
from pathlib import Path

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

from test_make_site import _pred  # noqa: E402
from src import make_site  # noqa: E402

SITE = Path(__file__).resolve().parent.parent / "site"


def test_compare_sentence_matches_python(tmp_path, monkeypatch):
    res = tmp_path / "res"
    res.mkdir()
    _pred(14, (1, 2), "2026-01-01", 0).to_parquet(res / "predictions.parquet", index=False)
    _pred(7, (1, 2), "2026-02-01", 1).to_parquet(res / "heldout_predictions.parquet", index=False)
    out = tmp_path / "site"
    out.mkdir()
    for p in SITE.iterdir():
        if p.name != "data":
            (out / p.name).symlink_to(p)
    monkeypatch.setattr(sys, "argv", ["make_site", "--results", str(res), "--out", str(out / "data")])
    make_site.main()
    from app import app as A
    df = A.load()
    exp = {}
    for d in sorted(df["origin"].dt.normalize().unique()):
        items = [(f"Zone {z}", df[(df.zone == z) & (df.origin.dt.normalize() == d)].sort_values("ts")) for z in (1, 2)]
        exp[f"{d:%Y-%m-%d}"] = A.compare_takeaway(items, d)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()
            pg.goto(f"http://127.0.0.1:{srv.server_port}/?view=Dashboard&tab=About")
            pg.wait_for_function("window.H && window.H.compareTakeaway")
            got = pg.evaluate("""async (days) => {const a = await (await fetch('data/zones/1.json')).json(), b = await (await fetch('data/zones/2.json')).json(), out = {};
              for (const d of days) out[d] = H.compareTakeaway([{name: 'Zone 1', m: a.mae[d][0], b: a.mae[d][1]}, {name: 'Zone 2', m: b.mae[d][0], b: b.mae[d][1]}], d);
              return out;}""", list(exp))
            b.close()
    finally:
        srv.shutdown()
    assert got == exp
