"""The main loop: buttons, pages, refreshes, alerts.

Hardware is reached only through the small `Hardware` interface at the
bottom, so `tests/` can drive the whole app with a fake.
"""
from __future__ import annotations

import configparser
import json
import os
import queue
import signal
import socket
import threading
import time
from datetime import datetime, time as dtime
from typing import Callable, List, Optional

from . import forecast, render, speech

HOLD_TO_QUIT = 2.0          # seconds holding Cancel hands the screen back
BATTERY_POLL = 30.0
RETRY_AFTER_ERROR = 120.0
CACHE = os.path.expanduser("~/.cache/pitop-weather")


class Config:
    def __init__(self, path: Optional[str]):
        c = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
        c.read_dict({
            "place": {"name": "London", "country": "GB", "latitude": "", "longitude": ""},
            "behaviour": {"refresh_minutes": "10", "screensaver_seconds": "120",
                          "start_page": "now",
                          "rain_alert_minutes": "30", "battery_warnings": "20, 10",
                          "quiet_from": "22:00", "quiet_until": "08:00"},
            "voice": {"voice": "en-gb", "speed": "150", "volume": "100"},
        })
        if path and os.path.exists(path):
            c.read(path)
        p, b, v = c["place"], c["behaviour"], c["voice"]
        self.place = p["name"]
        self.country = p["country"]
        self.lat = float(p["latitude"]) if p["latitude"].strip() else None
        self.lon = float(p["longitude"]) if p["longitude"].strip() else None
        self.refresh = b.getfloat("refresh_minutes") * 60
        self.saver_after = b.getfloat("screensaver_seconds")
        self.start_page = b["start_page"]
        self.rain_alert = b.getint("rain_alert_minutes")
        self.battery_warnings = sorted((int(x) for x in b["battery_warnings"].split(",") if x.strip()), reverse=True)
        self.quiet_from = _hhmm(b["quiet_from"])
        self.quiet_until = _hhmm(b["quiet_until"])
        self.voice, self.speed, self.volume = v["voice"], v.getint("speed"), v.getint("volume")


def _hhmm(s: str) -> dtime:
    h, m = s.strip().split(":")
    return dtime(int(h), int(m))


def in_quiet_hours(now: datetime, start: dtime, end: dtime) -> bool:
    t = now.time()
    if start == end:
        return False
    return (start <= t or t < end) if start > end else (start <= t < end)


