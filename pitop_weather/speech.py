"""What the box says out loud, and how it says it.

The wording is plain functions of Weather so it can be tested; `Speaker`
runs espeak-ng in the background so a long sentence never freezes the screen.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
from datetime import datetime
from typing import Optional

from . import audio
from .forecast import Weather, compass, describe
from .render import Status, barometer_word, uv_word


def _deg(t: float) -> str:
    n = round(t)
    return ("minus %d" % -n if n < 0 else "%d" % n) + (" degree" if abs(n) == 1 else " degrees")


def _clock(t: datetime) -> str:
    h = t.hour % 12 or 12
    ampm = "a.m." if t.hour < 12 else "p.m."
    return ("%d %s" % (h, ampm)) if t.minute == 0 else ("%d %02d %s" % (h, t.minute, ampm))


def _mins(m: int) -> str:
    m = max(5, int(5 * round(m / 5)))
    if m < 60:
        return "%d minutes" % m
    h, r = divmod(m, 60)
    return ("an hour" if h == 1 else "%d hours" % h) + (" and %d minutes" % r if r else "")


def rain_sentence(w: Weather) -> str:
    kind, mins = w.rain_eta()
    if kind == "now":
        return "It's raining, easing off in about %s." % _mins(mins) if mins is not None \
            else "It's raining, and it looks set for the next couple of hours."
    if kind == "soon":
        return "Rain expected in about %s." % _mins(mins)
    nxt = w.upcoming_hours(6)
    wet = next((x for x in nxt if x.pop >= 50), None)
    if wet:
        return "Dry for now, but rain is likely by %s." % _clock(wet.time)
    return "No rain expected for the next few hours."


def say_now(w: Weather, st: Status) -> str:
    s = "In %s it's %s and %s." % (w.place, _deg(w.temp), w.text.lower())
    if abs(w.feels - w.temp) >= 2:
        s += " It feels like %s." % _deg(w.feels)
    return s + " " + rain_sentence(w)


def say_next(w: Weather, st: Status) -> str:
    parts = []
    for x in w.upcoming_hours(3):
        parts.append("%s, %s, %s, %d percent chance of rain" % (
            _clock(x.time), _deg(x.temp), describe(x.code)[0].lower(), x.pop))
    return "Coming up. " + ". ".join(parts) + "." if parts else "No hourly forecast."


def say_rain(w: Weather, st: Status) -> str:
    return rain_sentence(w)


def say_wind(w: Weather, st: Status) -> str:
    s = "Wind from the %s at %d miles an hour" % (compass(w.wind_dir, words=True), round(w.wind))
    if w.gust - w.wind >= 8:
        s += ", gusting %d" % round(w.gust)
    return s + "."


def say_sun(w: Weather, st: Status) -> str:
    d = w.today
    if d is None:
        return "No sunrise data."
    if w.now < d.sunrise:
        return "Sunrise is at %s." % _clock(d.sunrise)
    if w.now < d.sunset:
        left = int((d.sunset - w.now).total_seconds() // 60)
        return "Sunset at %s, %s of daylight left. UV today is %s." % (
            _clock(d.sunset), _mins(left), {"mod": "moderate", "v.high": "very high"}.get(uv_word(d.uv), uv_word(d.uv)))
    t = w.tomorrow
    return "The sun has set. Sunrise tomorrow is at %s." % _clock(t.sunrise if t else d.sunrise)


def say_pressure(w: Weather, st: Status) -> str:
    _, word = w.pressure_trend()
    return "Pressure %d hectopascals, %s. %s." % (round(w.pressure), word.lower().replace(" fast", " quickly"),
                                                   barometer_word(w.pressure, w.pressure_trend()[0]))


def say_tomorrow(w: Weather, st: Status) -> str:
    t = w.tomorrow
    if t is None:
        return "No forecast for tomorrow."
    return "Tomorrow, %s. High of %s, low of %s, %d percent chance of rain." % (
        describe(t.code)[0].lower(), _deg(t.tmax), _deg(t.tmin), t.pop)


def say_device(w: Weather, st: Status) -> str:
    if st.battery is None:
        return "Battery level unknown."
    s = "Battery %d percent" % st.battery
    if st.charging:
        s += ", charging"
    elif st.minutes_left:
        s += ", about %s left" % _mins(st.minutes_left)
    return s + "."


SAY = {"now": say_now, "next": say_next, "rain": say_rain, "wind": say_wind,
       "sun": say_sun, "pressure": say_pressure, "tomorrow": say_tomorrow, "device": say_device}


def briefing(w: Weather, st: Status) -> str:
    return " ".join([say_now(w, st), say_wind(w, st), say_tomorrow(w, st)])


class Speaker:
    """Speaks one thing at a time; a new request cuts off the old one.

    With an output role ("speaker" / "usb") the speech is rendered to a WAV
    and played with pw-play --target, so it can go to the pi-top's speaker
    while music plays on the USB card. (Piping espeak into pw-play instead
    plays 2.2x too fast: espeak makes 22050 Hz and pw-play ignores the header
    on a pipe.)"""

    def __init__(self, voice: str = "en-gb", speed: int = 150, volume: int = 100,
                 output: str = "default"):
        self.cmd = shutil.which("espeak-ng") or shutil.which("espeak")
        self.voice, self.speed, self.volume, self.output = voice, speed, volume, output
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._gen = 0

    @property
    def available(self) -> bool:
        return self.cmd is not None

    def stop(self):
        with self._lock:
            self._gen += 1
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
            self._proc = None

    @property
    def busy(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def say(self, text: str):
        if not self.cmd:
            print("[speech unavailable] " + text, flush=True)
            return
        self.stop()
        espeak = [self.cmd, "-v", self.voice, "-s", str(self.speed), "-a", str(self.volume)]
        target = audio.sink_for(self.output) if self.output != "default" else None
        if target is None:
            with self._lock:
                self._proc = subprocess.Popen(espeak + [text], stdout=subprocess.DEVNULL,
                                              stderr=subprocess.DEVNULL)
            return
        with self._lock:
            gen = self._gen
        threading.Thread(target=self._say_to, args=(espeak, text, target, gen), daemon=True).start()

    def _say_to(self, espeak, text, target, gen):
        fd, wav = tempfile.mkstemp(suffix=".wav", prefix="pitop-say-")
        os.close(fd)
        try:
            subprocess.run(espeak + ["-w", wav, text], capture_output=True, timeout=30)
            with self._lock:
                if gen != self._gen:        # stopped or replaced while rendering
                    return
                self._proc = subprocess.Popen(["pw-play", "--target", target, wav],
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                proc = self._proc
            proc.wait()
        finally:
            try:
                os.remove(wav)
            except OSError:
                pass
