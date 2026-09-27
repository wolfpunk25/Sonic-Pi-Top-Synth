"""The KeebDeck Basic (a QWERTY USB keyboard) as a MIDI controller.

The keyboard is grabbed exclusively, so key presses don't also type on the
Pi, and turned into MIDI on a virtual ALSA port called "KeebDeck" that Sonic
Pi picks up like any other controller. The port exists only while the
keyboard is plugged in.

Layout ("musical typing", as in GarageBand and Ableton):

    black keys   W E   T Y U   O P                (C# D#  F# G# A#  C# D#)
    white keys  A S D F G H J K L ; '             (C D E F G A B  C D E F)
    octave below  Z X C V B N M , . /             (white keys only)

    1-8        jump to that octave (4 = middle C)
    <- ->      octave down / up
    up down    transpose a semitone up / down
    F1 (□)     stop the music
    F2 (△)     previous sketch in the category     \\  handled by the app,
    F3 (×)     next sketch in the category          >  the same actions as
    F4 (○)     headphones / speaker                /   its buttons
    F5 (☘)     sustain: notes hold while it's down
    F6 (◇)     panic: all notes off
    Esc        let go of the keyboard (it types normally) / take it back

The mapping (KeyMapper) is pure and tested on any machine; the device and
MIDI parts (KeebDeck) need evdev and rtmidi, and only run on the Pi.
"""
from __future__ import annotations

import glob
import threading
import time
from typing import Callable, List, Optional, Tuple

# Linux input event codes (linux/input-event-codes.h)
KEY_ESC = 1
KEY_1, KEY_8 = 2, 9
KEY_W, KEY_E, KEY_T, KEY_Y, KEY_U, KEY_O, KEY_P = 17, 18, 20, 21, 22, 24, 25
KEY_A, KEY_S, KEY_D, KEY_F, KEY_G, KEY_H, KEY_J, KEY_K, KEY_L = 30, 31, 32, 33, 34, 35, 36, 37, 38
KEY_SEMICOLON, KEY_APOSTROPHE = 39, 40
KEY_Z, KEY_X, KEY_C, KEY_V, KEY_B, KEY_N, KEY_M = 44, 45, 46, 47, 48, 49, 50
KEY_COMMA, KEY_DOT, KEY_SLASH = 51, 52, 53
KEY_F1, KEY_F2, KEY_F3, KEY_F4, KEY_F5, KEY_F6 = 59, 60, 61, 62, 63, 64
KEY_UP, KEY_LEFT, KEY_RIGHT, KEY_DOWN = 103, 105, 106, 108

# semitones above the octave's C
NOTE_KEYS = {
    KEY_A: 0, KEY_W: 1, KEY_S: 2, KEY_E: 3, KEY_D: 4, KEY_F: 5, KEY_T: 6, KEY_G: 7,
    KEY_Y: 8, KEY_H: 9, KEY_U: 10, KEY_J: 11, KEY_K: 12, KEY_O: 13, KEY_L: 14,
    KEY_P: 15, KEY_SEMICOLON: 16, KEY_APOSTROPHE: 17,
    # the row below: white keys from the octave below, running on into C D E
    KEY_Z: -12, KEY_X: -10, KEY_C: -8, KEY_V: -7, KEY_B: -5, KEY_N: -3, KEY_M: -1,
    KEY_COMMA: 0, KEY_DOT: 2, KEY_SLASH: 4,
}

ACTIONS = {KEY_F1: "stop", KEY_F2: "prev", KEY_F3: "next", KEY_F4: "output"}

Event = Tuple[str, object]     # ("midi", bytes) or ("action", name) or ("grab", bool)


