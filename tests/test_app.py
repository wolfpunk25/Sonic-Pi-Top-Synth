"""Run with:  python3 -m unittest discover tests"""
import copy
import json
import os
import unittest
from datetime import datetime, time as dtime, timedelta

from pitop_weather import app, forecast, render, speech

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = json.load(open(os.path.join(HERE, "sample_london.json")))
NIGHT = datetime(2026, 9, 26, 23, 29)
AFTERNOON = datetime(2026, 9, 26, 15, 10)


def weather(j=SAMPLE, now=NIGHT, **current):
    j = copy.deepcopy(j)
    j["current"].update(current)
    return forecast.Weather.from_api(j, "London", now=now, fetched_at=0)


def with_rain(slots, precip_now=0.0):
    j = copy.deepcopy(SAMPLE)
    j["minutely_15"]["precipitation"] = slots
    j["current"]["precipitation"] = precip_now
    return j


class FakeHW(app.Hardware):
    def __init__(self):
        self.cb, self.frames, self.batt = None, [], (80, False, 200)

    def on_button(self, cb):
        self.cb = cb

    def show(self, img):
        self.frames.append(img)

    def battery(self):
        return self.batt


class FakeSpeaker:
    def __init__(self):
        self.said, self.busy = [], False

    def say(self, t):
        self.said.append(t)

    def stop(self):
        self.busy = False


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make_app(local=NIGHT, **cfg):
    c = app.Config(None)
    c.quiet_from = c.quiet_until = dtime(0, 0)   # never quiet unless a test says so
    for k, v in cfg.items():
        setattr(c, k, v)
    hw, spk, clk = FakeHW(), FakeSpeaker(), Clock()
    a = app.App(hw, c, spk, clock=clk, local_now=lambda: local)
    return a, hw, spk, clk


def press(a, name, clk=None, hold=0.0):
    a.hw.cb(name, True)
    a.tick()
    if clk:
        clk.t += hold
    a.hw.cb(name, False)
    a.tick()


class TestForecast(unittest.TestCase):
    def test_dry(self):
        self.assertEqual(weather().rain_eta(), ("dry", None))

    def test_rain_soon(self):
        w = weather(with_rain([0, 0, 0, 0.2, 0.8, 1, 1, 0, 0]))
        kind, mins = w.rain_eta()
        self.assertEqual(kind, "soon")
        self.assertTrue(10 <= mins <= 30, mins)

    def test_raining_then_stops(self):
        w = weather(with_rain([1, 1, 0.5, 0, 0, 0, 0, 0, 0], precip_now=0.8))
        kind, mins = w.rain_eta()
        self.assertEqual(kind, "now")
        self.assertIsNotNone(mins)

    def test_trace_is_not_rain(self):
        self.assertEqual(weather(with_rain([0, 0.05, 0.05, 0, 0, 0, 0, 0, 0])).rain_eta()[0], "dry")

    def test_pressure_trend_words(self):
        j = copy.deepcopy(SAMPLE)
        n = len(j["hourly"]["time"])
        j["hourly"]["pressure_msl"] = [1015 - 1.5 * i for i in range(n)]
        w = forecast.Weather.from_api(j, "x", now=NIGHT)
        w.pressure = [h for h in w.hours if h.time <= NIGHT][-1].pressure
        self.assertTrue(w.pressure_trend()[1].startswith("Falling"))

    def test_compass(self):
        self.assertEqual(forecast.compass(0), "N")
        self.assertEqual(forecast.compass(350), "N")
        self.assertEqual(forecast.compass(225), "SW")

    def test_unknown_code_does_not_crash(self):
        self.assertEqual(weather(weather_code=42).icon, "cloud")


class TestRender(unittest.TestCase):
    """Every page, in every scenario, renders at the right size without error."""

    def scenarios(self):
        st = render.Status(battery=5, charging=True, ip="10.0.0.2", stale_minutes=90, error="URLError: x")
        yield weather(), st
        yield weather(now=AFTERNOON, is_day=1), render.Status()
        yield weather(with_rain([3, 4, 2, 1, 0, 0, 0, 0, 0], 2.0), weather_code=95, temperature_2m=-12.6,
                      wind_speed_10m=70, wind_gusts_10m=99), st
        yield weather(now=datetime(2026, 9, 26, 5, 0)), st

    def test_all_pages(self):
        for w, st in self.scenarios():
            for name, fn in render.PAGES:
                img = fn(w, st)
                self.assertEqual(img.size, (128, 64), name)
                self.assertEqual(img.mode, "1")
                self.assertTrue(img.getbbox(), "%s is blank" % name)

    def test_screensaver_moves(self):
        w = weather()
        a = render.screensaver(w, NIGHT, 0).getbbox()
        b = render.screensaver(w, NIGHT, 30).getbbox()
        self.assertNotEqual(a, b)


class TestSpeech(unittest.TestCase):
    def test_every_page_has_words(self):
        st = render.Status(battery=40, minutes_left=95)
        for w in (weather(), weather(now=AFTERNOON), weather(with_rain([0, 0, 1, 1, 0, 0, 0, 0, 0]))):
            for name, _ in render.PAGES:
                s = speech.SAY[name](w, st)
                self.assertTrue(s and s.endswith("."), (name, s))
                self.assertNotIn("°", s)

    def test_negative_temperature(self):
        self.assertIn("minus 3 degrees", speech.say_now(weather(temperature_2m=-3.2), render.Status()))

    def test_rain_soon_sentence(self):
        s = speech.rain_sentence(weather(with_rain([0, 0, 0, 0.5, 1, 1, 0, 0, 0])))
        self.assertTrue(s.startswith("Rain expected in about"), s)


