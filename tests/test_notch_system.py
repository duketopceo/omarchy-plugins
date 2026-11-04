"""System.js for the notch island (CPU/RAM/hwmon/fans/ANE/MLX parsing), run through node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

SYS = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch/System.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(expr):
    js = f"const S=require({json.dumps(str(SYS))});console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


def j(s):
    return json.dumps(s)


STAT1 = "cpu  100 0 100 800 0 0 0 0\ncpu0 50 0 50 400 0 0 0 0\ncpu1 50 0 50 400 0 0 0 0\ncpu2 0 0 0 0 0 0 0 0\n"
STAT2 = "cpu  200 0 200 1000 0 0 0 0\ncpu0 100 0 100 400 0 0 0 0\ncpu1 100 0 100 600 0 0 0 0\ncpu2 0 0 0 0 0 0 0 0\n"


def test_cpu_usage_delta_total_and_clusters():
    assert run(f"S.cpuUsage(S.parseCpuStat({j(STAT1)}), S.parseCpuStat({j(STAT2)}), null)") == 50
    assert run(f"S.cpuUsage(S.parseCpuStat({j(STAT1)}), S.parseCpuStat({j(STAT2)}), [0])") == 100
    assert run(f"S.cpuUsage(S.parseCpuStat({j(STAT1)}), S.parseCpuStat({j(STAT2)}), [1])") == 33
    assert run(f"S.cpuUsage(S.parseCpuStat({j(STAT1)}), S.parseCpuStat({j(STAT1)}), null)") is None
    assert run("S.cpuUsage(null, null, null)") is None


def test_clusters_from_policies():
    pol = [{"cpus": "6 7 8 9", "khz": "3000000"}, {"cpus": "0-1", "khz": "2000000"}, {"cpus": "2-5", "khz": "1000000"}]
    c = run(f"S.buildClusters({j(pol)})")
    assert c["e"]["cpus"] == [0, 1] and c["p"]["cpus"] == [2, 3, 4, 5, 6, 7, 8, 9] and c["p"]["khz"] == 2000000
    assert run("S.buildClusters([])") == {"e": None, "p": None}


def test_meminfo():
    txt = "MemTotal: 1048576 kB\nMemFree: 1 kB\nMemAvailable: 524288 kB\nSwapTotal: 1000 kB\nSwapFree: 750 kB\n"
    m = run(f"S.parseMeminfo({j(txt)})")
    assert m["pct"] == 50 and m["swapPct"] == 25 and m["ok"]
    assert run("S.parseMeminfo('')")["ok"] is False
    assert run("S.fmtGiB(1048576)") == "1.0 GB"


HW = "\n".join([
    "/sys/class/hwmon/hwmon0/name:macsmc_battery",
    "/sys/class/hwmon/hwmon2/name:macsmc_hwmon",
    "/sys/class/hwmon/hwmon2/temp1_input:31785",
    "/sys/class/hwmon/hwmon2/temp1_label:NAND Flash Temperature",
    "/sys/class/hwmon/hwmon2/temp2_input:49860",
    "/sys/class/hwmon/hwmon2/temp2_label:Charge Regulator Temp",
    "/sys/class/hwmon/hwmon2/fan1_input:2732",
    "/sys/class/hwmon/hwmon2/fan1_label:Fan 1",
    "/sys/class/hwmon/hwmon2/fan1_target:2800",
    "/sys/class/hwmon/hwmon2/fan1_max:7000",
    "/sys/class/hwmon/hwmon2/power1_input:43842979",
    "/sys/class/hwmon/hwmon2/power1_label:Total System Power",
])


def test_hwmon_label_mapping_and_fans():
    h = run(f"S.parseHwmon({j(HW)})")
    assert h["ok"] and h["name"] == "macsmc_hwmon"
    assert [t["name"] for t in h["temps"]] == ["SSD", "Charger"]
    assert h["hottest"]["c"] == 49.9 or h["hottest"]["c"] == 49.86
    f = h["fans"][0]
    assert f["rpm"] == 2732 and f["target"] == 2800 and f["max"] == 7000
    assert run(f"S.fanFraction({j(f)})") == pytest.approx(2732 / 7000)
    assert run(f"S.totalPower(S.parseHwmon({j(HW)}).powers)") == pytest.approx(43.843, abs=0.001)
    assert run("S.parseHwmon('')")["ok"] is False
    assert run("[S.tempName('CPU Package'), S.tempName('GPU Die'), S.tempName('Battery Hotspot'), S.tempName('Ambient Air')]") == ["CPU", "GPU", "Battery", "Ambient"]


def test_fan_helper_and_modes():
    h = run(f"S.parseFanHelper({j(json.dumps({'controllable': True, 'mode': 'low', 'version': '1.0.1'}))})")
    assert h == {"present": True, "controllable": True, "mode": "low", "version": "1.0.1"}
    assert run("S.parseFanHelper('nope')")["present"] is False
    assert run("[S.fanModeArg('high'), S.fanModeArg('rm -rf'), S.fanModeTitle('low')]") == ["high", None, "Quiet"]


def test_ane_status():
    a = run("S.parseAneStats('busy_ns 1000000000\\njobs 24\\npmp-not-running\\n')")
    assert a["ok"] and a["jobs"] == 24 and a["pmp"] == "pmp-not-running"
    b = {"ok": True, "busyNs": 1500000000}
    assert run(f"S.aneUtil({j(a)}, {j(b)}, 2000)") == 25
    assert run(f"S.aneUtil({j(a)}, {j(b)}, 0)") is None
    chk = "  ok    ane is loaded (version 0.5.7)\n  ok    ane is bound to 285c04000.ane\nomarchy-ane-check: ready\n"
    c = run(f"S.parseAneCheck({j(chk)})")
    assert c["ready"] and c["version"] == "0.5.7" and c["bound"] and c["state"] == "ready"
    assert run("S.parseAneCheck('')")["state"] == "unknown"
    assert run("S.parseFuserPids(' 12 345m\\n')") == [12, 345]


def test_mlx_scan_and_reservations():
    scan = "==ane\n77\n==mlx\n9 /x/python -m mlx_omarchy_serve._mlxlm_server --model /m/mlx-community/Qwen-4bit --port 8081\n10 pgrep -af mlx\n11 vim mlx_notes\n"
    s = run(f"S.parseScan({j(scan)})")
    assert s["anePids"] == [77] and len(s["mlx"]) == 1
    assert s["mlx"][0] == {"pid": 9, "model": "mlx-community/Qwen-4bit", "port": 8081}
    r = run(f"S.parseReservations({j(json.dumps({'a': {'bytes': 1073741824, 'note': 'x'}, 'b': {'bytes': 0}}))})")
    assert r["count"] == 1 and r["gib"] == 1
    assert run("S.parseReservations('bad')")["count"] == 0


def test_sparkline_buffer():
    assert run("S.pushSample([1,2,3], 4, 3)") == [2, 3, 4]
    assert run("S.pushSample(null, null, 3)") == [None]
    assert run("S.lastValue([1, 2, null])") == 2
    assert run("S.hasData([null, null])") is False
    buf = run("(function(){var b=[];for(var i=0;i<100;i++)b=S.pushSample(b,i);return b.length})()")
    assert buf == 30
