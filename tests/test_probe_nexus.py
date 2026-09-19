from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "plugins/lukedaduke.nexus/bin/probe_nexus.py"


def load():
    spec = importlib.util.spec_from_file_location("probe_nexus", PROBE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def make_usb_dev(base: Path, name: str, files: dict[str, str]) -> str:
    d = base / name
    d.mkdir(parents=True)
    for fname, content in files.items():
        fpath = d / fname
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content)
    return str(d)


def usb_files(**over) -> dict[str, str]:
    files = {
        "idVendor": "1234",
        "idProduct": "5678",
        "product": "Test Widget",
        "manufacturer": "Acme",
        "bDeviceClass": "00",
        "speed": "480",
        "power/runtime_status": "active",
    }
    files.update(over)
    return files


def patch_env(mod, monkeypatch, dev_paths=(), tools=None, run_out=None):
    """Point get_nexus at fake sysfs + canned tool output."""
    monkeypatch.setattr(mod, "glob", SimpleNamespace(glob=lambda _pat: list(dev_paths)))
    tools = tools or {}
    monkeypatch.setattr(mod, "_tool", lambda name: tools.get(name))
    run_out = run_out or {}

    def fake_run(argv, **_kw):
        for needle, out in run_out.items():
            if needle in argv:
                return out
        return None

    monkeypatch.setattr(mod, "_run", fake_run)


# --- resolve_device classification ---------------------------------------


def test_resolve_device_known_hardware() -> None:
    mod = load()
    name, cat, _icon, _desc = mod.resolve_device("0bda:8153", "whatever", "whoever", "00")
    assert name == "Gigabit Ethernet"
    assert cat == "Network"


@pytest.mark.parametrize(
    ("kwargs", "expected_cat"),
    [
        (dict(raw_product="", raw_mfg="", dev_class="09"), "Hub"),
        (dict(raw_product="Kbd", raw_mfg="", dev_class="00"), "Peripheral"),
        (dict(raw_product="My Keyboard", raw_mfg="", dev_class="00"), "Input"),
        (dict(raw_product="", raw_mfg="keyboard co", dev_class="00"), "Input"),
        (dict(raw_product="Gaming Mouse", raw_mfg="", dev_class="00"), "Input"),
        (dict(raw_product="Magic Trackpad", raw_mfg="", dev_class="00"), "Input"),
        (dict(raw_product="HD Webcam", raw_mfg="", dev_class="00"), "Camera"),
        (dict(raw_product="USB Audio Headset", raw_mfg="", dev_class="00"), "Audio"),
        (dict(raw_product="Flash Disk", raw_mfg="", dev_class="00"), "Storage"),
        (dict(raw_product="USB Ethernet LAN", raw_mfg="", dev_class="00"), "Network"),
        (dict(raw_product="Android Phone", raw_mfg="", dev_class="00"), "Mobile"),
    ],
)
def test_resolve_device_keywords(kwargs, expected_cat) -> None:
    mod = load()
    _name, cat, _icon, _desc = mod.resolve_device("ffff:ffff", **kwargs)
    assert cat == expected_cat


def test_resolve_device_fallback_names() -> None:
    mod = load()
    # Real product string wins over manufacturer.
    name, cat, _i, _d = mod.resolve_device("ffff:ffff", "Quux Gadget", "Acme", "00")
    assert name == "Quux Gadget"
    assert cat == "Peripheral"
    # "Generic Device" product falls through to manufacturer.
    name, *_ = mod.resolve_device("ffff:ffff", "Generic Device", "Acme", "00")
    assert name == "Acme"
    # Nothing usable → USB Peripheral.
    name, *_ = mod.resolve_device("ffff:ffff", "", "", "00")
    assert name == "USB Peripheral"


# --- USB sysfs walk + speed map ------------------------------------------


@pytest.mark.parametrize(
    ("speed", "tag"),
    [("480", "480M"), ("5000", "5G"), ("10000", "10G"), ("12", "12M"), ("1.5", "12M")],
)
def test_usb_speed_map(tmp_path: Path, monkeypatch, speed, tag) -> None:
    mod = load()
    dev = make_usb_dev(tmp_path, "1-1", usb_files(speed=speed))
    patch_env(mod, monkeypatch, dev_paths=[dev])
    data = mod.get_nexus()
    assert data["usb"][0]["speed"] == tag


def test_usb_sysfs_entry_fields(tmp_path: Path, monkeypatch) -> None:
    mod = load()
    hub = make_usb_dev(tmp_path, "1-0", usb_files(bDeviceClass="09", product="Root Hub"))
    leaf = make_usb_dev(
        tmp_path,
        "1-1.2",
        usb_files(speed="5000", **{"power/runtime_status": "suspended"}),
    )
    patch_env(mod, monkeypatch, dev_paths=[hub, leaf])
    data = mod.get_nexus()

    assert data["ok"] is True
    assert len(data["usb"]) == 2
    hub_row = next(r for r in data["usb"] if r["id"] == "1-0")
    leaf_row = next(r for r in data["usb"] if r["id"] == "1-1.2")
    assert hub_row["is_hub"] is True
    assert hub_row["tier"] == 0
    assert leaf_row["is_hub"] is False
    assert leaf_row["tier"] == 1  # one "." in "1-1.2"
    assert leaf_row["speed"] == "5G"
    assert leaf_row["status"] == "SLEEP"
    assert hub_row["status"] == "ONLINE"


