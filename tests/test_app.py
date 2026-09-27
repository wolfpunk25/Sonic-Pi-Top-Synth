"""Run with:  python3 -m unittest discover tests"""
import copy
import json
import os
import tempfile
import unittest
from datetime import datetime, time as dtime, timedelta

from pitop_weather import app, forecast, recorder, render, sonicpi, speech

HERE = os.path.dirname(os.path.abspath(__file__))
app.CACHE = tempfile.mkdtemp(prefix="pitop-cache-")      # never touch the real ~/.cache in tests
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


class FakeSource:
    """A mic that yields `seconds` of a quiet tone, or nothing at all."""

    def __init__(self, seconds, rate=8000, amplitude=3000):
        import math
        import struct
        n = int(seconds * rate)
        self.data = b"".join(struct.pack("<h", int(amplitude * math.sin(i / 5.0))) for i in range(n))
        self.pos = 0
        self.closed = False

    def read(self, n):
        chunk = self.data[self.pos:self.pos + n]
        self.pos += len(chunk)
        return chunk

    def close(self):
        self.closed = True


class FakePlayer:
    def __init__(self):
        self.playing = None
        self.played = []

    def play(self, path):
        self.playing = path
        self.played.append(path)

    def stop(self):
        self.playing = None


class FakeEngine:
    """Sonic Pi without Sonic Pi. start() leaves it 'starting' until boot()."""

    def __init__(self):
        self.state, self.error, self.error_at = "off", "", 0.0
        self.output, self.midi_name = "usb", "C Major Seven"
        self.ran, self.stops, self.starts, self.outputs_set = [], 0, 0, []
        self.on_change = lambda: None

    def start(self):
        self.starts += 1
        self.state = "starting"

    def boot(self):
        self.state = "ready"
        self.on_change()

    def run(self, code):
        self.ran.append(code)

    def stop_all(self):
        self.stops += 1

    def set_output(self, role):
        self.output = role
        self.outputs_set.append(role)

    def exit(self):
        self.state = "off"


def make_app(local=NIGHT, mic="Fake USB Mic", source_seconds=3.0, engine=None, cache=None, **cfg):
    app.CACHE = cache or tempfile.mkdtemp(prefix="pitop-cache-")   # each app starts with nothing remembered
    c = app.Config(None)
    c.quiet_from = c.quiet_until = dtime(0, 0)   # never quiet unless a test says so
    c.rec_folder = tempfile.mkdtemp(prefix="soundwalks-")
    c.sp_sketches = tempfile.mkdtemp(prefix="sketches-")
    for k, v in cfg.items():
        setattr(c, k, v)
    hw, spk, clk = FakeHW(), FakeSpeaker(), Clock()
    rec = recorder.Recorder(c.rec_folder, rate=8000, max_seconds=c.rec_seconds,
                            source_factory=lambda: FakeSource(source_seconds))
    a = app.App(hw, c, spk, clock=clk, local_now=lambda: local, rec=rec,
                player=FakePlayer(), find_mic=lambda: mic, engine=engine,
                outputs=lambda: ["usb", "speaker"])
    return a, hw, spk, clk


def goto(a, page):
    a.page = a.names.index(page)


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
                if name in ("record", "clips", "sonicpi"):   # Select records/browses there
                    continue
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
        self.assertEqual(a.names[a.page], "record")
        press(a, "up")
        press(a, "up")
        self.assertEqual(a.names[a.page], "device")
        press(a, "cancel", clk, 0.2)
        self.assertEqual(a.page, 0)
        self.assertTrue(a.running)

    def test_select_speaks_the_page(self):
        a, hw, spk, clk = make_app()
        a.set_weather(weather())
        goto(a, "rain")
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
        self.assertEqual(a.names[a.page], "record")

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


