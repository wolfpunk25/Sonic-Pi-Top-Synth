"""Fetch and interpret an Open-Meteo forecast (free, no API key).

Everything here is plain data: `Weather.from_api()` takes the decoded JSON
and a "now", so the pages can be rendered and tested without a network or
a clock.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

# WMO weather code -> (short text, icon kind)
WMO = {
    0: ("Clear", "clear"),
    1: ("Mostly clear", "clear"),
    2: ("Partly cloudy", "partly"),
    3: ("Overcast", "cloud"),
    45: ("Fog", "fog"),
    48: ("Freezing fog", "fog"),
    51: ("Light drizzle", "drizzle"),
    53: ("Drizzle", "drizzle"),
    55: ("Heavy drizzle", "drizzle"),
    56: ("Freezing drizzle", "drizzle"),
    57: ("Freezing drizzle", "drizzle"),
    61: ("Light rain", "rain"),
    63: ("Rain", "rain"),
    65: ("Heavy rain", "rain"),
    66: ("Freezing rain", "rain"),
    67: ("Freezing rain", "rain"),
    71: ("Light snow", "snow"),
    73: ("Snow", "snow"),
    75: ("Heavy snow", "snow"),
    77: ("Snow grains", "snow"),
    80: ("Light showers", "showers"),
    81: ("Showers", "showers"),
    82: ("Heavy showers", "showers"),
    85: ("Snow showers", "snow"),
    86: ("Snow showers", "snow"),
    95: ("Thunderstorm", "thunder"),
    96: ("Thunder + hail", "thunder"),
    99: ("Thunder + hail", "thunder"),
}

COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
COMPASS_WORDS = ["north", "north-east", "east", "south-east",
                 "south", "south-west", "west", "north-west"]

WET_MM = 0.1          # a 15-minute slot counts as rain at or above this
RAIN_LIKELY_PCT = 50  # an hour counts as rainy at or above this chance


def describe(code: int) -> Tuple[str, str]:
    return WMO.get(code, ("Unknown", "cloud"))


def compass(deg: float, words: bool = False) -> str:
    i = int((deg % 360) / 45 + 0.5) % 8
    return (COMPASS_WORDS if words else COMPASS)[i]


def _t(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M")


@dataclass
class Hour:
    time: datetime
    temp: float
    pop: int            # precipitation probability, %
    code: int
    pressure: float     # hPa, mean sea level
    wind: float


@dataclass
class Day:
    date: datetime
    tmax: float
    tmin: float
    code: int
    pop: int
    uv: float
    sunrise: datetime
    sunset: datetime


@dataclass
class Weather:
    place: str
    now: datetime               # local time at the forecast location
    fetched_at: float           # epoch seconds
    temp: float
    feels: float
    humidity: int
    code: int
    is_day: bool
    wind: float                 # mph
    wind_dir: float             # degrees the wind comes FROM
    gust: float
    pressure: float
    precip_now: float
    hours: List[Hour] = field(default_factory=list)      # includes a few past hours
    rain15: List[Tuple[datetime, float]] = field(default_factory=list)
    days: List[Day] = field(default_factory=list)

    # ---- building -------------------------------------------------------

    @classmethod
    def from_api(cls, j: dict, place: str, now: Optional[datetime] = None,
                 fetched_at: Optional[float] = None) -> "Weather":
        if now is None:
            now = datetime.utcnow() + timedelta(seconds=j.get("utc_offset_seconds", 0))
        c = j["current"]
        h = j["hourly"]
        hours = [Hour(_t(h["time"][i]), h["temperature_2m"][i],
                      h["precipitation_probability"][i] or 0,
                      h["weather_code"][i], h["pressure_msl"][i],
                      h["wind_speed_10m"][i])
                 for i in range(len(h["time"]))
                 if h["temperature_2m"][i] is not None]
        m = j.get("minutely_15", {})
        rain15 = [(_t(t), mm or 0.0) for t, mm in zip(m.get("time", []), m.get("precipitation", []))]
        d = j["daily"]
        days = [Day(_t(d["time"][i] + "T00:00"), d["temperature_2m_max"][i],
                    d["temperature_2m_min"][i], d["weather_code"][i],
                    d["precipitation_probability_max"][i] or 0,
                    d["uv_index_max"][i] or 0.0,
                    _t(d["sunrise"][i]), _t(d["sunset"][i]))
                for i in range(len(d["time"]))]
        return cls(place=place, now=now,
                   fetched_at=fetched_at if fetched_at is not None else time.time(),
                   temp=c["temperature_2m"], feels=c["apparent_temperature"],
                   humidity=c["relative_humidity_2m"], code=c["weather_code"],
                   is_day=bool(c["is_day"]), wind=c["wind_speed_10m"],
                   wind_dir=c["wind_direction_10m"], gust=c["wind_gusts_10m"],
                   pressure=c["pressure_msl"], precip_now=c.get("precipitation") or 0.0,
                   hours=hours, rain15=rain15, days=days)

    def at(self, now: datetime) -> "Weather":
        """The same forecast, viewed from a later moment (for the clock)."""
        w = Weather(**{**self.__dict__})
        w.now = now
        return w

    # ---- interpretation -------------------------------------------------

    @property
    def text(self) -> str:
        return describe(self.code)[0]

    @property
    def icon(self) -> str:
        return describe(self.code)[1]

    def upcoming_hours(self, n: int) -> List[Hour]:
        """The next n whole hours after now."""
        return [x for x in self.hours if x.time > self.now][:n]

    def pressure_series(self) -> List[Hour]:
        """Three hours back to six hours ahead, for the trend chart."""
        lo, hi = self.now - timedelta(hours=3, minutes=1), self.now + timedelta(hours=6)
        return [x for x in self.hours if lo <= x.time <= hi]

    def pressure_trend(self) -> Tuple[float, str]:
        """Change over the last three hours, in the shipping-forecast sense."""
        target = self.now - timedelta(hours=3)
        past = [x for x in self.hours if x.time <= self.now]
        if not past:
            return 0.0, "Steady"
        then = min(past, key=lambda x: abs((x.time - target).total_seconds()))
        delta = self.pressure - then.pressure
        mag = abs(delta)
        if mag < 0.5:
            return delta, "Steady"
        word = "Rising" if delta > 0 else "Falling"
        if mag < 1.6:
            return delta, word + " slowly"
        if mag < 3.6:
            return delta, word
        return delta, word + " fast"

    def rain_slots(self) -> List[Tuple[datetime, float]]:
        """The 15-minute slots from the current one onwards (two hours)."""
        start = self.now - timedelta(minutes=15)
        return [s for s in self.rain15 if s[0] > start][:8]

    def rain_eta(self) -> Tuple[str, Optional[int]]:
        """("now", minutes_until_it_stops) or ("soon", minutes_until_it_starts)
        or ("dry", None) over the next two hours."""
        slots = self.rain_slots()
        if not slots:
            return "dry", None
        raining = self.precip_now >= WET_MM or slots[0][1] >= WET_MM
        if raining:
            for t, mm in slots[1:]:
                if mm < WET_MM:
                    return "now", max(0, int((t - self.now).total_seconds() // 60))
            return "now", None
        for t, mm in slots:
            if mm >= WET_MM:
                return "soon", max(0, int((t - self.now).total_seconds() // 60))
        return "dry", None

    def outlook(self) -> str:
        """One short line about the next few hours."""
        kind, mins = self.rain_eta()
        if kind == "now":
            return "Rain easing in ~%d min" % _round5(mins) if mins is not None else "Raining for a while"
        if kind == "soon":
            return "Rain in about %d min" % _round5(mins)
        nxt = self.upcoming_hours(6)
        for x in nxt:
            if x.pop >= RAIN_LIKELY_PCT:
                return "Rain likely by %s" % x.time.strftime("%H:%M")
        if nxt:
            return "Dry until %s+" % nxt[-1].time.strftime("%H:%M")
        return "No forecast"

    @property
    def today(self) -> Optional[Day]:
        return next((d for d in self.days if d.date.date() == self.now.date()), None)

    @property
    def tomorrow(self) -> Optional[Day]:
        target = (self.now + timedelta(days=1)).date()
        return next((d for d in self.days if d.date.date() == target), None)

    def conditions_at(self, now: datetime, now_epoch: Optional[float] = None) -> Optional[dict]:
        """The weather to label a recording with.

        A fresh fetch has real "current" readings. Out on a walk there is
        usually no Wi-Fi, so after half an hour the best we have is the
        forecast for that hour, and the tag says so."""
        age = self.age_minutes(now_epoch)
        if age < 30:
            return {"source": "observed", "temp": self.temp, "feels": self.feels,
                    "conditions": self.text, "code": self.code, "wind_mph": self.wind,
                    "wind_from": compass(self.wind_dir), "gust_mph": self.gust,
                    "pressure_hpa": self.pressure, "humidity": self.humidity,
                    "forecast_age_min": age}
        near = [h for h in self.hours if abs((h.time - now).total_seconds()) <= 45 * 60]
        if not near:
            return None     # the saved forecast doesn't reach this far
        h = min(near, key=lambda h: abs((h.time - now).total_seconds()))
        return {"source": "forecast", "temp": h.temp, "conditions": describe(h.code)[0],
                "code": h.code, "wind_mph": h.wind, "pressure_hpa": h.pressure,
                "rain_chance": h.pop, "forecast_age_min": age}

    def age_minutes(self, now_epoch: Optional[float] = None) -> int:
        now_epoch = time.time() if now_epoch is None else now_epoch
        return int((now_epoch - self.fetched_at) // 60)


def _round5(m: int) -> int:
    return max(5, int(5 * round(m / 5)))


# ---- network --------------------------------------------------------------

def _get(url: str, params: dict, timeout: float = 15) -> dict:
    q = urllib.parse.urlencode(params)
    req = urllib.request.Request(url + "?" + q, headers={"User-Agent": "pitop-weather/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def geocode(name: str, country: str = "") -> Tuple[float, float, str]:
    params = {"name": name, "count": 1, "language": "en", "format": "json"}
    if country:
        params["countryCode"] = country
    j = _get(GEOCODE_URL, params)
    if not j.get("results"):
        raise ValueError("Couldn't find a place called %r" % name)
    r = j["results"][0]
    return r["latitude"], r["longitude"], r["name"]


def fetch(lat: float, lon: float) -> dict:
    return _get(FORECAST_URL, {
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                   "weather_code,is_day,wind_speed_10m,wind_direction_10m,"
                   "wind_gusts_10m,pressure_msl,precipitation",
        "hourly": "temperature_2m,precipitation_probability,weather_code,"
                  "pressure_msl,wind_speed_10m",
        "minutely_15": "precipitation",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "precipitation_probability_max,uv_index_max,sunrise,sunset",
        "past_hours": 3, "forecast_hours": 12,
        "past_minutely_15": 1, "forecast_minutely_15": 8,
        "forecast_days": 2, "past_days": 0,
        "wind_speed_unit": "mph", "timezone": "auto",
    })
