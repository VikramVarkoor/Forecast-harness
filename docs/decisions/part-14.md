# Decisions, part 14

## D29: Equal-height cards, tighter bottom, visible view switch
- Finding cards, test-step cards and next-step cards are now rendered inside one CSS grid (`.cards`, `card_grid()`), not Streamlit columns, so every card in a row has the same height. Verified by measuring: 158/158, 156x4, 176x4 px.
- Streamlit's default ~10rem bottom padding trimmed to 1.5rem on the main container.
- Switching between Story and Dashboard now scrolls to the top (the button sits at the bottom of the Story page, so the old behaviour dropped the visitor mid-page on the Dashboard). The view is wrapped in a keyed container, so a yellow bar wipes across and the content rises in over about half a second. It replays only when the view changes, not on slider or dropdown reruns. Disabled under prefers-reduced-motion.
