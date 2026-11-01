# Session 13 decisions

## D28: Story page opens with a verdict, closes with next steps
- Removed the "In plain English" heading (too obvious). The plain paragraphs now sit under a one-sentence verdict set as large type.
- Verdict is built from the results files: "Beats a simple guess by X% on days it had never seen." It adds "A blizzard still breaks it." only when the storm-day error ratio is at least 1.5, so it can only say what the numbers say.
- Added "What I would do next": add the weather, use more history, test more places, reuse the harness. Copy makes no numeric claims.
- CSS: `.stApp p.verdict` with !important, because Streamlit's markdown styles otherwise override it.
