# Session 15 decisions

## D30: Dashboard looks different from the Story, plus a takeaway under the chart
- Switching from the bottom of the Story page still felt unclear: the scroll jumped to the top but the big yellow hero looked identical, so nothing seemed to change. The Dashboard now uses a compact hero (small meter, two numbers, a kicker that says "Dashboard") so the chart sits above the fold and the page visibly changes. The hero moved inside the keyed view container so it animates with the rest.
- Chart tooltip now uses plain labels (What happened, Model forecast, Model missed by, Simple rule, Rule missed by, Expected range).
- New one-sentence takeaway under the Forecast chart, computed from the day's data. It says "simple rule won" when the rule did, and "about the same" within 5%. The model's biggest miss that day is named with the forecast and the actual.
- Tried highlight dots on hover; they did not render, so they were removed rather than shipped half-working.
