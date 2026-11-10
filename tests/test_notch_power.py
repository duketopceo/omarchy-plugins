"""Power.js for the notch island's Power tab, run through node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

POWER = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch/Power.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(expr):
    js = f"const P=require({json.dumps(str(POWER))});console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


STATUS = "percentage\t23%\nstate\tcharging\nrate\t52.3W\nsize\t82Wh\ntime\t1h 53m\ncycles\t290\nthreshold\t75-80%\n"


def test_parse_status():
    s = run(f"P.parseStatus({json.dumps(STATUS)})")
    assert s["ok"] and s["percent"] == 23 and s["state"] == "charging"
    assert s["rateW"] == 52.3 and s["sizeWh"] == 82 and s["cycles"] == 290
    assert s["timeSeconds"] == 6780 and s["thresholdLow"] == 75 and s["thresholdHigh"] == 80


def test_parse_status_junk_and_partial():
    assert run("P.parseStatus('')")["ok"] is False
    s = run("P.parseStatus('percentage\\t90%\\nthreshold\\t80%\\ntime\\t--')")
    assert s["percent"] == 90 and s["thresholdHigh"] == 80 and s["thresholdLow"] is None and s["timeSeconds"] is None


def test_parse_duration():
    assert run("P.parseDuration('53m')") == 3180
    assert run("P.parseDuration('2h')") == 7200
    assert run("P.parseDuration('nope')") is None


def test_watts_power_now_wins_and_direction_from_status():
    w = run("P.wattsFromSysfs({power_now:'52266000',current_now:'4476000',voltage_now:'11677000'},'Charging')")
    assert w == {"watts": 52.27, "flow": "in", "source": "power_now"}
    w = run("P.wattsFromSysfs({power_now:'-12500000'},'Discharging')")
    assert w["watts"] == 12.5 and w["flow"] == "out"


def test_watts_falls_back_to_current_times_voltage():
    w = run("P.wattsFromSysfs({current_now:'4476000',voltage_now:'11677000'},'Charging')")
    assert w["source"] == "current_now*voltage_now" and w["watts"] == 52.27


def test_watts_idle_and_missing():
    assert run("P.wattsFromSysfs({power_now:'0'},'Not charging')")["flow"] == "idle"
    assert run("P.wattsFromSysfs({},'Charging')")["watts"] is None
    assert run("P.wattsFromSysfs({power_now:'-3000000'},'')")["flow"] == "out"


def test_fmt_time_rounds_up():
    assert run("P.fmtTime(7140)") == "1h 59m"
    assert run("P.fmtTime(7141)") == "2h 0m"
    assert run("P.fmtTime(3180)") == "53m"
    assert run("P.fmtTime(0)") == run("P.DASH") and run("P.fmtTime(null)") == "—"


def test_time_text():
    assert run("P.timeText('charging',3180)") == "53m to full"
    assert run("P.timeText('discharging',7200)") == "2h 0m remaining"
    assert run("P.timeText('hold',3000)") == ""


@pytest.mark.parametrize("args,expected", [
    ("'Discharging',50,false,80", "discharging"),
    ("'Charging',23,true,80", "charging"),
    ("'Not charging',80,true,80", "hold"),
    ("'Full',100,true,80", "full"),
    ("'Full',80,true,80", "hold"),
    ("'Unknown',50,false,80", "discharging"),
    ("'Charging',99,true,80", "charging"),
])
def test_charge_state(args, expected):
    assert run(f"P.chargeState({args})") == expected


def test_state_labels():
    assert run("[P.stateLabel('charging'),P.stateLabel('discharging'),P.stateLabel('hold'),P.stateLabel('full')]") == [
        "Charging", "On battery", "Holding at limit", "Fully charged"]


def test_idle_badge_contract():
    assert run("P.idleBadge({percent:77,state:'charging'})") == "⚡ 77%"
    assert run("P.idleBadge({percent:77.4,state:'discharging'})") == "77%"
    assert run("P.idleBadge({percent:12,state:'discharging'})") == "▼ 12%"
    assert run("P.idleBadge({percent:100,state:'full'})") == "✓ 100%"
    assert run("P.idleBadge({percent:80,state:'hold'})") == "⏸ 80%"
    assert run("P.idleBadge(null)") == ""
    assert run("P.idleBadge({state:'charging'})") == ""
    assert run("P.idleBadge({percent:150,state:'full'})") == "✓ 100%"


DUMP = """==> /sys/class/power_supply/macsmc-battery/power_now <==
52266000

==> /sys/class/power_supply/macsmc-battery/status <==
Charging