class TestRecorder(unittest.TestCase):
    def test_clip_is_saved_with_its_label(self):
        folder = tempfile.mkdtemp()
        r = recorder.Recorder(folder, rate=8000, max_seconds=60, source_factory=lambda: FakeSource(2.0))
        done = []
        r.on_done = lambda clip, err: done.append((clip, err))
        tag = weather().conditions_at(NIGHT, 0)
        r.start(NIGHT, {"weather": tag})
        r.wait(5)
        clip, err = done[0]
        self.assertEqual(err, "")
        self.assertTrue(clip.wav.endswith("232900-partly-cloudy-16c.wav"), clip.wav)
        import wave
        with wave.open(clip.wav) as wf:
            self.assertEqual((wf.getnchannels(), wf.getframerate(), wf.getnframes()), (1, 8000, 16000))
        meta = json.load(open(clip.wav[:-4] + ".json"))
        self.assertEqual(meta["seconds"], 2.0)
        self.assertEqual(meta["weather"]["source"], "observed")
        self.assertLess(meta["peak_dbfs"], -10)
        self.assertEqual([c.wav for c in recorder.list_clips(folder)], [clip.wav])
        self.assertEqual(os.listdir(os.path.dirname(clip.wav)).count(os.path.basename(clip.wav) + ".part"), 0)

    def test_stops_at_the_limit(self):
        folder = tempfile.mkdtemp()
        src = FakeSource(10.0)
        r = recorder.Recorder(folder, rate=8000, max_seconds=1.5, source_factory=lambda: src)
        done = []
        r.on_done = lambda clip, err: done.append(clip)
        r.start(NIGHT, {})
        r.wait(5)
        self.assertEqual(done[0].seconds, 1.5)
        self.assertTrue(src.closed)

    def test_silent_mic_saves_nothing(self):
        folder = tempfile.mkdtemp()
        r = recorder.Recorder(folder, rate=8000, source_factory=lambda: FakeSource(0))
        done = []
        r.on_done = lambda clip, err: done.append((clip, err))
        r.start(NIGHT, {})
        r.wait(5)
        self.assertIsNone(done[0][0])
        self.assertIn("No sound", done[0][1])

    def test_a_tap_is_too_short(self):
        folder = tempfile.mkdtemp()
        r = recorder.Recorder(folder, rate=8000, source_factory=lambda: FakeSource(0.2))
        done = []
        r.on_done = lambda clip, err: done.append((clip, err))
        r.start(NIGHT, {})
        r.wait(5)
        self.assertEqual(done[0], (None, "Too short, not kept"))
        self.assertEqual(recorder.list_clips(folder), [])
        self.assertEqual(sum(len(f) for _, _, f in os.walk(folder)), 0)

    def test_names(self):
        self.assertEqual(recorder.clip_basename(NIGHT, {"temp": -2.6, "conditions": "Light snow"}),
                         "232900-light-snow-m3c")
        self.assertEqual(recorder.clip_basename(NIGHT, None), "232900")

    def test_parse_arecord_list(self):
        out = ("**** List of CAPTURE Hardware Devices ****\n"
               "card 3: Device [USB PnP Sound Device], device 0: USB Audio [USB Audio]\n")
        self.assertEqual(recorder.parse_arecord_list(out), "USB PnP Sound Device")
        self.assertIsNone(recorder.parse_arecord_list("**** List of CAPTURE Hardware Devices ****\n"))


class TestWeatherTag(unittest.TestCase):
    def test_fresh_forecast_is_observed(self):
        self.assertEqual(weather().conditions_at(NIGHT, 60 * 10)["source"], "observed")

    def test_old_forecast_falls_back_to_that_hour(self):
        w = weather()
        t = w.conditions_at(NIGHT + timedelta(hours=3), 60 * 60 * 3)
        self.assertEqual(t["source"], "forecast")
        self.assertIn("rain_chance", t)

    def test_beyond_the_forecast_is_none(self):
        self.assertIsNone(weather().conditions_at(NIGHT + timedelta(days=3), 3 * 86400))


