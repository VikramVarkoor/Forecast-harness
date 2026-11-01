# Session 23 decisions

## D38: Ticket-stub cards, three typefaces embedded in the page
- The yellow left border is gone. Cards are now tickets: a hard offset shadow (black in light mode, taxi yellow in dark), a tinted stub holding the big figure, a dashed tear line with notched edges, then the body. News cards put the lead image on top with a date stamp and the credit on the image. Hover lifts the card; reduced-motion turns that off; keyboard focus keeps a visible outline.
- The "How it was tested" cards are a real sequence, so they carry step numbers. The "What I would do next" cards are not a sequence, so their stubs are one word (Weather, History, Coverage, Harness) instead of numbers. The takeaway box and the new mind-change rows use the same ticket look.
- Typefaces (pairing C): Fraunces for headings, big numbers, card titles and the verdict; Figtree for interface text, labels, tabs and charts; Newsreader for story paragraphs and captions. All are variable fonts embedded as base64 in the page CSS, so they load on any host with no server setting. `.streamlit/config.toml` no longer needs static serving and `app/static` is deleted. Material icon font is left alone.
- Chart text uses Figtree, including the annotation label.

## D39: Footer sits at the bottom of short pages
- On pages shorter than the window (About, Compare) the footer used to end mid-window with blank space below it. The main block now has a minimum height of the window and the footer takes the leftover space above it, so nothing is blank below it. Long pages are unchanged.

## D40: Three additions
- Scoreboard tab: per-zone table and bar chart on held-out days (zone, average rides per hour, model miss, rule miss, percent fewer misses). The sentence above it is computed: zones beaten, the five busiest zones' share of rides, and their share of the total saving. It states the shares and does not call them good or bad.
- Story page: "What would change my mind". Four checks computed live from held-out data (beats the rule in at least half the zones; still ahead with the busiest zone removed; ahead on at least half of the days; interval coverage within 10 points of 80%), each shown as Holds, Fails or Untested. One check is fixed as Untested on purpose: another month or year was not held out.
- Compare zones: one computed sentence saying where the model helped more, or where the rule won. It stays silent if both pickers show the same zone.
- Tests: 49 passing, including a perfect model (all Holds) and an awful model (all Fails).

## Not built
- Keyboard and screen-reader pass: waiting for a yes.

## D41: Meter digits, section order, traffic
- The big meter digits are Figtree 900 with tabular figures. Fraunces' hook-tailed 1 and 7 looked wrong at that size. Fraunces stays on the smaller numbers.
- "Is this a real problem?" now follows the up-close chart, so the story reads: result, example, evidence it matters, then the rest.
- A two-lane road runs across the top of the hero on both views: five small taxis, pure CSS, always moving, hidden from screen readers. The dashboard gets a one-lane version. With reduced motion on they stand still.

## D42: Hover notes, centred box, spacing, sideways scroll
- Scoreboard bars now explain themselves on hover: what the method is, why it is in the comparison, its score. Descriptions come from the code in `src/baselines.py` and `src/models.py` (for example the blend is a 50/50 average, exponential smoothing is fitted per zone on 6 weeks). The sentence about how ETS and the blend scored is computed from the results. Tooltip is opaque and styled like the cards.
- The per-zone sentence box is centred. Other takeaway boxes stay left-aligned, next to text that is.
- Footer top margin cut from 3rem to 1.4rem to close the gap under the last caption.
- Bug fixed: the full-width yellow hero made the page scroll sideways (a grey bar at the bottom). The main area now clips horizontal overflow.

## D43: Traffic spans the screen, verdict names its subject
- The road was sized to the full-bleed hero, which is wider than the screen, so cars started and ended off-screen or mid-road. It is now exactly one screen wide, so cars enter and leave at the edges. The dashboard road is two lanes again, like the story page.
- The verdict now reads "My model beats a simple guess by X%. A winter storm still breaks it." The old version had no subject. "Blizzard" became "winter storm", the wording the cited news source uses.

## D44: Tooltip layout, zone box spacing, stray frame
- Hover cards use a two-column layout: bold title on the left, top-aligned, text on the right. Long text wraps inside the right column, so continuation lines line up under the first line and the card is wider (up to 600 px) before it wraps.
- The zone takeaway box has 2.2rem below it, and the note under the zone table is centred.
- The grey frame around the page after clicking was the browser's focus outline on the main scrolling area. It is removed there only; buttons, tabs, links and cards keep their focus outlines.

