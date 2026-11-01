# Session 17 decisions

## D32: Remove click-to-open help tooltips
- Streamlit's "?" help popovers stay open once clicked, stack on top of each other, and followed the visitor into other tabs (a stale popover appeared over the Where it fails tab). There is no setting to close them on blur.
- The three help texts under the Forecast metrics are now one plain caption below the numbers, and the download button's help is a caption above it. Same words, always visible, nothing to open or close. Verified: zero tooltip icons on the page, so nothing can get stuck.
