"""NotificationsPolicy.js: opt-in host never steals D-Bus by default."""
import json
import subprocess
from pathlib import Path

POL = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch/NotificationsPolicy.js"


def run(expr: str):
    script = POL.read_text() + f"\nconsole.log(JSON.stringify({expr}))\n"
    out = subprocess.check_output(["node", "-e", script], text=True).strip()
    return json.loads(out)


def test_off_means_stock():
    st = run("hostStatus(false, {})")
    assert st["ok"] is True
    assert st["code"] == "stock"


def test_on_without_disable_is_conflict():
    st = run("hostStatus(true, {disabledPlugins: []})")
    assert st["ok"] is False
    assert st["code"] == "conflict"
    assert "omarchy.notifications" in st["detail"]


def test_on_with_disable_is_ready():
    st = run('hostStatus(true, {disabledPlugins: ["omarchy.notifications"]})')
    assert st["ok"] is True
    assert st["code"] == "ready"


def test_osd_hint_only_when_island_owns_hud():
    assert "omarchy.osd" in run('osdHint("notch")')
    assert run('osdHint("omarchy")') == ""
