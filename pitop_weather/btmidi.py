"""Connect Bluetooth MIDI controllers automatically.

    python3 -m pitop_weather.btmidi          (run by btmidi-autoconnect.service)

Watches BlueZ over D-Bus for any device advertising the Bluetooth MIDI
service and connects to it. BlueZ's midi plugin then makes an ALSA MIDI port,
which Sonic Pi picks up by itself. No pairing is needed.

  * Scanning runs only while no MIDI controller is connected, and only for
    devices advertising MIDI - scanning while connected can add latency on
    the Pi's combined Wi-Fi/Bluetooth chip.
  * A device that keeps failing - or connects and then drops within 30 s,
    as a CircuitPython controller here does - is retried with a growing gap
    (5 s up to 2 min), so a misbehaving controller can't hog the radio.
  * The adapter is powered on at start and whenever it turns off.

Needs /etc/systemd/system/bluetooth.service.d/20-midi.conf (bluetoothd started
with the midi plugin); without it devices connect but no MIDI port appears.
"""
from __future__ import annotations

import configparser
import os
import sys
import time
from typing import Dict

MIDI_UUID = "03b80e5a-ede8-4b33-a751-6ce34ec4c700"
BLUEZ = "org.bluez"
ADAPTER = "org.bluez.Adapter1"
DEVICE = "org.bluez.Device1"
PROPS = "org.freedesktop.DBus.Properties"
OM = "org.freedesktop.DBus.ObjectManager"

MIN_BACKOFF, MAX_BACKOFF = 5.0, 120.0
STABLE_AFTER = 30.0       # a connection only counts as good once it has lasted this long


def log(msg: str):
    print(msg, flush=True)


