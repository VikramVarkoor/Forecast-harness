"""Viewer for the saved forecasts. Reads results/*.csv and *.parquet only; trains nothing."""
import base64
import html
import json
import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
RES = Path(os.environ.get("FORECAST_RESULTS", ROOT / "results"))
HERE = Path(__file__).resolve().parent
LOOKUP, FAVICON, GEO = HERE / "taxi_zone_lookup.csv", HERE / "favicon.png", HERE / "zones30.geojson"
REASONS = ROOT / "docs" / "day_reasons.csv"
BASE = "mean_same_hour_4w"
COLS = ["origin", "ts", "zone", "y", "lgbm", BASE, "q10_int", "q90_int"]
TAXI = "#FFC72C"
FONT = "Figtree, system-ui, sans-serif"
LINKS = [("Portfolio", "https://vikramvarkoor.vercel.app"), ("GitHub", "https://github.com/VikramVarkoor"),
         ("LinkedIn", "https://linkedin.com/in/vikram-varkoor")]
NAMES = {"lgbm": "LightGBM", "ets_weekly": "Exponential smoothing", "mean_same_hour_4w": "Mean of same hour, last 4 weeks",
         "same_hour_last_week": "Same hour last week", "same_hour_yesterday": "Same hour yesterday",
         "naive_last_hour": "Last hour held flat", "lgbm_plus_mean_same_hour_4w": "LightGBM + 4-week mean"}

# Light is the default. Both palettes were run through the dataviz validator against their surface.
# The baseline gray is a deliberate neutral, so the model it is compared with reads as the subject.
THEMES = {
    "light": dict(bg="#FBF8EF", panel="#F1ECDC", text="#111111", muted="#5E6370", grid="#E4DFCF", actual="#111111",
                  model="#2447D6", base="#80858F", warn="#D9480F", mid="#EFEBDD", band=0.55, held=0.35,
                  control="#111111", card="#F1ECDC", shadow="#111111", stub="#E9E3CE"),
    "dark": dict(bg="#12151C", panel="#1A1F29", text="#ECEEF2", muted="#9AA2B1", grid="#2A303C", actual="#ECEEF2",
                 model="#5C8DF5", base="#8A93A3", warn="#DE6A32", mid="#232A36", band=0.28, held=0.16,
                 control=TAXI, card="#1A1F29", shadow=TAXI, stub="#232A36"),
}


FONT_DIR = HERE / "fonts"
FACES = [("Fraunces", "fraunces.woff2", "normal", "100 900"), ("Figtree", "figtree.woff2", "normal", "300 900"),
         ("Newsreader", "newsreader.woff2", "normal", "200 800"), ("Newsreader", "newsreader-italic.woff2", "italic", "200 800")]


@st.cache_resource
def font_faces() -> str:
    """The three typefaces, embedded in the page itself so they load on any host without a static-file setting."""
    out = []
    for fam, fn, style, wt in FACES:
        p = FONT_DIR / fn
        if p.exists():
            b64 = base64.b64encode(p.read_bytes()).decode()
            out.append(f"@font-face {{font-family: '{fam}'; src: url(data:font/woff2;base64,{b64}) format('woff2'); "
                       f"font-weight: {wt}; font-style: {style}; font-display: swap;}}")
    return "\n".join(out)


