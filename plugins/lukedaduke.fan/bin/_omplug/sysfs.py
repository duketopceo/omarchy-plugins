"""Hardware readers over sysfs, parameterised by root (KTD5).

Every reader takes root ("/" on a live machine, a fixture tree in tests) and
probes by file and driver presence, never by architecture or DMI. hwmon
devices are resolved by name plus sensor label, never by hwmonN index, and
same-named devices stay distinct. Absent hardware yields empty results.

USB Type-C partner/cable identity attributes (identity/* and type) are never
read: on some kernels they dereference a borrowed pointer and Oops.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

ATTR_MAX = 4096
_SENSOR_RE = re.compile(r"^(temp|fan|in|curr|power|energy|humidity|pwm)(\d+)_input$")
_CARD_RE = re.compile(r"^card(\d+)$")
_CONNECTOR_RE = re.compile(r"^card(\d+)-(.+)$")


def _sys(root: "str | os.PathLike[str]", *parts: str) -> Path:
    return Path(root).joinpath("sys", *parts)


def _forbidden(path: Path) -> bool:
    parts = path.parts
    for i, part in enumerate(parts):
        if part.endswith("-partner") or part.endswith("-cable"):
            rest = parts[i + 1:]
            if "identity" in rest or rest == ("type",):
                return True
    return False


def read_attr(path: "str | os.PathLike[str]", limit: int = ATTR_MAX) -> str | None:
    """Stripped text of one sysfs attribute, bounded; None when unreadable."""
    p = Path(path)
    if _forbidden(p):
        return None
    try:
        if _forbidden(Path(os.path.realpath(p))):
            return None
        with open(p, "rb") as fh:
            raw = fh.read(limit + 1)
    except OSError:
        return None
    if len(raw) > limit:
        return None
    return raw.decode(errors="replace").strip()


def read_int(path: "str | os.PathLike[str]") -> int | None:
    raw = read_attr(path)
    try:
        return int(raw) if raw is not None else None
    except ValueError:
        return None


def _link_name(path: Path) -> str | None:
    """Basename of a sysfs link (e.g. device/driver).

    Fixture trees store such links as plain files holding the target name,
    so a regular file is read instead.
    """
    try:
        return Path(os.readlink(path)).name or None
    except OSError:
        pass
    if path.is_file():
        return read_attr(path) or None
    return None


def _sorted_dirs(base: Path) -> list[Path]:
    try:
        return sorted((e for e in base.iterdir() if e.is_dir()), key=lambda e: e.name)
    except OSError:
        return []


# --- hwmon ------------------------------------------------------------------

@dataclass
class Sensor:
    kind: str  # temp | fan | in | curr | power | energy | humidity | pwm
    key: str  # e.g. temp3 (index-bearing; not stable across boots)
    label: str  # *_label when present, else key
    path: Path  # the *_input attribute

    @property
    def value(self) -> int | None:
        return read_int(self.path)


@dataclass
class HwmonDevice:
    name: str
    path: Path
    device: str | None  # basename of the resolved device link, if any
    key: str = ""  # stable, unique among devices: name, or name@device / name#n

    def sensors(self, kind: str | None = None) -> list[Sensor]:
        out = []
        try:
            entries = sorted(self.path.iterdir(), key=lambda e: e.name)
        except OSError:
            return out
        for entry in entries:
            m = _SENSOR_RE.match(entry.name)
            if not m or (kind is not None and m.group(1) != kind):
                continue
            key = f"{m.group(1)}{m.group(2)}"
            label = read_attr(self.path / f"{key}_label") or key
            out.append(Sensor(kind=m.group(1), key=key, label=label, path=entry))
        return out

    def sensor(self, label: str, kind: str | None = None) -> Sensor | None:
        for s in self.sensors(kind):
            if s.label == label:
                return s
        return None


def hwmon_devices(root: "str | os.PathLike[str]" = "/") -> list[HwmonDevice]:
    """All hwmon devices with a name, ordered deterministically by identity."""
    devices = []
    for entry in _sorted_dirs(_sys(root, "class", "hwmon")):
        name = read_attr(entry / "name")
        if not name:
            continue
        device = None
        try:
            device = Path(os.path.realpath(entry / "device")).name if (entry / "device").exists() else None
        except OSError:
            device = None
        devices.append(HwmonDevice(name=name, path=entry, device=device))
    # Order by (name, device) — not by hwmonN — so keys survive renumbering
    # whenever the device link exists.
    devices.sort(key=lambda d: (d.name, d.device or "", d.path.name))
    counts: dict[str, int] = {}
    for d in devices:
        counts[d.name] = counts.get(d.name, 0) + 1
    seen: dict[str, int] = {}
    for d in devices:
        if counts[d.name] == 1:
            d.key = d.name
        elif d.device:
            d.key = f"{d.name}@{d.device}"
        else:
            n = seen.get(d.name, 0)
            seen[d.name] = n + 1
            d.key = f"{d.name}#{n}"
    return devices


def find_sensors(name: str, label: str, kind: str | None = None,
                 root: "str | os.PathLike[str]" = "/") -> list[Sensor]:
    """Every sensor with this label on every hwmon device with this name."""
    out = []
    for dev in hwmon_devices(root):
        if dev.name == name:
            s = dev.sensor(label, kind)
            if s is not None:
                out.append(s)
    return out


def find_sensor(name: str, label: str, kind: str | None = None,
                root: "str | os.PathLike[str]" = "/") -> Sensor | None:
    """First sensor matching hwmon name + label (device order is stable)."""
    found = find_sensors(name, label, kind, root)
    return found[0] if found else None


# --- power_supply -------------------------------------------------------------

@dataclass
class PowerSupply:
    name: str
    path: Path
    type: str | None  # Battery | Mains | USB | UPS | Wireless
    scope: str  # System | Device (absent scope means System)

    def attr(self, attr: str) -> str | None:
        return read_attr(self.path / attr)

    def int_attr(self, attr: str) -> int | None:
        return read_int(self.path / attr)


def power_supplies(type: str | None = None, scope: str | None = None,
                   root: "str | os.PathLike[str]" = "/") -> list[PowerSupply]:
    """power_supply nodes, filtered by type and/or scope."""
    out = []
    for entry in _sorted_dirs(_sys(root, "class", "power_supply")):
        ps_type = read_attr(entry / "type")
        ps_scope = read_attr(entry / "scope") or "System"
        if ps_scope not in ("System", "Device"):
            ps_scope = "System"
        if type is not None and ps_type != type:
            continue
        if scope is not None and ps_scope != scope:
            continue
        out.append(PowerSupply(name=entry.name, path=entry, type=ps_type, scope=ps_scope))
    return out


# --- drm ----------------------------------------------------------------------

@dataclass
class Connector:
    name: str  # e.g. eDP-1, DP-3
    path: Path
    status: str | None  # connected | disconnected | unknown


@dataclass
class DrmCard:
    name: str  # cardN
    path: Path
    driver: str | None  # kernel driver bound to the card's device
    vendor: str | None  # PCI vendor id (0x....) when the device has one
    boot_vga: bool
    connectors: list[Connector] = field(default_factory=list)


def drm_cards(root: "str | os.PathLike[str]" = "/") -> list[DrmCard]:
    """DRM cards (not render nodes) with their driver and connectors."""
    base = _sys(root, "class", "drm")
    entries = _sorted_dirs(base)
    cards = []
    for entry in entries:
        if not _CARD_RE.match(entry.name):
            continue
        dev = entry / "device"
        cards.append(DrmCard(
            name=entry.name,
            path=entry,
            driver=_link_name(dev / "driver"),
            vendor=read_attr(dev / "vendor"),
            boot_vga=read_attr(dev / "boot_vga") == "1",
        ))
    by_name = {c.name: c for c in cards}
    for entry in entries:
        m = _CONNECTOR_RE.match(entry.name)
        if not m or f"card{m.group(1)}" not in by_name:
            continue
        by_name[f"card{m.group(1)}"].connectors.append(
            Connector(name=m.group(2), path=entry, status=read_attr(entry / "status"))
        )
    cards.sort(key=lambda c: int(_CARD_RE.match(c.name).group(1)))
    return cards
