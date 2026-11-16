"""bin/island-calendar: source detection, normalization and meeting-URL allowlist."""
import json
import shutil
import stat
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island/bin/island-calendar"

# 2026-11-16 09:22:00 UTC
NOW = int(datetime(2026, 11, 16, 9, 22, tzinfo=timezone.utc).timestamp() * 1000)


def ms(h, m, day=16):
    return int(datetime(2026, 11, day, h, m, tzinfo=timezone.utc).timestamp() * 1000)


def fake(bindir: Path, name: str, body: str) -> None:
    p = bindir / name
    p.write_text("#!/bin/sh\n" + body + "\n")
    p.chmod(p.stat().st_mode | stat.S_IXUSR)


def run(tmp_path: Path, omarchy=None, tools=None, extra=()):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    if omarchy is not None:
        f = home / ".local/state/omarchy/calendar-events.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(omarchy if isinstance(omarchy, str) else json.dumps(omarchy))
    for name, body in (tools or {}).items():
        fake(bindir, name, body)
    env = {"HOME": str(home), "PATH": str(bindir), "TZ": "UTC", "ISLAND_CALENDAR_NO_EDS": "1"}
    r = subprocess.run([sys.executable, str(SCRIPT), "--now", str(NOW), *extra],
                       check=False, env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def wrap(events):
    return {"version": 1, "syncedAt": "2026-11-16T09:00:00+00:00", "source": "omarchy-calendar-sync-all", "events": events}


def test_no_sources_reports_none(tmp_path):
    assert run(tmp_path) == {"source": "none", "events": []}


def test_omarchy_wrapper_iso_and_datekey(tmp_path):
    out = run(tmp_path, omarchy=wrap([
        {"id": "b", "title": "Review", "dateKey": "2026-11-16", "start": "11:00", "end": "11:30"},
        {"id": "a", "title": "Standup", "start": "2026-11-16T09:30:00+00:00", "end": "2026-11-16T09:45:00+00:00",
         "location": "https://meet.google.com/abc-defg-hij"},
        {"id": "p", "title": "Past", "start": "2026-11-16T08:00:00Z", "end": "2026-11-16T09:00:00Z"},
        {"id": "d", "title": "Holiday", "dateKey": "2026-11-16", "allDay": True},
        {"id": "f", "title": "Far", "start": "2026-11-18T09:30:00Z", "end": "2026-11-18T10:00:00Z"},
    ]))
    assert out["source"] == "omarchy"
    assert [e["title"] for e in out["events"]] == ["Standup", "Review"]
    assert out["events"][0] == {"title": "Standup", "start": ms(9, 30), "end": ms(9, 45),
                                "url": "https://meet.google.com/abc-defg-hij"}
    assert out["events"][1]["start"] == ms(11, 0) and out["events"][1]["url"] == ""


def test_omarchy_bare_list_and_running_event_kept(tmp_path):
    out = run(tmp_path, omarchy=[{"title": "Now", "start": "2026-11-16T09:15:00Z", "end": "2026-11-16T10:00:00Z"}])
    assert [e["title"] for e in out["events"]] == ["Now"]


def test_missing_end_defaults_to_thirty_minutes(tmp_path):
    out = run(tmp_path, omarchy=wrap([{"title": "x", "start": "2026-11-16T10:00:00Z"}]))
    assert out["events"][0]["end"] == ms(10, 30)


def test_at_most_five_events(tmp_path):
    evs = [{"title": f"e{i}", "start": f"2026-11-16T1{i}:00:00Z", "end": f"2026-11-16T1{i}:30:00Z"} for i in range(8)]
    assert len(run(tmp_path, omarchy=wrap(evs))["events"]) == 5


def test_meeting_url_allowlist(tmp_path):
    cases = {
        "zoom": ("Join https://us02web.zoom.us/j/123?pwd=x.", "https://us02web.zoom.us/j/123?pwd=x"),
        "zoomroot": ("https://zoom.us/j/9", "https://zoom.us/j/9"),
        "teams": ("<https://teams.microsoft.com/l/meetup-join/19%3a>", "https://teams.microsoft.com/l/meetup-join/19%3a"),
        "teamslive": ("https://teams.live.com/meet/123", "https://teams.live.com/meet/123"),
        "http": ("http://meet.google.com/abc", ""),
        "lookalike": ("https://meet.google.com.evil.example/abc", ""),
        "userinfo": ("https://zoom.us@evil.example/j/1", ""),
        "suffix": ("https://evilzoom.us/j/1", ""),
        "other": ("https://example.com/meet", ""),
        "backslash": ("https://evil.example\\.zoom.us/j/1", ""),
    }
    evs = [{"title": k, "start": f"2026-11-16T10:{i:02d}:00Z", "end": "2026-11-16T11:00:00Z", "description": text}
           for i, (k, (text, _)) in enumerate(cases.items())]
    # Five per run: check in batches.
    got = {}
    for batch in (evs[:5], evs[5:]):
        assert len(batch) <= 5
        for e in run(tmp_path, omarchy=wrap(batch))["events"]:
            got[e["title"]] = e["url"]
    assert got == {k: want for k, (_, want) in cases.items()}


def test_url_field_wins_over_description(tmp_path):
    out = run(tmp_path, omarchy=wrap([{"title": "x", "start": "2026-11-16T10:00:00Z", "end": "2026-11-16T11:00:00Z",
                                        "hangoutLink": "https://meet.google.com/aaa-bbbb-ccc",
                                        "description": "https://zoom.us/j/1"}]))
    assert out["events"][0]["url"] == "https://meet.google.com/aaa-bbbb-ccc"


def test_empty_omarchy_alone_reports_omarchy(tmp_path):
    assert run(tmp_path, omarchy=wrap([])) == {"source": "omarchy", "events": []}


def test_bad_omarchy_json_falls_through_to_none(tmp_path):
    out = run(tmp_path, omarchy="{not json")
    assert out["source"] == "none" and out["events"] == []


KHAL = ('echo \'[{"title": "Planning", "start": "2026-11-16 10:00", "end": "2026-11-16 10:30", '
        '"location": "", "description": "https://zoom.us/j/42", "url": "", "all-day": "False"}]\'\n'
        'echo \'[{"title": "Offsite", "start": "2026-11-16", "end": "2026-11-17", "location": "", '
        '"description": "", "url": "", "all-day": "True"}]\'')


def test_empty_omarchy_file_is_authoritative(tmp_path):
    # A readable Omarchy file is the owner's calendar even with nothing due:
    # later sources (gcalcli talks to Google) are not run on every poll.
    log = tmp_path / "called"
    out = run(tmp_path, omarchy=wrap([]), tools={"khal": f"touch {log}\n" + KHAL})
    assert out == {"source": "omarchy", "events": []}
    assert not log.exists()


def test_khal_when_no_omarchy_file(tmp_path):
    out = run(tmp_path, tools={"khal": KHAL})
    assert out["source"] == "khal"
    assert out["events"] == [{"title": "Planning", "start": ms(10, 0), "end": ms(10, 30), "url": "https://zoom.us/j/42"}]


def test_khal_is_read_only_list_call(tmp_path):
    log = tmp_path / "args"
    run(tmp_path, tools={"khal": f'echo "$@" > {log}\necho "[]"'})
    args = log.read_text().split()
    assert args[0] == "list" and "--json" in args


GCALCLI = ("printf 'start_date\\tstart_time\\tend_date\\tend_time\\ttitle\\tlocation\\tdescription\\n'\n"
           "printf '2026-11-16\\t09:30\\t2026-11-16\\t10:00\\tSync\\thttps://teams.live.com/meet/9\\t\\n'\n"
           "printf '2026-11-16\\t\\t2026-11-17\\t\\tAll day\\t\\t\\n'")


def test_gcalcli_tsv_with_header(tmp_path):
    out = run(tmp_path, tools={"gcalcli": GCALCLI})
    assert out == {"source": "gcalcli", "events": [
        {"title": "Sync", "start": ms(9, 30), "end": ms(10, 0), "url": "https://teams.live.com/meet/9"}]}


def test_khal_wins_over_gcalcli_when_both_have_events(tmp_path):
    assert run(tmp_path, tools={"khal": KHAL, "gcalcli": GCALCLI})["source"] == "khal"


def test_hanging_tool_hits_deadline(tmp_path):
    # run() keeps PATH to the fake bin dir only, so name sleep by absolute path.
    sleep = shutil.which("sleep")
    t0 = time.monotonic()
    out = run(tmp_path, tools={"khal": f"exec {sleep} 30"}, extra=("--deadline", "1"))
    assert time.monotonic() - t0 < 10
    assert out == {"source": "khal", "events": [], "error": "khal timed out"}


def test_failing_tool_reports_available_but_empty(tmp_path):
    out = run(tmp_path, tools={"khal": "echo boom >&2; exit 1"})
    assert out["source"] == "khal" and out["events"] == []