def theme_css(t):
    return f"""
<style>
{font_faces()}
.stApp {{background: {t['bg']}; color: {t['text']};}}
.stApp, .stApp p, .stApp label, .stApp li, .stApp button, .stApp input, .stApp textarea, .stApp select,
.stApp [data-baseweb] div, .stApp [data-baseweb] span, .stApp [data-testid="stMarkdownContainer"] *,
[data-testid="stMetricLabel"] *, [data-baseweb="tab"] {{
  font-family: 'Figtree', system-ui, sans-serif;}}
.stApp h1, .stApp h2, .stApp h3, .stApp h1 *, .stApp h2 *, .stApp h3 *, [data-testid="stMetricValue"], [data-testid="stMetricValue"] * {{
  font-family: 'Fraunces', Georgia, serif !important; font-optical-sizing: auto;}}
[data-testid="stIconMaterial"], .stApp [class*="material-symbols"] {{font-family: 'Material Symbols Rounded' !important;}}
.stApp p, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3, [data-testid="stMetricValue"],
[data-testid="stMetricLabel"], [data-baseweb="tab"] p {{color: {t['text']};}}
.stApp a {{color: {t['text']}; text-decoration-color: {TAXI}; text-underline-offset: 3px;}}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {{color: {t['muted']};}}
[data-baseweb="tab-border"] {{background: {t['grid']};}}
.react-aria-SelectionIndicator {{background-color: {t['control']} !important;}}
[data-testid="stCheckbox"][data-selected="true"] label > div:first-of-type {{background-color: {t['control']} !important;}}
[data-testid="stCheckbox"][data-selected="true"] label > div:first-of-type * {{color: #111 !important; fill: #111 !important;}}
[data-testid="stSlider"] [class*="efbyxod3"] {{background-color: {t['control']} !important;}}
[data-testid="stButtonGroup"] button[role="radio"] {{background: transparent; border: 2px solid {t['text']};}}
[data-testid="stButtonGroup"] button[role="radio"] p {{color: {t['text']} !important; font-weight: 600;}}
[data-testid="stButtonGroup"] button[role="radio"][aria-checked="true"] {{background: {TAXI} !important;}}
[data-testid="stButtonGroup"] button[role="radio"][aria-checked="true"] p {{color: #111 !important;}}
.stSelectbox [role="group"] {{background-color: {t['panel']} !important; border-color: {t['grid']} !important;}}
.stSelectbox input, .stSelectbox [role="group"] * {{color: {t['text']} !important;}}
.stSelectbox svg {{fill: {t['text']} !important;}}
[role="listbox"], [role="listbox"] [role="option"], .react-aria-Popover {{
  background-color: {t['panel']} !important; color: {t['text']} !important;}}
[data-testid="stTooltipIcon"] button, [data-testid="stTooltipIcon"] svg {{color: {t['muted']} !important; stroke: {t['muted']} !important; fill: none !important;}}
{('[data-testid="stSlider"] [class*="efbyxod5"] {background: #3A4252 !important;}') if t['control'] == TAXI else ''}
[role="slider"] {{background-color: {t['control']} !important;}}
.stButton button, .stDownloadButton button {{background: {TAXI}; color: #111; border: 2px solid #111; font-weight: 700;}}
.stButton button p, .stDownloadButton button p {{color: #111 !important; font-weight: 700;}}
[data-testid="stAlert"] {{background: {t['panel']}; color: {t['text']};}}
header[data-testid="stHeader"] {{display: none;}}
.block-container {{padding-top: .8rem !important; max-width: 1200px;}}
.hero {{position: relative; background: {TAXI}; margin: .4rem -50vw 0; padding: 4.8rem 50vw 2.2rem;}}
.stApp .hero p {{color: #111111;}}
.hero-in {{max-width: 1200px; margin: 0 auto; display: flex; flex-wrap: wrap; gap: 1.5rem 4rem; align-items: flex-end;
  box-sizing: border-box;}}
.hero p.hero-kicker {{font-size: 1.05rem !important; font-weight: 600; margin: 0 0 1rem !important;}}
.meter {{display: block;}}
.meter span {{font-family: 'Figtree', system-ui, sans-serif !important; font-variant-numeric: tabular-nums; background: #111; color: {TAXI}; border-radius: .14em; font-weight: 900; letter-spacing: -0.02em;
  font-size: clamp(3.8rem, 10vw, 8rem); line-height: 1.02; padding: .02em .13em;
  box-shadow: inset 0 -.08em 0 rgba(255,255,255,.08);}}
.meter-in {{display: flex; gap: .35rem; align-items: stretch;}}
.meter span.d {{display: block; height: 1.06em; padding: 0 .13em; overflow: hidden; line-height: 1.06;}}
.meter .strip {{display: block; font-style: normal; transform: translateY(calc(var(--end) * -5%));
  animation: tick calc(1.1s + var(--i) * .2s) cubic-bezier(.2, .8, .2, 1) backwards; will-change: transform;}}
.meter .strip b {{display: block; height: 1.06em; line-height: 1.06; font-weight: 900;}}
@keyframes tick {{from {{transform: translateY(0);}}}}
@media (prefers-reduced-motion: reduce) {{.meter .strip {{animation: none;}}}}
.meter span.dot {{padding: .02em .05em;}}
.hero p.hero-kicker.lead {{font-size: 1.5rem !important; font-weight: 700; margin-bottom: .7rem !important;}}
.hero p.hero-cap {{font-size: 1.5rem !important; font-weight: 700; margin: .8rem 0 .5rem !important; line-height: 1.2;}}
.hero p.hero-fine {{font-size: 1rem !important; max-width: 31rem; margin: 0 !important; line-height: 1.4;}}
.tip {{display: inline-flex; align-items: center; gap: .5rem; border: 2px dashed {t['text']}; border-radius: 999px; padding: .2rem .9rem .2rem .7rem;
  font-size: .92rem; font-weight: 600; margin: .2rem 0 .8rem;}}
.tip svg {{flex: none;}}
.hero-side span {{display: block; font-size: .8rem; opacity: .85;}}
.hero.compact .hero-side span {{display: none;}}
.hero.compact {{padding-top: 3.6rem; padding-bottom: 1rem;}}
.hero.compact .meter span {{font-size: clamp(2rem, 5vw, 3.2rem);}}
.hero.compact .hero-side b {{font-size: 1.8rem;}}
.hero.compact .hero-side {{padding-bottom: 0;}}
.hero.compact p.hero-kicker {{margin-bottom: .5rem !important;}}
.hero-side {{display: flex; gap: 2.4rem; padding-bottom: .4rem; color: #111;}}
.hero-side div {{font-size: .95rem;}}
.hero-side b {{font-family: 'Fraunces', Georgia, serif !important; display: block; font-size: 2.8rem; line-height: 1; font-weight: 800;}}
.road {{position: absolute; left: 50%; width: 100vw; margin-left: -50vw; top: 16px; height: 46px; background: #111; overflow: hidden; pointer-events: none;}}
.road::after {{content: ""; position: absolute; left: 0; right: 0; top: calc(50% - 1px); height: 2px;
  background: repeating-linear-gradient(90deg, {TAXI} 0 16px, transparent 16px 34px);}}
.cab {{position: absolute; left: 0; height: 20px; width: 44px; animation: var(--dir) var(--dur) linear var(--delay) infinite; will-change: transform;}}
.cab svg {{display: block; width: 100%; height: 100%;}}
.cab.up {{top: 2px;}}
.cab.down {{top: 24px;}}
@keyframes east {{from {{transform: translateX(-60px);}} to {{transform: translateX(100vw);}}}}
@keyframes west {{from {{transform: translateX(100vw) scaleX(-1);}} to {{transform: translateX(-60px) scaleX(-1);}}}}
.hero.compact .road {{height: 40px; top: 10px;}}
.hero.compact .cab {{height: 17px; width: 38px;}}
.hero.compact .cab.up {{top: 2px;}}
.hero.compact .cab.down {{top: 21px;}}
@media (prefers-reduced-motion: reduce) {{.cab {{animation: none; transform: translateX(calc(var(--delay) * -40px - 20px));}} .cab.down {{transform: translateX(calc(var(--delay) * -40px + 400px)) scaleX(-1);}}}}
.checker {{height: 28px; margin: 0 -50vw 1.6rem;
  background: repeating-conic-gradient(#111 0% 25%, {TAXI} 0% 50%) 0 0 / 28px 28px;}}
[data-baseweb="tab"] p {{font-size: 1.05rem; font-weight: 600;}}
h2, h3 {{font-weight: 700 !important; letter-spacing: -0.01em;}}
.card, a.news {{position: relative; overflow: hidden; display: flex; flex-direction: column; background: {t['card']}; border: 2px solid {t['text']};
  border-radius: 12px; box-shadow: 6px 6px 0 {t['shadow']}; box-sizing: border-box; height: 100%;
  transition: transform .16s ease, box-shadow .16s ease;}}
.card:hover, a.news:hover {{transform: translate(-3px, -3px); box-shadow: 9px 9px 0 {t['shadow']};}}
.tear {{display: block; position: relative; height: 0; border-top: 2px dashed {t['text']}; margin: 0; flex: none;}}
.tear::before, .tear::after {{content: ""; position: absolute; top: -12px; width: 22px; height: 22px; border-radius: 50%;
  background: {t['bg']}; border: 2px solid {t['text']}; box-sizing: border-box;}}
.tear::before {{left: -13px;}}
.tear::after {{right: -13px;}}
.stApp .card p {{margin: 0;}}
.card .big {{font-family: 'Fraunces', Georgia, serif !important; font-optical-sizing: auto; font-size: 2.7rem; font-weight: 800; line-height: 1;
  letter-spacing: -0.02em; padding: 1.1rem 1.2rem 1rem; background: {t['stub']};}}
.card .lab {{font-family: 'Fraunces', Georgia, serif !important; font-weight: 700; font-size: 1.1rem; line-height: 1.2; padding: 1rem 1.2rem 0 !important;
  margin: 0 !important;}}
.card .sub {{color: {t['muted']}; font-size: .95rem; line-height: 1.4; padding: .4rem 1.2rem 1.1rem !important; flex: 1;}}
.timeline {{display: flex; border: 2px solid {t['text']}; border-radius: 6px; overflow: hidden; margin: .6rem 0 1.2rem;}}
.timeline div {{padding: .8rem 1rem; font-weight: 600; font-size: .95rem; box-sizing: border-box;}}
.timeline .train {{background: {t['panel']}; color: {t['text']};}}
.timeline .held {{background: {TAXI}; color: #111; border-left: 2px solid {t['text']};}}
.stApp p.verdict {{font-family: 'Fraunces', Georgia, serif !important; font-optical-sizing: auto; font-size: clamp(1.9rem, 4.2vw, 3rem) !important; font-weight: 800 !important; line-height: 1.1 !important; letter-spacing: -0.02em;
  max-width: 40rem; margin: .4rem 0 1.4rem !important;}}
.stApp p.takeaway {{font-size: 1.15rem !important; font-weight: 600; background: {t['stub']}; border: 2px solid {t['text']}; border-radius: 12px;
  box-shadow: 5px 5px 0 {t['shadow']}; padding: .8rem 1.1rem; max-width: 46rem; margin: .6rem 8px 1.2rem 0 !important;}}
[data-testid="stMain"], section.stMain {{overflow-x: hidden !important;}}
#vg-tooltip-element {{max-width: 600px; padding: 14px 18px !important; background: {t['card']} !important; color: {t['text']} !important;
  border: 2px solid {t['text']} !important; box-shadow: 4px 4px 0 {t['shadow']} !important;}}
#vg-tooltip-element table {{border-spacing: 0 10px; width: 100%;}}
#vg-tooltip-element td.key {{text-align: left !important; vertical-align: top !important; white-space: nowrap; padding-right: 18px !important;
  font-weight: 700; color: {t['muted']} !important;}}
#vg-tooltip-element td.value {{text-align: left !important; vertical-align: top !important; max-width: 420px !important; white-space: normal !important;
  overflow: visible !important; text-overflow: clip !important; line-height: 1.4;}}
.stApp p.takeaway.center {{margin: .6rem auto 2.2rem !important; text-align: center;}}
[data-testid="stMain"], [data-testid="stMain"]:focus, [data-testid="stMain"]:focus-visible, [data-testid="stMainBlockContainer"]:focus, [data-testid="stAppViewContainer"]:focus {{outline: none !important; box-shadow: none !important;}}
.stApp [data-testid="stCaptionContainer"].center, .stApp [data-testid="stCaptionContainer"].center p {{text-align: center;}}
.stApp p.zone-note {{font-family: 'Newsreader', Georgia, serif !important; font-style: italic; font-size: 1.08rem; line-height: 1.45;
  color: {t['muted']}; text-align: center; max-width: 46rem; margin: .8rem auto 0 !important;}}
.word {{font-size: 1.75rem !important; padding-top: 1.3rem !important; padding-bottom: 1.15rem !important;}}
a.news {{text-decoration: none !important; color: {t['text']} !important;}}
a.news > * {{display: block;}}
.news-img {{--checker-img: repeating-conic-gradient(#111 0% 25%, {TAXI} 0% 50%); position: relative; height: 160px;
  background-color: {TAXI}; background-size: cover, 24px 24px; background-position: center, 0 0;}}
.news-img.none {{height: 56px; background-image: var(--checker-img); background-size: 24px 24px; background-position: 0 0;}}
a.news .news-date {{position: absolute; top: .7rem; left: .7rem; background: {TAXI}; color: #111; border: 2px solid #111; border-radius: 4px;
  padding: .12rem .5rem; font-family: 'Fraunces', Georgia, serif; font-weight: 800; font-size: .95rem; transform: rotate(-3deg);}}
a.news .news-credit {{position: absolute; right: .5rem; bottom: .5rem; background: rgba(17,17,17,.78); color: #fff; font-size: .7rem;
  padding: .1rem .45rem; border-radius: 3px;}}
a.news .news-body {{display: flex; flex-direction: column; gap: .45rem; padding: .9rem 1.2rem 1.1rem; flex: 1;}}
a.news:focus-visible {{outline: 3px solid {TAXI}; outline-offset: 3px;}}
a.news .news-src {{font-size: .85rem; color: {t['muted']}; font-weight: 600;}}
a.news .news-title {{font-family: 'Fraunces', Georgia, serif !important; font-optical-sizing: auto; font-size: 1.3rem; line-height: 1.2; font-weight: 700;}}
a.news .news-why {{font-size: .95rem; line-height: 1.4;}}
a.news .news-go {{margin-top: auto; padding-top: .4rem; font-weight: 700; font-size: .9rem; text-decoration: underline; text-decoration-color: {TAXI}; text-underline-offset: 3px;}}
.cards {{display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1.4rem; margin: .8rem 0 1.8rem 0; padding: 0 8px 8px 0; align-items: stretch;}}
.cards .card, .cards a.news {{height: auto;}}
@media (prefers-reduced-motion: reduce) {{.card, a.news {{transition: none;}} .card:hover, a.news:hover {{transform: none;}}}}
@keyframes rise {{from {{opacity: 0; transform: translateY(14px);}} to {{opacity: 1; transform: none;}}}}
@keyframes wipe {{0% {{transform: scaleX(0); opacity: 1;}} 60% {{transform: scaleX(1); opacity: 1;}} 100% {{transform: scaleX(1); opacity: 0;}}}}
[class*="st-key-view_"] {{position: relative; animation: rise .45s cubic-bezier(.2,.7,.2,1) both;}}
[class*="st-key-view_"]::before {{content: ""; position: absolute; top: -6px; left: 0; right: 0; height: 6px; background: {TAXI};
  transform-origin: left; animation: wipe .9s cubic-bezier(.6,0,.2,1) both;}}
@media (prefers-reduced-motion: reduce) {{[class*="st-key-view_"], [class*="st-key-view_"]::before {{animation: none;}}}}
[data-testid="stMainBlockContainer"], .block-container {{padding-bottom: 1.5rem !important;}}
[data-testid="stAppScrollToBottomContainer"], [data-testid="stBottom"] {{min-height: 0 !important;}}
[data-testid="stMainBlockContainer"] {{min-height: 100vh; box-sizing: border-box;}}
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {{min-height: calc(100vh - 2.5rem);}}
[data-testid="stElementContainer"]:has(.footer) {{margin-top: auto;}}
.plain {{max-width: 46rem; margin: .2rem 0 1.6rem;}}
.stApp .plain p, .stApp .plain p * {{font-family: 'Newsreader', Georgia, serif !important;}}
.stApp .plain p {{ font-size: 1.38rem; line-height: 1.5; margin: 0 0 1rem; font-weight: 420;}}
.stApp [data-testid="stCaptionContainer"] p, .stApp [data-testid="stCaptionContainer"] p * {{font-family: 'Newsreader', Georgia, serif !important;}}
.stApp [data-testid="stCaptionContainer"] p {{ font-size: 1.08rem; line-height: 1.45; font-style: italic;}}
.stApp .plain b {{background: linear-gradient(transparent 62%, {TAXI} 62%);}}
.mind {{display: grid; gap: .8rem; margin: .6rem 8px 1.8rem 0; max-width: 52rem;}}
.mind-row {{display: flex; gap: 1rem; align-items: flex-start; border: 2px solid {t['text']}; border-radius: 12px; background: {t['card']};
  padding: .8rem 1rem; box-shadow: 4px 4px 0 {t['shadow']};}}
.mind-row div {{display: flex; flex-direction: column; gap: .15rem;}}
.mind-row b {{font-family: 'Fraunces', Georgia, serif; font-size: 1.1rem; font-weight: 700;}}
.mind-row div span {{color: {t['muted']}; font-size: .95rem; line-height: 1.4;}}
.chip {{flex: none; min-width: 6.2rem; text-align: center; font-weight: 800; font-size: .85rem; border: 2px solid #111; border-radius: 999px; padding: .15rem .6rem;}}
.chip.holds {{background: {TAXI}; color: #111;}}
.chip.fails {{background: {t['warn']}; color: #fff;}}
.chip.untested {{background: transparent; color: {t['text']}; border: 2px dashed {t['text']};}}
.gloss {{border: 2px solid {t['text']}; border-radius: 6px; padding: .7rem 1.1rem; margin: 1.2rem 0;}}
.gloss summary {{font-weight: 700; cursor: pointer;}}
.stApp .gloss p {{margin: .7rem 0 0; font-size: 1rem; line-height: 1.45;}}
.footer {{margin-top: 1.4rem; padding-top: 1rem; border-top: 2px solid {t['text']}; font-size: .95rem;}}
</style>
"""