class KeyMapper:
    """Key presses in, MIDI bytes and app actions out. No I/O."""

    def __init__(self, octave: int = 4, channel: int = 1, velocity: int = 100):
        self.octave = octave
        self.transpose = 0
        self.channel = max(1, min(16, channel)) - 1
        self.velocity = velocity
        self.held = {}                 # key code -> note it started
        self.sustain = False
        self.sustained = set()         # notes whose note-off waits for the pedal
        self.grabbed = True

    def note_for(self, code: int) -> Optional[int]:
        if code not in NOTE_KEYS:
            return None
        n = 12 * (self.octave + 1) + self.transpose + NOTE_KEYS[code]
        return n if 0 <= n <= 127 else None

    def on(self, n):
        return ("midi", bytes([0x90 | self.channel, n, self.velocity]))

    def off(self, n):
        return ("midi", bytes([0x80 | self.channel, n, 0]))

    def all_off(self) -> List[Event]:
        out = [self.off(n) for n in sorted(set(self.held.values()) | self.sustained)]
        out.append(("midi", bytes([0xB0 | self.channel, 64, 0])))     # sustain pedal up
        out.append(("midi", bytes([0xB0 | self.channel, 123, 0])))    # all notes off
        self.held.clear()
        self.sustained.clear()
        return out

    def handle(self, code: int, value: int) -> List[Event]:
        """value: 1 = press, 0 = release, 2 = autorepeat (ignored)."""
        if value == 2:
            return []
        down = value == 1
        if code == KEY_ESC:
            if not down:
                return []
            self.grabbed = not self.grabbed
            return ([] if self.grabbed else self.all_off()) + [("grab", self.grabbed)]
        if not self.grabbed:
            return []
        if code in NOTE_KEYS:
            if down:
                if code in self.held:
                    return []
                n = self.note_for(code)
                if n is None:
                    return []
                self.held[code] = n
                self.sustained.discard(n)
                return [self.on(n)]
            n = self.held.pop(code, None)
            if n is None:
                return []
            if self.sustain:
                self.sustained.add(n)
                return []
            return [self.off(n)]
        if not down:
            if code == KEY_F5:
                self.sustain = False
                out = [self.off(n) for n in sorted(self.sustained) if n not in self.held.values()]
                self.sustained.clear()
                return out + [("midi", bytes([0xB0 | self.channel, 64, 0]))]
            return []
        if KEY_1 <= code <= KEY_8:
            self.octave = code - KEY_1 + 1
        elif code == KEY_LEFT:
            self.octave = max(0, self.octave - 1)
        elif code == KEY_RIGHT:
            self.octave = min(8, self.octave + 1)
        elif code == KEY_UP:
            self.transpose = min(12, self.transpose + 1)
        elif code == KEY_DOWN:
            self.transpose = max(-12, self.transpose - 1)
        elif code == KEY_F5:
            self.sustain = True
            return [("midi", bytes([0xB0 | self.channel, 64, 127]))]
        elif code == KEY_F6:
            return self.all_off()
        elif code in ACTIONS:
            return [("action", ACTIONS[code])]
        return []


class KeebDeck:
    """Finds the keyboard, grabs it, and runs KeyMapper on its events.
    Unplugging is fine: it closes the MIDI port and waits for it to return."""

    def __init__(self, match: str = "KeebDeck", on_action: Callable[[str], None] = lambda a: None,
                 on_status: Callable[[str], None] = lambda s: None, **mapper_opts):
        self.match = match
        self.on_action = on_action
        self.on_status = on_status
        self.mapper_opts = mapper_opts
        self.connected = False
        self.running = True
        self.status = ""

    def find(self) -> Optional[str]:
        paths = glob.glob("/dev/input/by-id/*%s*event-kbd" % self.match)
        return paths[0] if paths else None

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _set_status(self, s: str):
        self.status = s
        self.on_status(s)

    def _run(self):
        try:
            import evdev
            import rtmidi
        except ImportError as e:
            self._set_status("KeebDeck needs python3-evdev and python3-rtmidi (%s)" % e)
            return
        while self.running:
            path = self.find()
            if not path:
                time.sleep(2)
                continue
            mapper = KeyMapper(**self.mapper_opts)
            midi = rtmidi.MidiOut(rtmidi.API_LINUX_ALSA, name="KeebDeck")
            midi.open_virtual_port("KeebDeck")
            dev = None
            try:
                dev = evdev.InputDevice(path)
                dev.grab()
                self.connected = True
                self._set_status("KeebDeck: playing")
                for ev in dev.read_loop():
                    if not self.running:
                        break
                    if ev.type != evdev.ecodes.EV_KEY:
                        continue
                    for kind, payload in mapper.handle(ev.code, ev.value):
                        if kind == "midi":
                            midi.send_message(list(payload))
                        elif kind == "action":
                            self.on_action(payload)
                        elif kind == "grab":
                            (dev.grab if payload else dev.ungrab)()
                            self._set_status("KeebDeck: playing" if payload else "KeebDeck: typing")
            except OSError:
                pass                                   # unplugged
            finally:
                self.connected = False
                for kind, payload in mapper.all_off():
                    try:
                        midi.send_message(list(payload))
                    except Exception:
                        pass
                try:
                    midi.close_port()
                    del midi
                except Exception:
                    pass
                if dev is not None:
                    try:
                        dev.close()
                    except Exception:
                        pass
                self._set_status("")
            time.sleep(1)

    def stop(self):
        self.running = False
