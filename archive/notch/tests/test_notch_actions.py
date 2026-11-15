"""Actions.js and the quick-actions setting (seeds, sanitising, editor ops, missing binaries)."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

NOTCH = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(expr):
    js = (
        f"const A=require({json.dumps(str(NOTCH / 'Actions.js'))});"
        f"const S=require({json.dumps(str(NOTCH / 'Settings.js'))});"
        f"const T=require({json.dumps(str(NOTCH / 'Tabs.js'))});"
        f"console.log(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


def test_seeds_are_valid_and_resolve_by_default():
    seeds = run("S.resolve(null).quickActions")
    assert [a["id"] for a in seeds] == ["screenshot", "lock", "wisp", "dictate", "terminal"]
    assert seeds == run("S.sanitizeActions(S.SEED_ACTIONS)")
    assert all(a["icon"] in run("Object.keys(S.ACTION_ICONS)") for a in seeds)


def test_seeded_binaries_exist_on_this_machine():
    """Seeds are only worth seeding if they work here (the owner's machine)."""
    seeds = run("S.resolve(null).quickActions")
    import os
    path = os.path.expanduser("~/.local/bin") + os.pathsep + os.environ["PATH"] + os.pathsep + "/usr/share/omarchy/bin"
    missing = [a["id"] for a in seeds if shutil.which(run(f"A.binaryOf({json.dumps(a['cmd'])})"), path=path) is None]
    if shutil.which("omarchy-system-lock", path=path) is None:
        pytest.skip("not the owner's Omarchy machine")
    assert missing == []


def test_saved_list_replaces_seeds_and_is_sanitised():
    s = run("S.resolve({quickActions:[{id:'a b!',label:'  Hi\\nthere ',kind:'weird',cmd:'echo  hi',icon:'nope'},{cmd:''},null,5,{label:'x',cmd:'ls',kind:'toggle',check:'true'}]}).quickActions")
    assert len(s) == 2
    assert s[0] == {"id": "ab", "label": "Hi there", "kind": "command", "cmd": "echo  hi", "icon": "play"}
    assert s[1]["kind"] == "toggle" and s[1]["check"] == "true"
    assert len(run("S.resolve({quickActions:Array.from({length:20},(_, i)=>({cmd:'x'+i}))}).quickActions")) == 6
    assert run("S.resolve({quickActions:[]}).quickActions") == []
    assert run("S.resolve({quickActions:'junk'}).quickActions") == run("S.resolve(null).quickActions")
    assert run("S.resolve({quickActions:null}).quickActions") == run("S.resolve(null).quickActions")


def test_ids_unique_and_check_only_on_toggles():
    s = run("S.sanitizeActions([{id:'a',cmd:'x',check:'y'},{id:'a',cmd:'z'}])")
    assert s[0]["id"] != s[1]["id"] and "check" not in s[0]


def test_binary_of_skips_env_and_quotes():
    assert run("A.binaryOf('FOO=1 BAR=2 omarchy-x --y')") == "omarchy-x"
    assert run("A.binaryOf('\"/usr/bin/foo\" a')") == "/usr/bin/foo"
    assert run("A.binaryOf('')") == ""


def test_run_args_runs_the_command_through_sh_with_local_bin():
    argv = run("A.runArgs({cmd:'wordink dictation toggle'})")
    assert argv[:2] == ["sh", "-c"] and argv[2].endswith("wordink dictation toggle") and ".local/bin" in argv[2]
    assert run("A.runArgs({cmd:'  '})") is None and run("A.runArgs(null)") is None


def test_probe_passes_names_as_parameters_not_script_text():
    argv = run("A.probeArgs(['a b','$(rm -rf ~)',''])")
    assert argv[3] == "notch-actions" and argv[4:] == ["a b", "$(rm -rf ~)"]
    assert "rm" not in argv[2]


def test_probe_finds_real_and_misses_fake():
    argv = run("A.probeArgs(['sh','definitely-not-a-binary-xyz'])")
    out = subprocess.run(argv, capture_output=True, text=True).stdout
    assert run(f"A.parseFound({json.dumps(out)})") == {"sh": True}


def test_missing_binary_is_disabled_with_reason_and_probing_is_enabled():
    acts = run("S.sanitizeActions([{id:'a',cmd:'present-bin x'},{id:'b',cmd:'gone-bin'}])")
    v = run(f"A.view({json.dumps(acts)}, {{'present-bin': true}})")
    assert v[0]["enabled"] and v[0]["reason"] == ""
    assert not v[1]["enabled"] and v[1]["reason"] == "gone-bin not found"
    assert all(x["enabled"] for x in run(f"A.view({json.dumps(acts)}, null)"))


def test_toggle_check_argv_only_for_toggles():
    assert run("A.checkArgs({kind:'toggle',check:'pgrep foo'})")[2].endswith("pgrep foo")
    assert run("A.checkArgs({kind:'command',check:'x'})") is None
    assert run("A.view([{id:'t',kind:'toggle',cmd:'x',check:'y'}], null)[0].hasCheck") is True


def test_editor_ops():
    base = run("S.resolve(null).quickActions")
    L = json.dumps(base)
    assert len(run(f"A.add({L}, 6)")) == 6
    assert len(run(f"A.add(A.add({L}, 6), 6)")) == 6                      # at the limit
    assert [a["id"] for a in run(f"A.remove({L}, 'lock')")][:2] == ["screenshot", "wisp"]
    assert [a["id"] for a in run(f"A.move({L}, 'lock', -1)")][:2] == ["lock", "screenshot"]
    assert [a["id"] for a in run(f"A.move({L}, 'screenshot', -1)")] == [a["id"] for a in base]   # edge: no-op
    assert run(f"A.update({L}, 'lock', {{label:'Lock now'}})")[1]["label"] == "Lock now"
    keys = run("Object.keys(S.ACTION_ICONS)")
    assert run(f"A.nextIcon({json.dumps(keys)}, {json.dumps(keys[-1])})") == keys[0]


def test_edit_persists_through_the_settings_mutator():
    cfg = run("(()=>{const c={plugins:[]};S.settingsMutator('p',{quickActions:S.sanitizeActions([{id:'x',label:'X',cmd:'echo'}])})(c);return c})()")
    assert cfg["plugins"][0]["quickActions"][0]["cmd"] == "echo"


def test_one_switch_in_features_and_editor_in_advanced():
    secs = {s["id"]: s["rows"] for s in run("S.sections(T.TABS, T.PINNED)")}
    assert [r["key"] for r in secs["features"] if r["key"].startswith("quickActions")] == ["quickActionsOn"]
    assert [r["key"] for r in secs["advanced"] if r["key"] == "quickActions"] == ["quickActions"]
    assert all(r["hint"] for r in secs["features"] + secs["advanced"] if r["key"] in ("quickActionsOn", "quickActions", "hudOwner", "clipboard"))
