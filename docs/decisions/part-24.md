# Decisions, part 24

## D85: Every percentage on the electricity page names its metric
- The hero, the first finding card and the plain-language paragraph all use the same number: the drop in average error measured in megawatts, shown to one decimal. The captions now say "average error, in megawatts".
- Percentage error (MAPE) is reported separately and labelled as percent.

## D86: One conclusion on the operator comparison
- The comparison has two measures: megawatts (counts large countries most) and percent (counts every country the same). When their 95% ranges disagree about whether the model is ahead, the page now says so and states that the conclusion stands on megawatts, the measure it leads with.
- With the current results megawatts is not clearly different from the operators and percent favours the model by 0.45 points (95% range 0.11 to 0.74), so the page reads: not clearly different overall, and the two measures disagree.

## D87: "Decisions written before code" removed
- The logs were committed together, so the git history cannot show that decisions came before code. The README no longer says it. The logs stay as a record of what was decided and why.

## D88: Taxi bias check
- `python -m src.bias_check` reads the development and held-out predictions and writes `results/bias_check.json`: bias on development days against held-out days, the share of the shortfall carried by the biggest zones, bias by hour and by day, bias of every model on the held-out weeks, and mean demand by held-out week.
- It trains nothing and changes no result. It looks at the held-out weeks after the fact, so whatever it finds goes in the README as a finding and is not used to tune.

## D89: Taxi bias finding goes in the README, from the check file
- The check found development bias +1.3 against -8.0 on the held-out days (-3.4% of mean demand). Mean demand in the held-out weeks was 4.6% above the development average. 20 of 30 zones and 20 of 28 days were negative, and the 5 worst zones (LaGuardia Airport, TriBeCa/Civic Center, Times Sq/Theatre District, West Chelsea/Hudson Yards, Midtown Center) carry 54% of the shortfall. Bias is largest in the evening and close to zero at 3:00.
- By model on the held-out weeks: 4-week mean -13.6, LightGBM -8.0, same hour last week -5.4, same hour yesterday -0.7. The simple baselines under-forecast too, which fits demand running above recent history. Why it ran higher (season, events, weather) was not tested.
- The README sentence is written from `results/bias_check.json`, so it changes if the check is re-run. Without that file it falls back to "the cause was not investigated".
- The check looks at the held-out weeks after they were scored once, so it explains the result and changes nothing.

## D90: Two failing tests fixed
- The dropdown test expected bare zone IDs, but the labels carry names when the TLC lookup file is present. It now compares the ID before the colon.
- `src/make_zone_geojson.py` was missing from the working tree, so its test could not import it. It is added.