==> /sys/class/power_supply/macsmc-battery/energy_full <==
82604400

==> /sys/class/power_supply/macsmc-battery/energy_full_design <==
99111600

==> /sys/class/power_supply/macsmc-battery/charge_control_end_threshold <==
80

==> /sys/class/power_supply/macsmc-battery/charge_control_start_threshold <==
75

==> /sys/class/power_supply/macsmc-ac/online <==
1

==> /sys/class/power_supply/macsmc-ac/input_power_limit <==
89200000
"""


def test_sysfs_dump_health_limit_adapter():
    f = run(f"P.parseSysfsDump({json.dumps(DUMP)})")
    assert f["power_now"] == "52266000" and f["status"] == "Charging" and f["ac_online"] == "1"
    h = run(f"P.health(P.parseSysfsDump({json.dumps(DUMP)}))")
    assert h == {"percent": 83, "fullWh": 82.6, "designWh": 99.11}
    lim = run(f"P.chargeLimit(P.parseSysfsDump({json.dumps(DUMP)}),null)")
    assert lim["text"] == "75–80%"
    assert run(f"P.adapterLimitW(P.parseSysfsDump({json.dumps(DUMP)}))") == 89.2
    assert run(f"P.acOnline(P.parseSysfsDump({json.dumps(DUMP)}))") is True
    assert run("P.health({})")["percent"] is None
    assert run("P.chargeLimit({}, {thresholdLow:null,thresholdHigh:80}).text") == "80%"


def test_sysfs_args_absolute_exec():
    a = run("P.sysfsArgs()")
    assert a[0] == "/usr/bin/tail" and all(x.startswith("/") or x.startswith("-") or x == "+1" for x in a)
    assert "/sys/class/power_supply/macsmc-ac/online" in a


def test_history_series_window_and_downsample():
    now = 100000
    hist = [{"time": now - 3600 * 10, "cap": 90}] + [
        {"time": now - 60 * i, "cap": 50 + i % 7, "w": -5.0 if i % 2 else 4.0} for i in range(200, 0, -1)
    ] + [{"bad": 1}]
    s = run(f"P.historySeries({json.dumps(hist)},{now},3,50)")
    assert s["count"] == 50 and len(s["cap"]) == 50 and len(s["watts"]) == 50
    assert s["lastTime"] == now - 60 and s["spanSeconds"] > 3000
    assert run("P.historySeries('not json',100000,3,50)")["count"] == 0


def test_samples_and_signed_watts():
    s = run("P.addSample(P.addSample([],1,50,-3,2),2,51,4,2)")
    assert len(s) == 2
    s = run("P.addSample([{time:1,cap:1,w:1},{time:2,cap:2,w:2}],3,3,3,2)")
    assert [x["time"] for x in s] == [2, 3]
    assert run("P.signedWatts({watts:5,flow:'out'})") == -5
    assert run("P.signedWatts({watts:5,flow:'in'})") == 5
    assert run("P.signedWatts({watts:null,flow:'idle'})") is None


def test_profiles():
    r = run("P.parseProfiles('performance\\t0\\nbalanced\\t1\\npower-saver\\t0\\n')")
    assert r["active"] == "balanced"
    assert run("P.orderedProfiles(['performance','balanced','power-saver'])") == ["power-saver", "balanced", "performance"]
    assert run("P.profileSetArgs('balanced',true)") == ["/usr/bin/omarchy-powerprofiles-set", "battery", "balanced"]
    assert run("P.profileSetArgs('performance',false)")[1] == "ac"


# ---------------------------------------------------------------- charging activity (R3)

SYSFS_CHARGING = "status=Charging\ncapacity=62\nenergy_now=50000000\nenergy_full=80000000\npower_now=30000000\ntime_to_full_now=\ncharge_control_end_threshold=100\nac_online=1\n"
SYSFS_UNPLUGGED = "status=Discharging\ncapacity=62\nenergy_now=50000000\nenergy_full=80000000\npower_now=9000000\nac_online=0\n"
SYSFS_AT_LIMIT = "status=Not charging\ncapacity=80\nenergy_now=64000000\nenergy_full=80000000\npower_now=0\ncharge_control_end_threshold=80\nac_online=1\n"
UPOWER = "src=upower\n  state:               charging\n  percentage:          41%\n  time to full:        1.5 hours\nac_online=1\n"


def test_parse_probe_sysfs_computes_time_to_full_from_energy_and_power():
    r = run(f"P.parseBatteryProbe({json.dumps(SYSFS_CHARGING)})")
    assert r["percent"] == 62 and r["state"] == "charging"
    assert r["ttfSeconds"] == 3600  # (80 - 50 Wh) / 30 W = 1 h


def test_time_to_full_stops_at_the_charge_limit_and_prefers_the_kernel_value():
    f = SYSFS_CHARGING.replace("charge_control_end_threshold=100", "charge_control_end_threshold=80")
    assert run(f"P.parseBatteryProbe({json.dumps(f)})")["ttfSeconds"] == 1680  # (64 - 50 Wh) / 30 W = 28 min
    k = SYSFS_CHARGING.replace("time_to_full_now=", "time_to_full_now=1500")
    assert run(f"P.parseBatteryProbe({json.dumps(k)})")["ttfSeconds"] == 1500
    r = run(f"P.parseBatteryProbe({json.dumps(SYSFS_AT_LIMIT)})")
    assert r["state"] == "hold" and r["ttfSeconds"] is None


def test_parse_probe_upower_fallback_and_junk():
    r = run(f"P.parseBatteryProbe({json.dumps(UPOWER)})")
    assert (r["percent"], r["state"], r["ttfSeconds"]) == (41, "charging", 5400)
    assert run("P.parseBatteryProbe('')") is None and run("P.parseBatteryProbe('x=1')") is None


def test_probe_script_picks_the_system_battery_not_a_peripheral():
    args = run("P.batteryProbeArgs()")
    assert args[:2] == ["/bin/sh", "-c"]
    assert "scope" in args[2] and "Device" in args[2] and "upower" in args[2]


def test_charging_text_shows_percent_and_time_to_full():
    assert run("P.chargingText({percent:62,state:'charging',ttfSeconds:4320})") == "62% · 1h 12m to full"
    assert run("P.chargingText({percent:62,state:'charging',ttfSeconds:null})") == "62% · charging"
    assert run("P.chargingText({percent:80,state:'hold'})") == "80% · at limit"
    assert run("P.chargingText({percent:100,state:'full'})") == "100% · full"
    assert run("P.chargingText({percent:50,state:'discharging'})") == ""


def test_plug_event_shows_the_line_for_six_seconds_then_it_expires():
    batt = {"percent": 62, "state": "discharging", "ttfSeconds": None}
    chg = {"percent": 62, "state": "charging", "ttfSeconds": 4320}
    m0 = run(f"P.chargingStep(P.chargingInitial(),{json.dumps(batt)},1000)")
    assert m0["plugged"] is False and run(f"P.chargingActive({json.dumps(m0)},1000)") is False
    m1 = run(f"P.chargingStep({json.dumps(m0)},{json.dumps(chg)},2000)")
    assert m1["text"] == "62% · 1h 12m to full" and m1["until"] == 2000 + run("P.CHARGING_MS")
    assert run(f"P.chargingActive({json.dumps(m1)},3000)") is True
    assert run(f"P.chargingActive({json.dumps(m1)},{2000 + 6000})") is False
    assert run("P.CHARGING_PRIORITY") == 60


def test_text_refreshes_while_visible_and_not_after_expiry():
    m = {"plugged": True, "text": "62% · 1h 12m to full", "until": 8000}
    r = {"percent": 63, "state": "charging", "ttfSeconds": 4200}
    assert run(f"P.chargingStep({json.dumps(m)},{json.dumps(r)},3000)")["text"] == "63% · 1h 10m to full"
    late = run(f"P.chargingStep({json.dumps(m)},{json.dumps(r)},9000)")
    assert late["text"] == "62% · 1h 12m to full"  # untouched; chargingActive is already false


def test_unplug_shows_nothing_and_clears_a_visible_line():
    m = {"plugged": True, "text": "62% · charging", "until": 8000}
    out = run(f"P.chargingStep({json.dumps(m)},{{percent:62,state:'discharging',ttfSeconds:null}},3000)")
    assert out == {"plugged": False, "text": "", "until": 0}
    assert run(f"P.chargingActive({json.dumps(out)},3001)") is False


def test_first_reading_on_ac_is_a_baseline_not_an_announcement():
    m = run("P.chargingStep(P.chargingInitial(),{percent:80,state:'hold',ttfSeconds:null},1000)")
    assert m["plugged"] is True and m["text"] == "" and run(f"P.chargingActive({json.dumps(m)},1001)") is False


def test_no_reading_keeps_the_model():
    m = {"plugged": True, "text": "x", "until": 9}
    assert run(f"P.chargingStep({json.dumps(m)},null,5)") == m


def test_reduce_motion_holds_the_bolt_still():
    assert run("P.chargingMotion(true)") == "static" and run("P.chargingMotion(false)") == "pulse"
