-- Hourly pickups per zone from raw HVFHV parquet files.
-- pickup_datetime is local NYC wall time (see DECISIONS D1), so date_trunc gives the local hour.
-- Placeholders are filled by src/build_hourly.py: {glob}, {start}, {end}, {brand_filter}
SELECT
    date_trunc('hour', pickup_datetime) AS ts,
    PULocationID                        AS zone,
    COUNT(*)                            AS trips
FROM read_parquet('{glob}')
WHERE pickup_datetime >= TIMESTAMP '{start}'
  AND pickup_datetime <  TIMESTAMP '{end}'
  {brand_filter}
GROUP BY 1, 2
ORDER BY 1, 2
