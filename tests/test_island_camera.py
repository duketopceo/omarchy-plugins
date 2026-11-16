"""island-camera: which processes hold a real camera node open, against a fake proc/sys tree."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CAM = ROOT / "plugins/io.github.duketopceo.island/bin/island-camera"


def add_video(root: Path, n: int, name: str):
    d = root / "sys/class/video4linux" / f"video{n}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "name").write_text(name + "\n")


def add_proc(root: Path, pid: int, comm: str, nodes: list[int]):
    p = root / "proc" / str(pid)
    (p / "fd").mkdir(parents=True, exist_ok=True)
    (p / "comm").write_text(comm + "\n")
    for i, n in enumerate(nodes):
        link = p / "fd" / str(10 + i)
        if not os.path.lexists(link):
            os.symlink(f"/dev/video{n}", link)


def run_once(root: Path):
    return subprocess.run(
        [sys.executable, str(CAM), "--root", str(root), "--once"],
        capture_output=True, text=True, timeout=10,
    )


def test_is_executable_with_python_shebang():
    assert os.access(CAM, os.X_OK)
    assert CAM.read_text().splitlines()[0] == "#!/usr/bin/env python3"


def test_real_camera_in_use(tmp_path):
    add_video(tmp_path, 10, "FaceTime HD Camera")
    add_proc(tmp_path, 100, "firefox", [10])
    proc = run_once(tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == {"inUse": True, "apps": ["firefox"]}
    assert len(proc.stdout.strip().splitlines()) == 1


def test_codec_node_ignored(tmp_path):
    add_video(tmp_path, 0, "avd")
    add_video(tmp_path, 1, "Some H264 Encoder")
    add_proc(tmp_path, 100, "mpv", [0, 1])
    assert json.loads(run_once(tmp_path).stdout) == {"inUse": False, "apps": []}


def test_no_video_fds(tmp_path):
    add_video(tmp_path, 10, "FaceTime HD Camera")
    add_proc(tmp_path, 100, "bash", [])
    (tmp_path / "proc/100/fd/3").symlink_to("/dev/null")
    assert json.loads(run_once(tmp_path).stdout) == {"inUse": False, "apps": []}


def test_apps_sorted_unique(tmp_path):
    add_video(tmp_path, 10, "Cam")
    add_proc(tmp_path, 100, "zoom", [10])
    add_proc(tmp_path, 101, "obs", [10])
    add_proc(tmp_path, 102, "zoom", [10])
    assert json.loads(run_once(tmp_path).stdout) == {"inUse": True, "apps": ["obs", "zoom"]}


def test_unreadable_fd_dir_skipped(tmp_path):
    add_video(tmp_path, 10, "Cam")
    add_proc(tmp_path, 100, "locked", [10])
    add_proc(tmp_path, 101, "firefox", [10])
    os.chmod(tmp_path / "proc/100/fd", 0)
    try:
        proc = run_once(tmp_path)
    finally:
        os.chmod(tmp_path / "proc/100/fd", 0o755)
    assert proc.returncode == 0, proc.stderr
    assert proc.stderr == ""
    assert json.loads(proc.stdout) == {"inUse": True, "apps": ["firefox"]}


def test_watch_prints_first_result_then_only_changes(tmp_path):
    add_video(tmp_path, 10, "Cam")
    add_proc(tmp_path, 100, "bash", [])
    p = subprocess.Popen(
        [sys.executable, str(CAM), "--root", str(tmp_path), "--watch", "0.2"],
        stdout=subprocess.PIPE, text=True,
    )
    try:
        first = json.loads(p.stdout.readline())
        assert first == {"inUse": False, "apps": []}
        time.sleep(0.5)  # unchanged polls print nothing
        add_proc(tmp_path, 200, "firefox", [10])
        second = json.loads(p.stdout.readline())
        assert second == {"inUse": True, "apps": ["firefox"]}
    finally:
        p.kill()
        p.wait(timeout=5)