class TestRecordingInApp(unittest.TestCase):
    def record(self, a, clk):
        goto(a, "record")
        press(a, "select")
        self.assertTrue(a.rec.recording or a.rec._thread)
        a.rec.wait(5)
        a.tick()

    def test_select_on_record_page_records_a_tagged_clip(self):
        a, hw, spk, clk = make_app()
        a.set_weather(weather())
        self.record(a, clk)
        self.assertEqual(len(a.clips), 1)
        meta = a.clips[0].meta
        self.assertEqual(meta["weather"]["conditions"], "Partly cloudy")
        self.assertEqual(meta["mic"], "Fake USB Mic")
        self.assertEqual(spk.said[-1], "Saved, 3 seconds.")
        self.assertTrue(a.status.rec.notice.startswith("Saved"))

    def test_records_without_any_forecast(self):
        a, hw, spk, clk = make_app()
        self.record(a, clk)
        self.assertEqual(len(a.clips), 1)
        self.assertIsNone(a.clips[0].meta["weather"])

    def test_no_mic(self):
        a, hw, spk, clk = make_app(mic=None)
        goto(a, "record")
        press(a, "select")
        self.assertFalse(a.rec.recording)
        self.assertEqual(a.status.rec.notice, "No microphone found")

    def test_nothing_speaks_while_recording(self):
        a, hw, spk, clk = make_app(source_seconds=30)
        a.set_weather(weather())
        goto(a, "record")
        threading = __import__("threading")
        gate, holding = threading.Event(), threading.Event()
        orig = a.rec.source_factory
        class Slow:
            """A second of audio at once, then waits like a real mic would."""
            def __init__(s):
                s.src, s.reads = orig(), 0
            def read(s, n):
                s.reads += 1
                if s.reads > 10:
                    holding.set()
                    gate.wait(5)
                return s.src.read(n)
            def close(s): s.src.close()
        a.rec.source_factory = Slow
        press(a, "select")
        self.assertTrue(holding.wait(5))    # a second is in, and the "mic" is now live
        self.assertTrue(a.rec.recording)
        a.set_weather(weather(with_rain([0, 0, 0, 0.5, 1, 1, 0, 0, 0])))
        hw.batt = (5, False, 10)
        clk.t += 31
        a.tick()
        self.assertEqual(spk.said, [])
        self.assertEqual(a.names[a.page], "record")
        press(a, "down")                 # ignored while recording
        self.assertEqual(a.names[a.page], "record")
        press(a, "select")               # stops
        gate.set()
        a.rec.wait(5)
        self.assertFalse(a.rec.recording)
        self.assertEqual(len(a.clips), 1)
        # the deferred alerts come through afterwards
        a.set_weather(weather(with_rain([0, 0, 0, 0.5, 1, 1, 0, 0, 0])))
        clk.t += 31
        a.tick()
        self.assertTrue(any(x.startswith("Heads up") for x in spk.said))
        self.assertTrue(any(x.startswith("Battery") for x in spk.said))

    def test_browse_and_play(self):
        a, hw, spk, clk = make_app()
        self.record(a, clk)
        clk.t += 1
        self.record(a, clk)   # same second on the fake clock: must not overwrite
        self.assertEqual(len(a.clips), 2, [c.wav for c in a.clips])
        goto(a, "clips")
        press(a, "select")
        self.assertTrue(a.browsing)
        press(a, "down")
        self.assertEqual(a.cursor, 1)
        press(a, "select")
        self.assertEqual(a.player.playing, a.clips[1].wav)
        press(a, "select")
        self.assertIsNone(a.player.playing)
        press(a, "cancel", clk, 0.1)
        self.assertFalse(a.browsing)
        self.assertEqual(a.names[a.page], "clips")

    def test_record_and_clip_pages_render(self):
        a, hw, spk, clk = make_app()
        for page in ("record", "clips"):
            goto(a, page)
            self.assertTrue(a.frame().getbbox())
        self.record(a, clk)
        goto(a, "clips")
        press(a, "select")
        self.assertTrue(a.frame().getbbox())