def test_usb_interface_dirs_skipped(tmp_path: Path, monkeypatch) -> None:
    mod = load()
    # Basenames containing ":" are interface descriptors, not devices.
    dev = make_usb_dev(tmp_path / "sys", "1-1:1.0", usb_files())
    patch_env(mod, monkeypatch, dev_paths=[dev])
    data = mod.get_nexus()
    assert data["usb"] == []


# --- bluetoothctl parsing -------------------------------------------------

BT_OUT = """\
Agent registered
Device AA:BB:CC:DD:EE:FF MX Master 3S
Device 11:22:33:44:55:66 MCHNCL K855
Device 77:88:99:AA:BB:CC AirPods Pro
Device 00:11:22:33:44:55 Living Room Speaker
Device DE:AD:BE:EF:00:01
"""


def test_bluetoothctl_split_and_classification(monkeypatch) -> None:
    mod = load()
    patch_env(
        mod,
        monkeypatch,
        tools={"bluetoothctl": "/fake/bluetoothctl"},
        run_out={"devices": BT_OUT},
    )
    data = mod.get_nexus()
    bt = {r["mac"]: r for r in data["bluetooth"]}

    # Non-"Device" line skipped; 5 devices parsed.
    assert len(bt) == 5

    master = bt["AA:BB:CC:DD:EE:FF"]
    assert master["name"] == "MX Master 3S Mouse"
    assert master["category"] == "Mouse"

    kbd = bt["11:22:33:44:55:66"]
    assert kbd["name"] == "MX Mechanical Keyboard"
    assert kbd["category"] == "Keyboard"

    pods = bt["77:88:99:AA:BB:CC"]
    assert pods["name"] == "Status Between 3ANC"
    assert pods["category"] == "Earbuds"

    # Unknown device keeps its raw name, generic bucket.
    spk = bt["00:11:22:33:44:55"]
    assert spk["name"] == "Living Room Speaker"
    assert spk["category"] == "Wireless"
    assert spk["status"] == "ONLINE"

    # "Device <mac>" with no name field → placeholder.
    noname = bt["DE:AD:BE:EF:00:01"]
    assert noname["name"] == "Bluetooth Device"


def test_bluetooth_missing_tool(monkeypatch) -> None:
    mod = load()
    patch_env(mod, monkeypatch)
    data = mod.get_nexus()
    assert data["ok"] is True
    assert data["bluetooth"] == []


# --- network parsing ------------------------------------------------------

IP_JSON = json.dumps(
    [
        {"ifname": "lo", "operstate": "UNKNOWN", "addr_info": []},
        {"ifname": "docker0", "operstate": "DOWN", "addr_info": []},
        {"ifname": "veth1234", "operstate": "UP", "addr_info": []},
        {
            "ifname": "wlp0s20f3",
            "operstate": "UP",
            "addr_info": [{"family": "inet", "local": "192.168.1.50"}],
        },
        {
            "ifname": "enp0s20f0u1u2u4",
            "operstate": "UP",
            "addr_info": [{"family": "inet", "local": "10.0.0.5"}],
        },
        {"ifname": "tailscale0", "operstate": "UNKNOWN", "addr_info": []},
        {"ifname": "nordlynx", "operstate": "UP", "addr_info": [{"family": "inet6", "local": "fe80::1"}]},
    ]
)


def test_ip_addr_parsing(monkeypatch) -> None:
    mod = load()
    patch_env(
        mod,
        monkeypatch,
        tools={"ip": "/fake/ip"},
        run_out={"addr": IP_JSON},
    )
    data = mod.get_nexus()
    names = [r["name"] for r in data["network"]]

    # loopback / container interfaces dropped.
    assert "lo" not in names
    assert "docker0" not in names
    assert "veth1234" not in names

    wifi = next(r for r in data["network"] if r["name"] == "Wi-Fi 6 Wireless")
    assert wifi["ip"] == "192.168.1.50"
    assert wifi["status"] == "CONNECTED"

    dock = next(r for r in data["network"] if r["name"] == "Dock Gigabit LAN")
    assert dock["ip"] == "10.0.0.5"

    ts = next(r for r in data["network"] if r["name"] == "Tailscale Mesh")
    assert ts["ip"] == "No IP"
    assert ts["status"] == "OFFLINE"

    nord = next(r for r in data["network"] if r["name"] == "NordVPN Tunnel")
    # inet6 addr is ignored, but operstate UP still counts as connected.
    assert nord["ip"] == "No IP"
    assert nord["status"] == "CONNECTED"


