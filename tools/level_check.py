#!/usr/bin/env python3
"""Measure how loud each sketch is and write a "# gain:" line so they all match.

    python3 tools/level_check.py sketches/*.rb            # measure and write gains
    python3 tools/level_check.py --verify sketches/*.rb   # measure with gains applied

Each sketch plays on the real Sonic Pi while the USB card's output is
recorded. Keys and Sequencers get a standard MIDI phrase through Midi
Through; Grooves and Ambient are measured playing by themselves. Loudness
is the 90th-percentile RMS over 0.4 s windows, ignoring silence - roughly
"how loud it gets while it's making sound". The reference is Keys (01), so
the headphone volume that suits it suits everything.

Grooves aim 2 dB under the reference, leaving room for the Keys sound that
plays over them (it has its own gain).
"""
import array
import glob
import math
import os
import re
import struct
import subprocess
import sys
import tempfile
import time
import wave

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from pitop_weather import sonicpi  # noqa: E402

SINK_HINT = "usb"
PHRASE = [60, 64, 67, 72, 67, 64, 62, 65, 69, 72, 71, 67]
GROOVE_OFFSET_DB = -2.0
SECONDS = {"Keys": 9, "Sequencers": 12, "Grooves": 10, "Ambient": 24, "Other": 12}


def midi_phrase(path, notes, gap_ticks=134):         # 384 ticks/beat at 120 bpm: ~0.35 s apart
    ev = b""
    for n in notes:
        ev += b"\x00" + bytes([0x90, n, 100])
        ev += bytes([0x81, gap_ticks - 128]) + bytes([0x80, n, 0])
    ev += b"\x00\xff\x2f\x00"
    with open(path, "wb") as f:
        f.write(b"MThd" + struct.pack(">IHHH", 6, 0, 1, 384))
        f.write(b"MTrk" + struct.pack(">I", len(ev)) + ev)


def loudness(path):
    w = wave.open(path)
    rate, ch = w.getframerate(), w.getnchannels()
    a = array.array("h", w.readframes(w.getnframes()))
    w.close()
    win = int(rate * 0.4) * ch
    levels = []
    for i in range(0, len(a) - win, win):
        chunk = a[i:i + win]
        rms = math.sqrt(sum(x * x for x in chunk) / len(chunk))
        if rms > 30:                                  # skip silence (about -60 dBFS)
            levels.append(20 * math.log10(rms / 32768))
    if not levels:
        return None
    levels.sort()
    return levels[int(0.9 * (len(levels) - 1))]


def measure(e, sketch, sink, mid, gain):
    """Loudness of a sketch; one that's silent on its own (e.g. Finger drums,
    a Groove that only sounds when you play) is measured again with the phrase."""
    level, err = _measure(e, sketch, sink, mid, gain, sketch.category in ("Keys", "Sequencers"))
    if level is None and sketch.category not in ("Keys", "Sequencers"):
        level, err = _measure(e, sketch, sink, mid, gain, True)
    return level, err


def _measure(e, sketch, sink, mid, gain, with_phrase):
    sk = sonicpi.Sketch(sketch.path, sketch.title, sketch.category, gain, "")   # keys measured separately
    wav = os.path.join(tempfile.gettempdir(), "level.wav")
    e.stop_all()
    time.sleep(1.2)
    rec = subprocess.Popen(["pw-record", "-P", "{ stream.capture.sink=true }", "--target", sink,
                            "--rate", "48000", "--channels", "2", "--format", "s16", wav],
                           stderr=subprocess.DEVNULL)
    time.sleep(0.3)
    e.run(sonicpi.build_code(sk, None))
    secs = SECONDS.get(sketch.category, 12)
    if with_phrase:
        time.sleep(1.0)
        subprocess.run(["aplaymidi", "-p", "14:0", mid], capture_output=True)
        subprocess.run(["aplaymidi", "-p", "14:0", mid], capture_output=True)
        time.sleep(max(0.5, secs - 1.0 - 2 * 0.35 * len(PHRASE)))
    else:
        time.sleep(secs)
    rec.terminate()
    rec.wait()
    e.stop_all()
    return loudness(wav), e.error


def write_gain(path, gain):
    lines = open(path, encoding="utf-8").read().split("\n")
    lines = [l for l in lines if not re.match(r"#\s*gain\s*:", l, re.I)]
    at = max(i for i, l in enumerate(lines[:8]) if re.match(r"#\s*(category|keys)\s*:", l, re.I)) + 1
    lines.insert(at, "# gain: %.2f" % gain)
    open(path, "w", encoding="utf-8").write("\n".join(lines))


def main(args):
    verify = "--verify" in args
    paths = [a for a in args if not a.startswith("--")]
    from pitop_weather import audio
    sink = audio.sink_for(SINK_HINT)
    if not sink:
        sys.exit("no USB sound card found")
    mid = os.path.join(tempfile.gettempdir(), "level-phrase.mid")
    midi_phrase(mid, PHRASE)
    folder = os.path.dirname(os.path.abspath(paths[0]))
    sketches = {os.path.abspath(s.path): s for s in sonicpi.load_sketches(folder)}
    ref = sketches.get(os.path.abspath(os.path.join(folder, "01-keys.rb")))
    e = sonicpi.Engine("~/apps/sonic-pi-5.0.0", os.path.join(REPO, "tools", "trixie-run.sh"))
    e.start()
    while e.state == "starting":
        time.sleep(0.1)
    time.sleep(1.5)
    target, _ = measure(e, ref, sink, mid, ref.gain if verify else 1.0)
    print("reference %-24s %6.1f dB" % (ref.title, target), flush=True)
    worst = 0.0
    for p in paths:
        sk = sketches[os.path.abspath(p)]
        want = target + (GROOVE_OFFSET_DB if sk.category == "Grooves" else 0.0)
        level, err = measure(e, sk, sink, mid, sk.gain if verify else 1.0)
        if level is None:
            print("%-28s silent?! %s" % (os.path.basename(p), err), flush=True)
            continue
        if verify:
            worst = max(worst, abs(level - want))
            print("%-28s %6.1f dB  (%+.1f from target) %s" % (os.path.basename(p), level, level - want, err), flush=True)
        else:
            gain = max(0.3, min(6.0, 10 ** ((want - level) / 20)))
            write_gain(p, gain)
            print("%-28s %6.1f dB -> gain %.2f %s" % (os.path.basename(p), level, gain, err), flush=True)
    if verify:
        print("largest difference from target: %.1f dB" % worst)
    e.exit()


if __name__ == "__main__":
    main(sys.argv[1:])