@st.cache_data
def load(res_dir: str = str(RES)):
    d = Path(res_dir)
    a = pd.read_parquet(d / "predictions.parquet", columns=COLS).assign(split="development")
    h = d / "heldout_predictions.parquet"
    if h.exists():
        a = pd.concat([a, pd.read_parquet(h, columns=COLS).assign(split="held-out")], ignore_index=True)
    return a


@st.cache_data
def zone_names(path: str = str(LOOKUP)) -> dict:
    """LocationID -> 'Borough, Zone' from the TLC lookup file. Empty if the file is missing."""
    p = Path(path)
    if not p.exists():
        return {}
    z = pd.read_csv(p)
    return {int(r.LocationID): f"{r.Borough}, {r.Zone}" for r in z.itertuples()}


@st.cache_data
def day_reasons(path: str = str(REASONS)) -> pd.DataFrame:
    p = Path(path)
    return pd.read_csv(p, parse_dates=["date"]) if p.exists() else pd.DataFrame(columns=["date", "reason", "source"])


@st.cache_data
def evidence(path: str = str(ROOT / "docs" / "evidence.csv")) -> pd.DataFrame:
    """Sources showing the problem is real. Every row was opened and read before it was added."""
    p = Path(path)
    return pd.read_csv(p) if p.exists() else pd.DataFrame(columns=["outlet", "date", "title", "url", "why"])


def evidence_items(ev):
    """Source cards as plain dicts. Only https links are kept, and an image address is kept only if it is safe to put in a CSS url()."""
    out = []
    for r in ev.itertuples():
        if not str(r.url).startswith("https://"):
            continue
        img = str(getattr(r, "image", "") or "")
        safe_img = img.startswith("https://") and not any(c in img for c in "\"'()<> \\;{}")
        out.append(dict(outlet=str(r.outlet), date=f"{pd.Timestamp(r.date):%b %Y}", title=str(r.title), why=str(r.why), url=str(r.url),
                        host=r.url.split("/")[2].removeprefix("www."), image=img if safe_img else "",
                        credit=str(getattr(r, "credit", "") or "") if safe_img else ""))
    return out


def evidence_cards(ev):
    """Clickable source cards. Text is escaped, and only https links are accepted."""
    out = []
    for it in evidence_items(ev):
        date = f'<span class="news-date">{it["date"]}</span>'
        img, credit = it["image"], html.escape(it["credit"])
        pic = (f'<span class="news-img" style="background-image: url({img}), var(--checker-img);">{date}'
               + (f'<span class="news-credit">{credit}</span>' if credit else "") + "</span>" if img
               else f'<span class="news-img none">{date}</span>')
        out.append(
            f'<a class="news" href="{html.escape(it["url"], quote=True)}" target="_blank" rel="noopener noreferrer">{pic}<i class="tear"></i>'
            '<span class="news-body">'
            f'<span class="news-src">{html.escape(it["outlet"])}</span>'
            f'<span class="news-title">{html.escape(it["title"])}</span>'
            f'<span class="news-why">{html.escape(it["why"])}</span>'
            f'<span class="news-go">Read it at {html.escape(it["host"])}</span></span></a>')
    return card_grid(out) if out else ""


@st.cache_data
def scoreboard(res_dir: str = str(RES)) -> pd.DataFrame:
    """Held-out MAE and MASE per model (all-zone rows only). Empty if heldout.csv is missing."""
    p = Path(res_dir) / "heldout.csv"
    if not p.exists():
        return pd.DataFrame(columns=["key", "MAE", "MASE", "bias", "model"])
    d = pd.read_csv(p, index_col=0)
    d = d[~d.index.str.contains(r"\|")]
    out = d[["MAE", "MASE", "bias"]].reset_index()
    out.columns = ["key", "MAE", "MASE", "bias"]
    out["model"] = out["key"].map(lambda k: NAMES.get(k, k))
    return out


@st.cache_data
def heldout_runs(res_dir: str = str(RES)):
    p = Path(res_dir) / "heldout_run.json"
    return len(json.loads(p.read_text())["runs"]) if p.exists() else None


@st.cache_data
def zone_geo(path: str = str(GEO)):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else None


def headline(df):
    """Held-out MAE over all zones. None if there are no held-out rows."""
    h = df[df["split"] == "held-out"]
    if h.empty:
        return None
    m, b = (h["lgbm"] - h["y"]).abs().mean(), (h[BASE] - h["y"]).abs().mean()
    return m, b, 100 * (b - m) / b, h["origin"].nunique()


def daily_error(df):
    d = df.assign(model=(df["lgbm"] - df["y"]).abs(), base=(df[BASE] - df["y"]).abs())
    g = d.groupby([d["origin"].dt.normalize(), "split"])[["model", "base"]].mean().reset_index()
    return g.rename(columns={"origin": "date"})


def unexplained_days(df, reasons, mult=1.5):
    """Days the model missed by at least `mult` times the typical day whose cause was not looked up."""
    g = daily_error(df)
    big = g[g["model"] >= mult * g["model"].median()]
    known = set(reasons["date"]) if not reasons.empty else set()
    return sorted(d for d in big["date"] if d not in known)


def hour_weekday_gain(df):
    """Baseline MAE minus LightGBM MAE by weekday and hour. Positive means LightGBM is better."""
    gain = (df[BASE] - df["y"]).abs() - (df["lgbm"] - df["y"]).abs()
    out = gain.groupby([df["ts"].dt.day_name().rename("weekday"), df["ts"].dt.hour.rename("hour")]).mean()
    return out.rename("gain").reset_index()


def zone_gain(df):
    """Per zone: baseline MAE, LightGBM MAE and the percent reduction, on held-out days if present, else all days."""
    d = df[df["split"] == "held-out"] if (df["split"] == "held-out").any() else df
    g = d.assign(m=(d["lgbm"] - d["y"]).abs(), b=(d[BASE] - d["y"]).abs()).groupby("zone")[["m", "b"]].mean()
    g["gain_pct"] = 100 * (g["b"] - g["m"]) / g["b"]
    return g.rename(columns={"m": "model_mae", "b": "base_mae"}).reset_index()


def zone_table(df, names):
    """One row per zone on the held-out days: average rides per hour, both misses, and the percent the model cut."""
    d = df[df["split"] == "held-out"] if (df["split"] == "held-out").any() else df
    g = d.assign(m=(d["lgbm"] - d["y"]).abs(), b=(d[BASE] - d["y"]).abs()).groupby("zone").agg(
        rides=("y", "mean"), model_miss=("m", "mean"), rule_miss=("b", "mean"), rows=("y", "size")).reset_index()
    g["gain_pct"] = 100 * (g["rule_miss"] - g["model_miss"]) / g["rule_miss"].where(g["rule_miss"] > 0)
    g["saving"] = (g["rule_miss"] - g["model_miss"]) * g["rows"]
    g["name"] = g["zone"].map(lambda z: names.get(z) or f"Zone {z}")
    return g.sort_values("rides", ascending=False).reset_index(drop=True)


def zone_spread(zt, top=5):
    """(zones beaten, zones, share of all rides in the `top` busiest zones, their share of the total saving or None)."""
    if zt.empty:
        return None
    busiest = zt.head(top)
    total = zt["saving"].sum()
    return (int((zt["saving"] > 0).sum()), len(zt), busiest["rides"].sum() / zt["rides"].sum(),
            busiest["saving"].sum() / total if total > 0 else None)


