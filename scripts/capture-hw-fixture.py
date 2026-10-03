#!/usr/bin/env python3
"""Snapshot the read-only sysfs subset plugins rely on into a fixture tree.

Usage: capture-hw-fixture.py --out DIR [--root /]

Output mirrors sysfs paths under DIR/sys/.... Symlinks are resolved into real
directories (hwmonN, card0, BAT0); no symlinks are written. Deterministic,
read-only, skips unreadable files silently.
"""
import argparse
import fnmatch
import os
import re
import sys

HWMON_PATTERNS = [
    "name", "*_label", "*_input", "fan*_min", "fan*_max", "fan*_target",
    "pwm*", "pwm*_enable", "power*_input",
]
PSY_PATTERNS = [
    "type", "scope", "status", "capacity", "charge_control_*_threshold",
    "charge_behaviour", "energy_*", "charge_*", "power_now", "current_now",
    "voltage_now", "cycle_count", "online",
]
DRM_FILES = ["vendor", "device", "power/runtime_status"]
MODULE_FILES = ["/sys/module/macsmc_hwmon/parameters/fan_control"]

# Hard exclusions: never read, whatever the patterns say. Reading typec
# identity/* Oopses some kernels.
EXCLUDED_NAMES = {"identity", "serial_number", "serial", "uevent"}
EXCLUDED_PARTS = {"typec", "identity"}

MAC_RE = re.compile(r"\b[0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5}\b")
REDACTED_MAC = "00:00:00:00:00:00"
MAX_BYTES = 4096


def excluded(path):
    parts = set(path.replace("\\", "/").split("/"))
    return bool(parts & EXCLUDED_PARTS) or os.path.basename(path) in EXCLUDED_NAMES


def read_text(path):
    if excluded(path):
        return None
    try:
        with open(path, "rb") as fh:
            raw = fh.read(MAX_BYTES)
    except OSError:
        return None
    text = raw.decode("utf-8", "replace")
    return MAC_RE.sub(REDACTED_MAC, text)


def write(out, rel, text):
    dest = os.path.join(out, rel.lstrip("/"))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(text)


def matches(name, patterns):
    return any(fnmatch.fnmatchcase(name, p) for p in patterns)


def list_dir(path):
    try:
        return sorted(os.listdir(path))
    except OSError:
        return []


def capture_dir(root, out, cls, patterns, dirname_ok=lambda n: True):
    base = os.path.join(root, "sys/class", cls)
    for entry in list_dir(base):
        if not dirname_ok(entry) or excluded(entry):
            continue
        src = os.path.join(base, entry)
        for name in list_dir(src):
            if not matches(name, patterns) or excluded(name):
                continue
            path = os.path.join(src, name)
            if os.path.isdir(path):
                continue
            text = read_text(path)
            if text is not None:
                write(out, f"sys/class/{cls}/{entry}/{name}", text)


def capture_drm(root, out):
    base = os.path.join(root, "sys/class/drm")
    for entry in list_dir(base):
        if not re.fullmatch(r"card\d+", entry):
            continue
        dev = os.path.join(base, entry, "device")
        for rel in DRM_FILES:
            text = read_text(os.path.join(dev, rel))
            if text is not None:
                write(out, f"sys/class/drm/{entry}/device/{rel}", text)
        try:
            drv = os.path.basename(os.readlink(os.path.join(dev, "driver")))
        except OSError:
            continue
        write(out, f"sys/class/drm/{entry}/device/driver", drv + "\n")


def capture(root, out):
    capture_dir(root, out, "hwmon", HWMON_PATTERNS)
    capture_dir(root, out, "power_supply", PSY_PATTERNS)
    capture_drm(root, out)
    for mod in MODULE_FILES:
        text = read_text(os.path.join(root, mod.lstrip("/")))
        if text is not None:
            write(out, mod, text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--root", default="/")
    args = ap.parse_args(argv)
    capture(args.root, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
