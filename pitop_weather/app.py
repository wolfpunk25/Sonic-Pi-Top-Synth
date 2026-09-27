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

from . import audio, forecast, recorder, render, sonicpi, speech

HOLD_TO_QUIT = 2.0          # seconds holding Cancel hands the screen back
BATTERY_POLL = 30.0
MIC_POLL = 5.0              # how often the Record page looks for a newly plugged mic
NOTICE_SECONDS = 6.0
RETRY_AFTER_ERROR = 120.0
CACHE = os.path.expanduser("~/.cache/pitop-weather")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Config:
    def __init__(self, path: Optional[str]):
        c = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
        c.read_dict({
            "place": {"name": "Lincoln", "country": "GB", "latitude": "", "longitude": ""},
            "behaviour": {"refresh_minutes": "10", "screensaver_seconds": "120",
                          "start_page": "now",
                          "rain_alert_minutes": "30", "battery_warnings": "20, 10",
                          "quiet_from": "22:00", "quiet_until": "08:00"},
            "voice": {"voice": "en-gb", "speed": "150", "volume": "100", "output": "speaker"},
            "sonicpi": {"app_dir": "~/apps/sonic-pi-5.0.0",
                        "runner": os.path.join(REPO, "tools", "trixie-run.sh"),
                        "sketches": "~/sonicpi-sketches", "buffer_size": "128", "output": "usb"},
            "recorder": {"folder": "~/soundwalks", "seconds": "60", "device": "default",
                         "sample_rate": "48000", "announce": "yes"},
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
        r = c["recorder"]
        self.rec_folder = os.path.expanduser(r["folder"])
        self.rec_seconds = r.getfloat("seconds")
        self.rec_device = r["device"]
        self.rec_rate = r.getint("sample_rate")
        self.rec_announce = r.getboolean("announce")
        self.voice_output = v["output"]
        sp = c["sonicpi"]
        self.sp_dir = os.path.expanduser(sp["app_dir"])
        self.sp_runner = os.path.expanduser(sp["runner"])
        self.sp_sketches = os.path.expanduser(sp["sketches"])
        self.sp_buffer = sp.getint("buffer_size")
        self.sp_output = sp["output"]


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
                 local_now: Callable[[], datetime] = datetime.now, rec=None, player=None,
                 find_mic: Callable[[], Optional[str]] = recorder.find_mic, engine=None,
                 outputs: Callable[[], List[str]] = audio.roles_present):
        self.hw, self.cfg, self.speaker = hw, cfg, speaker
        self.rec = rec or recorder.Recorder(cfg.rec_folder, cfg.rec_rate, cfg.rec_seconds,
                                            device=cfg.rec_device)
        self.rec.on_done = self.recording_done
        self.player = player or recorder.Player()
        self.find_mic = find_mic
        self.mic: Optional[str] = None
        self.clips: List[recorder.Clip] = []
        self.browsing = False
        self.cursor = 0
        self.notice = ""
        self.notice_until = 0.0
        self.place_info: Optional[tuple] = None     # (lat, lon, name) once resolved
        # Sonic Pi: None when it isn't installed
        if engine is None and os.path.isdir(cfg.sp_dir):
            engine = sonicpi.Engine(cfg.sp_dir, cfg.sp_runner, cfg.sp_buffer, cfg.sp_output)
        self.engine = engine
        if engine is not None:
            engine.on_change = self.engine_changed
        self.outputs = outputs
        self.sketches: List[sonicpi.Sketch] = []
        self.sp_browsing = False
        self.sp_cursor = 0
        self.sp_playing: Optional[str] = None     # title of the running sketch
        self.sp_playing_cat: Optional[str] = None
        self.sp_cat: Optional[str] = None         # None = the category list
        self.sp_cat_cursor = 0                    # where to come back to
        self.sp_with: Optional[str] = None        # the Keys sound added to a "# keys: last" sketch
        self.sp_last_keys = self.load_last_keys()
        self.sp_pending: Optional[sonicpi.Sketch] = None
        self.sp_started_at = 0.0
        self._last_mic_poll = -1e9
        self.clock, self.local_now = clock, local_now
        self.events: "queue.Queue[tuple]" = queue.Queue()
        self.names = [n for n, _ in render.PAGES]
        self.page = self.names.index(cfg.start_page) if cfg.start_page in self.names else 0
        self.weather: Optional[forecast.Weather] = None
        self.status = render.Status(rec=render.RecView(max_seconds=cfg.rec_seconds),
                                    sp=render.SpView())
        self.last_input = clock()
        self.saver = False
        self.cancel_down_at: Optional[float] = None
        self.running = True
        self.rain_alerted = False
        self.battery_warned: set = set()
        self._last_battery_poll = -1e9
        self._last_frame: Optional[bytes] = None
        self._last_draw = -1e9
        self._dirty = False     # set from other threads when there's news to show
        self._lock = threading.Lock()
        hw.on_button(lambda name, down: self.events.put((name, down)))
        self.refresh_clips()

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
        if self.rec.recording:  # while recording, Select or Cancel stops; nothing else
            if name in ("select", "cancel"):
                self.rec.stop()
            return
        if self.browsing:
            self.handle_browse(name)
            return
        if self.sp_browsing:
            self.handle_sonicpi(name)
            return
        page = self.names[self.page]
        if name == "up":
            self.page = (self.page - 1) % len(self.names)
        elif name == "down":
            self.page = (self.page + 1) % len(self.names)
        elif name == "select" and page == "record":
            self.start_recording()
        elif name == "select" and page == "sonicpi":
            self.open_sonicpi()
        elif name == "select" and page == "clips":
            self.refresh_clips()
            if self.clips:
                self.browsing, self.cursor = True, 0
        elif name == "select":
            self.player.stop()
            if self.speaker.busy:
                self.speaker.stop()
            elif self.weather:
                w = self.view()
                self.speaker.say(speech.SAY[self.names[self.page]](w, self.status))
            else:
                self.speaker.say("No forecast yet.")
        elif name == "cancel":
            self.page = 0

    def handle_browse(self, name: str):
        if name == "up":
            self.cursor = max(0, self.cursor - 1)
        elif name == "down":
            self.cursor = min(len(self.clips) - 1, self.cursor + 1)
        elif name == "select":
            clip = self.clips[self.cursor]
            if self.player.playing == clip.wav:
                self.player.stop()
            else:
                self.speaker.stop()
                self.player.play(clip.wav)
        elif name == "cancel":
            self.player.stop()
            self.browsing = False

    # ---- Sonic Pi ------------------------------------------------------

    def open_sonicpi(self):
        if self.engine is None:
            return
        if self.cfg.sp_sketches:
            sonicpi.install_starters(self.cfg.sp_sketches)
        self.sketches = sonicpi.load_sketches(self.cfg.sp_sketches)
        self.sp_browsing = True
        self.sp_cat = None
        self.sp_cursor = min(self.sp_cat_cursor, len(self.sp_rows()) - 1)
        if self.engine.state in ("off", "error"):
            self.engine.start()

    def sp_group(self, cat: Optional[str]) -> List["sonicpi.Sketch"]:
        return next((g for n, g in sonicpi.categories(self.sketches) if n == cat), [])

    def sp_rows(self) -> list:
        """The categories (and Output) at the top level; a category's sketches inside it."""
        if self.sp_cat is None:
            return [("cat", n, len(g)) for n, g in sonicpi.categories(self.sketches)] + [("output",)]
        return [("sketch", s) for s in self.sp_group(self.sp_cat)]

    def handle_sonicpi(self, name: str):
        rows = self.sp_rows()
        if name in ("up", "down"):           # wraps, so the bottom of a long list is one press away
            self.sp_cursor = (self.sp_cursor + (1 if name == "down" else -1)) % len(rows)
        elif name == "select":
            row = rows[self.sp_cursor]
            if row[0] == "output":
                self.cycle_output()
            elif row[0] == "cat":
                self.sp_cat, self.sp_cat_cursor = row[1], self.sp_cursor
                titles = [sk.title for sk in self.sp_group(row[1])]
                self.sp_cursor = titles.index(self.sp_playing) if self.sp_playing in titles else 0
            else:
                self.play_sketch(row[1])
        elif name == "cancel":
            if self.sp_cat is not None:      # back up to the categories; the music carries on
                self.sp_cat, self.sp_cursor = None, self.sp_cat_cursor
            elif self.sp_playing or self.sp_pending:
                self.engine.stop_all()
                self.sp_playing = self.sp_pending = self.sp_playing_cat = self.sp_with = None
            else:
                self.sp_browsing = False

    def play_sketch(self, sketch: "sonicpi.Sketch"):
        if self.engine.state in ("off", "error"):
            self.engine.start()
        if self.engine.state != "ready":
            self.sp_pending = sketch            # runs as soon as Sonic Pi is up
            return
        self.speaker.stop()
        self.engine.stop_all()
        if sketch.category == "Keys":
            self.sp_last_keys = sketch.title
            self.save_last_keys()
        keys = self.keys_sketch() if sketch.keys == "last" else None
        try:
            code = sonicpi.build_code(sketch, self.view(), keys)
        except OSError as e:
            self.engine.error = str(e)
            return
        self.engine.run(code)
        self.sp_playing, self.sp_pending = sketch.title, None
        self.sp_playing_cat = sketch.category
        self.sp_with = keys.title if keys else None
        self.sp_started_at = self.clock()

    def keys_sketch(self) -> Optional["sonicpi.Sketch"]:
        """The last Keys sketch played; Pluck (or the first Keys sketch) until then."""
        keys = self.sp_group("Keys")
        for want in (self.sp_last_keys, "Pluck"):
            found = next((k for k in keys if k.title == want), None)
            if found:
                return found
        return keys[0] if keys else None

    def load_last_keys(self) -> Optional[str]:
        try:
            with open(os.path.join(CACHE, "sonicpi.json")) as f:
                return json.load(f).get("last_keys")
        except (OSError, ValueError):
            return None

    def save_last_keys(self):
        try:
            os.makedirs(CACHE, exist_ok=True)
            with open(os.path.join(CACHE, "sonicpi.json"), "w") as f:
                json.dump({"last_keys": self.sp_last_keys}, f)
        except OSError:
            pass

    def cycle_output(self):
        roles = self.outputs() or ["default"]
        cur = self.engine.output
        nxt = roles[(roles.index(cur) + 1) % len(roles)] if cur in roles else roles[0]
        self.engine.set_output(nxt)
        self._dirty = True

    def engine_changed(self):
        """Called from the engine's threads."""
        if self.engine.state == "ready" and self.sp_pending is not None:
            self.events.put(("_sp_pending", True))
        if self.engine.state in ("off", "error"):
            self.sp_playing = None
        self._dirty = True

    def sp_view(self):
        v = self.status.sp
        e = self.engine
        v.installed = e is not None
        if e is None:
            return
        v.state, v.midi, v.output = e.state, e.midi_name, audio.LABELS.get(e.output, e.output)
        v.browsing, v.cursor, v.playing = self.sp_browsing, self.sp_cursor, self.sp_playing
        v.playing_with = self.sp_with if self.sp_playing else None
        v.pending = self.sp_pending.title if self.sp_pending else None
        v.title = self.sp_cat or "Sonic Pi"
        pend_cat = self.sp_pending.category if self.sp_pending else None
        v.rows = []
        for row in self.sp_rows():
            if row[0] == "cat":
                mark = ">" if row[1] == self.sp_playing_cat else ("~" if row[1] == pend_cat else "")
                v.rows.append((row[1], str(row[2]), mark))
            elif row[0] == "output":
                v.rows.append(("Output: " + v.output, "", ""))
            else:
                t = row[1].title
                v.rows.append((t, "", ">" if t == v.playing else ("~" if t == v.pending else "")))
        v.error = e.error if e.error and self.clock() - e.error_at < 15 else ""

    def check_hold(self):
        if self.cancel_down_at is not None and self.clock() - self.cancel_down_at >= HOLD_TO_QUIT:
            self.speaker.stop()
            self.running = False

    # ---- recording ---------------------------------------------------

    def poll_mic(self, force: bool = False):
        if not force and (self.names[self.page] != "record" or
                          self.clock() - self._last_mic_poll < MIC_POLL):
            return
        self._last_mic_poll = self.clock()
        if not self.rec.recording:
            self.mic = self.find_mic()
            self.status.rec.free_minutes = recorder.free_minutes(self.cfg.rec_folder, self.cfg.rec_rate)

    def weather_tag(self) -> Optional[dict]:
        with self._lock:
            w = self.weather
        return w.conditions_at(self.local_now(), self.clock()) if w else None

    def start_recording(self):
        self.poll_mic(force=True)
        if not self.mic:
            self.show_notice("No microphone found")
            return
        self.speaker.stop()
        self.player.stop()
        lat, lon, name = self.place_info or (None, None, self.cfg.place)
        meta = {"place": name, "latitude": lat, "longitude": lon,
                "place_note": "the weather station's home, not a GPS fix",
                "weather": self.weather_tag(), "mic": self.mic,
                "battery": self.status.battery, "charging": self.status.charging}
        self.rec.start(self.local_now(), meta)

    def recording_done(self, clip: Optional[recorder.Clip], err: str):
        """Called on the recorder's thread when a clip is finished."""
        if clip:
            self.refresh_clips()
            self.show_notice("Saved %s" % render.mmss(clip.seconds))
            if self.cfg.rec_announce:
                self.speaker.say("Saved, %d seconds." % round(clip.seconds))
        else:
            self.show_notice(err)
        self.last_input = self.clock()

    def show_notice(self, text: str):
        self.notice, self.notice_until = text, self.clock() + NOTICE_SECONDS
        self._dirty = True

    def refresh_clips(self):
        self.clips = recorder.list_clips(self.cfg.rec_folder)
        self.cursor = min(self.cursor, max(0, len(self.clips) - 1))

    def rec_view(self):
        r = self.status.rec
        r.mic, r.recording = self.mic, self.rec.recording
        r.elapsed, r.level_db, r.peak_db = self.rec.elapsed, self.rec.level_db, self.rec.peak_db
        r.max_seconds = self.rec.max_seconds
        r.notice = self.notice if self.clock() < self.notice_until else ""
        r.clips, r.browsing, r.cursor = self.clips, self.browsing, self.cursor
        r.playing = self.player.playing
        tag = self.weather_tag() if not r.recording or not r.tag else None
        if tag is not None or not r.recording:
            r.tag = tag_text(tag)

    # ---- data --------------------------------------------------------

    def set_weather(self, w: forecast.Weather):
        with self._lock:
            self.weather = w
            self.status.error = ""
            self._dirty = True
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
        self._dirty = True
        self.page = self.names.index(page)
        self.saver = False
        self.last_input = self.clock()
        if not self.quiet():
            self.speaker.say(text)

    def check_rain_alert(self):
        w = self.view()
        if not w or self.rec.recording:     # looked at again on the next fetch
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
        if pct is None or self.rec.recording:   # looked at again on the next poll
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
        busy = self.rec.recording or self.player.playing
        if busy:
            self.last_input = now
        if not self.saver and now - self.last_input >= self.cfg.saver_after:
            self.saver = True
            self.browsing = False
            self.sp_browsing = False      # music, if any, keeps playing
        if self.saver:
            return render.screensaver(w, self.local_now(), int(now // 60))
        self.status.now = self.local_now()
        self.rec_view()
        self.sp_view()
        if w is None and self.names[self.page] not in ("record", "clips", "sonicpi"):
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
        pressed = False
        while True:
            try:
                name, down = self.events.get_nowait()
            except queue.Empty:
                break
            if name == "_sp_pending":
                if self.sp_pending is not None:
                    self.play_sketch(self.sp_pending)
            else:
                self.handle(name, down)
            pressed = True
        self.check_hold()
        self.poll_battery()
        self.poll_mic()
        # buttons redraw at once; otherwise once a second is plenty for a clock,
        # but the level meter needs five
        now = self.clock()
        interval = 0.2 if self.rec.recording else 1.0
        if pressed or self._dirty or now - self._last_draw >= interval:
            self._dirty = False
            self._last_draw = now
            self.draw()


def tag_text(tag: Optional[dict]) -> str:
    if not tag:
        return ""
    return "%s%s %d°%s" % ("~" if tag["source"] == "forecast" else "", tag["conditions"],
                           round(tag["temp"]), " (forecast)" if tag["source"] == "forecast" else "")


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
                app.place_info = place
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
        # the SDK calls these with no arguments, so bind the name in a closure
        def handler(name, down):
            return lambda: cb(name, down)
        for name in ("up", "down", "select", "cancel"):
            b = getattr(self.ms, name + "_button")
            b.when_pressed = handler(name, True)
            b.when_released = handler(name, False)

    def show(self, img):
        self.ms.display_image(img)
        # a copy of the screen in RAM (tmpfs), so it can be checked over SSH
        run = os.environ.get("XDG_RUNTIME_DIR")
        if run:
            try:
                img.save(os.path.join(run, "pitop-weather.png"))
            except OSError:
                pass

    def battery(self):
        try:
            # one request to pi-topd rather than one per property
            state, capacity, left, _watts = self.pt.battery.get_full_state()
            left = int(left)
            return int(capacity), state != "0", (left if left > 0 else None)
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
    spk = speech.Speaker(cfg.voice, cfg.speed, cfg.volume, cfg.voice_output)
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
        if app.rec.recording:   # a Cancel-hold or shutdown mid-clip still saves it
            app.rec.stop()
            app.rec.wait(5)
        app.player.stop()
        if app.engine is not None:
            app.engine.exit()
        spk.stop()
        hw.close()   # the pi-top system menu takes the screen back from here


if __name__ == "__main__":
    main()