class TestSonicPi(unittest.TestCase):
    def setUp(self):
        self.eng = FakeEngine()
        self.a, self.hw, self.spk, self.clk = make_app(engine=self.eng)
        self.a.set_weather(weather())
        goto(self.a, "sonicpi")

    def open_category(self, name):
        rows = self.a.sp_rows()
        self.a.sp_cursor = [r[1] if r[0] == "cat" else None for r in rows].index(name)
        press(self.a, "select")

    def test_select_installs_starters_boots_and_shows_categories(self):
        press(self.a, "select")
        self.assertTrue(self.a.sp_browsing)
        self.assertEqual(self.eng.starts, 1)
        cats = [(r[1], r[2]) for r in self.a.sp_rows() if r[0] == "cat"]
        self.assertEqual([c for c, _ in cats], ["Keys", "Sequencers", "Grooves", "Ambient"])
        self.assertEqual(sum(n for _, n in cats), len(self.a.sketches))
        self.assertEqual(self.a.sp_rows()[-1], ("output",))
        self.assertNotIn("Other", [c for c, _ in cats])      # every starter is filed

    def test_categories_hold_the_right_sketches(self):
        press(self.a, "select")
        self.open_category("Sequencers")
        titles = [r[1].title for r in self.a.sp_rows()]
        self.assertIn("Evolving sequencer", titles)
        self.assertIn("Arpeggio", titles)
        self.assertNotIn("Keys", titles)
        self.assertEqual(self.a.status.sp.title if self.a.frame() else None, "Sequencers")

    def test_sketch_chosen_while_starting_plays_when_ready(self):
        press(self.a, "select")
        self.open_category("Keys")
        press(self.a, "down")
        press(self.a, "select")            # Chords, before Sonic Pi is up
        self.assertEqual(self.eng.ran, [])
        self.assertEqual(self.a.sp_pending.title, "Chords")
        self.eng.boot()                    # from the engine's thread...
        self.a.tick()                      # ...and picked up on the main loop
        self.assertEqual(len(self.eng.ran), 1)
        self.assertIn("with_fx :reverb", self.eng.ran[0])
        self.assertTrue(self.eng.ran[0].startswith("set :wx_known, true; set :wx_temp, 16.2"))
        self.assertEqual(self.a.sp_playing, "Chords")

    def test_cancel_goes_up_then_stops_then_leaves(self):
        press(self.a, "select")
        self.eng.boot()
        self.open_category("Keys")
        press(self.a, "select")            # play Keys
        self.assertEqual(self.a.sp_playing, "Keys")
        press(self.a, "cancel", self.clk, 0.1)          # up to the categories, still playing
        self.assertIsNone(self.a.sp_cat)
        self.assertEqual(self.a.sp_playing, "Keys")
        self.assertEqual(self.a.status.sp.rows[0][2] if self.a.frame() else None, ">")  # Keys marked
        press(self.a, "cancel", self.clk, 0.1)          # stop
        self.assertIsNone(self.a.sp_playing)
        self.assertTrue(self.a.sp_browsing)
        press(self.a, "cancel", self.clk, 0.1)          # leave
        self.assertFalse(self.a.sp_browsing)
        self.assertEqual(self.a.names[self.a.page], "sonicpi")

    def test_reopening_a_category_lands_on_the_playing_sketch(self):
        press(self.a, "select")
        self.eng.boot()
        self.open_category("Ambient")
        press(self.a, "down")
        press(self.a, "down")
        playing = self.a.sp_rows()[self.a.sp_cursor][1].title
        press(self.a, "select")
        press(self.a, "cancel", self.clk, 0.1)
        press(self.a, "select")            # back into Ambient
        self.assertEqual(self.a.sp_rows()[self.a.sp_cursor][1].title, playing)

    def test_up_wraps_to_output_and_it_toggles(self):
        press(self.a, "select")
        self.eng.boot()
        press(self.a, "up")                # from the first category straight to "Output"
        self.assertEqual(self.a.sp_rows()[self.a.sp_cursor], ("output",))
        press(self.a, "select")
        press(self.a, "select")
        self.assertEqual(self.eng.outputs_set, ["speaker", "usb"])

    def test_new_sketch_replaces_old(self):
        press(self.a, "select")
        self.eng.boot()
        self.open_category("Keys")
        press(self.a, "select")
        press(self.a, "down")
        press(self.a, "select")
        self.assertEqual(self.a.sp_playing, "Chords")
        self.assertEqual(len(self.eng.ran), 2)

    def test_music_keeps_playing_off_the_page(self):
        press(self.a, "select")
        self.eng.boot()
        self.open_category("Keys")
        press(self.a, "select")
        self.a.sp_browsing = False                # e.g. the screensaver closed the list
        press(self.a, "up")
        self.assertEqual(self.a.names[self.a.page], "clips")
        self.assertEqual(self.a.sp_playing, "Keys")

    def test_uncategorised_sketches_go_under_other(self):
        with open(os.path.join(self.a.cfg.sp_sketches, "99-mine.rb"), "w") as f:
            f.write("# Mine - no category line\nplay 60\n")
        press(self.a, "select")
        cats = [r[1] for r in self.a.sp_rows() if r[0] == "cat"]
        self.assertEqual(cats[-1], "Other")

    def test_error_shows_and_times_out(self):
        press(self.a, "select")
        self.eng.boot()
        self.eng.error, self.eng.error_at = "Runtime Error x", self.clk.t
        self.a.frame()
        self.assertEqual(self.a.status.sp.error, "Runtime Error x")
        self.clk.t += 20
        self.a.frame()
        self.assertEqual(self.a.status.sp.error, "")

    def test_every_state_renders(self):
        self.a.frame()
        press(self.a, "select")
        self.assertTrue(self.a.frame().getbbox())      # starting, categories
        self.eng.boot()
        self.open_category("Keys")
        press(self.a, "select")
        self.eng.error, self.eng.error_at = "Syntax Error", self.clk.t
        self.assertTrue(self.a.frame().getbbox())      # sketches, playing, error bar
        self.a.sp_browsing = False
        self.assertTrue(self.a.frame().getbbox())      # summary

    def test_not_installed(self):
        a, hw, spk, clk = make_app()
        a.engine = None
        goto(a, "sonicpi")
        press(a, "select")
        self.assertFalse(a.sp_browsing)
        self.assertTrue(a.frame().getbbox())

    def play(self, category, title):
        self.a.sp_cat, self.a.sp_cursor = None, 0
        self.open_category(category)
        titles = [r[1].title for r in self.a.sp_rows()]
        self.a.sp_cursor = titles.index(title)
        press(self.a, "select")

    def test_groove_uses_pluck_until_a_keys_sound_is_chosen(self):
        press(self.a, "select")
        self.eng.boot()
        self.play("Grooves", "Beat and keys")
        self.assertIn("sample :bd_haus", self.eng.ran[-1])
        self.assertIn("synth :pluck", self.eng.ran[-1])
        self.assertEqual(self.a.sp_with, "Pluck")

    def test_groove_uses_the_last_keys_sound_even_after_a_restart(self):
        press(self.a, "select")
        self.eng.boot()
        self.play("Keys", "Piano")
        self.play("Sequencers", "Arpeggio")          # not Keys: doesn't change the choice
        self.play("Grooves", "Beat and keys")
        self.assertIn("synth :piano", self.eng.ran[-1])
        self.assertNotIn("synth :pluck", self.eng.ran[-1])
        self.assertEqual(self.a.sp_with, "Piano")
        self.assertEqual(self.a.frame() and self.a.status.sp.playing_with, "Piano")
        # a new app (e.g. after a reboot) remembers
        eng2 = FakeEngine()
        a2, _, _, _ = make_app(engine=eng2, cache=app.CACHE)
        self.assertEqual(a2.sp_last_keys, "Piano")

    def test_sketch_gains_wrap_the_code(self):
        press(self.a, "select")
        self.eng.boot()
        sk = next(k for k in self.a.sketches if k.title == "Beat and keys")
        keys = next(k for k in self.a.sketches if k.title == "Pluck")
        sk.gain, keys.gain = 0.5, 2.0
        code = sonicpi.build_code(sk, None, keys)
        self.assertIn("with_fx :level, amp: 0.50 do\n", code)
        self.assertIn("with_fx :level, amp: 2.00 do\n", code)
        self.assertEqual(code.count("with_fx :level"), 2)

    def test_speech_is_silenced_by_a_new_sketch(self):
        press(self.a, "select")
        self.eng.boot()
        self.open_category("Keys")
        self.spk.busy = True
        press(self.a, "select")
        self.assertFalse(self.spk.busy)