class App:
    def __init__(self, hw: "Hardware", cfg: Config, speaker, clock: Callable[[], float] = time.time,
                 local_now: Callable[[], datetime] = datetime.now):
        self.hw, self.cfg, self.speaker = hw, cfg, speaker
        self.clock, self.local_now = clock, local_now
        self.events: "queue.Queue[tuple]" = queue.Queue()
        self.names = [n for n, _ in render.PAGES]
        self.page = self.names.index(cfg.start_page) if cfg.start_page in self.names else 0
        self.weather: Optional[forecast.Weather] = None
        self.status = render.Status()
        self.last_input = clock()
        self.saver = False
        self.cancel_down_at: Optional[float] = None
        self.running = True
        self.rain_alerted = False
        self.battery_warned: set = set()
        self._last_battery_poll = -1e9
        self._last_frame: Optional[bytes] = None
        self._lock = threading.Lock()
        hw.on_button(lambda name, down: self.events.put((name, down)))

    # ---- inputs ------------------------------------------------------

    def handle(self, name: str, down: bool):
        now = self.clock()
        if name == "cancel":
            if down:
                self.cancel_down_at = now
                return
            if self.cancel_down_at is None:
                return
            self.cancel_down_at = None
        elif not down:
            return
        self.last_input = now
        if self.saver:          # the first press only wakes the screen
            self.saver = False
            return
        if name == "up":
            self.page = (self.page - 1) % len(self.names)
        elif name == "down":
            self.page = (self.page + 1) % len(self.names)
        elif name == "select":
            if self.speaker.busy:
                self.speaker.stop()
            elif self.weather:
                w = self.view()
                self.speaker.say(speech.SAY[self.names[self.page]](w, self.status))
            else:
                self.speaker.say("No forecast yet.")
        elif name == "cancel":
            self.page = 0

    def check_hold(self):
        if self.cancel_down_at is not None and self.clock() - self.cancel_down_at >= HOLD_TO_QUIT:
            self.speaker.stop()
            self.running = False

    # ---- data --------------------------------------------------------

    def set_weather(self, w: forecast.Weather):
        with self._lock:
            self.weather = w
            self.status.error = ""
        self.check_rain_alert()

    def view(self) -> Optional[forecast.Weather]:
        with self._lock:
            w = self.weather
        return w.at(self.local_now()) if w else None

    def poll_battery(self):
        if self.clock() - self._last_battery_poll < BATTERY_POLL:
            return
        self._last_battery_poll = self.clock()
        b = self.hw.battery()
        self.status.battery, self.status.charging, self.status.minutes_left = b
        self.status.ip = local_ip()
        self.check_battery_alert()

    # ---- alerts ------------------------------------------------------

    def quiet(self) -> bool:
        return in_quiet_hours(self.local_now(), self.cfg.quiet_from, self.cfg.quiet_until)

    def alert(self, text: str, page: str):
        self.page = self.names.index(page)
        self.saver = False
        self.last_input = self.clock()
        if not self.quiet():
            self.speaker.say(text)

    def check_rain_alert(self):
        w = self.view()
        if not w:
            return
        kind, mins = w.rain_eta()
        if kind == "dry":
            self.rain_alerted = False
        elif kind == "soon" and mins is not None and mins <= self.cfg.rain_alert and not self.rain_alerted:
            self.rain_alerted = True
            self.alert("Heads up. " + speech.rain_sentence(w), "rain")
        elif kind == "now":
            self.rain_alerted = True    # no alert for rain that's already here

    def check_battery_alert(self):
        pct, charging = self.status.battery, self.status.charging
        if pct is None:
            return
        if charging:
            self.battery_warned.clear()
            return
        for level in self.cfg.battery_warnings:
            if pct <= level and level not in self.battery_warned:
                self.battery_warned.update(l for l in self.cfg.battery_warnings if l >= level)
                self.alert("Battery at %d percent." % pct, "device")
                break

    # ---- output ------------------------------------------------------

    def frame(self):
        w = self.view()
        now = self.clock()
        if self.weather:
            self.status.stale_minutes = self.weather.age_minutes(now)
        if not self.saver and now - self.last_input >= self.cfg.saver_after:
            self.saver = True
        if self.saver:
            return render.screensaver(w, self.local_now(), int(now // 60))
        if w is None:
            return render.message("Weather", "Fetching forecast\nfor %s..." % self.cfg.place +
                                  ("\n" + self.status.error if self.status.error else ""))
        return render.PAGES[self.page][1](w, self.status)

    def draw(self):
        img = self.frame()
        b = img.tobytes()
        if b != self._last_frame:
            self._last_frame = b
            self.hw.show(img)

    def tick(self):
        while True:
            try:
                name, down = self.events.get_nowait()
            except queue.Empty:
                break
            self.handle(name, down)
        self.check_hold()
        self.poll_battery()
        self.draw()


# ---- fetching -----------------------------------------------------------------

def resolve_place(cfg: Config):
    if cfg.lat is not None and cfg.lon is not None:
        return cfg.lat, cfg.lon, cfg.place
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, "place.json")
    try:
        with open(path) as f:
            c = json.load(f)
        if c["query"] == [cfg.place, cfg.country]:
            return c["lat"], c["lon"], c["name"]
    except (OSError, ValueError, KeyError):
        pass
    lat, lon, name = forecast.geocode(cfg.place, cfg.country)
    with open(path, "w") as f:
        json.dump({"query": [cfg.place, cfg.country], "lat": lat, "lon": lon, "name": name}, f)
    return lat, lon, name


def load_cached(place: str) -> Optional[forecast.Weather]:
    try:
        with open(os.path.join(CACHE, "last.json")) as f:
            c = json.load(f)
        return forecast.Weather.from_api(c["data"], place, fetched_at=c["at"])
    except (OSError, ValueError, KeyError):
        return None


def fetcher(app: App):
    """Background thread: fetch on start, then every refresh period."""
    place = None
    cached = load_cached(app.cfg.place)
    if cached:
        app.set_weather(cached)
    while app.running:
        wait = app.cfg.refresh
        try:
            if place is None:
                place = resolve_place(app.cfg)
            lat, lon, name = place
            j = forecast.fetch(lat, lon)
            app.set_weather(forecast.Weather.from_api(j, name))
            os.makedirs(CACHE, exist_ok=True)
            with open(os.path.join(CACHE, "last.json"), "w") as f:
                json.dump({"at": time.time(), "data": j}, f)
        except Exception as e:   # network down, DNS, bad place name...
            app.status.error = "%s: %s" % (type(e).__name__, e)
            print("fetch failed:", app.status.error, flush=True)
            wait = RETRY_AFTER_ERROR
        end = time.time() + wait
        while app.running and time.time() < end:
            time.sleep(1)


def local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.0.2.1", 9))     # no packet is sent; it just picks a route
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return ""


# ---- hardware ----------------------------------------------------------------

class Hardware:
    def on_button(self, cb: Callable[[str, bool], None]): ...
    def show(self, img): ...
    def battery(self): return (None, False, None)
    def close(self): ...


class PiTop(Hardware):
    def __init__(self):
        from pitop import Pitop   # imported here so the rest runs on any machine
        self.pt = Pitop()
        self.ms = self.pt.miniscreen

    def on_button(self, cb):
        for name in ("up", "down", "select", "cancel"):
            b = getattr(self.ms, name + "_button")
            b.when_pressed = (lambda n=name: cb(n, True))
            b.when_released = (lambda n=name: cb(n, False))

    def show(self, img):
        self.ms.display_image(img)

    def battery(self):
        try:
            b = self.pt.battery
            left = b.time_remaining
            return int(b.capacity), bool(b.is_charging), (int(left) if left else None)
        except Exception:
            return None, False, None

    def close(self):
        try:
            self.ms.reset()
        except Exception:
            pass
        try:
            self.pt.close()
        except Exception:
            pass


def main(argv: Optional[List[str]] = None):
    import argparse
    ap = argparse.ArgumentParser(description="pi-top weather station")
    ap.add_argument("--config", default=os.path.expanduser("~/.config/pitop-weather.ini"))
    a = ap.parse_args(argv)
    cfg = Config(a.config)
    hw = PiTop()
    spk = speech.Speaker(cfg.voice, cfg.speed, cfg.volume)
    app = App(hw, cfg, spk)

    def stop(*_):
        app.running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    threading.Thread(target=fetcher, args=(app,), daemon=True).start()
    try:
        while app.running:
            app.tick()
            time.sleep(0.05)
    finally:
        spk.stop()
        hw.close()   # the pi-top system menu takes the screen back from here


if __name__ == "__main__":
    main()
