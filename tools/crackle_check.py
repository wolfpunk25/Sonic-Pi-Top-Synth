#!/usr/bin/env python3
"""Find out why a sketch crackles: missed deadlines (xruns) or clipping.

    python3 tools/crackle_check.py [--seconds N] [--buffer N] sketches/33-aurora.rb ...

For each sketch, as the station would play it (gain included):
  * xruns  - PipeWire's error count on the Sonic Pi node, before and after
  * overruns - SuperSonic's own "render took longer than the budget" lines
  * clipped - samples at the USB card within 0.1 dB of full scale
  * peak    - loudest sample
  * cpu     - SuperSonic's share of one core while it played
"""
import array
import math
import os
import re
import subprocess
import sys
import tempfile
import time
import wave

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from pitop_weather import audio, sonicpi  # noqa: E402

LOG = os.path.expanduser("~/.sonic-pi/log/supersonic.log")


def pw_errors():
    """ERR column for the Sonic Pi output node (0 if not found)."""
    out = subprocess.run(["pw-top", "-b", "-n", "2"], capture_output=True, text=True).stdout
    errs = [int(l.split()[8]) for l in out.splitlines()
            if l.rstrip().endswith("Sonic Pi") and len(l.split()) > 8 and l.split()[8].isdigit()]
    return errs[-1] if errs else 0


def overruns():
    try:
        with open(LOG, errors="replace") as f:
            return sum(1 for l in f if "[overrun]" in l)
    except OSError:
        return 0


def cpu_ticks():
    pids = subprocess.run(["pgrep", "-f", "sonic-pi-supersonic"], capture_output=True, text=True).stdout.split()
    total = 0
    for p in pids:
        try:
            f = open("/proc/%s/stat" % p).read().split()
            total += int(f[13]) + int(f[14])
        except (OSError, IndexError):
            pass
    return total


def gaps(samples, channels=2, rate=48000):
    """Dropouts you can hear: a run of at least 1 ms of exact digital silence
    in both channels while the sound either side of it is clearly audible.
    An xrun leaves exactly that hole; real music almost never does."""
    n = len(samples) // channels
    mono = [abs(samples[i * channels]) + abs(samples[i * channels + 1]) for i in range(n)]
    need, around = int(rate * 0.001), int(rate * 0.005)
    found, i = 0, around
    while i < n - around:
        if mono[i] == 0:
            j = i
            while j < n and mono[j] == 0:
                j += 1
            if j - i >= need and j < n - around:
                before = max(mono[i - around:i])
                after = max(mono[j:j + around])
                if before > 300 and after > 300:          # about -40 dBFS on both sides
                    found += 1
            i = j
        else:
            i += 1
    return found


def main(args):
    secs, buf = 40.0, 128
    while args and args[0].startswith("--"):
        if args[0] == "--seconds":
            secs = float(args[1])
        elif args[0] == "--buffer":
            buf = int(args[1])
        args = args[2:]
    sink = audio.sink_for("usb")
    folder = os.path.dirname(os.path.abspath(args[0]))
    everything = {os.path.abspath(s.path): s for s in sonicpi.load_sketches(folder)}
    pluck = next((s for s in everything.values() if s.title == "Pluck"), None)
    e = sonicpi.Engine("~/apps/sonic-pi-5.0.0", os.path.join(REPO, "tools", "trixie-run.sh"), buffer_size=buf)
    e.start()
    while e.state == "starting":
        time.sleep(0.1)
    time.sleep(2)
    print("buffer %d samples (%.1f ms), real-time priority %s" % (
        buf, 1000.0 * buf / 48000, "OFF" if os.environ.get("PITOP_NO_RT") else "on"), flush=True)
    wav = os.path.join(tempfile.gettempdir(), "crackle.wav")
    for p in args:
        sk = everything[os.path.abspath(p)]
        e.stop_all()
        time.sleep(1.5)
        e.run(sonicpi.build_code(sk, None, pluck))
        time.sleep(3)                                  # skip start-up, which always has a hiccup
        err0, over0, cpu0, t0 = pw_errors(), overruns(), cpu_ticks(), time.time()
        rec = subprocess.Popen(["pw-record", "-P", "{ stream.capture.sink=true }", "--target", sink,
                                "--rate", "48000", "--channels", "2", "--format", "s16", wav],
                               stderr=subprocess.DEVNULL)
        time.sleep(secs)
        rec.terminate()
        rec.wait()
        err1, over1, cpu1, t1 = pw_errors(), overruns(), cpu_ticks(), time.time()
        w = wave.open(wav)
        a = array.array("h", w.readframes(w.getnframes()))
        w.close()
        peak = max(abs(x) for x in a) or 1
        clipped = sum(1 for x in a if abs(x) >= 32400)
        holes = gaps(a)
        cpu = 100.0 * (cpu1 - cpu0) / os.sysconf("SC_CLK_TCK") / (t1 - t0)
        print("%-26s dropouts %3d  overruns %3d  clipped %5d  peak %6.1f dBFS  cpu %4.0f%%  %s" % (
            os.path.basename(p), holes, over1 - over0, clipped, 20 * math.log10(peak / 32768),
            cpu, e.error), flush=True)
    e.stop_all()
    e.exit()


if __name__ == "__main__":
    main(sys.argv[1:])