class TestSonicPiPieces(unittest.TestCase):
    def test_parse_osc_roundtrip(self):
        addr, args = sonicpi.parse_osc(sonicpi.osc("/x", 5, "hello", -2))
        self.assertEqual((addr, args), ("/x", [5, "hello", -2]))

    def test_ports_and_names(self):
        ports = sonicpi.parse_ports(["1\tmidi_through_midi_through_port-0_14_0\n"
                                     "1\tc_major_seven_c_major_seven_out_32_0\n0\tsomething_off_1_0"])
        self.assertEqual(ports, ["c_major_seven_c_major_seven_out_32_0"])
        e = sonicpi.Engine("x", "y")
        e.midi_in = ports
        self.assertEqual(e.midi_name, "C Major Seven")

    def test_port_names(self):
        self.assertEqual(sonicpi.port_name("c_major_seven_c_major_seven_out_32_0"), "C Major Seven")
        self.assertEqual(sonicpi.port_name("lydian7_lydian7_bluetooth_132_0"), "Lydian7 (BT)")
        self.assertEqual(sonicpi.port_name("wolfpunk_wolfpunk_bluetooth_132_0"), "Wolfpunk (BT)")
        e = sonicpi.Engine("x", "y")
        e.midi_in = ["c_major_seven_c_major_seven_out_32_0", "lydian7_lydian7_bluetooth_132_0"]
        self.assertEqual(e.midi_name, "C Major Seven + Lydian7 (BT)")

    def test_btmidi_backoff(self):
        from pitop_weather import btmidi
        t = [100.0]
        b = btmidi.Backoff(clock=lambda: t[0])
        self.assertTrue(b.ready("d"))
        gaps = [b.failed("d") for _ in range(8)]
        self.assertEqual(gaps[:3], [5.0, 10.0, 20.0])
        self.assertEqual(gaps[-1], btmidi.MAX_BACKOFF)
        self.assertFalse(b.ready("d"))
        t[0] += btmidi.MAX_BACKOFF
        self.assertTrue(b.ready("d"))
        b.succeeded("d")
        self.assertEqual(b.failed("d"), 5.0)
        self.assertTrue(btmidi.is_midi({"UUIDs": ["03B80E5A-EDE8-4B33-A751-6CE34EC4C700"]}))
        self.assertFalse(btmidi.is_midi({"UUIDs": ["0000180f-0000-1000-8000-00805f9b34fb"]}))

    def test_weather_header_is_one_line(self):
        self.assertEqual(sonicpi.weather_header(weather()).count("\n"), 1)
        self.assertEqual(sonicpi.weather_header(None), "set :wx_known, false\n")

    def test_short_errors(self):
        self.assertEqual(sonicpi.short_error("Runtime Error Sonic Pi doesn't know a function called `wobble`"),
                         "Unknown: wobble")
        self.assertEqual(sonicpi.short_error("Syntax Error Sonic Pi couldn't read your code"), "Syntax error")
        self.assertEqual(sonicpi.short_error("Runtime Error [buffer 3, line 4] - ZeroDivisionError"),
                         "[buffer 3, line 4] - ZeroDivisionError")

    def test_gain_and_keys_lines_are_read(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "01-x.rb"), "w") as f:
            f.write("# X - thing\n# category: grooves\n# keys: last\n# gain: 1.75\nplay 60\n")
        with open(os.path.join(d, "02-y.rb"), "w") as f:
            f.write("# Y\n# gain: nonsense\nplay 60\n")
        x, y = sonicpi.load_sketches(d)
        self.assertEqual((x.category, x.keys, x.gain), ("Grooves", "last", 1.75))
        self.assertEqual((y.gain, y.keys), (1.0, ""))
        self.assertEqual(sonicpi.wrap_gain("play 60\n", 1.0), "play 60\n")

    def test_starters_fill_the_four_categories(self):
        sketches = sonicpi.load_sketches(sonicpi.STARTER_SKETCHES)
        cats = sonicpi.categories(sketches)
        self.assertEqual([c for c, _ in cats], ["Keys", "Sequencers", "Grooves", "Ambient"])
        self.assertTrue(all(len(g) >= 15 for _, g in cats))
        self.assertTrue(all(s.gain != 1.0 or s.title == "Keys" for s in sketches),
                        [s.title for s in sketches if s.gain == 1.0 and s.title != "Keys"])   # all levelled

    def test_errors_are_never_blank(self):
        reserved = ("Runtime Error \n\nbuffer eval, line 1392\nYou may not use the built-in fn names as "
                    "variable names. (SonicPi::PreParser::PreParseError)\n You attempted to use: line")
        self.assertEqual(sonicpi.short_error(reserved), "Reserved name: line")
        self.assertEqual(sonicpi.short_error("Runtime Error\n\nbuffer eval, line 3\nNoMethodError: "
                                             "undefined method '[]' for nil"),
                         "NoMethodError: undefined method '[]' for nil")
        self.assertTrue(sonicpi.short_error("Runtime Error\n"))
        self.assertTrue(sonicpi.short_error(""))

    def test_run_before_ready_is_refused(self):
        e = sonicpi.Engine("x", "y")
        self.assertFalse(e.run("play 60"))


