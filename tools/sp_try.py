#!/usr/bin/env python3
"""Boot Sonic Pi's daemon headless, send it code, and keep it alive.

    python3 sp_try.py DAEMON_CMD...          # boots, plays a test, stops
    python3 sp_try.py --hold DAEMON_CMD...   # boots, then reads code from stdin

The daemon prints "daemon gui-listen gui-send scsynth osc-cues token" on
one line of stdout, wants /daemon/keep-alive <token> at least every 3 s,
and runs code sent as /run-code <token> <code> to the gui-send port.
"""
import socket
import struct
import subprocess
import sys
import threading
import time


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


class SonicPi:
    def __init__(self, cmd):
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        t0 = time.time()
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("daemon exited before printing its ports")
            parts = line.split()
            if len(parts) == 6 and all(p.lstrip("-").isdigit() for p in parts):
                break
            print("daemon:", line.rstrip(), flush=True)
        (self.daemon_port, self.listen_port, self.send_port,
         self.scsynth_port, self.cue_port, self.token) = map(int, parts)
        print("ports after %.1fs: daemon %d, send %d, token ok" % (time.time() - t0, self.daemon_port, self.send_port))
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # stand in for the GUI: the spider server sends it logs and errors, and
        # exits if nothing is listening on this port
        self.gui = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.gui.bind(("127.0.0.1", self.listen_port))
        self.alive = True
        self.seen, self.t0 = {}, t0
        self.ready = threading.Event()   # set by /spider/ready (~3 s after boot)
        threading.Thread(target=self._listen, daemon=True).start()
        threading.Thread(target=self._keep_alive, daemon=True).start()
        threading.Thread(target=self._drain, daemon=True).start()

    def _keep_alive(self):
        while self.alive:
            self.sock.sendto(osc("/daemon/keep-alive", self.token), ("127.0.0.1", self.daemon_port))
            time.sleep(1)

    def _listen(self):
        while self.alive:
            try:
                data, _ = self.gui.recvfrom(65536)
            except OSError:
                return
            addr = data.split(b"\0", 1)[0].decode(errors="replace")
            if addr == "/spider/ready":
                self.ready.set()
            if addr not in self.seen:
                self.seen[addr] = time.time()
                print("gui-port: first %s at +%.1fs" % (addr, time.time() - self.t0), flush=True)
            if addr in ("/log/info", "/log/multi_message", "/error", "/syntax_error", "/runs/all-completed"):
                text = b" ".join(t for t in data.split(b"\0") if t and not t.startswith(b",")).decode(errors="replace")
                print("spider:", text[:300], flush=True)

    def _drain(self):
        for line in self.proc.stdout:
            print("daemon:", line.rstrip(), flush=True)

    def run(self, code: str):
        # code sent before the spider server is up is silently dropped
        if not self.ready.wait(60):
            raise RuntimeError("Sonic Pi never said it was ready")
        self.sock.sendto(osc("/run-code", self.token, code), ("127.0.0.1", self.send_port))

    def stop_all(self):
        self.sock.sendto(osc("/stop-all-jobs", self.token), ("127.0.0.1", self.send_port))

    def exit(self):
        self.sock.sendto(osc("/daemon/exit", self.token), ("127.0.0.1", self.daemon_port))
        self.alive = False
        try:
            self.proc.wait(15)
        except subprocess.TimeoutExpired:
            self.proc.kill()


if __name__ == "__main__":
    hold = sys.argv[1] == "--hold"
    sp = SonicPi(sys.argv[2:] if hold else sys.argv[1:])
    if hold:
        for line in sys.stdin:
            line = line.strip()
            if line == "stop":
                sp.stop_all()
            elif line == "exit":
                break
            elif line.startswith("wait "):
                time.sleep(float(line[5:]))
            elif line:
                sp.run(line.replace("\\n", "\n"))
    sp.exit()