## D45: Pickers are pick-only, hero says what the number is
- Both selectboxes (taxi zone, storm day) use `filter_mode=None`: clicking opens a plain list, typing does nothing and no caret shows. With 30 zones the list is short enough to scroll, and the typed text used to clash with the highlighted option.
- Hero copy rewritten for a reader who knows nothing. The kicker is now the question the project answers. The big number is followed by "fewer misses than a simple rule of thumb, which just repeats the average of that same hour over the last 4 weeks". The two side figures read "My forecast is off by ... rides, per zone, per hour". The number itself is unchanged.

## D46: Hero as one sentence, hover pills
- The hero now reads as a sentence around the number: "My ride forecast misses by [13.7%] less than a simple guess." A one-line footnote defines the simple guess and the test. The two side figures stay.
- A small dashed pill with a cursor icon, "Hover over the chart to read the numbers.", sits above the charts on Forecast, Compare, Where it fails, Storm days and Map. On the Scoreboard it says what the hover shows for each method.

## D47: Headline no longer repeats the hero
- The hero says how much smaller the miss is (percentage) and how the test was run. The headline under it said the same. It now says something new, computed from the held-out days: "My model won on 26 of those 28 days. A winter storm still breaks it." The storm half only shows when the biggest storm day was at least 1.5 times a typical day's error, as before. Without held-out days it falls back to a plain sentence.

## D48: Neutral voice outside the story text
- "My" was in the hero line, a side label and the headline. Those are now neutral: hero line "Ride demand in New York, forecast a day ahead"; under the number "smaller average error than a simple guess."; side figures "Model: off by" and "Simple guess: off by"; headline "It won on 26 of 28 days. A winter storm still broke it." First person stays in the story paragraphs and the "What would change my mind" section.

## D49: Hero reads as one sentence, one "my"
- Line above the number, number, line below now form a sentence: "The model's average error is [13.7%] lower than a simple guess." What the project forecasts moved into the small footnote. The headline says "My model won on 26 of 28 days. A winter storm still broke it." That is the one first-person phrase up top.

## D50: Question hook and a rolling meter
- The hero opens with the question the project answers: "Can you predict where New York wants a ride tomorrow?" The number answers it ("lower error than a simple guess"). LightGBM is named once, in the footnote, with the one "I": "That is the LightGBM model I trained ...". Everything after says "the model": side figure, headline ("The model won on 26 of 28 days. A winter storm still broke it.").
- The digits roll up like an odometer once when the page or view loads, staggered left to right, about two seconds. The markup carries the final value as an accessible label, and with reduced motion the roll is skipped and the final number simply shows. The value is the computed one, never a typed constant.

## D51: Say what the storm line means, say what a simple guess is
- The headline promised "A winter storm still broke it" but the text under it never mentioned a storm. The story now has a paragraph straight after the busiest-zone one: the worst day, its cause from the checked source, how many times a typical day's error it was, and why (no weather input). It is computed, and only appears when that ratio is at least 1.5, the same condition that adds the storm half of the headline, so the two cannot disagree.
- "Simple guess" now comes with an example everywhere a reader first meets it: to guess next Tuesday at 6pm, average the last four Tuesdays at 6pm. That matches the code (same hour of the week, 1 to 4 weeks back), not just "same hour". Hero footnote, the story paragraph and the glossary use it.

## D52: Front end moves to a static site (Vercel), Streamlit kept as the local option
Why: Streamlit limits layout and animation, and a visitor cannot run it from GitHub without Python. A static site (plain HTML/CSS/JS, Vega-Lite charts) deploys free beside the portfolio.
How: `python -m src.make_site` imports the same app functions and writes `site/data/story.json` and `theme.json`, so every number and sentence on the site is the one the Streamlit app computes. The browser only draws.
Stage 1 is the Story page. Nothing is switched until the look matches. Dashboard is stage 2. Fake preview data is never shipped.