def zone_gain_chart(zt, t):
    d = zt.dropna(subset=["gain_pct"])
    return alt.Chart(d).mark_bar(cornerRadiusEnd=2).encode(
        y=alt.Y("name:N", sort=alt.EncodingSortField("gain_pct", order="descending"), title=None, axis=alt.Axis(labelLimit=220)),
        x=alt.X("gain_pct:Q", title="percent fewer misses than the simple rule (left of zero: the rule won)"),
        color=alt.condition(alt.datum.gain_pct >= 0, alt.value(t["model"]), alt.value(t["warn"])),
        tooltip=[alt.Tooltip("name:N", title="Zone"), alt.Tooltip("gain_pct:Q", title="Fewer misses, %", format=".1f"),
                 alt.Tooltip("rides:Q", title="Rides per hour", format=".1f")]).properties(height=18 * len(d) + 40)


def mind_checks(df):
    """Claims I would drop if they failed, each checked live on the held-out days. status: holds, fails or untested."""
    h = df[df["split"] == "held-out"]
    if h.empty:
        return []
    zt = zone_table(df, {})
    out = []
    won, n = int((zt["saving"] > 0).sum()), len(zt)
    out.append(("holds" if won * 2 >= n else "fails", "It beats the simple rule in most zones",
                f"It beat the rule in {won} of {n} zones."))
    top = zt.iloc[0]
    rest = h[h["zone"] != top["zone"]]
    rb = (rest[BASE] - rest["y"]).abs().mean() if len(rest) else 0
    if rb > 0:
        pct = 100 * (rb - (rest["lgbm"] - rest["y"]).abs().mean()) / rb
        out.append(("holds" if pct > 0 else "fails", "The gain is not just the busiest zone",
                    f"With the busiest zone removed, the model still made {abs(pct):.1f}% {'fewer' if pct > 0 else 'more'} misses than the rule."))
    g = daily_error(df)
    g = g[g["split"] == "held-out"]
    if len(g):
        wins = int((g["model"] < g["base"]).sum())
        out.append(("holds" if wins * 2 >= len(g) else "fails", "It wins on most days, not a few lucky ones",
                    f"It beat the rule on {wins} of {len(g)} held-out days."))
    cov = ((h["y"] >= h["q10_int"]) & (h["y"] <= h["q90_int"])).mean()
    raw = None
    try:
        raw = float(pd.read_csv(RES / "heldout_intervals.csv").set_index("scope").loc["all", "coverage_raw"])
    except Exception:
        pass
    lead = f"The 10 to 90% band caught {raw:.0%} of held-out hours before rounding, and {cov:.0%} after its edges were rounded out to whole trips" if raw is not None \
        else f"The 10 to 90% band, with edges rounded out to whole trips, caught {cov:.0%} of held-out hours"
    out.append(("holds" if abs((raw if raw is not None else cov) - 0.8) <= 0.1 else "fails", "The yellow band can be trusted",
                lead + "; an ideal band catches 80%."))
    out.append(("untested", "It keeps winning in another month or year",
                "Only one month was held out, and I have one year of history. I cannot rule this out."))
    return out


def mind_box(checks):
    label = {"holds": "\u2713 Holds", "fails": "\u2715 Fails", "untested": "? Untested"}
    rows = "".join(
        f'<div class="mind-row"><span class="chip {st_}">{label[st_]}</span><div><b>{html.escape(ti)}</b>'
        f'<span>{html.escape(de)}</span></div></div>' for st_, ti, de in checks)
    return f'<div class="mind">{rows}</div>'


def compare_takeaway(items, day):
    """One sentence on two zones for one day. items: [(name, day_frame), (name, day_frame)]."""
    rows = []
    for name, d in items:
        if d.empty:
            return ""
        m, b = (d["lgbm"] - d["y"]).abs().mean(), (d[BASE] - d["y"]).abs().mean()
        rows.append((name, m, b, 100 * (b - m) / b if b > 0 else None))
    (an, am, ab, ap), (bn, bm, bb, bp) = rows
    if an == bn:
        return ""
    if ap is None or bp is None:
        return ""
    lead = f"{day:%a %d %b}: "
    if ap > 0 and bp > 0:
        hi, lo = (rows[0], rows[1]) if ap >= bp else (rows[1], rows[0])
        return (lead + f"the model beat the simple rule in both zones, and helped more in {hi[0]} ({hi[3]:.0f}% fewer misses) "
                f"than in {lo[0]} ({lo[3]:.0f}%).")
    if ap <= 0 and bp <= 0:
        return lead + "the simple rule beat the model in both zones."
    w, l = (rows[0], rows[1]) if ap > 0 else (rows[1], rows[0])
    return (lead + f"the model beat the simple rule in {w[0]} ({w[3]:.0f}% fewer misses) but lost in {l[0]}, "
            f"where the rule missed by {l[2]:.1f} rides an hour and the model by {l[1]:.1f}.")


def _storm_row(df, reasons):
    g = daily_error(df)
    if g.empty or reasons.empty:
        return None
    med = g["model"].median()
    r = reasons.merge(g, on="date")
    if r.empty:
        return None
    return r.assign(ratio=r["model"] / med).sort_values("ratio", ascending=False).iloc[0]


def storm_story(df, reasons):
    """The reason day whose model error was the largest multiple of the median day. None if no match."""
    r = _storm_row(df, reasons)
    return None if r is None else (r["date"], str(r["reason"]).split(";")[0].strip(), float(r["ratio"]))


def storm_split(df, reasons):
    """'development' or 'held-out': which part of the data that storm day sits in. None if no match."""
    r = _storm_row(df, reasons)
    return None if r is None else str(r["split"])


PERIOD = {"development": "in the development period, before the held-out test", "held-out": "in the held-out test"}


def style(chart, t):
    return (chart.configure(background=t["bg"])
                 .configure_axis(labelFont=FONT, titleFont=FONT, labelColor=t["text"], titleColor=t["text"],
                                 gridColor=t["grid"], domainColor=t["muted"], tickColor=t["muted"])
                 .configure_legend(labelFont=FONT, labelColor=t["text"], titleFont=FONT, titleColor=t["text"])
                 .configure_view(stroke=None))


def show(chart, t):
    """theme=None so the chart follows our light/dark palette, not the app's fixed Streamlit theme."""
    st.altair_chart(style(chart, t), width="stretch", theme=None)


def forecast_chart(d, show_band, t, intervals=True, height=340, annotate=False):
    """Three lines for one day. Tooltip rows are written as plain phrases ("912, off by 323")."""
    N_ACT, N_MOD, N_RULE = "What happened", "Model forecast", "Simple rule"
    series = {N_ACT: t["actual"], N_MOD: t["model"], N_RULE: t["base"]}
    wide = d.rename(columns={"y": N_ACT, "lgbm": N_MOD, BASE: N_RULE}).copy()
    long = wide.melt(id_vars="ts", value_vars=list(series), var_name="series", value_name="pickups")
    x = alt.X("ts:T", axis=alt.Axis(format="%H:%M", tickCount=8, title="hour of the day", grid=False))
    color = alt.Color("series:N", scale=alt.Scale(domain=list(series), range=list(series.values())),
                      legend=alt.Legend(orient="bottom", title=None))
    ymax = float(long["pickups"].max())
    ysc = alt.Scale(domain=[0, ymax * 1.3]) if annotate else alt.Undefined       # headroom for the label
    lines = alt.Chart(long).mark_line(strokeWidth=2.2).encode(
        x=x, y=alt.Y("pickups:Q", title="ride requests per hour", scale=ysc), color=color,
        strokeDash=alt.StrokeDash("series:N", legend=None, scale=alt.Scale(
            domain=list(series), range=[[1, 0], [1, 0], [5, 4]])))
    pick = alt.selection_point(nearest=True, on="pointerover", fields=["ts"], empty=False)
    miss_m, miss_r = (wide[N_MOD] - wide[N_ACT]).abs(), (wide[N_RULE] - wide[N_ACT]).abs()
    wide["t_happened"] = wide[N_ACT].map(lambda v: f"{v:,.0f} ride requests")
    wide["t_model"] = [f"{a:,.0f}, off by {m:,.0f}" for a, m in zip(wide[N_MOD], miss_m)]
    wide["t_rule"] = [f"{a:,.0f}, off by {m:,.0f}" for a, m in zip(wide[N_RULE], miss_r)]
    tip = [alt.Tooltip("ts:T", title="Hour", format="%H:%M"), alt.Tooltip("t_happened:N", title=N_ACT),
           alt.Tooltip("t_model:N", title=N_MOD), alt.Tooltip("t_rule:N", title=N_RULE)]
    if intervals:
        wide["t_range"] = [f"{lo:,.0f} to {hi:,.0f}" for lo, hi in zip(wide["q10_int"], wide["q90_int"])]
        tip.append(alt.Tooltip("t_range:N", title="Model expected"))
    rule = alt.Chart(wide).mark_rule(color=t["text"]).encode(
        x="ts:T", opacity=alt.condition(pick, alt.value(0.9), alt.value(0)), tooltip=tip).add_params(pick)
    layers = [lines, rule]
    if show_band and intervals:
        band = alt.Chart(wide).mark_area(opacity=t["band"], color=TAXI).encode(x="ts:T", y="q10_int:Q", y2="q90_int:Q")
        layers.insert(0, band)
    if annotate and len(wide):
        i = int(miss_m.values.argmax())
        row = wide.iloc[[i]].assign(label=f"Biggest miss, {wide['ts'].iloc[i]:%H:%M}: model {wide[N_MOD].iloc[i]:,.0f}, "
                                          f"actual {wide[N_ACT].iloc[i]:,.0f}")
        left = wide["ts"].iloc[i].hour < 12
        top = ymax * 1.2
        row = row.assign(top=top)
        layers.append(alt.Chart(row).mark_rule(color=t["warn"], strokeWidth=1.5, strokeDash=[3, 3]).encode(x="ts:T", y=f"{N_ACT}:Q", y2="top:Q"))
        layers.append(alt.Chart(row).mark_point(size=170, filled=False, color=t["warn"], strokeWidth=2.5).encode(x="ts:T", y=f"{N_ACT}:Q"))
        kw = dict(align="left" if left else "right", dx=8 if left else -8, fontSize=13, fontWeight=700, font="Figtree")
        layers.append(alt.Chart(row).mark_text(color=t["warn"], **kw).encode(x="ts:T", y="top:Q", text="label:N"))
    return alt.layer(*layers).properties(height=height)