class Backoff:
    """Per-device retry timing: fast at first, slower each time it fails."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.next_try: Dict[str, float] = {}
        self.gap: Dict[str, float] = {}

    def ready(self, key: str) -> bool:
        return self.clock() >= self.next_try.get(key, 0.0)

    def failed(self, key: str):
        g = min(MAX_BACKOFF, self.gap.get(key, MIN_BACKOFF / 2) * 2)
        self.gap[key] = g
        self.next_try[key] = self.clock() + g
        return g

    def attempted(self, key: str):
        # don't hammer while a connection attempt is still in flight
        self.next_try[key] = self.clock() + MIN_BACKOFF

    def succeeded(self, key: str):
        self.gap.pop(key, None)
        self.next_try.pop(key, None)


def is_midi(props) -> bool:
    return MIDI_UUID in [str(u).lower() for u in props.get("UUIDs", [])]


def ignored_names(path=os.path.expanduser("~/.config/pitop-weather.ini")):
    c = configparser.ConfigParser(inline_comment_prefixes=(";", "#"))
    c.read(path)
    raw = c.get("bluetooth_midi", "ignore", fallback="")
    return {n.strip().lower() for n in raw.split(",") if n.strip()}


class AutoConnect:
    def __init__(self):
        import dbus
        import dbus.mainloop.glib
        from gi.repository import GLib
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.dbus, self.GLib = dbus, GLib
        self.bus = dbus.SystemBus()
        self.om = dbus.Interface(self.bus.get_object(BLUEZ, "/"), OM)
        self.backoff = Backoff()
        self.connected_since = {}                    # path -> when it connected
        self.pending = set()
        self.ignore = ignored_names()
        self.adapter_path = None
        self.scanning = False

    # -- bluez helpers

    def objects(self):
        return self.om.GetManagedObjects()

    def find_adapter(self):
        for path, ifs in self.objects().items():
            if ADAPTER in ifs:
                return path
        return None

    def adapter(self, iface=ADAPTER):
        return self.dbus.Interface(self.bus.get_object(BLUEZ, self.adapter_path), iface)

    def midi_devices(self):
        for path, ifs in self.objects().items():
            d = ifs.get(DEVICE)
            if d and is_midi(d) and str(d.get("Name", "")).lower() not in self.ignore:
                yield str(path), d

    # -- the loop

    def ensure_powered(self):
        props = self.adapter(PROPS)
        if not props.Get(ADAPTER, "Powered"):
            log("adapter off - powering on")
            props.Set(ADAPTER, "Powered", self.dbus.Boolean(True))

    def set_scanning(self, on: bool):
        if on == self.scanning:
            return
        a = self.adapter()
        try:
            if on:
                a.SetDiscoveryFilter({"Transport": "le", "UUIDs": [MIDI_UUID], "DuplicateData": False})
                a.StartDiscovery()
            else:
                a.StopDiscovery()
            self.scanning = on
            log("scanning %s" % ("on" if on else "off (a controller is connected)"))
        except self.dbus.DBusException as e:
            # "InProgress"/"NotReady" are normal around adapter restarts
            log("discovery %s: %s" % ("start" if on else "stop", e.get_dbus_name()))
            self.scanning = on if "InProgress" in e.get_dbus_name() else self.scanning

    def connect(self, path, props):
        name = str(props.get("Name", path))
        if path in self.pending or not self.backoff.ready(path):
            return
        self.pending.add(path)
        self.backoff.attempted(path)
        log("connecting to %s" % name)
        dev = self.dbus.Interface(self.bus.get_object(BLUEZ, path), DEVICE)

        def ok():
            self.pending.discard(path)
            log("connected: %s" % name)

        def err(e):
            self.pending.discard(path)
            gap = self.backoff.failed(path)
            log("could not connect to %s (%s); next try in %.0f s" % (name, e.get_dbus_name(), gap))
        dev.Connect(reply_handler=ok, error_handler=err, timeout=30)

    def tick(self):
        try:
            if self.adapter_path is None:
                self.adapter_path = self.find_adapter()
                if self.adapter_path is None:
                    return True                      # no adapter yet (bluetoothd restarting)
            self.ensure_powered()
            devices = list(self.midi_devices())
            connected = [p for p, d in devices if d.get("Connected")]
            now = time.monotonic()
            for p, d in devices:
                if p in connected:
                    since = self.connected_since.setdefault(p, now)
                    if now - since >= STABLE_AFTER:
                        self.backoff.succeeded(p)
                elif p in self.connected_since:
                    lasted = now - self.connected_since.pop(p)
                    if lasted < STABLE_AFTER:            # connected, then dropped: treat as a failure
                        gap = self.backoff.failed(p)
                        log("%s dropped after %.0f s; next try in %.0f s" % (d.get("Name", p), lasted, gap))
                    else:
                        log("%s disconnected" % d.get("Name", p))
            self.set_scanning(not connected)
            for p, d in devices:
                if not d.get("Connected"):
                    self.connect(p, d)
        except self.dbus.DBusException as e:
            log("bluez: %s" % e.get_dbus_name())
            self.adapter_path, self.scanning = None, False   # bluetoothd restarted: start over
        return True

    def run(self):
        log("Bluetooth MIDI auto-connect: watching for %s" % MIDI_UUID)
        if self.ignore:
            log("ignoring: %s" % ", ".join(sorted(self.ignore)))
        # react at once to new devices and disconnects, and check every 3 s regardless
        self.bus.add_signal_receiver(lambda *a: self.tick(), dbus_interface=OM, signal_name="InterfacesAdded")
        self.bus.add_signal_receiver(lambda *a, **k: self.tick(), dbus_interface=PROPS,
                                     signal_name="PropertiesChanged", arg0=DEVICE)
        self.GLib.timeout_add_seconds(3, self.tick)
        self.tick()
        self.GLib.MainLoop().run()


def main():
    while True:
        try:
            AutoConnect().run()
        except Exception as e:                       # D-Bus not ready at boot, etc.
            log("restarting after error: %s" % e)
            time.sleep(5)


if __name__ == "__main__":
    sys.exit(main())
