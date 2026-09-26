"""Sound-walk recorder: capture a clip, meter it, and label it with the weather.

Audio comes from `arecord` as raw 16-bit mono (through PipeWire, so any USB
mic works) and is written straight to a WAV. Each clip gets a JSON sidecar
with the time, the weather and the battery, so the folder is a diary.

    ~/soundwalks/2026-09-27/071204-light-rain-14c.wav
    ~/soundwalks/2026-09-27/071204-light-rain-14c.json
"""
from __future__ import annotations

import glob
import sys
from array import array
import json
import math
import os
import re
import shutil
import socket
import subprocess
import threading
import time
import wave
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional


SAMPLE_WIDTH = 2        # bytes, S16_LE
CHUNK_SECONDS = 0.1     # meter update rate
FLOOR_DB = -60.0


# ---- microphones ---------------------------------------------------------------

def find_mic() -> Optional[str]:
    """Name of the first capture device, or None if there is no microphone."""
    try:
        out = subprocess.run(["arecord", "-l"], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return parse_arecord_list(out)


def parse_arecord_list(out: str) -> Optional[str]:
    # card 3: Device [USB PnP Sound Device], device 0: USB Audio [USB Audio]
    m = re.search(r"^card \d+: [^\[]*\[([^\]]+)\]", out, re.M)
    return m.group(1).strip() if m else None


class ArecordSource:
    """Raw PCM from the default capture device (PipeWire picks the USB mic)."""

    def __init__(self, device: str, rate: int):
        self.proc = subprocess.Popen(
            ["arecord", "-q", "-D", device, "-f", "S16_LE", "-r", str(rate), "-c", "1", "-t", "raw"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def read(self, n: int) -> bytes:
        return self.proc.stdout.read(n)

    def close(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()


# ---- clips ------------------------------------------------------------------------

@dataclass
class Clip:
    wav: str
    meta: dict

    @property
    def when(self) -> datetime:
        return datetime.fromisoformat(self.meta["started"])

    @property
    def seconds(self) -> float:
        return float(self.meta.get("seconds", 0))

    @property
    def label(self) -> str:
        w = self.meta.get("weather") or {}
        if not w:
            return "no weather"
        return "%s %d°" % (w.get("conditions", "?"), round(w.get("temp", 0)))


def list_clips(folder: str) -> List[Clip]:
    """Every clip that has both its WAV and its label, newest first."""
    clips = []
    for js in glob.glob(os.path.join(folder, "*", "*.json")):
        wav = js[:-5] + ".wav"
        if not os.path.exists(wav):
            continue
        try:
            with open(js) as f:
                clips.append(Clip(wav, json.load(f)))
        except (OSError, ValueError):
            continue
    clips.sort(key=lambda c: c.meta.get("started", ""), reverse=True)
    return clips


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "clip"


def clip_basename(started: datetime, weather: Optional[dict]) -> str:
    name = started.strftime("%H%M%S")
    if weather:
        t = round(weather["temp"])
        name += "-%s-%s%dc" % (slug(weather["conditions"]), "m" if t < 0 else "", abs(t))
    return name


def db(peak: int) -> float:
    return FLOOR_DB if peak <= 0 else max(FLOOR_DB, 20 * math.log10(peak / 32768.0))


def free_minutes(folder: str, rate: int) -> Optional[int]:
    try:
        path = folder
        while not os.path.exists(path):
            path = os.path.dirname(path) or "/"
        return int(shutil.disk_usage(path).free / (rate * SAMPLE_WIDTH) / 60)
    except OSError:
        return None


# ---- the recorder ----------------------------------------------------------------

class Recorder:
    def __init__(self, folder: str, rate: int = 48000, max_seconds: float = 60,
                 source_factory: Optional[Callable[[], object]] = None, device: str = "default"):
        self.folder = os.path.expanduser(folder)
        self.rate = rate
        self.max_seconds = max_seconds
        self.source_factory = source_factory or (lambda: ArecordSource(device, rate))
        self.on_done: Callable[[Optional[Clip], str], None] = lambda clip, err: None
        self.recording = False
        self.elapsed = 0.0
        self.level_db = FLOOR_DB     # this chunk
        self.peak_db = FLOOR_DB      # loudest so far in this clip
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self, started: datetime, meta: dict):
        if self.recording:
            return
        self.recording = True
        self.elapsed, self.level_db, self.peak_db = 0.0, FLOOR_DB, FLOOR_DB
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(started, meta), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def wait(self, timeout: Optional[float] = None):
        if self._thread:
            self._thread.join(timeout)

    def _run(self, started: datetime, meta: dict):
        day = os.path.join(self.folder, started.strftime("%Y-%m-%d"))
        base = os.path.join(day, clip_basename(started, meta.get("weather")))
        n = 2
        stem = base
        while os.path.exists(base + ".wav") or os.path.exists(base + ".wav.part"):
            base = "%s-%d" % (stem, n)     # two clips in one second never overwrite
            n += 1
        part = base + ".wav.part"
        clip, err = None, ""
        frames = 0
        peak = 0
        src = None
        try:
            os.makedirs(day, exist_ok=True)
            src = self.source_factory()
            chunk = int(self.rate * CHUNK_SECONDS) * SAMPLE_WIDTH
            limit = int(self.max_seconds * self.rate)
            with wave.open(part, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(SAMPLE_WIDTH)
                wf.setframerate(self.rate)
                while not self._stop.is_set() and frames < limit:
                    data = src.read(min(chunk, (limit - frames) * SAMPLE_WIDTH))
                    if not data:
                        break       # the mic went away (or a test source ran dry)
                    data = data[:len(data) - len(data) % SAMPLE_WIDTH]
                    wf.writeframes(data)
                    frames += len(data) // SAMPLE_WIDTH
                    samples = array("h", data)
                    if sys.byteorder != "little":
                        samples.byteswap()
                    p = max(max(samples), -min(samples)) if samples else 0
                    peak = max(peak, p)
                    self.level_db, self.peak_db = db(p), db(peak)
                    self.elapsed = frames / self.rate
        except Exception as e:   # disk full, arecord missing...
            err = "%s: %s" % (type(e).__name__, e)
        finally:
            if src is not None:
                src.close()
        if not err and frames == 0:
            err = "No sound from the microphone"
        elif not err and frames < self.rate * 0.5:
            err = "Too short, not kept"
        if err:
            try:
                os.remove(part)
            except OSError:
                pass
        else:
            meta = dict(meta, started=started.isoformat(timespec="seconds"),
                        seconds=round(frames / self.rate, 2), sample_rate=self.rate,
                        peak_dbfs=round(db(peak), 1), clipped=peak >= 32767,
                        host=socket.gethostname())
            os.replace(part, base + ".wav")
            with open(base + ".json", "w") as f:
                json.dump(meta, f, indent=1)
            clip = Clip(base + ".wav", meta)
        self.recording = False
        self.level_db = FLOOR_DB
        self.on_done(clip, err)


class Player:
    """Plays one clip at a time through the default output (the speaker)."""

    def __init__(self):
        self._proc: Optional[subprocess.Popen] = None
        self.path: Optional[str] = None

    @property
    def busy(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def play(self, path: str):
        self.stop()
        self.path = path
        self._proc = subprocess.Popen(["aplay", "-q", path],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def stop(self):
        if self.busy:
            self._proc.terminate()
        self._proc = None
        self.path = None

    @property
    def playing(self) -> Optional[str]:
        return self.path if self.busy else None