def story_day(df):
    """The last held-out day for the busiest zone. Chosen by rule, not because it looks good."""
    held = df[df["split"] == "held-out"]
    base = held if len(held) else df          # same definition of "busiest" as the plain-English paragraph
    zone = base.groupby("zone")["y"].sum().idxmax()
    z = df[df["zone"] == zone]
    pool = z[z["split"] == "held-out"] if (z["split"] == "held-out").any() else z
    day = pool["origin"].max().normalize()
    return zone, day, z[z["origin"].dt.normalize() == day].sort_values("ts")


def best_worst_days(df, n=5):
    """Daily error across all zones. Returns (days the model beat the rule most, days it did worst against it)."""
    g = daily_error(df).assign(gain=lambda x: x["base"] - x["model"])
    g = g.rename(columns={"date": "Day", "split": "Data", "model": "Model miss", "base": "Rule miss", "gain": "Rule minus model"})
    g["Day"] = g["Day"].dt.strftime("%a %d %b %Y")
    g = g.round(2)
    return g.nlargest(n, "Rule minus model").reset_index(drop=True), g.nsmallest(n, "Rule minus model").reset_index(drop=True)


def heldout_csv(df):
    h = df[df["split"] == "held-out"][COLS].rename(columns={
        "origin": "forecast_made_at", "ts": "hour", "y": "actual", "lgbm": "model_forecast", BASE: "rule_of_thumb_forecast",
        "q10_int": "model_low_10pct", "q90_int": "model_high_90pct"})
    return h.round({"model_forecast": 2, "rule_of_thumb_forecast": 2, "model_low_10pct": 1, "model_high_90pct": 1}).to_csv(index=False).encode()


def day_takeaway(d, day):
    """One plain sentence about one zone on one day. Says 'worse' when the model was worse."""
    if d.empty:
        return ""
    miss = (d["lgbm"] - d["y"]).abs()
    base = (d[BASE] - d["y"]).abs()
    m, b = miss.mean(), base.mean()
    if abs(m - b) < 0.05 * max(b, 1e-9):
        verdict_ = f"About the same as the simple rule ({m:.1f} against {b:.1f} rides an hour)."
    elif m < b:
        verdict_ = f"The model beat the simple rule here: it missed by {m:.1f} rides an hour, the rule by {b:.1f}."
    else:
        verdict_ = f"The simple rule won here: it missed by {b:.1f} rides an hour, the model by {m:.1f}."
    w = d.loc[miss.idxmax()]
    return (f"{day:%a %d %b}: {verdict_} The model's biggest miss was at {w['ts']:%H:%M}, "
            f"when it forecast {w['lgbm']:.0f} and {w['y']:.0f} rides actually happened.")


def error_chart(g, reasons, t):
    base = alt.Chart(g).encode(x=alt.X("date:T", title=None, axis=alt.Axis(format="%b", tickCount="month", grid=False)))
    held = g[g["split"] == "held-out"]
    layers = []
    if not held.empty:
        layers.append(alt.Chart(pd.DataFrame({"a": [held["date"].min()], "b": [held["date"].max()]}))
                      .mark_rect(color=TAXI, opacity=t["held"]).encode(x="a:T", x2="b:T"))
    ln = lambda col, name: base.transform_calculate(series=f"'{name}'").mark_line(strokeWidth=1.8).encode(
        y=alt.Y(f"{col}:Q", title="MAE, trips per zone-hour"),
        color=alt.Color("series:N", scale=alt.Scale(domain=["LightGBM", "4-week same-hour mean"],
                                                    range=[t["model"], t["base"]]),
                        legend=alt.Legend(orient="bottom", title=None)))
    layers += [ln("base", "4-week same-hour mean"), ln("model", "LightGBM")]
    pick = alt.selection_point(nearest=True, on="pointerover", fields=["date"], empty=False)
    layers.append(base.mark_rule(color=t["text"]).encode(
        opacity=alt.condition(pick, alt.value(0.9), alt.value(0)),
        tooltip=[alt.Tooltip("date:T"), alt.Tooltip("model:Q", title="LightGBM", format=".1f"),
                 alt.Tooltip("base:Q", title="4-week mean", format=".1f"), "split:N"]).add_params(pick))
    if not reasons.empty:
        r = reasons.merge(g, on="date")
        if not r.empty:
            layers.append(alt.Chart(r).mark_point(size=130, filled=False, color=t["warn"], strokeWidth=2.5).encode(
                x="date:T", y="model:Q", tooltip=[alt.Tooltip("date:T"), alt.Tooltip("reason:N", title="cause")]))
    return alt.layer(*layers).properties(height=300)


def heatmap(h, t):
    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    lim = float(h["gain"].abs().max())
    return alt.Chart(h).mark_rect(stroke=t["bg"], strokeWidth=1.5).encode(
        x=alt.X("hour:O", title="hour of day", axis=alt.Axis(labelAngle=0, labelOverlap=True)),
        y=alt.Y("weekday:N", sort=order, title=None, axis=alt.Axis(labelOverlap=False)),
        color=alt.Color("gain:Q", title="trips per zone-hour", scale=alt.Scale(
            domain=[-lim, 0, lim], range=[t["warn"], t["mid"], t["model"]], interpolate="lab"),
            legend=alt.Legend(orient="bottom")),
        tooltip=["weekday:N", "hour:O", alt.Tooltip("gain:Q", title="LightGBM better by", format=".2f")]).properties(height=300)


METHODS = {
    "lgbm": ("One machine-learning model (LightGBM) trained on all 30 zones together, using recent demand, hour, weekday and holidays.",
             "This is the model being tested."),
    "lgbm_plus_mean_same_hour_4w": ("A 50/50 average of the LightGBM forecast and the 4-week mean.",
                                    "Checks whether mixing the model with the simple rule beats the model alone."),
    "mean_same_hour_4w": ("For each hour, the average of that same hour over the previous 4 weeks. Nothing is learned.",
                          "The rule of thumb everything else is compared against."),
    "same_hour_last_week": ("Copies the same hour from exactly one week earlier.", "A simple baseline that captures the weekly rhythm."),
    "same_hour_yesterday": ("Copies the same hour from yesterday.", "A simple baseline: tomorrow looks like today."),
    "naive_last_hour": ("Takes the last hour seen at midnight and repeats it for all 24 hours of the next day.",
                        "The laziest possible forecast. It marks the floor."),
    "ets_weekly": ("A classic statistical method (exponential smoothing with a weekly pattern), fitted separately for each zone on its last 6 weeks.",
                   "Checks whether a classic method is enough without machine learning."),
}


def method_notes(sb):
    """Plain-English notes per method for the scoreboard hover. The outcome sentence is computed from the scores."""
    m = sb.set_index("key")["MAE"]
    out = {}
    for k, (what, why) in METHODS.items():
        if k not in m.index:
            continue
        if k == "ets_weekly" and BASE in m.index:
            why += f" It scored {m[k]:.1f}, {'worse' if m[k] > m[BASE] else 'better'} than the 4-week mean ({m[BASE]:.1f})."
        if k.startswith("lgbm_plus_") and "lgbm" in m.index:
            why += f" It scored {m[k]:.1f}, {'worse' if m[k] > m['lgbm'] else 'no worse'} than LightGBM alone ({m['lgbm']:.1f})."
        out[k] = (what, why)
    return out


def score_chart(sb, t):
    notes = method_notes(sb)
    d = sb.sort_values("MAE").assign(what=lambda x: x["key"].map(lambda k: notes.get(k, ("", ""))[0]),
                                     why=lambda x: x["key"].map(lambda k: notes.get(k, ("", ""))[1]))
    return alt.Chart(d).mark_bar(cornerRadiusEnd=3, height=22).encode(
        y=alt.Y("model:N", sort=list(d["model"]), title=None, axis=alt.Axis(labelLimit=260)),
        x=alt.X("MAE:Q", title="held-out MAE, trips per zone-hour (lower is better)"),
        color=alt.condition(alt.datum.key == "lgbm", alt.value(t["model"]), alt.value(t["base"])),
        tooltip=[alt.Tooltip("model:N", title="Method"), alt.Tooltip("what:N", title="What it is"), alt.Tooltip("why:N", title="Why it is here"),
                 alt.Tooltip("MAE:Q", title="Average miss (MAE)", format=".2f"), alt.Tooltip("MASE:Q", format=".3f")]).properties(height=34 * len(d) + 40)


def map_chart(geo, zg, names, t):
    zg = zg.set_index("zone")
    feats = []
    for f in geo["features"]:
        z = f["properties"]["zone"]
        if z in zg.index:
            p = {"zone": z, "name": names.get(z, str(z)), "gain_pct": float(zg.loc[z, "gain_pct"]),
                 "model_mae": float(zg.loc[z, "model_mae"]), "base_mae": float(zg.loc[z, "base_mae"])}
            feats.append({"type": "Feature", "properties": p, "geometry": f["geometry"]})
    lim = max(1.0, float(zg["gain_pct"].abs().max()))
    return alt.Chart(alt.Data(values=feats)).mark_geoshape(stroke=t["bg"], strokeWidth=1).encode(
        color=alt.Color("properties.gain_pct:Q", title="error reduction vs baseline, %", scale=alt.Scale(
            domain=[-lim, 0, lim], range=[t["warn"], t["mid"], t["model"]], interpolate="lab"),
            legend=alt.Legend(orient="bottom")),
        tooltip=[alt.Tooltip("properties.name:N", title="zone"),
                 alt.Tooltip("properties.gain_pct:Q", title="reduction %", format=".1f"),
                 alt.Tooltip("properties.model_mae:Q", title="LightGBM MAE", format=".2f"),
                 alt.Tooltip("properties.base_mae:Q", title="baseline MAE", format=".2f")]
    ).project("mercator").properties(height=460)