# --- lsblk walk + storage classification ----------------------------------

LSBLK_JSON = json.dumps(
    {
        "blockdevices": [
            {
                "name": "nvme0n1",
                "model": "PC711 NVMe SK hynix 512GB",
                "tran": "nvme",
                "size": "476.9G",
                "mountpoints": [None],
                "type": "disk",
                "children": [
                    {
                        "name": "nvme0n1p1",
                        "mountpoints": ["/boot"],
                        "type": "part",
                        "children": [
                            {"name": "nvme0n1p2", "mountpoints": ["/", "/home"], "type": "part"}
                        ],
                    }
                ],
            },
            {
                "name": "sda",
                "model": "Samsung SSD 870",
                "tran": "sata",
                "size": "931.5G",
                "mountpoints": [None],
                "type": "disk",
            },
            {
                "name": "sdb",
                "model": "Ventoy",
                "tran": "usb",
                "size": "32G",
                "mountpoints": ["/mnt/ventoy"],
                "type": "disk",
            },
            {
                "name": "zram0",
                "model": None,
                "tran": None,
                "size": "8G",
                "mountpoints": ["[SWAP]"],
                "type": "disk",
            },
            {
                "name": "loop0",
                "model": None,
                "tran": None,
                "size": "100M",
                "mountpoints": ["/snap/x"],
                "type": "loop",
            },
            {
                "name": "mmcblk0",
                "model": "",
                "tran": "",
                "size": "59G",
                "mountpoints": [None],
                "type": "disk",
            },
        ]
    }
)


def run_lsblk_probe(monkeypatch):
    mod = load()
    patch_env(
        mod,
        monkeypatch,
        tools={"lsblk": "/fake/lsblk"},
        run_out={"-J": LSBLK_JSON},
    )
    return mod.get_nexus()


def test_lsblk_storage_rows(monkeypatch) -> None:
    data = run_lsblk_probe(monkeypatch)
    storage = {r["name"]: r for r in data["storage"]}

    # loop devices skipped entirely.
    assert all("loop" not in name for name in storage)

    # Model match → friendly NVMe title; mounts walked depth-first through
    # children, first non-null mount wins.
    nvme = storage["OS Root NVMe (512GB)"]
    assert nvme["mount"] == "/boot"
    assert nvme["status"] == "MOUNTED"

    # tran == "usb" is what earns the flash-drive label.
    usb = storage["USB Flash Drive (32G)"]
    assert usb["desc"] == "Ventoy Multi-Boot USB Stick"
    assert usb["mount"] == "/mnt/ventoy"

    zram = next(r for r in data["storage"] if r["name"].startswith("ZRAM"))
    assert zram["name"] == "ZRAM Fast Swap (8G)"

    # No mounts → Unmounted/READY.
    mmc = storage["Storage (mmcblk0)"]
    assert mmc["mount"] == "Unmounted"
    assert mmc["status"] == "READY"


def test_lsblk_sata_disk_not_labeled_usb(monkeypatch) -> None:
    """Regression: name.startswith('sd') must not imply a USB flash drive —
    a SATA sda renders as a generic storage row."""
    data = run_lsblk_probe(monkeypatch)
    sda = next(r for r in data["storage"] if "sda" in r["name"])
    assert sda["name"] == "Storage (sda)"
    assert sda["desc"] == "SATA drive"
    assert sda["icon"] == "󰋊"


def test_lsblk_bad_json(monkeypatch) -> None:
    mod = load()
    patch_env(
        mod,
        monkeypatch,
        tools={"lsblk": "/fake/lsblk"},
        run_out={"-J": "{not json"},
    )
    data = mod.get_nexus()
    assert data["ok"] is True
    assert data["storage"] == []


def test_lsblk_mount_cap(monkeypatch) -> None:
    mod = load()
    # 20 mountpoints across nested children → capped at 16.
    children = [
        {"name": f"p{i}", "mountpoints": [f"/mnt/{i}"], "type": "part"} for i in range(20)
    ]
    ls = json.dumps(
        {
            "blockdevices": [
                {
                    "name": "sdc",
                    "model": "m",
                    "tran": "sata",
                    "size": "1T",
                    "mountpoints": [],
                    "type": "disk",
                    "children": children,
                }
            ]
        }
    )
    patch_env(
        mod,
        monkeypatch,
        tools={"lsblk": "/fake/lsblk"},
        run_out={"-J": ls},
    )
    data = mod.get_nexus()
    # Cap is internal; observable contract is the row exists and stays sane.
    row = next(r for r in data["storage"] if "sdc" in r["name"])
    assert row["mount"] == "/mnt/0"
    assert row["status"] == "MOUNTED"


# --- top-level shape ------------------------------------------------------


def test_empty_system_returns_ok_shape(monkeypatch) -> None:
    mod = load()
    patch_env(mod, monkeypatch)
    data = mod.get_nexus()
    assert data == {"ok": True, "usb": [], "bluetooth": [], "network": [], "storage": []}
    json.dumps(data)