class TestApp(unittest.TestCase):
    def test_buttons_cycle_pages(self):
        a, hw, spk, clk = make_app()
        a.set_weather(weather())
        press(a, "down")
        self.assertEqual(a.names[a.page], "next")
        press(a, "up")
        press(a, "up")
        self.assertEqual(a.names[a.page], "device")
        press(a, "cancel", clk, 0.2)
        self.assertEqual(a.page, 0)
        self.assertTrue(a.running)

    def test_select_speaks_the_page(self):
        a, hw, spk, clk = make_app()
        a.set_weather(weather())
        press(a, "down")
        press(a, "down")
        press(a, "select")
        self.assertEqual(spk.said[-1], speech.say_rain(a.view(), a.status))

    def test_hold_cancel_quits(self):
        a, hw, spk, clk = make_app()
        a.hw.cb("cancel", True)
        a.tick()
        clk.t += app.HOLD_TO_QUIT + 0.1
        a.tick()
        self.assertFalse(a.running)

    def test_screensaver_and_wake(self):
        a, hw, spk, clk = make_app()
        a.set_weather(weather())
        press(a, "down")
        clk.t += a.cfg.saver_after + 1
        a.tick()
        self.assertTrue(a.saver)
        press(a, "down")                # wakes, does NOT change page
        self.assertFalse(a.saver)
        self.assertEqual(a.names[a.page], "next")

    def test_redraw_is_throttled_but_buttons_are_instant(self):
        a, hw, spk, clk = make_app()
        a.set_weather(weather())
        a.tick()
        renders = []
        orig = a.frame
        a.frame = lambda: renders.append(1) or orig()
        for _ in range(10):
            a.tick()
        self.assertEqual(renders, [])
        press(a, "down")                    # press and release: both re-render...
        self.assertEqual(len(renders), 2)
        self.assertEqual(len(hw.frames), 2)  # ...but only the new picture is sent
        clk.t += 1.0
        a.tick()
        self.assertEqual(len(renders), 3)

    def test_redraws_only_on_change(self):
        a, hw, spk, clk = make_app()
        a.set_weather(weather())
        for _ in range(5):
            a.tick()
        self.assertEqual(len(hw.frames), 1)

    def test_rain_alert_once_then_rearms(self):
        a, hw, spk, clk = make_app()
        soon = weather(with_rain([0, 0, 0, 0.5, 1, 1, 0, 0, 0]))
        a.set_weather(soon)
        a.set_weather(soon)
        self.assertEqual(len([s for s in spk.said if s.startswith("Heads up")]), 1)
        self.assertEqual(a.names[a.page], "rain")
        a.set_weather(weather())               # dry again
        a.set_weather(soon)
        self.assertEqual(len([s for s in spk.said if s.startswith("Heads up")]), 2)

    def test_rain_far_off_is_not_alerted(self):
        a, hw, spk, clk = make_app(rain_alert=30)
        a.set_weather(weather(with_rain([0, 0, 0, 0, 0, 0, 0.5, 1, 1])))
        self.assertEqual(spk.said, [])

    def test_quiet_hours_show_but_dont_speak(self):
        a, hw, spk, clk = make_app(quiet_from=dtime(22, 0), quiet_until=dtime(8, 0))
        a.set_weather(weather(with_rain([0, 0, 0, 0.5, 1, 1, 0, 0, 0])))
        self.assertEqual(spk.said, [])
        self.assertEqual(a.names[a.page], "rain")

    def test_battery_warnings(self):
        a, hw, spk, clk = make_app()
        hw.batt = (19, False, 40)
        a.tick()
        hw.batt = (18, False, 38)
        clk.t += 31
        a.tick()
        self.assertEqual(spk.said, ["Battery at 19 percent."])
        hw.batt = (9, False, 20)
        clk.t += 31
        a.tick()
        self.assertEqual(spk.said[-1], "Battery at 9 percent.")
        # starting low only warns once, for the lowest level crossed
        a2, hw2, spk2, _ = make_app()
        hw2.batt = (8, False, 10)
        a2.tick()
        self.assertEqual(spk2.said, ["Battery at 8 percent."])

    def test_charging_rearms_battery_warning(self):
        a, hw, spk, clk = make_app()
        hw.batt = (15, False, 30)
        a.tick()
        hw.batt = (16, True, None)
        clk.t += 31
        a.tick()
        hw.batt = (15, False, 30)
        clk.t += 31
        a.tick()
        self.assertEqual(len(spk.said), 2)

    def test_quiet_hours_wrap_midnight(self):
        q = app.in_quiet_hours
        self.assertTrue(q(datetime(2026, 1, 1, 23, 0), dtime(22), dtime(8)))
        self.assertTrue(q(datetime(2026, 1, 1, 7, 59), dtime(22), dtime(8)))
        self.assertFalse(q(datetime(2026, 1, 1, 8, 0), dtime(22), dtime(8)))
        self.assertTrue(q(datetime(2026, 1, 1, 13, 0), dtime(12), dtime(14)))

    def test_no_forecast_yet(self):
        a, hw, spk, clk = make_app()
        a.tick()
        self.assertEqual(len(hw.frames), 1)
        press(a, "select")
        self.assertEqual(spk.said, ["No forecast yet."])


if __name__ == "__main__":
    unittest.main()