def hover_tip(text="Hover over the chart to read the numbers."):
    """Small pill that tells a visitor the charts answer to the mouse."""
    icon = ('<svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true"><path d="M2 1 L2 11 L4.8 8.6 L6.6 12.6 L8.4 11.8 L6.6 7.9 L10.2 7.9 Z" '
            'fill="currentColor"/></svg>')
    return f'<span class="tip">{icon}{html.escape(text)}</span>'


def card_grid(items):
    """Cards in one CSS grid, so every card in a row is the same height."""
    return '<div class="cards">' + "".join(items) + "</div>"


def card(big, lab, sub):
    cls = "big word" if len(big) > 6 and not any(c.isdigit() for c in big) else "big"
    return f'<div class="card"><p class="{cls}">{big}</p><i class="tear"></i><p class="lab">{lab}</p><p class="sub">{sub}</p></div>'


def meter(text):
    """The big number as a taxi-meter. Digits roll up once on load; the final value is the real one, and screen readers get it as text."""
    out = []
    for i, c in enumerate(text):
        if c == ".":
            out.append('<span class="dot">.</span>')
        elif c.isdigit():
            strip = "".join(f"<b>{n}</b>" for n in list(range(10)) * 2)
            out.append(f'<span class="d"><i class="strip" style="--end:{int(c) + 10}; --i:{i}">{strip}</i></span>')
        else:
            out.append(f"<span>{html.escape(c)}</span>")
    return f'<div class="meter" role="img" aria-label="{html.escape(text)}"><div class="meter-in" aria-hidden="true">' + "".join(out) + "</div></div>"


TAXI_SVG = ('<svg viewBox="0 0 46 20" aria-hidden="true"><path d="M3 9 Q3 7 6 7 L12 7 L16 2 L31 2 L36 7 L42 7 Q44 7 44 9 L44 15 L3 15 Z" fill="#FFC72C"/>'
            '<path d="M17.5 3.5 L30 3.5 L33.6 7 L14.6 7 Z" fill="#9FB3C8"/><rect x="21" y="0" width="6" height="2.4" rx="1" fill="#fff"/>'
            '<path d="M3 11 H44" stroke="#111" stroke-width="1.6" stroke-dasharray="2 2"/>'
            '<circle cx="13" cy="15.5" r="3.4" fill="#111" stroke="#ddd" stroke-width="1.3"/><circle cx="34" cy="15.5" r="3.4" fill="#111" stroke="#ddd" stroke-width="1.3"/></svg>')
# (direction, seconds to cross, delay) per cab. Negative delays mean the road is already busy when the page loads.
TRAFFIC = [("up", "east", 22, -3), ("up", "east", 22, -11), ("up", "east", 22, -17), ("down", "west", 27, -6), ("down", "west", 27, -20)]


def road():
    cabs = "".join(f'<div class="cab {lane}" style="--dir:{d}; --dur:{sec}s; --delay:{dl}s">{TAXI_SVG}</div>' for lane, d, sec, dl in TRAFFIC)
    return f'<div class="road" aria-hidden="true">{cabs}</div>'


def hero_copy(hl, compact=False):
    """The words in the hero, as data. Used by the Streamlit page and the static site."""
    kicker = "Dashboard: pick a zone and a day, the headline stays up here" if compact else "Can you predict where New York wants a ride tomorrow?"
    if not hl:
        return dict(kicker=kicker, pct="", cap="", fine="", side=[])
    return dict(
        kicker=kicker, pct=f"{hl[2]:.1f}%",
        cap="" if compact else "lower error than a simple guess.",
        fine="" if compact else (
            "That is the LightGBM model I trained, forecasting ride demand in each of 30 New York zones, a day ahead. "
            "A simple guess averages what happened at that hour on that weekday over the last 4 weeks: for next Tuesday at 6pm, the last four Tuesdays at 6pm. "
            f"Tested on {hl[3]} days it never saw, scored once."),
        side=[("Model: off by", f"{hl[0]:.2f}", "rides per zone per hour"), ("Simple guess: off by", f"{hl[1]:.2f}", "rides per zone per hour")])


def hero(hl, compact=False):
    c = hero_copy(hl, compact)
    big = meter(c["pct"]) if hl else ""
    cap = f'<p class="hero-cap">{c["cap"]}</p><p class="hero-fine">{c["fine"]}</p>' if c["cap"] else ""
    side = ('<div class="hero-side">' + "".join(f"<div>{lab}<b>{val}</b><span>{unit}</span></div>" for lab, val, unit in c["side"]) + "</div>") if c["side"] else ""
    return (f'<div class="hero{" compact" if compact else ""}">{road()}<div class="hero-in"><div>'
            f'<p class="hero-kicker{"" if compact else " lead"}">{c["kicker"]}</p>'
            f'{big}{cap}</div>{side}</div></div><div class="checker"></div>')


def plain_summary(df, hl, names, reasons=None):
    """Plain-English paragraphs built from the numbers. Returns a list of HTML strings."""
    out = ["When you open a ride-hailing app, a car is usually already nearby. That is because someone guessed, ahead of time, "
           "how many people would want a ride in each part of the city that hour. This project makes that guess."]
    out.append("It predicts, a day ahead and hour by hour, how many ride requests each of 30 parts of New York will get. "
               "It learns from real trip records published by the city's Taxi and Limousine Commission.")
    if hl:
        out.append("To check it honestly, I hid the last 4 weeks of data and made the model forecast each of those days before "
                   f"seeing what happened. Its guesses were off by about <b>{hl[0]:.0f} rides</b> per zone per hour. "
                   "A simple guess was off by about " f"{hl[1]:.0f}: to guess next Tuesday at 6pm, it just averages the last four Tuesdays at 6pm. "
                   f"That is <b>{hl[2]:.0f}% fewer misses</b>.")
        h = df[df["split"] == "held-out"]
        z = h.groupby("zone")["y"].sum().idxmax()
        hz = h[h["zone"] == z]
        m, b = (hz["lgbm"] - hz["y"]).abs().mean(), (hz[BASE] - hz["y"]).abs().mean()
        label = names.get(z, f"zone {z}")
        out.append(f"In the busiest zone ({label}), the model missed by about {m:.0f} rides an hour against {b:.0f} for the simple guess.")
        rs = day_reasons() if reasons is None else reasons
        s = storm_story(df, rs)
        if s and s[2] >= 1.5:
            when = PERIOD.get(storm_split(df, rs), "")
            out.append(f"It has one big blind spot: the weather. The worst day was {s[0]:%d %B}{', ' + when if when else ''} (cause: {html.escape(s[1])}), when its average miss was "
                       f"<b>{s[2]:.1f} times</b> a typical day's. The model cannot see the weather, so a storm like that catches it out. "
                       "The Storm days tab in the dashboard has the details.")
    return out


def day_wins(df):
    """(held-out days the model beat the simple rule, held-out days). None if nothing was held out."""
    g = daily_error(df)
    g = g[g["split"] == "held-out"]
    return (int((g["model"] < g["base"]).sum()), len(g)) if len(g) else None


def verdict(hl, storm_ratio=None, wins=None, storm_where=None):
    """One honest sentence under the hero. It says something the hero does not: how often the model won, not by how much."""
    if not hl:
        return "Forecasting hourly ride demand for 30 parts of New York."
    lead = (f"The model won on {wins[0]} of {wins[1]} held-out days." if wins else "The model was tested on days it had never seen.")
    if storm_ratio and storm_ratio >= 1.5:
        if storm_where == "development":
            return lead + " Its largest miss, a winter storm, was in the development period, before the held-out test."
        return lead + " A winter storm still broke it."
    return lead


NEXT_STEPS = [("Weather", "Add the weather", "The model cannot see the weather, and storms change how many people want a ride. Feeding in a forecast is the obvious next step."),
              ("History", "Use more history", "One year means every holiday appears once. Two or three years would let the model learn them properly."),
              ("Coverage", "Test more places", "30 zones were checked. The honest next test is every zone in the city, and a different month of held-out days."),
              ("Harness", "Reuse the harness", "The same testing code can be pointed at a different forecasting problem, such as electricity demand, to see if the approach holds.")]


def next_steps():
    return card_grid([card(k, h, b) for k, h, b in NEXT_STEPS])


GLOSSARY = [("Baseline", "The simple guess the model has to beat. Here: to forecast next Tuesday at 6pm, average the last four Tuesdays at 6pm."),
            ("MAE", "Mean absolute error: how many rides the forecast was off by, on average, in one zone in one hour. Lower is better."),
            ("Held-out", "Data the model never saw while it was being built, saved for one final test so the result cannot be flattered."),
            ("Backtest", "Replaying the past: pretend it is midnight on some past day, forecast the next 24 hours, then compare with what happened."),
            ("Interval", "The yellow band on the charts: the range the model expected most hours to land in. It is not a promise."),
            ("Zone", "One of New York's taxi zones, the neighbourhood-sized areas the city uses for trip records.")]


def glossary():
    items = "".join(f"<p><b>{k}.</b> {v}</p>" for k, v in GLOSSARY)
    return f'<details class="gloss"><summary>Words used on this page</summary>{items}</details>'


