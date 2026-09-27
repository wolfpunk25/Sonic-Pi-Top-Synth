#!/usr/bin/env python3
"""Run sketches on the real Sonic Pi and report any errors.

    python3 tools/sketch_check.py sketches/*.rb

Each sketch runs for a few seconds with a short MIDI phrase played into
ALSA's Midi Through port (which Sonic Pi listens to as well), so code that
only runs on a key press gets exercised too. Needs Sonic Pi installed.
"""
import os
import struct
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pitop_weather import sonicpi  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTES = list(range(60, 72)) + [45, 80]      # every pitch class, plus extremes


def midi_file(path):
    ev = b""
    for n in NOTES:
        ev += b"\x00" + bytes([0x90, n, 100])          # note on, no delay
        ev += b"\x60" + bytes([0x80, n, 0])            # note off after 96 ticks (1/8 s)
    ev += b"\x00\xff\x2f\x00"
    with open(path, "wb") as f:
        f.write(b"MThd" + struct.pack(">IHHH", 6, 0, 1, 384))   # 384 ticks/beat, 120 bpm
        f.write(b"MTrk" + struct.pack(">I", len(ev)) + ev)


def main(paths, seconds=4.0):
    mid = os.path.join(tempfile.gettempdir(), "sketch-check.mid")
    midi_file(mid)
    e = sonicpi.Engine("~/apps/sonic-pi-5.0.0", os.path.join(REPO, "tools", "trixie-run.sh"))
    e.start()
    while e.state == "starting":
        time.sleep(0.1)
    if e.state != "ready":
        sys.exit("Sonic Pi didn't start: " + e.error)
    bad = 0
    for p in paths:
        with open(p) as f:
            code = f.read()
        e.stop_all()
        time.sleep(0.5)
        e.run("set :wx_known, true; set :wx_temp, 11.0; set :wx_rain, 0.4; set :wx_wind, 12.0; "
              "set :wx_code, 61; set :wx_day, true\n" + code)
        time.sleep(1.5)
        subprocess.run(["aplaymidi", "-p", "14:0", mid], capture_output=True)
        time.sleep(max(0.5, seconds - 1.5))
        status = "ok" if not e.error else "ERROR: " + e.error
        bad += bool(e.error)
        print("%-32s %s" % (os.path.basename(p), status), flush=True)
    e.stop_all()
    e.exit()
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    args = sys.argv[1:]
    secs = 4.0
    if args[:1] == ["--seconds"]:
        secs, args = float(args[1]), args[2:]
    main(args, secs)