## D53: Static dashboard (stage 2)
Tabs: Forecast, Compare zones, Scoreboard, Where it fails, Storm days, Method, About. Map waits for the zone geojson.
Data: `dashboard.json` plus one `zones/<id>.json` per zone, loaded only when picked. The per-day sentence and per-day MAE are computed in Python at build time (full precision), so the browser never recomputes a claim. The compare-zones sentence is ported to JS and checked against Python for every day (0 mismatches on the preview data; test in tests/test_site_parity.py, skipped if Playwright is missing).
Additions that only a static site allows: day scrubber with Play and a win/loss strip of every day, linked hover across two charts, receipt-style scoreboard, weather replay on storm days (shown only when the verified cause names snow, rain or a storm), cabs slow down on storm days, save chart as image, copy link.
Not yet: forecaster game, punch-in checks, accessibility pass, map, Domain B toggle.

## D54: Stage 3 additions
Chart actions (save image, copy link, CSV) now sit in one toolbar row directly above the chart they act on, hover hint on the left.
"Your turn": the visitor draws a forecast for a held-out day (never the day shown above, same zone, a week earlier), then sees their miss next to the model's and the simple rule's, computed in the browser from the day's rows. Copy says one day proves nothing.
Punch-in status chips, a table view under each chart, tab ARIA, live-region takeaways, keyboard drawing, striped (not colour-only) loss ticks.
Map tab appears only when `app/zones30.geojson` exists. Link previews: `assets/og.png` has no numbers so it can never go stale; `--site-url` writes the absolute address into index.html.
Domain B toggle is not built: it needs Domain B results first.

## D55: Motion pass
Up-close lines draw in the first time the chart is half on screen (actual, model, then the dashed rule, then the biggest-miss marker). A small cab rides the model line on the Forecast tab: it drives across when the day changes, then follows the mouse; it carries no numbers. Map tab: zoom buttons, drag to pan, ctrl/cmd + wheel; legend stays fixed. Storm weather runs 8 seconds then fades; Replay restarts it.
Under reduced motion: lines are static, the cab only follows the pointer, weather does not run. Checked at 390px: no sideways scroll.

## D56: fix round after review of the motion pass
- Centering is scoped to dashboard result cards and takeaways (`.tabpanel`). The Story game result cards are left-aligned again; the earlier rule leaked into them.
- Map zoom is rebuilt on Vega signals (zoom, panx, pany) rather than DOM edits, so it survives re-renders. Zoom in, Zoom out, Reset buttons, drag to pan when zoomed, ctrl/cmd + scroll to zoom. Zoom persists when switching map mode.
- Zone outlines are re-wound in the browser (outer ring clockwise). d3 fills the outside of a wrongly wound polygon, which painted the whole canvas one colour in a test. Tested on fake polygons only, not the real TLC shapes.
- Banner: a lead cab sits on the road and follows page scroll on the Story, the chosen day on Forecast and the hour on the map. The Storm tab slows traffic and snows on the banner.

