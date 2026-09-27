"""Drive Sonic Pi 5 headless, and the folder of sketches it plays.

Sonic Pi's arm64 AppImage needs glibc 2.38 and the pi-top runs Bookworm
(2.36), so the daemon runs inside a Debian 13 chroot (tools/trixie-run.sh)
while this client stays on the host. The protocol, from Sonic Pi's
daemon.rb and spider-server.rb:

  * the daemon prints "daemon gui-listen gui-send scsynth osc-cues token"
  * /daemon/keep-alive <token> to the daemon port at least every 3 s, or it
    kills everything (so a crashed app never leaves Sonic Pi running)
  * /run-code <token> <code> and /stop-all-jobs <token> to gui-send
  * the spider server talks back to gui-listen; /spider/ready arrives ~3 s
    after boot and code sent before it is silently dropped
"""
from __future__ import annotations

import glob
import os
import re
import shutil
import socket
import struct
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

from . import audio

STREAM_NAME = "Sonic Pi"        # the PipeWire node SuperSonic creates
HERE = os.path.dirname(os.path.abspath(__file__))
STARTER_SKETCHES = os.path.join(os.path.dirname(HERE), "sketches")


# ---- OSC -------------------------------------------------------------------------

def _pad(b: bytes) -> bytes:
    return b + b"\0" * (4 - len(b) % 4)


def osc(address: str, *args) -> bytes:
    tags, data = ",", b""
    for a in args:
        if isinstance(a, int):
            tags += "i"
            data += struct.pack(">i", a)
        elif isinstance(a, float):
            tags += "f"
            data += struct.pack(">f", a)
        else:
            tags += "s"
            data += _pad(str(a).encode("utf-8"))
    return _pad(address.encode()) + _pad(tags.encode()) + data


