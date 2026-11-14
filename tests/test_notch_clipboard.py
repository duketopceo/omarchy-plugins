"""Clipboard.js (cliphist list/decode, masking, actions) and the tab's capability gate."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

NOTCH = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

FIXTURE = "\n".join([
    "12\thello world",
    "11\thttps://example.com/a?b=1",
    "10\t/home/u/Docs/a.pdf",
    "9\tsk-abc123def456ghi789jkl",
    "8\tmy password is hunter2",
    "7\tdGhpcyBpcyBhIGxvbmcgYmFzZTY0IHN0cmluZyAxMjM0",
    "6\t[[ binary data 12 KiB png 800x600 ]]",
    "5\tghp_abcdefghijklmnopqrstuvwxyz0123456789",
    "4\t0123456789abcdef0123456789abcdef",
    "3\tjust some long ordinary prose that is fine",
    "2\t~/notes/todo.md",
    "1\txoxb-1234567890-abcdefghij",
])


def run(expr):
    js = (
        f"const C=require({json.dumps(str(NOTCH / 'Clipboard.js'))});"
        f"const T=require({json.dumps(str(NOTCH / 'Tabs.js'))});"
        f"const S=require({json.dumps(str(NOTCH / 'Settings.js'))});"
        f"const K=require({json.dumps(str(NOTCH / 'Capabilities.js'))});"
        f"const F={json.dumps(FIXTURE)};"
        f"console.log(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


def by_id():
    return {e["id"]: e for e in run("C.parseList(F)")}


def test_lists_recent_entries_newest_first_and_capped():
    entries = run("C.parseList(F)")
    assert [e["id"] for e in entries][:3] == ["12", "11", "10"]
    assert len(run("C.parseList(F, 5)")) == 5
    assert len(run("C.parseList(F)")) == 12 and run("C.MAX_ENTRIES") == 12


def test_kinds_and_actions():
    e = by_id()
    assert e["12"]["kind"] == "text" and not e["12"]["canOpen"]
    assert e["11"]["kind"] == "link" and e["11"]["canOpen"] and not e["11"]["canFolder"]
    assert e["10"]["kind"] == "path" and e["10"]["canFolder"]
    assert e["2"]["kind"] == "path" and e["2"]["canFolder"]
    assert e["6"]["kind"] == "image" and e["6"]["text"] == "Image 800x600 · png · 12 KiB"


@pytest.mark.parametrize("eid", ["9", "8", "7", "5", "4", "1"])
def test_secret_looking_entries_are_masked(eid):
    e = by_id()[eid]
    assert e["secret"] is True and e["text"].startswith("Hidden")
    assert not e["canOpen"] and not e["canFolder"]
    assert "sk-" not in e["text"] and "hunter2" not in e["text"] and "ghp_" not in e["text"]


def test_masked_text_never_leaks_into_any_field():
    blob = json.dumps(run("C.parseList(F)"))
    for leaked in ("hunter2", "sk-abc123", "ghp_abcdef", "xoxb-1234", "0123456789abcdef0123"):
        assert leaked not in blob


def test_ordinary_text_is_not_masked():
    e = by_id()
    for eid in ("12", "11", "10", "3", "2"):
        assert e[eid]["secret"] is False
    assert run("C.looksSecret('git commit -m fix && git push origin feat/hud')") is False
    assert run("C.looksSecret('https://example.com/some/long/path/that/goes/on/and/on/for/a/while')") is False
    assert run("C.looksSecret('-----BEGIN OPENSSH PRIVATE KEY-----')") is True


def test_actions_are_argv_with_validated_ids():
    copy = run("C.copyArgs('42')")
    assert copy[0] == "sh" and 'cliphist decode "$1" | wl-copy' in copy[2] and copy[-1] == "42"
    assert "42" not in copy[2]                      # the id is a positional parameter, not spliced
    assert run("C.copyArgs('1; rm -rf ~')") is None
    assert run("C.openArgs('x')") is None and run("C.folderArgs('')") is None
    assert "xdg-open" in run("C.openArgs('7')")[2] and "dirname" in run("C.folderArgs('7')")[2]
    assert "http://*|https://*" in run("C.openArgs('7')")[2]   # only web links are ever opened


def test_junk_lines_are_dropped():
    assert run("C.parseList('nonsense\\n\\n5\\t   \\n6\\tok')") == [run("C.parseLine('6\\tok')")]


def test_tab_hidden_when_cliphist_missing_but_listed_without_a_probe():
    on = {"clipboard": True}
    shown = lambda probe: "clipboard" in [t["id"] for t in run(f"T.visibleTabs(S.resolve(null), undefined, {json.dumps(probe)})")]
    assert shown({"clipboard": True}) is True
    assert shown({"clipboard": False}) is False
    assert shown({}) is False
    assert "clipboard" in [t["id"] for t in run("T.visibleTabs(S.resolve(null))")]
    assert "clipboard" not in [t["id"] for t in run("T.visibleTabs(S.resolve({clipboard:false}), undefined, {clipboard:true})")]
    assert "clipboard" not in run("T.visibleIds(S.resolve(null), undefined, {clipboard:false})")


def test_probe_carries_clipboard_and_hud_flags():
    assert run("K.parseProbe(JSON.stringify({clipboard:true,hud:true})).clipboard") is True
    assert run("K.emptyProbe().clipboard") is False and run("K.emptyProbe().hud") is False
    out = subprocess.run(["python3", str(NOTCH / "bin/notch-probe")], check=True, capture_output=True, text=True).stdout
    d = json.loads(out)
    assert isinstance(d["clipboard"], bool) and isinstance(d["hud"], bool)


def test_one_switch_in_features_and_never_logs():
    rows = run("S.sections(T.TABS, T.PINNED)[1].rows.filter(r=>/clipboard/i.test(r.key+r.label)).map(r=>r.key)")
    assert rows == ["clipboard"]
    src = (NOTCH / "ClipboardTab.qml").read_text() + (NOTCH / "Clipboard.js").read_text()
    assert "console." not in src