def finding_cards(df, hl, sb, reasons):
    """The three finding cards as (big, label, sub) tuples. Shared by the Streamlit app and the static site build."""
    cards = []
    if hl:
        cards.append((f"{hl[2]:.1f}%", "Fewer misses than the simple rule",
                      f"Average miss {hl[0]:.2f} against {hl[1]:.2f} rides per zone per hour, on {hl[3]} held-out days the model never saw."))
    if not sb.empty and {"ets_weekly", BASE, "lgbm"} <= set(sb["key"]):
        m = sb.set_index("key")["MAE"]
        rel = 100 * (m["ets_weekly"] - m[BASE]) / m[BASE]
        cards.append((f"{abs(rel):.0f}% {'worse' if rel > 0 else 'better'}", "A classic statistical model vs the simple rule",
                      "Fancier did not mean better. Mixing the main model back toward the simple rule did "
                      f"{'worse' if m.get('lgbm_plus_' + BASE, 0) > m['lgbm'] else 'no better'} than LightGBM alone."))
    s = storm_story(df, reasons)
    if s and s[2] >= 1.5:
        where = {"development": "development period", "held-out": "held-out test"}.get(storm_split(df, reasons), "")
        cards.append((f"{s[2]:.1f}x", f"{s[1]} on {s[0]:%d %b}{' (' + where + ')' if where else ''}: storms still fool it",
                      "the median daily error. Nothing in the model knows the weather."))
    return cards


def test_steps(runs):
    return [("Midnight forecasts", "Every day at 00:00 the model forecasts the next 24 hours using only data before that moment."),
            ("No peeking", "A leak test recomputes every feature from raw history. It was shown to catch three deliberately planted leaks."),
            ("Baselines first", "Four simple rules were scored by the same code before any model, so a model has to earn its place."),
            ("Scored once", "The last 4 weeks were set aside until every choice was frozen"
                            + (f", then scored {runs} time." if runs == 1 else f", then scored {runs} times." if runs else "."))]


def evidence_section():
    ev = evidence()
    if len(ev):
        st.subheader("Is this a real problem?")
        st.markdown('<div class="plain"><p>Fair question. Here is what other people have published about why ride-hail demand gets forecast at all. '
                    "These show the problem is real and studied. They do not show my model works; the held-out result at the top of the page does that.</p></div>",
                    unsafe_allow_html=True)
        st.markdown(evidence_cards(ev), unsafe_allow_html=True)


def story(df, hl, t):
    sb, reasons = scoreboard(), day_reasons()
    storm = storm_story(df, day_reasons())
    st.markdown(f'<p class="verdict">{verdict(hl, storm[2] if storm else None, day_wins(df), storm_split(df, day_reasons()))}</p>', unsafe_allow_html=True)
    st.markdown('<div class="plain">' + "".join(f"<p>{p}</p>" for p in plain_summary(df, hl, zone_names())) + "</div>",
                unsafe_allow_html=True)
    zone, day, d = story_day(df)
    if not d.empty:
        nm = zone_names().get(zone)
        place = nm if nm else f"zone {zone}"
        st.subheader("A forecast, up close")
        st.markdown(
            '<div class="plain"><p>' + f"Here is {place}, the busiest zone, on {day:%A %d %B}, the last day I tested. "
            "The night before, at midnight, the model had to guess how many rides people would request in every hour of that day, "
            "without seeing any of it. "
            f'<b style="background:none;color:{t["actual"]}">The solid dark line is what really happened.</b> '
            f'<b style="background:none;color:{t["model"]}">The blue line is the model\'s guess.</b> '
            "The dashed gray line is the simple rule of thumb. Move your mouse over any hour to read the numbers.</p></div>",
            unsafe_allow_html=True)
        show(forecast_chart(d, False, t, intervals=False, height=260, annotate=True), t)
        st.markdown(f'<p class="takeaway">{day_takeaway(d, day)}</p>', unsafe_allow_html=True)
        st.caption("This day was picked by rule, not because it looks good: the busiest zone, on the last day tested.")
    evidence_section()
    st.markdown(glossary(), unsafe_allow_html=True)
    cards = [card(*c) for c in finding_cards(df, hl, sb, reasons)]
    if cards:
        st.markdown(card_grid(cards), unsafe_allow_html=True)
    checks = mind_checks(df)
    if checks:
        st.subheader("What would change my mind")
        st.markdown('<div class="plain"><p>A result is only worth something if it could have failed. Each line is something that has to be true for my claim to stand. '
                    "If one fails, I change my mind. The numbers come from the held-out days.</p></div>", unsafe_allow_html=True)
        st.markdown(mind_box(checks), unsafe_allow_html=True)
    st.subheader("How it was tested")
    st.markdown("Forecasts are easy to flatter by accident, mostly by letting a model peek at the future. Here is how I prevented that.")
    n_dev, n_held = df.loc[df["split"] == "development", "origin"].nunique(), df.loc[df["split"] == "held-out", "origin"].nunique()
    if n_dev and n_held:
        st.markdown(f'<div class="timeline"><div class="train" style="flex:{n_dev}">Rolling backtest, {n_dev} daily forecasts</div>'
                    f'<div class="held" style="flex:{max(n_held, n_dev * 0.25):.0f}">Held out, {n_held} days</div></div>',
                    unsafe_allow_html=True)
    runs = heldout_runs()
    steps = test_steps(runs)
    st.markdown(card_grid([card(str(i), h, b) for i, (h, b) in enumerate(steps, 1)]), unsafe_allow_html=True)
    st.subheader("What I would do next")
    st.markdown(next_steps(), unsafe_allow_html=True)
    st.write("")
    st.button("Open the dashboard", on_click=lambda: st.session_state.update(view="Dashboard"))


def zone_picker(df, key, default_idx, names):
    zones = sorted(df["zone"].unique())
    kw = {} if key in st.session_state else {"index": min(default_idx, len(zones) - 1)}
    return st.selectbox("Taxi zone", zones, key=key, filter_mode=None, **kw,
                        format_func=lambda z: f"{z}: {names[z]}" if z in names else str(z))


def seed_from_url(df):
    """Open a shared link on the same zone and day. Runs once, before the widgets exist."""
    if st.session_state.get("_seeded"):
        return
    st.session_state["_seeded"] = True
    qp = st.query_params
    zone = next((z for z in df["zone"].unique() if str(z) == qp.get("zone")), None)
    if zone is None:
        return
    st.session_state["zone_a"] = zone
    days = sorted(df.loc[df["zone"] == zone, "origin"].dt.date.unique())
    day = next((d for d in days if d.isoformat() == qp.get("day")), None)
    if day is not None:
        st.session_state["day_a"] = day


def write_url(view, dark):
    qp = {"view": view}
    if dark:
        qp["dark"] = "1"
    if view == "Dashboard" and "zone_a" in st.session_state:
        qp["zone"] = str(st.session_state["zone_a"])
        if st.session_state.get("day_a") is not None:
            qp["day"] = st.session_state["day_a"].isoformat()
    st.query_params.from_dict(qp)