class TestKeebDeck(unittest.TestCase):
    from pitop_weather import keeb as K

    def press(self, m, code):
        return m.handle(code, 1) + m.handle(code, 0)

    def test_musical_typing_layout(self):
        K = self.K
        m = K.KeyMapper(octave=4)
        self.assertEqual(m.handle(K.KEY_A, 1), [("midi", bytes([0x90, 60, 100]))])   # middle C
        self.assertEqual(m.handle(K.KEY_A, 0), [("midi", bytes([0x80, 60, 0]))])
        notes = {code: m.note_for(code) for code in (K.KEY_W, K.KEY_J, K.KEY_K, K.KEY_APOSTROPHE, K.KEY_Z, K.KEY_M)}
        self.assertEqual(notes, {K.KEY_W: 61, K.KEY_J: 71, K.KEY_K: 72, K.KEY_APOSTROPHE: 77,
                                 K.KEY_Z: 48, K.KEY_M: 59})

    def test_octave_and_transpose(self):
        K = self.K
        m = K.KeyMapper(octave=4)
        m.handle(K.KEY_1 + 1, 1)            # "2"
        self.assertEqual(m.note_for(K.KEY_A), 36)
        m.handle(K.KEY_RIGHT, 1); m.handle(K.KEY_UP, 1); m.handle(K.KEY_UP, 1)
        self.assertEqual(m.note_for(K.KEY_A), 50)
        for _ in range(20):
            m.handle(K.KEY_LEFT, 1)
        self.assertEqual(m.octave, 0)

    def test_note_off_matches_note_on_after_an_octave_change(self):
        K = self.K
        m = K.KeyMapper(octave=4)
        m.handle(K.KEY_A, 1)
        m.handle(K.KEY_RIGHT, 1)
        self.assertEqual(m.handle(K.KEY_A, 0), [("midi", bytes([0x80, 60, 0]))])

    def test_autorepeat_and_double_press_are_ignored(self):
        K = self.K
        m = K.KeyMapper()
        m.handle(K.KEY_A, 1)
        self.assertEqual(m.handle(K.KEY_A, 2), [])
        self.assertEqual(m.handle(K.KEY_A, 1), [])

    def test_sustain_holds_notes_until_released(self):
        K = self.K
        m = K.KeyMapper()
        m.handle(K.KEY_F5, 1)
        self.press(m, K.KEY_A)
        self.press(m, K.KEY_D)
        out = m.handle(K.KEY_F5, 0)
        offs = [p[1] for k, p in out if k == "midi" and p[0] == 0x80]
        self.assertEqual(offs, [60, 64])

    def test_panic_and_actions(self):
        K = self.K
        m = K.KeyMapper()
        m.handle(K.KEY_A, 1)
        out = m.handle(K.KEY_F6, 1)
        self.assertIn(("midi", bytes([0x80, 60, 0])), out)
        self.assertIn(("midi", bytes([0xB0, 123, 0])), out)
        self.assertEqual(m.handle(K.KEY_F1, 1), [("action", "stop")])
        self.assertEqual(m.handle(K.KEY_F3, 1), [("action", "next")])

    def test_escape_lets_go_and_takes_back(self):
        K = self.K
        m = K.KeyMapper()
        m.handle(K.KEY_A, 1)
        out = m.handle(K.KEY_ESC, 1)
        self.assertEqual(out[-1], ("grab", False))
        self.assertIn(("midi", bytes([0x80, 60, 0])), out)    # held note released
        self.assertEqual(m.handle(K.KEY_S, 1), [])            # typing: no MIDI
        self.assertEqual(m.handle(K.KEY_ESC, 1), [("grab", True)])

    def test_channel_and_range(self):
        K = self.K
        m = K.KeyMapper(octave=8, channel=3)
        self.assertEqual(m.handle(K.KEY_A, 1)[0][1][0], 0x92)
        self.assertEqual(m.note_for(K.KEY_APOSTROPHE), 125)   # 108+17: still a note
        for _ in range(12):
            m.handle(K.KEY_UP, 1)
        self.assertIsNone(m.note_for(K.KEY_APOSTROPHE))       # +12 more is past 127
        self.assertEqual(m.handle(K.KEY_APOSTROPHE, 1), [])   # silently nothing


