"""Link-preview image and favicon for the electricity page. Every number comes from the same dict that feeds the page."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FONTS = Path(__file__).parent / "fonts"
NAVY, CYAN, WHITE, MUTED = (11, 18, 32), (76, 215, 246), (232, 243, 255), (150, 168, 190)


def _font(name, size, axes=None):
    f = ImageFont.truetype(str(FONTS / name), size)
    if axes:
        f.set_variation_by_axes(axes)
    return f


def _wrap(d, text, font, width):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + [cur]


def og_image(path, hero, series_day):
    """hero: the page's hero dict. series_day: (actual, model), 24 values each."""
    W, H = 1200, 630
    im = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(im)
    for x in range(0, W, 40):
        d.line([(x, 0), (x, H)], fill=(18, 36, 56))
    for y in range(0, H, 40):
        d.line([(0, y), (W, y)], fill=(18, 36, 56))
    act, mod = series_day
    lo, hi = min(act + mod), max(act + mod)
    pad = (hi - lo) * 0.15 or 1
    X = lambda i: 60 + i * (W - 120) / 23
    Y = lambda v: H - 40 - (v - (lo - pad)) / (hi - lo + 2 * pad) * 130
    d.line([(X(i), Y(v)) for i, v in enumerate(act)], fill=(120, 140, 165), width=6, joint="curve")
    d.line([(X(i), Y(v)) for i, v in enumerate(mod)], fill=CYAN, width=5, joint="curve")
    d.text((60, 50), hero["kicker"], font=_font("figtree.ttf", 34), fill=WHITE)
    d.text((54, 100), hero["pct"], font=_font("fraunces.ttf", 190, [144, 900]), fill=CYAN)
    d.text((60, 330), hero["cap"], font=_font("figtree.ttf", 44), fill=WHITE)
    small = _font("figtree.ttf", 24)
    first = hero["fine"].split(". ")[-1].rstrip(".") if ". " in hero["fine"] else hero["fine"]
    d.text((60, 392), first + ".", font=small, fill=MUTED)
    im.save(path)


def favicon(path):
    s = 256
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=52, fill=NAVY)
    pts = [(28, 170), (70, 150), (100, 96), (128, 60), (156, 96), (186, 150), (228, 170)]
    d.line(pts, fill=CYAN, width=22, joint="curve")
    im.resize((64, 64), Image.LANCZOS).save(path)