def dashboard(df, t):
    seed_from_url(df)
    reasons = day_reasons()
    names = zone_names()
    geo = zone_geo()
    tabs = ["Forecast", "Compare zones", "Scoreboard", "Where it fails", "Storm days"] + (["Map"] if geo else []) + ["Method", "About"]
    objs = dict(zip(tabs, st.tabs(tabs)))
    with objs["Forecast"]:
        c_l, c_r = st.columns([2, 3])
        with c_l:
            zone = zone_picker(df, "zone_a", 0, names)
        z = df[df["zone"] == zone]
        days = sorted(z["origin"].dt.date.unique())
        if st.session_state.get("day_a") not in days:
            st.session_state.pop("day_a", None)
        day = c_r.select_slider("Day", options=days, key="day_a", **({} if "day_a" in st.session_state else {"value": days[-1]}))
        st.caption("How to read this: black is what actually happened. Blue is the model's forecast, made the night before. "
                   "The gray dashed line is the simple rule of thumb. The yellow band is the range the model expected most hours to land in.")
        show_band = st.checkbox("Show 10-90% interval", value=True)
        d = z[z["origin"].dt.date == day].sort_values("ts")
        st.markdown(hover_tip(), unsafe_allow_html=True)
        show(forecast_chart(d, show_band, t), t)
        st.markdown(f'<p class="takeaway">{day_takeaway(d, day)}</p>', unsafe_allow_html=True)
        mae = lambda c: (d[c] - d["y"]).abs().mean()
        m1, m2, m3 = st.columns(3)
        m1.metric("Model: average miss, this day", f"{mae('lgbm'):.2f}")
        m2.metric("Simple rule: average miss, this day", f"{mae(BASE):.2f}")
        m3.metric("Data", d["split"].iloc[0])
        st.caption("Average miss is how many rides an hour the forecast was off by, in this zone on this day. Lower is better. "
                   "The simple rule is the average of that same hour over the past four weeks. Held-out days were never seen by the model "
                   "while it was being built; development days were used for building and checking.")
        st.caption("One zone on one day proves nothing. The overall result is at the top of the page. "
                   "The address bar link keeps your zone and day, so you can share this exact view.")
    with objs["Compare zones"]:
        days = sorted(df["origin"].dt.date.unique())
        day = st.select_slider("Day", options=days, value=days[-1], key="day_b")
        st.markdown(hover_tip(), unsafe_allow_html=True)
        left, right = st.columns(2)
        picked = []
        for col, key, idx in ((left, "zone_c1", 0), (right, "zone_c2", 1)):
            with col:
                zone = zone_picker(df, key, idx, names)
                d = df[(df["zone"] == zone) & (df["origin"].dt.date == day)].sort_values("ts")
                picked.append((names.get(zone) or f"zone {zone}", d))
                if d.empty:
                    st.info("No forecast for this zone on this day.")
                    continue
                show(forecast_chart(d, True, t, height=280), t)
                st.metric("LightGBM MAE vs baseline", f"{(d['lgbm'] - d['y']).abs().mean():.2f}",
                          delta=f"baseline {(d[BASE] - d['y']).abs().mean():.2f}", delta_color="off")
        tk = compare_takeaway(picked, day)
        if tk:
            st.markdown(f'<p class="takeaway">{html.escape(tk)}</p>', unsafe_allow_html=True)
    with objs["Scoreboard"]:
        sb = scoreboard()
        if sb.empty:
            st.info("heldout.csv is not in the results folder yet.")
        else:
            st.subheader("Every model on the held-out weeks")
            st.caption("Same harness, same days, same zones. LightGBM (blue) is lowest. Exponential smoothing lost to the "
                       "simple 4-week mean, and blending LightGBM back toward it made LightGBM worse.")
            st.markdown(hover_tip("Hover a bar to see what each method is and why it is here."), unsafe_allow_html=True)
            show(score_chart(sb, t), t)
            st.download_button("Download scoreboard CSV", sb.drop(columns="key").to_csv(index=False), "heldout_scoreboard.csv")
            zt = zone_table(df, names)
            sp = zone_spread(zt)
            if sp:
                st.subheader("Is the gain spread across zones, or carried by a few?")
                st.markdown(f'<p class="takeaway center">The model beat the simple rule in {sp[0]} of {sp[1]} zones. The 5 busiest zones carry '
                            f'{sp[2]:.0%} of the rides and supplied {sp[3]:.0%} of the total saving.</p>' if sp[3] is not None else
                            f'<p class="takeaway center">The model beat the simple rule in {sp[0]} of {sp[1]} zones.</p>', unsafe_allow_html=True)
                show(zone_gain_chart(zt, t), t)
                tbl = zt[["name", "rides", "model_miss", "rule_miss", "gain_pct"]].rename(columns={
                    "name": "Zone", "rides": "Rides per hour", "model_miss": "Model miss", "rule_miss": "Rule miss", "gain_pct": "Fewer misses, %"})
                st.dataframe(tbl, hide_index=True, width="stretch", column_config={
                    "Rides per hour": st.column_config.NumberColumn(format="%.1f"), "Model miss": st.column_config.NumberColumn(format="%.2f"),
                    "Rule miss": st.column_config.NumberColumn(format="%.2f"), "Fewer misses, %": st.column_config.NumberColumn(format="%.1f")})
                st.markdown('<p class="zone-note">Busiest zone first; click a column header to sort. Miss means the average number of rides per hour the forecast was off by, on held-out days.</p>',
                            unsafe_allow_html=True)
    with objs["Where it fails"]:
        st.subheader("Daily error, all zones")
        st.caption("Each line is how far off the forecasts were on average each day. Lower is better. Rings mark days with a verified cause; hover them. Yellow marks the held-out weeks.")
        st.markdown(hover_tip(), unsafe_allow_html=True)
        show(error_chart(daily_error(df), reasons, t), t)
        st.subheader("Where LightGBM beats the baseline")
        st.caption("Blue: LightGBM has the lower error. Orange: the baseline does. Averaged over every day in the data.")
        show(heatmap(hour_weekday_gain(df), t), t)
        best, worst = best_worst_days(df)
        st.subheader("Best and worst days")
        st.caption("Daily average miss across all zones. A positive last column means the model beat the simple rule that day, negative means the rule won.")
        cl, cr = st.columns(2)
        cl.markdown("**Days the model beat the rule by the most**")
        cl.dataframe(best, hide_index=True, width="stretch")
        cr.markdown("**Days that went worst for the model**")
        cr.dataframe(worst, hide_index=True, width="stretch")
    with objs["Storm days"]:
        r = reasons.merge(daily_error(df), on="date") if not reasons.empty else reasons
        if r.empty:
            st.info("No verified storm days in the data.")
        else:
            st.subheader("Days the weather broke the forecast")
            st.caption("City-wide pickups across all 30 zones. Each cause below was checked against a news source.")
            more = unexplained_days(df, reasons)
            st.caption("Only days where I read a source for the cause are listed. "
                       + (f"{len(more)} other day{'s' if len(more) != 1 else ''} had a miss at least 1.5 times the typical day "
                          f"({', '.join(f'{d:%d %b}' for d in more[:8])}{', and more' if len(more) > 8 else ''}). "
                          "I did not look up their causes, so none are guessed." if more else
                          "No other day had a miss that large."))
            pick = st.selectbox("Day", list(r["date"]), filter_mode=None, format_func=lambda d: f"{d:%a %d %b %Y}: {str(r.set_index('date').loc[d, 'reason']).split(';')[0]}")
            row = r.set_index("date").loc[pick]
            d = df[df["origin"].dt.normalize() == pick].groupby("ts")[["y", "lgbm", BASE]].sum().reset_index()
            st.markdown(hover_tip(), unsafe_allow_html=True)
            show(forecast_chart(d, False, t, intervals=False, height=320), t)
            med = daily_error(df)["model"].median()
            c1, c2 = st.columns(2)
            c1.metric("LightGBM MAE that day", f"{row['model']:.1f}", delta=f"median day {med:.1f}", delta_color="off")
            c2.metric("Baseline MAE that day", f"{row['base']:.1f}")
            st.markdown(f"**Cause:** {row['reason']}. [Source]({row['source']})")
    if geo:
        with objs["Map"]:
            st.subheader("Where LightGBM helps most")
            st.caption("Percent reduction in MAE against the 4-week mean, by zone, on held-out days. Hover a zone.")
            st.markdown(hover_tip(), unsafe_allow_html=True)
            show(map_chart(geo, zone_gain(df), names, t), t)
    with objs["Method"]:
        held = df[df["split"] == "held-out"]
        cov = ((held["y"] >= held["q10_int"]) & (held["y"] <= held["q90_int"])).mean() if len(held) else None
        st.subheader("Setup")
        st.markdown("- Every day at midnight, forecast the next 24 hours for each zone, using only data from before that moment.\n"
                    "- Rolling-origin backtest with an expanding window. The last 4 weeks were held out and scored once.\n"
                    "- Error is MAE, RMSE, bias and MASE (scaled by a one-week seasonal naive). No MAPE, because quiet zone-hours are near zero.")
        st.subheader("Model")
        st.markdown("- One global LightGBM across all zones, Poisson objective, refit every 7 days.\n"
                    "- Features: demand 24 and 168 hours ago, the mean of the previous 24 hours, the mean of the same hour over the past 4 weeks, "
                    "hour, weekday, holiday flag and zone.\n"
                    "- Settings fixed in advance, not tuned on the backtest: 300 rounds, learning rate 0.05, 63 leaves.\n"
                    "- The yellow band comes from two more LightGBM models fitted for the 10% and 90% quantiles.")
        st.subheader("Checks")
        st.markdown("- A leak test recomputes every feature from raw history and is shown to fail on three deliberately planted leaks.\n"
                    "- Four simple baselines and exponential smoothing were scored by the same code first, so the model had to beat them.\n"
                    + (f"- The 10 to 90% band contained {cov:.0%} of held-out hours (an ideal band would be 80%).\n" if cov is not None else "")
                    + "- Decisions were written down before the code, in the repository.")
    with objs["About"]:
        st.caption("Every forecast made for the 4 held-out weeks, next to what actually happened.")
        st.download_button("Download held-out forecasts (CSV)", heldout_csv(df), "heldout_forecasts.csv", "text/csv")
        st.markdown(
            "- **Task:** at midnight, forecast hourly pickups for each zone for the next 24 hours.\n"
            "- **Data:** NYC TLC High Volume For-Hire Vehicle trips, 30 zones (busiest, mid, quiet).\n"
            "- **Evaluation:** rolling-origin backtest with a daily origin; the last 4 weeks were held out and scored once.\n"
            "- **Models:** four baselines, exponential smoothing, and one global LightGBM. LightGBM was best; "
            "exponential smoothing lost to the simple baseline.\n"
            "- **Limits:** 28 held-out days in one month, one year of history, no weather input. Storm days are the largest errors.\n"
            "- **Credit:** NYC Taxi and Limousine Commission trip records and zone lookup.")


def scroll_top():
    """After switching view, jump back to the top so the change is visible."""
    st.iframe("<script>const d=window.parent.document;"
                    "for(const e of [d.querySelector('section.stMain'),d.querySelector('[data-testid=\"stMain\"]'),d.scrollingElement])"
                    "{if(e)e.scrollTo({top:0,behavior:'instant'});}</script>", height=1)


def main():
    st.set_page_config(page_title="Day-ahead demand forecast, NYC ride-hail", layout="wide",
                       page_icon=str(FAVICON) if FAVICON.exists() else None)
    if not st.session_state.get("_url_read"):
        st.session_state["_url_read"] = True
        if st.query_params.get("view") in ("Story", "Dashboard"):
            st.session_state["view"] = st.query_params["view"]
        if st.query_params.get("dark") == "1":
            st.session_state["dark"] = True
    if st.session_state.get("view") is None:
        st.session_state["view"] = "Story"   # also catches a click on the selected option, which would clear it
    left, right = st.columns([8, 2])
    with left:
        st.segmented_control("View", ["Story", "Dashboard"], key="view", label_visibility="collapsed")
    dark = right.toggle("Dark mode", key="dark")
    t = THEMES["dark" if dark else "light"]
    st.markdown(theme_css(t), unsafe_allow_html=True)
    with st.spinner("Loading the forecasts..."):
        df = load()
    hl = headline(df)
    view = st.session_state.get("view") or "Story"
    if st.session_state.get("_last_view") not in (None, view):
        scroll_top()
    st.session_state["_last_view"] = view
    with st.container(key=f"view_{view}"):
        st.markdown(hero(hl, compact=view == "Dashboard"), unsafe_allow_html=True)
        if view == "Dashboard":
            dashboard(df, t)
        else:
            story(df, hl, t)
    links = " &nbsp;|&nbsp; ".join(f'<a href="{u}" target="_blank">{n}</a>' for n, u in LINKS)
    write_url(view, dark)
    st.markdown(f'<div class="footer">Built by Vikram Varkoor &nbsp;|&nbsp; {links}</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
