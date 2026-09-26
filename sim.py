#!/usr/bin/env python3
"""Render every page to a PNG contact sheet, exactly as the OLED will show it.

    python3 sim.py                     # saved sample, several made-up scenarios
    python3 sim.py --live "Brighton"   # today's real forecast for a place
"""
import argparse
import copy
import json
import os
from datetime import datetime, timedelta

from PIL import Image, ImageDraw

from pitop_weather import forecast, render

HERE = os.path.dirname(os.path.abspath(__file__))
SCALE = 3


def scenarios(j):
    """The saved sample, plus variations that exercise every branch."""
    base_now = datetime(2026, 9, 26, 23, 29)
    yield "sample (night)", j, base_now

    day = copy.deepcopy(j)
    day["current"]["is_day"] = 1
    yield "afternoon", day, datetime(2026, 9, 26, 15, 10)

    soon = copy.deepcopy(j)
    soon["minutely_15"]["precipitation"] = [0, 0, 0, 0.2, 0.8, 1.6, 1.1, 0.4, 0.1]
    soon["current"]["weather_code"] = 3
    for i in range(len(soon["hourly"]["time"])):
        soon["hourly"]["pressure_msl"][i] = 1012 - i * 1.2
        soon["hourly"]["weather_code"][i] = 63 if i > 4 else 3
        soon["hourly"]["precipitation_probability"][i] = min(100, i * 12)
    soon["current"]["pressure_msl"] = soon["hourly"]["pressure_msl"][3]
    yield "rain coming, pressure falling", soon, base_now

    storm = copy.deepcopy(j)
    storm["current"].update(weather_code=95, wind_speed_10m=34, wind_gusts_10m=58,
                            wind_direction_10m=250, precipitation=2.4, temperature_2m=-3.4,
                            apparent_temperature=-11.2)
    storm["minutely_15"]["precipitation"] = [2.0, 3.5, 2.2, 1.0, 0.3, 0, 0, 0, 0]
    yield "storm", storm, base_now


def sheet(frames, title):
    pad, label_h = 8, 14
    cols = 4
    rows = (len(frames) + cols - 1) // cols
    cw, ch = render.W * SCALE, render.H * SCALE
    out = Image.new("RGB", (pad + cols * (cw + pad), label_h + pad + rows * (ch + label_h + pad)), (40, 40, 40))
    d = ImageDraw.Draw(out)
    d.text((pad, 2), title, fill=(230, 230, 230))
    for i, (name, img) in enumerate(frames):
        x = pad + (i % cols) * (cw + pad)
        y = label_h + pad + (i // cols) * (ch + label_h + pad)
        d.text((x, y), name, fill=(200, 200, 200))
        big = img.convert("L").resize((cw, ch), Image.NEAREST)
        # tint white pixels OLED-blue-white, dark stays black
        rgb = Image.merge("RGB", [big.point(lambda v: 210 if v else 0),
                                  big.point(lambda v: 235 if v else 0),
                                  big.point(lambda v: 255 if v else 0)])
        out.paste(rgb, (x, y + label_h))
    return out


def recorder_sheet(w, out):
    """The Record and Clips pages in each of their states."""
    from pitop_weather import recorder
    now = datetime(2026, 9, 27, 7, 12)

    def clip(d, h, m, sec, cond, t):
        return recorder.Clip("/x/%d%d%d.wav" % (d, h, m), {
            "started": "2026-09-%02dT%02d:%02d:00" % (d, h, m), "seconds": sec,
            "weather": {"conditions": cond, "temp": t}})
    clips = [clip(27, 7, 12, 58, "Light rain", 14), clip(27, 6, 55, 60, "Overcast", 13),
             clip(27, 6, 40, 22.5, "Fog", 11), clip(26, 18, 31, 60, "Mostly clear", 10),
             clip(26, 18, 20, 41, "Clear", 9)]

    def st(**r):
        return render.Status(battery=64, stale_minutes=70, now=now, rec=render.RecView(**r))
    mic, tag = "USB PnP Sound Device", "~Light rain 14° (forecast)"
    frames = [
        ("record: no mic", render.page_record(w, st(mic=None))),
        ("record: ready", render.page_record(w, st(mic=mic, tag=tag, clips=clips, free_minutes=17000))),
        ("record: recording", render.page_record(w, st(mic=mic, recording=True, elapsed=23.4,
                                                       level_db=-18, peak_db=-9, tag=tag))),
        ("record: loud", render.page_record(w, st(mic=mic, recording=True, elapsed=41.9,
                                                  level_db=-2, peak_db=-0.5, tag="Heavy rain 9°"))),
        ("record: saved", render.page_record(w, st(mic=mic, notice="Saved 0:58", tag=tag, clips=clips,
                                                   free_minutes=17000))),
        ("clips: summary", render.page_clips(w, st(clips=clips))),
        ("clips: browsing", render.page_clips(w, st(clips=clips, browsing=True, cursor=3,
                                                    playing="/x/261831.wav"))),
        ("clips: none", render.page_clips(w, st(clips=[]))),
    ]
    path = os.path.join(out, "recorder.png")
    sheet(frames, "recorder pages").save(path)
    print(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", metavar="PLACE")
    ap.add_argument("--country", default="GB", help="two-letter code; stops Lincoln meaning Nebraska")
    ap.add_argument("--out", default=os.path.join(HERE, "sim-out"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    st = render.Status(battery=64, charging=False, minutes_left=205, ip="192.168.68.53", stale_minutes=3)

    if a.live:
        lat, lon, name = forecast.geocode(a.live, a.country)
        runs = [("live", forecast.fetch(lat, lon), None, name)]
    else:
        j = json.load(open(os.path.join(HERE, "tests", "sample_london.json")))
        runs = [(n, jj, now, "London") for n, jj, now in scenarios(j)]

    for n, jj, now, place in runs:
        w = forecast.Weather.from_api(jj, place, now=now)
        frames = [(pname, fn(w, st)) for pname, fn in render.PAGES]
        frames.append(("screensaver", render.screensaver(w, w.now, 17)))
        path = os.path.join(a.out, n.split(" ")[0].replace(",", "") + ".png")
        sheet(frames, "%s  -  %s" % (n, w.now.strftime("%a %H:%M"))).save(path)
        print(path)
    recorder_sheet(w, a.out)


if __name__ == "__main__":
    main()