def parse_osc(data: bytes):
    """(address, [args]) for the int/float/string/blob types Sonic Pi sends."""
    def read_str(i):
        j = data.index(b"\0", i)
        return data[i:j].decode("utf-8", "replace"), (j // 4 + 1) * 4
    try:
        addr, i = read_str(0)
        if i >= len(data) or data[i:i + 1] != b",":
            return addr, []
        tags, i = read_str(i)
        args = []
        for t in tags[1:]:
            if t == "i":
                args.append(struct.unpack(">i", data[i:i + 4])[0]); i += 4
            elif t == "f":
                args.append(struct.unpack(">f", data[i:i + 4])[0]); i += 4
            elif t == "d":
                args.append(struct.unpack(">d", data[i:i + 8])[0]); i += 8
            elif t == "h":
                args.append(struct.unpack(">q", data[i:i + 8])[0]); i += 8
            elif t == "s":
                v, i = read_str(i); args.append(v)
            elif t == "b":
                n = struct.unpack(">i", data[i:i + 4])[0]; i += 4 + ((n + 3) // 4) * 4
                args.append(None)
            elif t in "TF":
                args.append(t == "T")
        return addr, args
    except (ValueError, struct.error):
        return "", []


def short_error(text: str) -> str:
    """Sonic Pi's errors, cut down to fit 128 pixels. Never empty: some
    messages start with a bare "Runtime Error" line and say what went wrong
    further down, so look through all of it."""
    clean = re.sub(r"<[^>]+>", "", text or "")
    lines = [l.strip() for l in clean.splitlines() if l.strip()]
    m = re.search(r"doesn't know a function called `([^`]+)`", clean)
    if m:
        return "Unknown: " + m.group(1)
    m = re.search(r"You attempted to use: `?(\w+)", clean)
    if m:
        return "Reserved name: " + m.group(1)
    if "couldn't read your code" in clean or (lines and lines[0].startswith("Syntax Error")):
        return "Syntax error"
    m = re.search(r"\b([A-Z]\w*Error): (.+)", clean)
    if m:
        return ("%s: %s" % (m.group(1), m.group(2)))[:80]
    for l in lines:
        t = re.sub(r"^(Runtime Error|Error)[:\s]*", "", l).replace("Sonic Pi ", "").strip()
        if t and not t.startswith("buffer eval"):
            return t[:80]
    return "Error (see Sonic Pi log)"


def port_name(port: str) -> str:
    """ALSA/Sonic Pi port id -> a readable name:
    "c_major_seven_c_major_seven_out_32_0" -> "C Major Seven"
    "lydian7_lydian7_bluetooth_132_0"      -> "Lydian7 (BT)"   (BlueZ's port)"""
    n = re.sub(r"_(out|in)?_?\d+_\d+$", "", port)
    words = n.split("_")
    bt = words[-1:] == ["bluetooth"]
    if bt:
        words = words[:-1]
    for size in range(len(words) // 2, 0, -1):          # "x_y_x_y" -> "x_y"
        if words[:size] == words[size:2 * size]:
            words = words[:size] + words[2 * size:]
            break
    name = " ".join(w if w[:1].isdigit() else w.capitalize() for w in words)
    return name + (" (BT)" if bt else "")


def parse_ports(args) -> List[str]:
    """/midi/in-ports sends one string, a line per port: "<enabled>\t<name>".
    Returns the enabled ports, leaving out ALSA's built-in Midi Through."""
    out = []
    for arg in args:
        if not isinstance(arg, str):
            continue
        for line in arg.splitlines():
            flag, _, name = line.partition("\t")
            if not name:
                flag, name = "1", line
            if flag.strip() == "1" and name.strip() and "through" not in name.lower():
                out.append(name.strip())
    return out


# ---- sketches ------------------------------------------------------------------

CATEGORY_ORDER = ["Keys", "Sequencers", "Grooves", "Ambient"]


@dataclass
class Sketch:
    path: str
    title: str
    category: str = "Other"
    gain: float = 1.0             # "# gain: 1.4" - set by tools/level_check.py so sketches match
    keys: str = ""                # "# keys: last" - add the last-played Keys sketch as the instrument

    def code(self) -> str:
        with open(self.path, encoding="utf-8") as f:
            return f.read()


def load_sketches(folder: str) -> List[Sketch]:
    """Every .rb in the folder, in filename order. The title is the first
    comment line ("# Keys - Prophet synth") up to a dash, else the filename;
    a "# category: Ambient" line in the first few lines files it."""
    out = []
    for path in sorted(glob.glob(os.path.join(folder, "*.rb"))):
        title = re.sub(r"^\d+[-_ ]*", "", os.path.splitext(os.path.basename(path))[0]).replace("-", " ")
        category = "Other"
        try:
            with open(path, encoding="utf-8") as f:
                head = [f.readline().strip() for _ in range(8)]
        except OSError:
            continue
        if head[0].startswith("#"):
            title = re.split(r"\s+[-–—]\s+", head[0].lstrip("# ").strip())[0] or title
        gain, keys = 1.0, ""
        for line in head:
            m = re.match(r"#\s*(category|gain|keys)\s*:\s*(.+)", line, re.I)
            if not m:
                continue
            key, val = m.group(1).lower(), m.group(2).strip()
            if key == "category":
                category = val.title()
            elif key == "gain":
                try:
                    gain = max(0.05, min(8.0, float(val)))
                except ValueError:
                    pass
            else:
                keys = val.lower()
        out.append(Sketch(path, title, category, gain, keys))
    return out


def wrap_gain(code: str, gain: float) -> str:
    """Put a sketch inside a level effect so its loudness matches the others.
    Everything it starts - live_loops included - plays through the effect."""
    if abs(gain - 1.0) < 0.005:
        return code
    return "with_fx :level, amp: %.2f do\n%s\nend\n" % (gain, code.rstrip("\n"))


def build_code(sketch: Sketch, weather, keys_sketch: Optional[Sketch] = None) -> str:
    """The code sent to Sonic Pi: weather, the sketch at its level, and, for a
    "# keys: last" sketch, the chosen Keys sketch at its own level alongside."""
    code = weather_header(weather) + wrap_gain(sketch.code(), sketch.gain)
    if sketch.keys == "last" and keys_sketch is not None:
        code += "\n" + wrap_gain(keys_sketch.code(), keys_sketch.gain)
    return code


def categories(sketches: List[Sketch]) -> List[tuple]:
    """[(name, [sketches...])] with the usual four first, then any others A-Z."""
    groups = {}
    for s in sketches:
        groups.setdefault(s.category, []).append(s)
    known = [c for c in CATEGORY_ORDER if c in groups]
    return [(c, groups[c]) for c in known + sorted(c for c in groups if c not in CATEGORY_ORDER)]


def install_starters(folder: str) -> bool:
    """Copy the bundled sketches into an empty or missing folder."""
    if os.path.isdir(folder) and glob.glob(os.path.join(folder, "*.rb")):
        return False
    os.makedirs(folder, exist_ok=True)
    for src in glob.glob(os.path.join(STARTER_SKETCHES, "*.rb")):
        shutil.copy(src, folder)
    return True


def weather_header(w) -> str:
    """One line of `set`s so sketches can read the weather with get(:wx_temp).
    Kept to one line so error line numbers are off by exactly one."""
    if w is None:
        return "set :wx_known, false\n"
    return ("set :wx_known, true; set :wx_temp, %.1f; set :wx_rain, %.2f; set :wx_wind, %.1f; "
            "set :wx_code, %d; set :wx_day, %s\n" % (w.temp, w.precip_now, w.wind, w.code,
                                                     "true" if w.is_day else "false"))


# ---- the engine ------------------------------------------------------------------

class Engine:
    """States: off -> starting -> ready -> (stopped by exit) off; or error."""

    def __init__(self, appimage_dir: str, runner: str, buffer_size: int = 128,
                 output: str = "usb"):
        self.appimage_dir = os.path.expanduser(appimage_dir)
        self.runner = runner
        self.buffer_size = buffer_size
        self.output = output
        self.state = "off"
        self.error = ""               # last Sonic Pi error, for the screen
        self.error_at = 0.0
        self.midi_in: List[str] = []
        self.on_change: Callable[[], None] = lambda: None
        self._proc: Optional[subprocess.Popen] = None
        self._ready = threading.Event()
        self._alive = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # -- lifecycle

    def command(self) -> List[str]:
        h = self.appimage_dir
        return [self.runner, "env",
                "PATH=%s/usr/ruby/bin:/usr/bin:/bin" % h,
                "LD_LIBRARY_PATH=%s/usr/lib:%s/usr/ruby/lib" % (h, h),
                "ruby", "%s/usr/share/sonic-pi/app/server/ruby/bin/daemon.rb" % h,
                "--audio-buffer-size", str(self.buffer_size)]

    def start(self):
        if self.state in ("starting", "ready"):
            return
        self.state, self.error = "starting", ""
        self._ready.clear()
        self.on_change()
        threading.Thread(target=self._boot, daemon=True).start()

    def _write_audio_settings(self):
        path = os.path.expanduser("~/.sonic-pi/config/v5-audio-settings.toml")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("# written by pitop-weather; PIPEWIRE_QUANTUM for SuperSonic\n"
                    "linux_pipewire_buffsize = %d\nlinux_pipewire_samplerate = 48000\n" % self.buffer_size)

    def _boot(self):
        try:
            self._write_audio_settings()
            self._proc = subprocess.Popen(self.command(), stdout=subprocess.PIPE,
                                          stderr=subprocess.STDOUT, text=True)
            while True:
                line = self._proc.stdout.readline()
                if not line:
                    raise RuntimeError("Sonic Pi exited while starting")
                parts = line.split()
                if len(parts) == 6 and all(p.lstrip("-").isdigit() for p in parts):
                    break
            (self.daemon_port, listen_port, self.send_port,
             _scsynth, _cues, self.token) = map(int, parts)
            # stand in for the GUI: spider errors if nobody listens here
            self.gui = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.gui.bind(("127.0.0.1", listen_port))
            self._alive = True
            threading.Thread(target=self._keep_alive, daemon=True).start()
            threading.Thread(target=self._listen, daemon=True).start()
            threading.Thread(target=self._drain, daemon=True).start()
            if not self._ready.wait(60):
                raise RuntimeError("Sonic Pi never said it was ready")
            self.state = "ready"
            self.set_output(self.output)
        except Exception as e:
            self.state, self.error = "error", str(e)
            self.error_at = time.time()
            self._kill()
        self.on_change()

    def _keep_alive(self):
        while self._alive:
            try:
                self.sock.sendto(osc("/daemon/keep-alive", self.token), ("127.0.0.1", self.daemon_port))
            except OSError:
                pass
            time.sleep(1)

    def _drain(self):
        for _ in self._proc.stdout:
            pass
        # the daemon has gone (crash, or its own kill switch)
        if self._alive:
            self._alive = False
            self.state, self.error = "error", "Sonic Pi stopped unexpectedly"
            self.error_at = time.time()
            self.on_change()

    def _listen(self):
        while self._alive:
            try:
                data, _ = self.gui.recvfrom(65536)
            except OSError:
                return
            addr, args = parse_osc(data)
            if addr == "/spider/ready":
                self._ready.set()
            elif addr in ("/error", "/syntax_error"):
                text = next((a for a in args if isinstance(a, str) and a.strip()), "error")
                self.error = short_error(text)
                self.error_at = time.time()
                self.on_change()
            elif addr == "/midi/in-ports":
                self.midi_in = parse_ports(args)
                self.on_change()

    def exit(self):
        if self._proc is None:
            return
        try:
            self.sock.sendto(osc("/daemon/exit", self.token), ("127.0.0.1", self.daemon_port))
        except (OSError, AttributeError):
            pass
        self._alive = False
        try:
            self._proc.wait(10)
        except subprocess.TimeoutExpired:
            self._kill()
        self._proc = None
        self.state = "off"

    def _kill(self):
        self._alive = False
        if self._proc and self._proc.poll() is None:
            self._proc.kill()

    # -- playing

    def run(self, code: str):
        if self.state != "ready":
            return False
        self.error = ""
        self.sock.sendto(osc("/run-code", self.token, code), ("127.0.0.1", self.send_port))
        return True

    def stop_all(self):
        if self.state == "ready":
            self.sock.sendto(osc("/stop-all-jobs", self.token), ("127.0.0.1", self.send_port))

    def set_output(self, role: str) -> bool:
        self.output = role
        return self.state == "ready" and audio.move_stream(STREAM_NAME, role)

    @property
    def midi_name(self) -> str:
        """Every connected controller, e.g. "C Major Seven + Lydian7 (BT)"."""
        return " + ".join(port_name(p) for p in self.midi_in)
