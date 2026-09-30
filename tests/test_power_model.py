"""Formatter tests for lukedaduke.power's Model.js.

Model.js is plain ES5 with a `module.exports` tail, so it is exercised through
node rather than duplicated in Python. Every case asserts the exact string the
panel will paint — these formatters exist to keep precision honest, and a
regression here silently rounds a battery reading.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "plugins/lukedaduke.power/Model.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

DASH = "—"


@pytest.fixture(scope="module")
def call():
    """Run one Model.js function and return its result as JSON."""
    counter = {"n": 0}

    def _call(fn: str, *args):
        counter["n"] += 1
        payload = json.dumps({"fn": fn, "args": list(args), "id": counter["n"]})
        script = f"""
        const M = require({json.dumps(str(MODEL))});
        const line = require("fs").readFileSync(0, "utf8");
        const req = JSON.parse(line);
        const out = typeof M[req.fn] === "function"
          ? M[req.fn].apply(null, req.args)
          : M[req.fn];
        require("fs").writeFileSync(1, JSON.stringify(out));
        """
        proc = subprocess.run(
            ["node", "-e", script],
            input=payload,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout)

    return _call


# ---------- presence ----------


def test_every_export_is_callable_or_a_value(call) -> None:
    script = f"require('fs').writeFileSync(1, JSON.stringify(Object.keys(require({json.dumps(str(MODEL))}))))"
    proc = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    exports = json.loads(proc.stdout)
    # The pre-existing icon/state helpers must survive the formatter additions.
    for name in ("batteryIcon", "modeLabel", "parseProfiles", "profileIcon", "fmtPower"):
        assert name in exports


# ---------- fmtPower ----------


def test_fmt_power_keeps_discharge_sign(call) -> None:
    assert call("fmtPower", -12.49, "out") == "-12.49 W out"


def test_fmt_power_two_decimals_in(call) -> None:
    assert call("fmtPower", 45.2, "in") == "45.20 W in"


def test_fmt_power_zero_reads_idle(call) -> None:
    """0.00 W must not claim a direction it doesn't have."""
    assert call("fmtPower", 0, "out") == "0.00 W idle"


def test_fmt_power_missing_is_dash(call) -> None:
    assert call("fmtPower", None, "out") == DASH


def test_fmt_power_rejects_non_numbers(call) -> None:
    assert call("fmtPower", "12.5", "out") == DASH
    assert call("fmtPower", True, "out") == DASH
    assert call("fmtPower", [1], "out") == DASH


def test_fmt_power_rejects_nan(call) -> None:
    """NaN can't ride the JSON transport, so exercise it in node directly."""
    script = (
        f"const M = require({json.dumps(str(MODEL))});"
        "require('fs').writeFileSync(1, M.fmtPower(NaN, 'out'));"
    )
    proc = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == DASH


def test_fmt_power_rejects_infinity(call) -> None:
    script = (
        f"const M = require({json.dumps(str(MODEL))});"
        "require('fs').writeFileSync(1, M.fmtPower(Infinity, 'in'));"
    )
    proc = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == DASH


def test_fmt_power_unknown_flow_falls_back_to_idle(call) -> None:
    assert call("fmtPower", -4.0, "sideways") == "-4.00 W idle"


# ---------- fmtTemp ----------


def test_fmt_temp_one_decimal(call) -> None:
    assert call("fmtTemp", 33.24) == "33.2 °C"


def test_fmt_temp_missing_is_dash(call) -> None:
    assert call("fmtTemp", None) == DASH


# ---------- fmtEnergy ----------


def test_fmt_energy_present_over_full(call) -> None:
    assert call("fmtEnergy", 31.13, 84.5) == "31.13 / 84.50 Wh"


def test_fmt_energy_needs_both_halves(call) -> None:
    """Half a reading is not a reading."""
    assert call("fmtEnergy", 31.13, None) == DASH
    assert call("fmtEnergy", None, 84.5) == DASH


# ---------- fmtRuntime ----------


def test_fmt_runtime_hours_and_minutes(call) -> None:
    assert call("fmtRuntime", 8340) == "2h 19m"


def test_fmt_runtime_rounds_up(call) -> None:
    """7141s is 119.02 minutes; rounding down would understate the estimate."""
    assert call("fmtRuntime", 7140) == "1h 59m"
    assert call("fmtRuntime", 7141) == "2h 0m"
    assert call("fmtRuntime", 119) == "2m"


def test_fmt_runtime_sub_minute(call) -> None:
    assert call("fmtRuntime", 30) == "1m"


def test_fmt_runtime_zero_is_dash(call) -> None:
    """The kernel reports 0s at full charge; that is not a runtime."""
    assert call("fmtRuntime", 0) == DASH
    assert call("fmtRuntime", None) == DASH


# ---------- fmtLimit ----------


def test_fmt_limit_with_resume_point(call) -> None:
    assert call("fmtLimit", 80, 75) == "80% · resumes 75%"


def test_fmt_limit_without_resume_point(call) -> None:
    assert call("fmtLimit", 80, None) == "80%"


def test_fmt_limit_missing_is_dash(call) -> None:
    assert call("fmtLimit", None, 75) == DASH


# ---------- fmtAge ----------


def test_fmt_age_drops_day_precision(call) -> None:
    assert call("fmtAge", "2022-07-09") == "2022-07"


def test_fmt_age_rejects_malformed(call) -> None:
    assert call("fmtAge", "2022-07") == DASH
    assert call("fmtAge", "nonsense") == DASH
    assert call("fmtAge", None) == DASH


# ---------- pre-existing helpers still behave ----------


def test_icons_and_labels_unchanged(call) -> None:
    assert call("profileIcon", "power-saver") == "󰌪"
    assert call("profileIcon", "balanced") == "󰊚"
    assert call("profileIcon", "performance") == "󰓅"
    assert call("batteryIcon", {"isPresent": False}, False, {}) == ""
    assert call("modeLabel", {"isPresent": False}, False, {}) == ""


def test_clamp_index_bounds(call) -> None:
    assert call("clampIndex", 5, 3) == 2
    assert call("clampIndex", -1, 3) == 0
    assert call("clampIndex", 0, 0) == 0


def test_select_profile_index_wraps_within_bounds(call) -> None:
    assert call("selectProfileIndex", 0, -1, ["a", "b", "c"]) == 0
    assert call("selectProfileIndex", 2, 1, ["a", "b", "c"]) == 2
    assert call("selectProfileIndex", 0, 1, []) == 0


def test_parse_profiles_finds_active(call) -> None:
    parsed = call(
        "parseProfiles", "power-saver\t0\nbalanced\t1\nperformance\t0\n", 0
    )
    assert parsed["profiles"] == ["power-saver", "balanced", "performance"]
    assert parsed["activeProfile"] == "balanced"