## D57: motion pass 2
- New `site/assets/motion.js` holds every new effect; app.js and dashboard.js only call into it. Everything animates transform or opacity only, is paused off-screen where it loops (map zones), and checks `prefers-reduced-motion` first (final state shown, nothing moves).
- Banner: click a cab to make it jolt and show a "Beep!" bubble (no sound, decided against it). Rush hour button adds 4 cars and speeds traffic; on the map's "Demand by hour" the traffic follows the real share of the day's rides in that hour. Storm slowdown and rush speed multiply. Picking a zone makes the lead cab pull over with a pickup pin. Clicking the headline meter spins it again. Headlights come on in dark mode.
- Story: the up-close chart draws what happened, then the model, then the simple rule, then fades in shaded misses (blue model, gray rule). Game: your line morphs into the model line, then the real lines draw and the three cards count up. The storm finding card gets a typical-day vs storm-day bar pair (heights from the card's own ratio), light snow and a count-up when scrolled into view. Dark mode switches with a circular wipe (View Transitions, falls back to an instant switch).
- Dashboard: day ticks pop in one by one; Play leaves faint trails of the previous 3 days' model line; scoreboard and zone-gain bars grow in order (gain bars out from zero); the heatmap wipes in; map zones breathe with demand; sorted table rows slide to their new places; skeleton shimmer while data loads.
- Measured in headless Chromium: 60 fps, p95 frame time 17 ms in every scene with all effects on (rush hour, map pulse, Play with trail). Not measured on a phone.

## D58: fixes after trying motion pass 2
- The lead cab looked stuck: the banner scrolls away, so a scroll-driven cab never visibly moved. A thin road with a tiny lead cab and a yellow trail is now pinned to the top of the window once the banner is off screen. The banner cab gets a trail and a small idle bounce.
- Click-to-honk removed (nobody clicks cars). Cars now honk by themselves in two moments: when Rush hour is switched on and when you beat the model in the game.
- "Copy link to this chart" now copies a chart-only link (`focus=1`): no banner, tabs or controls, a title (zone and day), the chart, the takeaway and the metric cards, plus a button to open the full dashboard. Works on every dashboard tab; the Forecast tab is the one tested end to end.
- Day ticks pop in over under a second however many days there are (it was 22 ms per day, several seconds on 250 days).
- Heatmap (Where it fails tab, second chart) wipes in when scrolled to; bars and heatmap now have a 9 second failsafe so a missed visibility event can never leave them hidden.

## D59: motion pass 3
- Scoreboard receipt prints from the top in steps, rows drop in one by one and the MAE numbers count up to their real values.
- Map "Demand by hour": zones pulse by absolute demand (busiest hour and zone fastest), the busiest zones get a glow, and a "Near the day's peak demand" badge shows when that hour's total is within 8% of the day's busiest hour. It says demand, not prices, on purpose: the data has no surge pricing.
- Forecast tab: "Replay the held-out weeks" steps through the held-out days of the chosen zone at one per second with a running tally (days won, average miss for model and simple rule), computed from that zone's own numbers, not the headline.
- Where it fails: a "Dispatch log" of the six days with the largest model error, typed out line by line, with the verified cause where the records have one and "No verified cause" otherwise.

## D60: fixes from trying motion pass 3
- The chart cab took 3.2 s to cross but each replayed day lasts 1 s, so it reset a quarter of the way across. While playing it now crosses in 85% of the day's time.
- Play and Replay got a Speed control (Slow 2 s, Normal 1 s, Fast 0.5 s per day). Replay runs only the held-out days with a running tally; Play runs every day in the zone.
- The lead cab follows the page scroll on both views. Before, the dashboard tied it to the selected day, which by default is the last day, so it sat at the far right and looked stuck.
- Dispatch log lines now have a "See this day" button that opens that day in the Forecast tab. The log is the all-zone daily error, the same for every zone.
- Numeric table columns are centred under their headings. After a game reveal, Start over now restarts the game like "Try another go".

## D61: mobile pass, map click-through, game rounds, result card
- Phone width (390 px): no sideways page scroll on any tab. Fixes: tab bar scrolls sideways (and keeps the active tab in view) instead of wrapping to four rows; the Rush hour button was stretched into a tall pill in the compact banner; the drawing game uses a taller canvas with larger labels and dots.
- Map: click a zone to open its Forecast (drag-to-pan is ignored), plus an "Open a zone's forecast" dropdown for keyboard and screen-reader use.
- Game: `games` in story.json holds up to 5 rounds (the original, then zones spread busiest to quietest on held-out days by a fixed rule, never the day the page shows). "Next round" cycles them. A running tally of the visitor's own rounds is kept in localStorage (last 60) and reads only "you beat the rule in A, the model in B", nothing more.
- Result card: "Save the result as an image" draws a 1200x630 PNG from the same hero text the page shows, so it cannot disagree with the page.
- Tested on fake data and a 390 px headless phone viewport. Not tested on a real phone.

## D62 Richer card, chart saves, hints, error states, score history, methods
- Result card now includes one real zone-day line chart (from the page's own up_close rows) and a scope line ("30 NYC zones, N held-out days, scored once") parsed from the hero text, so it cannot disagree with the page.
- Every chart gets "Save chart as image": PNG with its heading as title, page background and a footer. Existing Forecast and Storm buttons use the same composer.
- One-line hint at the top of each tab; "The test in 60 seconds" at the top of Method (counts read from timeline, not typed).
- Failed zone or dashboard fetch shows a message with Try again instead of an empty chart.
- Game shows the last 10 rounds as labelled chips (text, not colour alone). Scores stay in localStorage only.
- Keyboard pass in headless Chromium: all focusable elements show a focus style, tab arrow keys work. Not tested with a real screen reader.
- Domain B toggle not built: no Domain B results yet.

## D63 Fixes after review of D62
- Yellow highlight in body text is now a 3px underline below the text (the old gradient covered the lower third of the letters in dark mode).
- Result card chart title shrinks to fit its box (the long date overflowed on real data).
- Tab hint is small and muted. Discovery no longer depends on reading it: sortable headers carry a faint sort glyph, and the day strip ripples once per visit.
- Not done: a map hover tip (vega geoshape tooltip cannot take a constant line cheaply); the pointer cursor and the "Open a zone's forecast" dropdown stay.

## D64 Play the day, day/night shading, fleet section
- Map "Play the day" now glides between hours (dataset updated in place, about 25 updates a second), with a clock and a night tint. With reduced motion it steps hourly as before.
- Forecast chart has faint day/night shading from a fixed 06:00 to 18:00 curve, not real sunrise times (the page says so).
- Story gets "Taking this into a real fleet": what carries over, what would change, what this does not prove. Text lives in make_site.FLEET, no numbers. The middle column is labelled as a plan.

## D65 Result card button hidden from visitors; Domain B step 1
- The "Save the result card" button only shows with ?card=1 in the address. A visitor has no reason to save it; its use is as the link preview and social image, which only the site owner sets up.
- Domain B (European electricity) started: src/opsd_download.py downloads OPSD hourly data, keeps national load (actual) and the operators' day-ahead forecast, and prints coverage per country. The country list and held-out weeks are chosen from that report, not before it. Nothing modelled yet.

## D66 Domain B (European electricity) pipeline, built on synthetic data only
- Coverage table (real) showed 2015-01-01 to 2020-09-30, 27 usable countries. Country rule fixed before any model: measured load gap <= 14 h, <= 0.1% missing, operator forecast <= 0.2% missing, then the 10 with the largest average load (src/elec_data.py). Small gaps interpolated and counted.
- Time: UTC index, midnight UTC origins, 24 h horizon. Hour, weekday, month, day of year and holidays are read from each country's local clock; national holidays only, no regional ones.
- Model: one global LightGBM predicting load relative to a recent level (672 h mean ending 24 h before the target), so a 60 GW and a 5 GW country share one model. L2 objective, parameters fixed in advance, refit every 7 days.
- Benchmark: the grid operators' own day-ahead forecast. It was issued about half a day before our origin and uses weather forecasts we do not have, so it is a reference line, not a fair fight. Stated on the site.
- Split: dev = the 364 midnights before the cut; held-out = the last 28 origin days (cut = 28 origin days before the last full day). Held-out weeks fall in Sept 2020, after the spring lockdowns, and COVID will be named as a limit.
- Metrics: MAE (MW), MASE, MAPE and weighted MAPE (MAPE is what operators publish). MAPE and MASE weight countries differently from MAE, which big countries dominate.
- Best simple baseline is chosen on dev only and written to results/elec_dev_best.txt; the final stage reads it and refuses a second run (results/elec_heldout_run.json).
- Same leak tests as ride-hail: features equal an independent recomputation, truncation invariance, and a planted leak is caught. Smoke-tested end to end on synthetic data only; no real electricity number exists yet.

## D67 Fix: operator forecast gaps at the ends
- Real run failed: some operator-forecast series start or end later than the measured load, and interpolation does not fill the ends. The common span now starts at the latest first value and ends at the earliest last value across all actual and operator series. The eligibility rule also requires the operator forecast to have no gap over 14 hours. The error now names the column and the first missing hour. The test reproduces the failure.

## D68 Country rule revised once, after the first development run (disclosed)
- My D67 fix added "operator forecast has no gap over 14 hours". On the real data that removed DE, IT, PL, BE, CH, HU and HR (each has one missing day in the operator forecast), leaving 7 countries without the largest ones. That was an artefact of my own fix, not a considered choice.
- Revised: operator forecast gaps are no longer a reason to drop a country and are not interpolated. Hours with no operator forecast are left out of scoring for every model, so all models are scored on identical hours. The count is reported.
- This was decided after a first development run on the 7-country set (held-out weeks were never read). The development numbers from that run (LightGBM MAE 465 vs 944 for same-hour-last-week; operator forecast 560) are discarded and the development run is redone on the new set. Nothing about the held-out weeks informed the change.
- Pre-committed before the rerun: every chosen country stays in whatever its operator forecast looks like. A data check (operator forecast vs measured load by year) is printed to flag series that look like they measure something else; if one does, it is named on the site, not removed.
- First run also showed: the operator forecast was far worse for NL (about 13% error) and much better than the model for DK, ES and FR. So the site will not claim the model beats the operator forecast unless the per-country table supports it.

## D69 Electricity page and project switch
- New page site/elec.html (script assets/elec.js) reads data/elec/elec.json, built by src/make_site_elec.py from results/elec_*; python -m src.make_site writes it automatically when the electricity results exist. A switch at the top of both pages moves between ride-hail and electricity; the dark-mode choice carries over.
- Every number and every result-dependent sentence is computed in make_site_elec.py. Wording follows the sign of the result (a bad result says "higher error" and "more misses"); a test covers it. The operator forecast is flagged as not like for like when its mean error is above 4% in every year of the data (rule written before the held-out run; NL, CH and AT trip it).
- Electricity accent is light blue (ride-hail stays yellow); same type and layout.
- Checked on synthetic results only: layout light and dark, 390 px width with no sideways scroll. Real numbers will appear when make_site is run on the real results.

## D70 Electricity page split into Story and Dashboard
- The first version put everything on one long page. It now mirrors the ride-hail site: Story (headline, three short paragraphs, three cards, one fixed up-close chart, the top three limits) and Dashboard with four tabs (Forecast with country and day pickers, Countries, Worst days with a day-by-day chart, Method and limits). Same Story/Dashboard switch in the header.
- Result-dependent sentences are sign-aware ("worse" when the model is worse). Removed a sentence about weekends and holidays being harder because I had not checked it.

## D71: the electricity page gets its own look and its own interaction
The electricity page was a recolored copy of the taxi page. Now: dark control-room banner (graph paper, a real held-out day drawn across it, large cyan number counting up), dark by default unless the visitor chose a mode, and a "Ten countries, one day" section (a day slider and Play moving through the 28 held-out days, one row per country, shaded gap is the miss). All numbers are computed in the browser from elec.json, which comes from the results files. Motion is skipped under reduced motion. Operator figures stay numbers only, flagged where not like for like.

## D72: electricity extras
Added: Replay this day on each worst-day card (redraws that country and day); weekday by hour heatmap of model miss pooled over countries, with a plain note that each weekday has only 4 test days; a "Your turn" tab where the visitor draws a day and is scored against the model and the simple guess (session tally, no storage); a tile map beside the slider showing whether the model or the operators were closer that day, with operator-flagged countries dashed and no winner called. Everything is computed in the browser from elec.json. make_site_elec now adds day index and worst-country code to the worst-day entries. Not added: band hover note.

## D73: electricity chart and heatmap motion
Charts wipe in from the left the first time they scroll into view (and when a worst day is replayed); heatmap squares fade in left to right by hour; the game's answer lines draw on after Check my guess. All of it is skipped under reduced motion, has a timer fallback if the scroll observer is missing, and removes its clip once done so tooltips are not cut off.

## D74: electricity charts start animating sooner
The wipe and heatmap fade now start as soon as a few percent of the chart is on screen (was a quarter or a third), the wipe takes 0.9 s, and the heatmap stagger is 16 ms per hour, so nothing waits to be scrolled into the middle first.

## D75: link preview and favicon for the electricity page
elec.html gets its own og:image, og:url, twitter card, theme colour and a cyan favicon. The preview picture (site/assets/og-elec.png) is drawn by src/og_elec.py every time make_site_elec runs, from the same hero numbers and the same last held-out day as the page, so it cannot drift from the results. If drawing fails the page data still builds. make_site --site-url now fills in both pages' og:image and og:url. Two small font files (src/fonts) are used for the picture only.

## D76: weather test, set up before any weather result existed (option 2: a different window)
Why a new window: scoring a weather model on the September 2020 held-out days would be a second look at days already scored once, and the weather file (OPSD weather_data, MERRA-2, population-weighted country temperature, hourly UTC) ends in 2019 anyway.
Fixed in advance, in code (src/elec_weather_run.py): window = the 28 origin days 3 to 30 November 2018 (heating season, pre-COVID, no national holiday); the run refuses to start if the window is not wholly before the development days used for the first test (they begin about 4 September 2019); models = the best baseline from the development result, the operators' forecast, the existing LightGBM, and the same LightGBM with four added features (temperature at the target hour, its 24 h mean, heating degrees below 15 C, cooling degrees above 22 C); all settings identical to the existing model, nothing tuned; expanding window, weekly refit, one scored run guarded by results/elec_weather_run.json.
Known weakness, stated on the page: the temperature given to the model is the measured one at the target hour, a perfect forecast, so the result is an upper bound on what weather adds.
The page gets a Weather tab and a short Story section only if the results files exist; all wording follows the sign of the result. The main headline (September 2020, scored once) is unchanged.
Pipeline: python -m src.opsd_weather (downloads about 220 MB once), python -m src.elec_weather_run (once), python -m src.make_site.

## D77: charts show at once when a tab is clicked
Measured on the Forecast tab: the chart waited about 3.7 s because the left-to-right wipe only started when an observer fired, and the chart sat low on the page with no height yet, so it fell back to a timer. Now any chart within one and a third screens of the top fades in over 0.22 s (about 0.25 to 0.3 s in all, including drawing); only charts far below the fold keep the scroll-in wipe, and its timer fallback is 6 s. Heatmap uses the same rule.

## D78: the wipe is back on tab clicks, and starts at once
Charts near the top of the page wipe in left to right again (0.8 s) starting the moment the tab is clicked, instead of waiting for a scroll watcher. Measured on the three tabs: the wipe is already moving at the first sample (under 30 ms) and finished by about 0.85 s. Charts far down the page still wipe when scrolled to. Reduced motion skips all of it.

## D79: "Is this a real problem?" on the electricity page
Three sources in docs/evidence_elec.csv, each opened and read before it was added: S&P Global Market Intelligence (6 Apr 2023, Texas grid operator's next-day peak forecast of 67,775 MW against 73,658 MW actual, 8% higher, Dec 2022); Ember (4 Jul 2025, 2025 European heatwave: demand up to 14% in Spain, average daily prices up 106% to 175% in Poland, France and Germany; the article is about demand and prices, not forecasting, and the card says so by only claiming that such moves are what a forecast must anticipate); Nature Communications (21 Aug 2026, load forecasting in heat and cold waves; one case study puts the extra cost of under-forecasting a day ahead at about 449 USD per MWh). The section says these show the problem is real, not that my model works. Only https links and safe image addresses are kept; only the Ember image has a credit I could read, so the other two cards have no picture. Also fixed a mobile sideways scroll caused by the tile map text on narrow screens.

## D80: pictures on all three source cards
S&P card: the article's own lead photo (credited in the article to 101cats via Getty Images); the card text now also gives the article's 9% against 3% target error figure. Nature card: Figure 1 from the paper, credited. The paper's licence is CC BY-NC-ND 4.0, which allows non-commercial sharing but no changes, so the figure is shown whole (fit inside the frame, not cropped) with its credit and licence in the corner. The Ember card keeps its photo. Images are hotlinked from the publishers, so a card falls back to the cyan block if a publisher blocks or moves its picture; the rest of the card still works.

## D81: three taxi-page features brought to the electricity page
(1) "What would change my mind": seven claims, each marked Holds, Fails or Untested by code from the results files (beats the simple guess in most countries; not just the biggest country; wins on most days; keeps up with the operators in countries whose operator series looks sound; the 10% to 90% range is near 80%; weather helps on the separate window, by the sign of its 95% range; and one Untested line about other months and years). A claim that fails is shown as failed. (2) "Taking this into a real grid": built, planned and not-proved columns, company-neutral. (3) A "Save chart as image" button under each chart, same picture layout as the taxi site, with a title and footer on the page background.

## D82: status stamps on the electricity page
The Holds, Fails and Untested labels stamp onto their rows one after another (160 ms apart) the first time the section scrolls into view, same as the ride-hail page. Skipped under reduced motion, and a 12 s timer shows them anyway if the scroll watcher never fires.
