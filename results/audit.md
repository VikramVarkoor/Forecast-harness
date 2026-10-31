# Data audit

## Hourly table
- Range: 2025-10-01 00:00:00 to 2026-09-30 23:00:00, 8,760 expected hours, 8,760 present
- Hours with no row at all: 0. Note: build_hourly fills a complete grid with zeros, so a real data gap shows up as a near-zero city total below, not here.
- Duplicate (hour, zone) rows in the hourly table: 0
- Zones: 262. Zones with trips in under 1% of hours: 3
- Zones with zero trips in the whole period: 0
- Hours where the whole city has zero trips: 0
- Gap candidates (city total under 5% of that hour-of-week median): 1
  - 2026-03-08 02:00:00: 85 trips against a median of 26080
- City-level hours more than 6 robust sigmas from their hour-of-week median: 108
  - 2026-01-01 03:00:00: city total 49552, robust z 79.3
  - 2026-01-01 04:00:00: city total 34927, robust z 58.2
  - 2026-01-01 02:00:00: city total 59542, robust z 55.9
  - 2026-01-01 01:00:00: city total 62761, robust z 37.1
  - 2026-01-01 00:00:00: city total 57582, robust z 20.6
  - 2025-11-01 04:00:00: city total 31884, robust z 19.1
  - 2026-02-23 10:00:00: city total 3951, robust z -18.4
  - 2025-11-01 03:00:00: city total 38721, robust z 17.3
  - 2025-11-02 01:00:00: city total 75292, robust z 17.0
  - 2026-02-23 05:00:00: city total 1381, robust z -17.0
- Daylight saving (local wall time, so one hour is nearly empty and one is doubled):
  - autumn 01:00 on 2025-11-02: 75,292 trips (same hour a week before: 36606, a week after: 34275)
  - spring 02:00 on 2026-03-08: 85 trips (same hour a week before: 26159, a week after: 27096)

## Raw files
- Raw trips: 272,844,412, between 2025-09-01 00:00:00 and 2026-09-30 23:59:59
- Exact duplicate rows (same brand, times, zones, miles): 303
- Null pickup_datetime: 0, null PULocationID: 0
