# Decisions, part 16

## D31: Clearer hero, five new features, dark-mode fixes
- Hero copy was ambiguous ("fewer misses" of what, and "simple rule" undefined). It now says "lower forecast error than a simple rule of thumb (the average of that same hour over the last 4 weeks). Tested on N days the model never saw, scored once." The two side numbers are labelled "The model is off by" and "The rule of thumb is off by", with the unit "rides per zone per hour" printed under each.
- Story page now shows one real day as a chart. Rule: the busiest zone (same definition as the plain-English paragraph, by held-out volume) on the last held-out day. The caption says it was chosen by rule, not because it looks good.
- Shareable links: view, dark mode, zone and day are written to the address bar and read back on load. Widgets are seeded from the URL once, before they exist, so no Streamlit session-state warnings.
- "Where it fails" tab: tables of the 5 days the model beat the rule by the most and the 5 that went worst for the model. The worst list can show days the rule won; nothing is hidden.
- Download of the held-out forecasts as CSV (About tab), with plain column names.
- New Method tab for technical readers. Every statement comes from the code (features, Poisson objective, weekly refit, fixed settings, 10/90% quantile models, leak test) and the interval coverage is computed from the held-out rows, not typed in.
- Cleanups: removed deprecated components.html and use_container_width calls, and removed the segmented control default so URL seeding does not trigger a warning.
- Dark mode: help icons and the day slider track were nearly invisible; both fixed.
