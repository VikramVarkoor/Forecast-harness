"""Draw the 1200x630 share image (taxi-meter number on yellow) from the held-out results.

    python -m src.make_social            # writes docs/social-preview.png

Use it as the GitHub repository social preview (Settings, General, Social preview) and as the
image when you post the link. Streamlit apps cannot set their own link-preview tags, so the
image has to be attached where you post. The number is computed from the results files, not typed.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
TAXI, INK = (255, 199, 44), (17, 17, 17)
BOLD = ["/System/Library/Fonts/Supplemental/Arial Black.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:/Windows/Fonts/ariblk.ttf", "C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
REG = ["/System/Library/Fonts/Supplemental/Arial.ttf", "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


def font(paths, size):
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def draw(hl, out):
    W, H = 1200, 630
    im = Image.new("RGB", (W, H), TAXI)
    d = ImageDraw.Draw(im)
    d.text((70, 52), "Day-ahead hourly demand, NYC ride-hail zones", font=font(BOLD, 34), fill=INK)
    text, x, big = f"{hl[2]:.1f}%", 70, font(BOLD, 190)
    for ch in text:
        w = d.textlength(ch, font=big)
        bw = max(int(w) + 40, 130 if ch != "." else 70)
        d.rounded_rectangle((x, 120, x + bw, 400), radius=26, fill=INK)
        d.text((x + bw / 2, 262), ch, font=big, fill=TAXI, anchor="mm")
        x += bw + 12
    reg = font(REG, 34)
    d.text((70, 425), "lower forecast error than a simple rule of thumb.", font=reg, fill=INK)
    d.text((70, 470), f"Tested on {hl[3]} days the model never saw, scored once.", font=reg, fill=INK)
    d.text((70, 522), f"Off by {hl[0]:.1f} rides per zone per hour, against {hl[1]:.1f} for the rule.", font=font(BOLD, 28), fill=INK)
    s = 30
    for i in range(W // s + 1):
        for j in range(2):
            if (i + j) % 2 == 0:
                d.rectangle((i * s, H - 2 * s + j * s, i * s + s, H - 2 * s + j * s + s), fill=INK)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out


def main():
    from app.app import headline, load
    hl = headline(load())
    if not hl:
        raise SystemExit("No held-out results found. Run the held-out evaluation first.")
    print("wrote", draw(hl, ROOT / "docs" / "social-preview.png"))


if __name__ == "__main__":
    main()
