"""Capabilities.js + notch-probe for optional-module setup."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAPS = ROOT / "plugins/io.github.duketopceo.notch/Capabilities.js"
PROBE = ROOT / "plugins/io.github.duketopceo.notch/bin/notch-probe"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(expr):
    js = f"const C=require({json.dumps(str(CAPS))});console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


def test_probe_script_prints_ok_json():
    out = subprocess.run(["python3", str(PROBE)], check=True, capture_output=True, text=True).stdout
    data = json.loads(out)
    assert data["ok"] is True
    assert data["macos"] is False
    assert "screenshots" in data and "gpu" in data and "npu" in data and "display" in data


def test_parse_probe_and_empty():
    raw = {"ok": True, "screenshots": True, "agents": False, "messages": True, "wordink": True,
           "wisp": False, "finance": True, "fan": False, "gpu": {"kind": "asahi-agx", "label": "Asahi AGX", "util": False, "note": "x"},
           "npu": {"kind": "ane", "label": "ANE", "present": True}, "display": {"model": "j316", "cutouts": 2, "note": "n"},
           "platform": "linux", "omarchyHost": True, "appleSilicon": True, "macos": False, "machine": "aarch64"}
    p = run(f"C.parseProbe({json.dumps(json.dumps(raw))})")
    assert p["ok"] and p["screenshots"] and p["messages"] and not p["agents"]
    assert p["gpu"]["kind"] == "asahi-agx" and p["npu"]["present"] is True
    assert run("C.parseProbe('nope')")["ok"] is False


def test_setup_offers_only_detected_disabled():
    probe = run("C.parseProbe(" + json.dumps(json.dumps({
        "ok": True, "screenshots": True, "agents": True, "messages": False, "wordink": False,
        "wisp": False, "finance": True, "fan": False
    })) + ")")
    settings = {"snapdex": False, "optAgents": True, "optMessages": False, "showStocks": False, "setupDone": False}
    offers = run(f"C.offers({json.dumps(probe)},{json.dumps(settings)})")
    ids = [o["id"] for o in offers]
    assert "screenshots" in ids and "finance" in ids
    assert "agents" not in ids  # already enabled
    assert "messages" not in ids  # not detected


def test_needs_setup_and_platform_truth():
    assert run("C.needsSetup(null)") is True
    assert run("C.needsSetup({setupDone:false})") is True
    assert run("C.needsSetup({setupDone:true})") is False
    truth = run("C.platformTruth({macos:true})")
    assert "does not run on macOS" in truth
    asahi = run("C.platformTruth({macos:false,appleSilicon:true,omarchyHost:true,machine:'aarch64'})")
    assert "Apple Silicon" in asahi and "Not macOS" in asahi


def test_standalone_list_covers_core_tabs():
    ids = [m["id"] for m in run("C.STANDALONE")]
    for need in ("home", "media", "network", "power", "system", "stocks", "plugins", "settings"):
        assert need in ids
