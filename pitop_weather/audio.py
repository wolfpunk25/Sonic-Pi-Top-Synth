"""Which PipeWire output things play on.

Outputs are named by role rather than by device, so settings survive the
USB card being plugged into a different port:

    "speaker"  - the pi-top's own speaker (the Pi's analogue output)
    "usb"      - a USB sound card (headphones / external speaker)
    "default"  - whatever PipeWire's default is
"""
from __future__ import annotations

import json
import subprocess
from typing import Dict, List, Optional

LABELS = {"speaker": "Speaker", "usb": "Headphones", "default": "Default"}


def _pw_dump() -> list:
    try:
        out = subprocess.run(["pw-dump"], capture_output=True, text=True, timeout=5).stdout
        return json.loads(out) if out.strip() else []
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


def sinks(dump: Optional[list] = None) -> Dict[str, str]:
    """{role: node.name} for the outputs that are present right now."""
    found = {}
    for o in dump if dump is not None else _pw_dump():
        p = o.get("info", {}).get("props", {}) if isinstance(o.get("info"), dict) else {}
        if p.get("media.class") != "Audio/Sink":
            continue
        name = p.get("node.name", "")
        if "usb" in name.lower() and "usb" not in found:
            found["usb"] = name
        elif ("platform" in name or "bcm2835" in name.lower() or "Built-in" in p.get("node.description", "")) \
                and "speaker" not in found:
            found["speaker"] = name
    return found


def roles_present(dump: Optional[list] = None) -> List[str]:
    s = sinks(dump)
    return [r for r in ("usb", "speaker") if r in s]


def sink_for(role: str, dump: Optional[list] = None) -> Optional[str]:
    """The node.name to target for a role, or None for PipeWire's default."""
    if role == "default":
        return None
    return sinks(dump).get(role)


def node_id(node_name: str, dump: Optional[list] = None) -> Optional[int]:
    for o in dump if dump is not None else _pw_dump():
        if o.get("type", "").endswith("Node") and \
                o.get("info", {}).get("props", {}).get("node.name") == node_name:
            return o["id"]
    return None


def move_stream(stream_name: str, role: str) -> bool:
    """Send an already-playing stream (e.g. "Sonic Pi") to an output.

    Setting target.object in PipeWire's metadata makes WirePlumber relink it,
    exactly as a volume-control app would; the default output is untouched."""
    dump = _pw_dump()
    nid = node_id(stream_name, dump)
    target = sink_for(role, dump)
    if nid is None or (role != "default" and target is None):
        return False
    try:
        subprocess.run(["pw-metadata", str(nid), "target.object", target or "-1"],
                       capture_output=True, timeout=5)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
