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

## D91: Electricity operator card leads with the conclusion
- The card's number is still the count of days the model had the lower error (shown as a fraction of the held-out days), but its text now opens with the conclusion ("Not clearly different overall") and gives the day count as context. The count leans one way and the 95% range includes zero, so the conclusion is the range.

## D92: Development and held-out numbers are labelled
- The storm days are all in the development period (January and February), while the headline win count is on held-out days. The verdict now reads "won on N of M held-out days", and when the largest miss was a development-period storm it says so instead of "a winter storm still broke it".
- The storm card, the storm paragraph in the summary, the Storm days tab dropdown and the "what would change" line each name the period.

## D93: Interval coverage leads with the raw figure
- The README and the "yellow band can be trusted" check give the raw coverage first, then the figure after rounding the edges outward to whole trips, and name 80% as the target. The README says the rounding is not a calibration.

## D94: README lists the file behind each headline number
- A "Where the numbers come from" section is generated from the results folder and lists only files that exist. It also states that `app/app.py` is the original Streamlit dashboard and that the static site generator reuses its data code, which is why it stays.

## D95: Tests no longer overwrite the real link-preview picture
- `python -m src.make_site_elec` always wrote `site/assets/og-elec.png`, including when a test ran it on made-up data, so a test run replaced the real picture with one showing the test's numbers. A commit made right after the tests had picked that up.
- The picture path is now an option (`--og`), the test points it at a temporary folder, and the test checks that the real file is unchanged.

## D96: Interval check can say "Partly"
- "The range can be trusted" holds within 3 points of the 80% target, says "Partly" within 10 points, and fails beyond that. At 75% the range is 5 points low, so the page now says "Partly" and "a little too narrow, so treat it as optimistic" instead of "Holds". The taxi check uses the raw coverage for the same rule. "Partly" has its own chip.

## D97: Country tiles name the period they describe
- Each tile now has two lines: the first is the day picked on the slider, the second is the average over all held-out days. The second line uses the same percentage-error comparison as the written paragraph, so the two can no longer look like a contradiction. The caption says which is which.

## D98: Taxi finding cards separated
- The exponential smoothing result (against the simple rule) and the blend result (against LightGBM alone) are two cards with their own captions. They used to share one caption.

## D99: Two-pixel horizontal scroll removed
- The per-country figure line used a no-wrap rule that pushed the page 2 px wider than the window at about 1000 to 1200 px. It now wraps.
