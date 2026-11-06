"""Shareable 'Band Card' (1080x1920 story format) rendered with Pillow."""
import io
import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")

RED = (228, 0, 43)
DEEP = (120, 0, 28)
NIGHT = (18, 14, 28)
WHITE = (255, 255, 255)
SOFT = (255, 220, 225)


def _font(name, size):
    try:
        return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    except OSError:
        return ImageFont.load_default(size=size)


def _center(draw, y, text, font, fill=WHITE):
    w = draw.textlength(text, font=font)
    draw.text(((W - w) / 2, y), text, font=font, fill=fill)


def _fit(draw, text, font_name, size, max_w):
    f = _font(font_name, size)
    while draw.textlength(text, font=f) > max_w and size > 24:
        size -= 2
        f = _font(font_name, size)
    return f


def render_card(name, school, city, band, fc, lr, gra, streak, xp, bot_username) -> bytes:
    img = Image.new("RGB", (W, H), NIGHT)
    d = ImageDraw.Draw(img)
    # vertical gradient red -> deep red -> night
    for y in range(H):
        t = y / H
        if t < 0.55:
            k = t / 0.55
            c = tuple(int(RED[i] * (1 - k) + DEEP[i] * k) for i in range(3))
        else:
            k = (t - 0.55) / 0.45
            c = tuple(int(DEEP[i] * (1 - k) + NIGHT[i] * k) for i in range(3))
        d.line([(0, y), (W, y)], fill=c)

    # decorative rings
    d.ellipse((W / 2 - 360, 430, W / 2 + 360, 1150), outline=(255, 255, 255), width=6)
    d.ellipse((W / 2 - 330, 460, W / 2 + 330, 1120), outline=(255, 160, 175), width=2)

    _center(d, 120, "BAND BATTLE", _font("Inter-Black.otf", 104))
    _center(d, 250, "#WhatsYourBand", _font("Inter-Bold.otf", 52), SOFT)

    band_txt = f"{band:.1f}"
    _center(d, 560, band_txt, _font("Inter-Black.otf", 330))
    _center(d, 925, "ESTIMATED SPEAKING BAND", _font("Inter-Bold.otf", 30), SOFT)

    _center(d, 1200, name or "Student", _fit(d, name or "Student", "Inter-Black.otf", 80, W - 140))
    sub = school or city or ""
    _center(d, 1300, sub, _fit(d, sub, "Inter-Medium.otf", 46, W - 140), SOFT)

    # criteria bars
    labels = [("Fluency", fc), ("Vocabulary", lr), ("Grammar", gra)]
    fl = _font("Inter-Bold.otf", 36)
    y = 1420
    for label, val in labels:
        d.text((120, y), label, font=fl, fill=WHITE)
        vt = f"{val:.1f}"
        d.text((W - 120 - d.textlength(vt, font=fl), y), vt, font=fl, fill=WHITE)
        bx0, by0, bx1 = 120, y + 52, W - 120
        d.rounded_rectangle((bx0, by0, bx1, by0 + 18), radius=9, fill=(95, 40, 60))
        d.rounded_rectangle((bx0, by0, bx0 + (bx1 - bx0) * max(0.05, val / 9), by0 + 18), radius=9, fill=WHITE)
        y += 110

    _center(d, 1760 - 20, f"Streak {streak} day{'s' if streak != 1 else ''}   |   {xp} XP",
            _font("Inter-Bold.otf", 40))
    _center(d, 1812, f"Get yours: t.me/{bot_username}", _font("Inter-Medium.otf", 36), SOFT)
    _center(d, 1866, "AI practice estimate, not an official IELTS score",
            _font("Inter-Medium.otf", 26), (230, 200, 205))

    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