class TestKeebActions(unittest.TestCase):
    def setUp(self):
        self.eng = FakeEngine()
        self.a, self.hw, self.spk, self.clk = make_app(engine=self.eng)
        self.eng.boot()

    def act(self, action):
        self.a.events.put(("_keeb", action))
        self.a.tick()

    def test_next_and_prev_step_through_the_category(self):
        self.act("next")
        self.assertEqual(self.a.sp_playing, "Keys")          # first in Keys
        self.assertEqual(self.a.names[self.a.page], "sonicpi")
        self.act("next")
        self.assertEqual(self.a.sp_playing, "Chords")
        self.act("prev")
        self.act("prev")
        self.assertEqual(self.a.sp_playing_cat, "Keys")
        self.assertEqual(self.a.sp_playing, self.a.sp_group("Keys")[-1].title)   # wraps

    def test_next_scrolls_the_list_like_the_buttons(self):
        self.act("next")
        self.act("next")
        self.act("next")
        a = self.a
        self.assertTrue(a.sp_browsing)
        self.assertEqual(a.sp_cat, "Keys")
        self.assertEqual(a.sp_rows()[a.sp_cursor][1].title, a.sp_playing)      # cursor on the playing one
        a.frame()
        self.assertEqual(a.status.sp.title, "Keys")
        marked = [label for label, _, mark in a.status.sp.rows if mark == ">"]
        self.assertEqual(marked, [a.sp_playing])
        self.assertEqual(a.sp_playing, "Echo keys")                              # Keys, Chords, Echo keys
        press(a, "cancel", self.clk, 0.1)                                        # back up to the categories
        self.assertIsNone(a.sp_cat)
        self.assertEqual(a.sp_rows()[a.sp_cursor][1], "Keys")
        self.assertEqual(a.sp_playing, "Echo keys")                              # still playing

    def test_stop_and_output(self):
        self.act("next")
        self.act("stop")
        self.assertIsNone(self.a.sp_playing)
        self.act("output")
        self.assertEqual(self.eng.outputs_set, ["speaker"])

    def test_status_shows_in_the_bottom_bar(self):
        goto(self.a, "sonicpi")
        self.act("status:KeebDeck: typing")
        self.a.frame()
        self.assertEqual(self.a.status.sp.error, "KeebDeck: typing")
