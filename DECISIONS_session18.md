# Session 18 decisions

## D33: Honest storm tab, loading message, share image
- Storm days tab now says plainly that only days whose cause was read in a source are listed, and counts the other days where the miss was at least 1.5 times the typical day (computed from the data, dates shown). Their causes are explicitly not guessed.
- Loading the forecasts shows a spinner. The Streamlit Cloud "app is waking up" screen after inactivity is outside the app's control and cannot be changed from inside it.
- Streamlit apps cannot set Open Graph tags, so a link pasted on LinkedIn gets a generic preview. Instead `python -m src.make_social` draws a 1200x630 taxi-meter image from the held-out results (the number is computed, not typed) into docs/social-preview.png, to be attached to the post and set as the GitHub repository social preview.
