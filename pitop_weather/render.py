"""Draw the pages as 128x64 one-bit images.

Every page is a pure function of (Weather, Status) so the simulator and the
tests see exactly what the OLED will.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from .forecast import Weather, compass, describe

W, H = 128, 64
HEADER = 11     # pixels used by the title bar

_FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
_fonts = {}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (size, bold)
    if key not in _fonts:
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        _fonts[key] = ImageFont.truetype(os.path.join(_FONT_DIR, name), size)
    return _fonts[key]


@dataclass
class Status:
    battery: Optional[int] = None      # percent
    charging: bool = False
    minutes_left: Optional[int] = None
    ip: str = ""
    stale_minutes: Optional[int] = None  # age of the forecast
    error: str = ""


def new() -> "tuple[Image.Image, ImageDraw.ImageDraw]":
    img = Image.new("1", (W, H), 0)
    return img, ImageDraw.Draw(img)


def text_w(d: ImageDraw.ImageDraw, s: str, f) -> int:
    return int(d.textlength(s, font=f))


def fit(d, s: str, size: int, max_w: int, bold: bool = False):
    """Largest font no bigger than `size` that fits `s` in `max_w`."""
    while size > 7 and text_w(d, s, font(size, bold)) > max_w:
        size -= 1
    return font(size, bold)


def deg(t: float) -> str:
    return "%d°" % round(t)


# ---- chrome ----------------------------------------------------------------

def battery_icon(d, x: int, y: int, st: Status):
    """A 13x7 battery at (x, y)."""
    d.rectangle([x, y, x + 11, y + 6], outline=1)
    d.rectangle([x + 12, y + 2, x + 13, y + 4], fill=1)
    if st.battery is None:
        d.text((x + 4, y - 2), "?", font=font(8), fill=1)
        return
    fill = round(9 * max(0, min(100, st.battery)) / 100)
    if fill:
        d.rectangle([x + 1, y + 1, x + 1 + fill, y + 5], fill=1)
    if st.charging:  # a small bolt cut out of the fill
        bolt = [(x + 7, y), (x + 4, y + 4), (x + 6, y + 4), (x + 5, y + 7), (x + 9, y + 2), (x + 7, y + 2)]
        d.polygon(bolt, fill=0, outline=0)
        d.line([(x + 7, y + 1), (x + 5, y + 4), (x + 7, y + 4), (x + 6, y + 6)], fill=1)


def header(d, title: str, w: Weather, st: Status):
    d.text((0, -1), title, font=font(9, True), fill=1)
    clock = w.now.strftime("%H:%M")
    f = font(9)
    cw = text_w(d, clock, f)
    x_batt = W - 14
    d.text((x_batt - 3 - cw, -1), clock, font=f, fill=1)
    battery_icon(d, x_batt, 1, st)
    if st.stale_minutes is not None and st.stale_minutes >= 30:
        # a forecast older than half an hour is flagged with a small "!" box
        x = x_batt - 3 - cw - 9
        d.rectangle([x, 0, x + 6, 8], fill=1)
        d.text((x + 2, -1), "!", font=font(8, True), fill=0)
    d.line([(0, HEADER - 1), (W - 1, HEADER - 1)], fill=1)


# ---- icons (drawn, so they scale) ---------------------------------------------

def _sun(d, cx, cy, r):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=1, fill=1)
    for i in range(8):
        a = i * math.pi / 4
        d.line([(cx + math.cos(a) * (r + 2), cy + math.sin(a) * (r + 2)),
                (cx + math.cos(a) * (r + 2 + r * 0.6), cy + math.sin(a) * (r + 2 + r * 0.6))], fill=1)


def _moon(d, cx, cy, r):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=1)
    o = int(r * 0.7)
    d.ellipse([cx - r + o, cy - r - o // 2, cx + r + o, cy + r - o // 2], fill=0)


def _cloud(d, x, y, s, fill=0):
    """A cloud whose bounding box is roughly (x, y, x+s, y+s*0.6)."""
    parts = [(x + s * 0.05, y + s * 0.25, x + s * 0.45, y + s * 0.6),
             (x + s * 0.25, y + s * 0.0, x + s * 0.7, y + s * 0.5),
             (x + s * 0.55, y + s * 0.15, x + s * 0.95, y + s * 0.6)]
    for p in parts:   # outlines first, then fill the inside so the joins vanish
        d.ellipse([p[0] - 1, p[1] - 1, p[2] + 1, p[3] + 1], fill=1)
    d.rectangle([x + s * 0.25, y + s * 0.4, x + s * 0.75, y + s * 0.6 + 1], fill=1)
    for p in parts:
        d.ellipse(p, fill=fill)
    d.rectangle([x + s * 0.25, y + s * 0.42, x + s * 0.75, y + s * 0.6 - 1], fill=fill)


def draw_icon(d, kind: str, x: int, y: int, s: int, night: bool = False):
    """Draw a weather icon in an s x s box at (x, y)."""
    cx, cy = x + s / 2, y + s / 2
    if kind == "clear":
        (_moon if night else _sun)(d, cx, cy, s * 0.22)
        return
    if kind == "partly":
        (_moon if night else _sun)(d, x + s * 0.35, y + s * 0.32, s * 0.16)
        _cloud(d, x + s * 0.15, y + s * 0.35, s * 0.85)
        return
    if kind == "fog":
        for i in range(4):
            yy = y + s * (0.25 + i * 0.17)
            inset = s * (0.05 if i % 2 else 0.15)
            d.line([(x + inset, yy), (x + s - inset, yy)], fill=1, width=max(1, s // 16))
        return
    cloud_y = y + s * 0.05
    _cloud(d, x, cloud_y, s, fill=1 if kind == "thunder" else 0)
    below = y + s * 0.68
    if kind in ("rain", "showers", "drizzle"):
        n = 2 if kind == "drizzle" else 3
        for i in range(n):
            xx = x + s * (0.3 + i * 0.2) + (s * 0.1 if n == 2 else 0)
            ln = s * (0.12 if kind == "drizzle" else 0.24)
            d.line([(xx, below), (xx - ln * 0.4, below + ln)], fill=1, width=max(1, s // 20))
    elif kind == "snow":
        for i in range(3):
            xx, yy = x + s * (0.3 + i * 0.2), below + s * (0.1 if i % 2 else 0.2)
            r = max(1, s * 0.05)
            d.line([(xx - r, yy), (xx + r, yy)], fill=1)
            d.line([(xx, yy - r), (xx, yy + r)], fill=1)
            d.point((xx, yy), fill=1)
    elif kind == "thunder":
        bx = x + s * 0.5
        d.polygon([(bx + s * 0.05, below - s * 0.08), (bx - s * 0.12, below + s * 0.14),
                   (bx, below + s * 0.14), (bx - s * 0.08, below + s * 0.32),
                   (bx + s * 0.14, below + s * 0.06), (bx + s * 0.02, below + s * 0.06)], fill=1)


# ---- pages -----------------------------------------------------------------

def page_now(w: Weather, st: Status) -> Image.Image:
    img, d = new()
    header(d, w.place[:12], w, st)
    draw_icon(d, w.icon, 0, 13, 32, night=not w.is_day)
    t = deg(w.temp)
    d.text((36, 10), t, font=font(26, True), fill=1)
    tw = text_w(d, t, font(26, True))
    small = font(9)
    d.text((38 + tw, 15), "feels", font=small, fill=1)
    d.text((38 + tw, 25), deg(w.feels), font=font(10, True), fill=1)
    line1 = w.text
    d.text((0, 41), line1, font=fit(d, line1, 11, W, True), fill=1)
    line2 = w.outlook()
    d.text((0, 53), line2, font=fit(d, line2, 9, W), fill=1)
    return img


def page_next(w: Weather, st: Status) -> Image.Image:
    """The next three hours, side by side."""
    img, d = new()
    header(d, "Next hours", w, st)
    hrs = w.upcoming_hours(3)
    col = W // 3
    for i, hr in enumerate(hrs):
        x0 = i * col
        f = font(9)
        label = hr.time.strftime("%H:%M")
        d.text((x0 + (col - text_w(d, label, f)) // 2, 11), label, font=f, fill=1)
        night = w.today is not None and not (w.today.sunrise <= hr.time <= w.today.sunset)
        draw_icon(d, describe(hr.code)[1], x0 + (col - 20) // 2, 22, 20, night=night)
        t = deg(hr.temp)
        fb = font(11, True)
        d.text((x0 + (col - text_w(d, t, fb)) // 2, 40), t, font=fb, fill=1)
        p = "rain %d%%" % hr.pop
        fs = font(8, hr.pop >= 50)
        d.text((x0 + (col - text_w(d, p, fs)) // 2, 53), p, font=fs, fill=1)
        if i:
            d.line([(x0, 12), (x0, 62)], fill=1)
    return img


def page_rain(w: Weather, st: Status) -> Image.Image:
    """Rainfall per 15 minutes over the next two hours."""
    img, d = new()
    header(d, "Rain radar", w, st)
    kind, mins = w.rain_eta()
    if kind == "dry":
        msg = "Dry for 2 hours"
    elif kind == "soon":
        msg = "Rain in ~%d min" % max(5, 5 * round(mins / 5))
    elif mins is None:
        msg = "Raining, 2 hrs+"
    else:
        msg = "Stops in ~%d min" % max(5, 5 * round(mins / 5))
    d.text((0, 11), msg, font=fit(d, msg, 11, W, True), fill=1)
    slots = w.rain_slots()
    top, base = 26, 54
    peak = max([mm for _, mm in slots] + [1.0])     # at least 1 mm of headroom
    bw = W // 8
    for i, (t, mm) in enumerate(slots[:8]):
        x = i * bw
        h = 0 if mm <= 0 else max(2, int((base - top) * mm / peak))
        if h:
            d.rectangle([x + 2, base - h, x + bw - 3, base], fill=1)
        else:
            d.line([(x + 2, base), (x + bw - 3, base)], fill=1)
    d.line([(0, base + 1), (W - 1, base + 1)], fill=1)
    f = font(8)
    for i in (0, 4):
        if i < len(slots):
            d.text((i * bw + 1, 55), "now" if i == 0 else slots[i][0].strftime("%H:%M"), font=f, fill=1)
    if slots:
        end = (slots[-1][0] + timedelta(minutes=15)).strftime("%H:%M")
        d.text((W - text_w(d, end, f), 55), end, font=f, fill=1)
    return img


def page_wind(w: Weather, st: Status) -> Image.Image:
    img, d = new()
    header(d, "Wind", w, st)
    cx, cy, r = 25, 38, 23
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=1)
    for i, lab in enumerate("NESW"):
        a = math.radians(i * 90)
        lx, ly = cx + math.sin(a) * (r - 6), cy - math.cos(a) * (r - 6)
        f = font(7)
        d.text((lx - text_w(d, lab, f) / 2, ly - 5), lab, font=f, fill=1)
    # arrow points the way the wind is blowing TO
    a = math.radians(w.wind_dir + 180)
    tip = (cx + math.sin(a) * (r - 3), cy - math.cos(a) * (r - 3))
    tail = (cx - math.sin(a) * (r - 8), cy + math.cos(a) * (r - 8))
    d.line([tail, tip], fill=1, width=2)
    left = a + math.radians(150)
    right = a - math.radians(150)
    d.polygon([tip, (tip[0] + math.sin(left) * 8, tip[1] - math.cos(left) * 8),
               (tip[0] + math.sin(right) * 8, tip[1] - math.cos(right) * 8)], fill=1)
    x = 54
    sp = "%d" % round(w.wind)
    d.text((x, 11), sp, font=font(24, True), fill=1)
    d.text((x + text_w(d, sp, font(24, True)) + 2, 24), "mph", font=font(9), fill=1)
    d.text((x, 39), "gusts %d" % round(w.gust), font=font(10), fill=1)
    frm = "from " + compass(w.wind_dir)
    d.text((x, 51), frm, font=font(10, True), fill=1)
    return img


def page_sun(w: Weather, st: Status) -> Image.Image:
    img, d = new()
    header(d, "Sun", w, st)
    day = w.today
    if day is None:
        d.text((0, 25), "No data", font=font(11), fill=1)
        return img
    # a horizon arc with the sun placed along it
    x0, x1, base = 4, 62, 50
    d.line([(0, base), (66, base)], fill=1)
    d.arc([x0, base - 32, x1, base + 32], 180, 360, fill=1)
    span = (day.sunset - day.sunrise).total_seconds()
    frac = (w.now - day.sunrise).total_seconds() / span if span else 0
    if 0 <= frac <= 1:
        a = math.pi * (1 - frac)
        sx = (x0 + x1) / 2 + math.cos(a) * (x1 - x0) / 2
        sy = base - math.sin(a) * 32
        d.ellipse([sx - 4, sy - 4, sx + 4, sy + 4], fill=1)
    else:
        _moon(d, 58, 20, 5)
    d.text((0, 52), day.sunrise.strftime("%H:%M"), font=font(9), fill=1)
    ss = day.sunset.strftime("%H:%M")
    d.text((66 - text_w(d, ss, font(9)), 52), ss, font=font(9), fill=1)
    x = 72
    if w.now < day.sunrise:
        lab, val = "sunrise in", day.sunrise - w.now
    elif w.now < day.sunset:
        lab, val = "light left", day.sunset - w.now
    else:
        tm = w.tomorrow
        lab, val = "sunrise in", ((tm.sunrise if tm else day.sunrise + timedelta(days=1)) - w.now)
    mins = int(val.total_seconds() // 60)
    d.text((x, 12), lab, font=font(9), fill=1)
    d.text((x, 22), "%dh%02d" % (mins // 60, mins % 60), font=font(14, True), fill=1)
    d.text((x, 40), "UV max", font=font(9), fill=1)
    d.text((x, 49), "%.0f %s" % (day.uv, uv_word(day.uv)), font=font(10, True), fill=1)
    return img


def uv_word(uv: float) -> str:
    return "low" if uv < 3 else "mod" if uv < 6 else "high" if uv < 8 else "v.high"


def page_pressure(w: Weather, st: Status) -> Image.Image:
    img, d = new()
    header(d, "Pressure", w, st)
    delta, word = w.pressure_trend()
    p = "%d" % round(w.pressure)
    d.text((0, 11), p, font=font(18, True), fill=1)
    pw = text_w(d, p, font(18, True))
    d.text((pw + 2, 19), "hPa", font=font(8), fill=1)
    # trend arrow
    ax, ay = pw + 24, 20
    if word == "Steady":
        d.line([(ax, ay), (ax + 12, ay)], fill=1, width=2)
        d.polygon([(ax + 14, ay), (ax + 9, ay - 4), (ax + 9, ay + 4)], fill=1)
    else:
        up = delta > 0
        y_from, y_to = (ay + 6, ay - 6) if up else (ay - 6, ay + 6)
        d.line([(ax, y_from), (ax + 10, y_to)], fill=1, width=2)
        tip = (ax + 12, y_to + (-1 if up else 1))
        d.polygon([tip, (ax + 5, y_to + (1 if up else -1)), (ax + 10, y_to + (6 if up else -6))], fill=1)
    d.text((0, 31), word, font=fit(d, word, 10, 70, True), fill=1)
    d.text((0, 43), "%+.1f in 3h" % delta, font=font(9), fill=1)
    bw_ = barometer_word(w.pressure, delta)
    d.text((0, 53), bw_, font=fit(d, bw_, 9, 70), fill=1)
    # sparkline: 3h back to 6h ahead, with a tick at now
    series = w.pressure_series()
    gx0, gx1, gy0, gy1 = 72, 127, 14, 60
    d.rectangle([gx0, gy0, gx1, gy1], outline=1)
    if len(series) >= 2:
        vals = [s.pressure for s in series]
        lo, hi = min(vals), max(vals)
        if hi - lo < 2:
            mid = (hi + lo) / 2
            lo, hi = mid - 1, mid + 1
        t0 = series[0].time
        t1 = series[-1].time
        span = (t1 - t0).total_seconds() or 1
        pts = [(gx0 + 2 + (gx1 - gx0 - 4) * (s.time - t0).total_seconds() / span,
                gy1 - 3 - (gy1 - gy0 - 6) * (s.pressure - lo) / (hi - lo)) for s in series]
        d.line(pts, fill=1)
        nx = gx0 + 2 + (gx1 - gx0 - 4) * (w.now - t0).total_seconds() / span
        if gx0 < nx < gx1:
            for yy in range(gy0 + 1, gy1, 3):
                d.point((nx, yy), fill=1)
    return img


def barometer_word(p: float, delta: float) -> str:
    if delta <= -1.6:
        return "Unsettled coming"
    if delta >= 1.6:
        return "Settling down"
    if p >= 1022:
        return "Settled"
    if p <= 1000:
        return "Unsettled"
    return "Changeable"


def page_tomorrow(w: Weather, st: Status) -> Image.Image:
    img, d = new()
    tm = w.tomorrow
    header(d, "Tomorrow", w, st)
    if tm is None:
        d.text((0, 25), "No data", font=font(11), fill=1)
        return img
    txt, kind = describe(tm.code)
    draw_icon(d, kind, 0, 13, 32)
    d.text((38, 11), deg(tm.tmax), font=font(20, True), fill=1)
    mw = text_w(d, deg(tm.tmax), font(20, True))
    d.text((40 + mw, 20), "/ " + deg(tm.tmin), font=font(10), fill=1)
    d.text((38, 34), "rain %d%%" % tm.pop, font=font(9), fill=1)
    d.text((0, 42), txt, font=fit(d, txt, 11, W, True), fill=1)
    d.text((0, 54), "UV %.0f  sunrise %s" % (tm.uv, tm.sunrise.strftime("%H:%M")), font=font(8), fill=1)
    return img


def page_device(w: Weather, st: Status) -> Image.Image:
    img, d = new()
    header(d, "Device", w, st)
    if st.battery is None:
        bl = "Battery ?"
    else:
        bl = "Battery %d%%" % st.battery
    d.text((0, 11), bl, font=font(12, True), fill=1)
    if st.charging:
        sub = "charging"
    elif st.minutes_left:
        sub = "about %dh%02d left" % (st.minutes_left // 60, st.minutes_left % 60)
    else:
        sub = "on battery"
    d.text((0, 25), sub, font=font(9), fill=1)
    d.text((0, 37), st.ip or "no network", font=font(9), fill=1)
    age = st.stale_minutes
    upd = "updated %s" % ("just now" if age is not None and age < 1 else
                          "%d min ago" % age if age is not None else "never")
    d.text((0, 48), upd, font=font(9), fill=1)
    if st.error:
        d.text((0, 55), st.error[:26], font=font(7), fill=1)
    return img


PAGES = [
    ("now", page_now),
    ("next", page_next),
    ("rain", page_rain),
    ("wind", page_wind),
    ("sun", page_sun),
    ("pressure", page_pressure),
    ("tomorrow", page_tomorrow),
    ("device", page_device),
]


def screensaver(w: Optional[Weather], now: datetime, tick: int) -> Image.Image:
    """Time and temperature, wandering slowly so no pixel is lit for long."""
    img, d = new()
    s = now.strftime("%H:%M") + ("  " + deg(w.temp) if w else "")
    f = font(12, True)
    tw = text_w(d, s, f)
    # a slow Lissajous walk: moves a pixel or so each minute
    x = int((W - tw) / 2 + math.sin(tick / 7.0) * (W - tw) / 2)
    y = int((H - 14) / 2 + math.sin(tick / 5.0) * (H - 14) / 2)
    d.text((x, y), s, font=f, fill=1)
    return img


def message(title: str, body: str) -> Image.Image:
    img, d = new()
    d.text((0, 0), title, font=font(11, True), fill=1)
    y = 16
    for line in body.split("\n"):
        d.text((0, y), line, font=fit(d, line, 10, W), fill=1)
        y += 12
    return img
