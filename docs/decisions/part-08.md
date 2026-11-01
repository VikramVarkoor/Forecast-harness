
## D23. App redesign (done)

- Dark theme in `.streamlit/config.toml`. Colors: amber for LightGBM, blue for the baseline, light gray for actuals; amber and blue checked with the dataviz validator against the dark surface.
- Interactive Altair charts with hover. New "Where it fails" tab: daily error over time with verified-cause days circled (from `docs/day_reasons.csv`), and an hour-by-weekday heatmap of where LightGBM beats the baseline.
