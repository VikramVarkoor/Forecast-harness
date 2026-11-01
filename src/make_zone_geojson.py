"""Cut the NYC taxi zone shapes down to the zones this project models.

    python -m src.make_zone_geojson path/to/taxi_zones.geojson

Input: the NYC Taxi Zones GeoJSON from NYC Open Data (WGS84 longitude/latitude). Output: app/zones30.geojson,
holding only zones that appear in results/predictions.parquet, with coordinates rounded to 5 decimals.
Each feature gets properties {"zone": <LocationID>}. The app draws the map from this file only.
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ID_KEYS = ("location_id", "LocationID", "locationid", "LOCATIONID", "zone_id")


def zone_id(props: dict) -> int:
    for k in ID_KEYS:
        if k in props:
            return int(props[k])
    raise SystemExit(f"No zone id property found. Properties present: {sorted(props)}. Tell me which one is the TLC LocationID.")


def _round(coords):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], 5), round(coords[1], 5)]
    return [_round(c) for c in coords]


def cut(geo: dict, keep: set) -> dict:
    feats = []
    for f in geo["features"]:
        z = zone_id(f["properties"])
        if z in keep:
            feats.append({"type": "Feature", "properties": {"zone": z},
                          "geometry": {"type": f["geometry"]["type"], "coordinates": _round(f["geometry"]["coordinates"])}})
    if not feats:
        raise SystemExit("No modelled zones matched the file. Wrong id property or the wrong dataset?")
    first = feats[0]["geometry"]["coordinates"]
    while isinstance(first[0], list):
        first = first[0]
    if abs(first[0]) > 180 or abs(first[1]) > 90:
        raise SystemExit("Coordinates are not longitude/latitude. Export the GeoJSON (WGS84), not the state-plane shapefile.")
    return {"type": "FeatureCollection", "features": feats}


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    geo = json.loads(Path(sys.argv[1]).read_text())
    zones = set(pd.read_parquet(ROOT / "results" / "predictions.parquet", columns=["zone"])["zone"].unique())
    out = cut(geo, zones)
    path = ROOT / "app" / "zones30.geojson"
    path.write_text(json.dumps(out, separators=(",", ":")))
    print(f"wrote {path} with {len(out['features'])} of {len(zones)} zones ({path.stat().st_size / 1024:.0f} KB)")
    missing = zones - {f["properties"]["zone"] for f in out["features"]}
    if missing:
        print(f"zones with no shape in the file: {sorted(missing)}")


if __name__ == "__main__":
    main()
