"""Descriptor-relative state I/O: no-follow, owner-checked, capped, atomic.

Directories are opened with O_NOFOLLOW and must be real directories owned by
the effective user; files are opened relative to that descriptor so a swapped
path component cannot redirect a read or write.
"""

from __future__ import annotations

import os
import stat
from contextlib import contextmanager
from typing import Iterator, Union

DirLike = Union[str, "os.PathLike[str]", int]


def open_dir(path: "str | os.PathLike[str]") -> int:
    """Descriptor for a user-owned real directory; raises OSError otherwise."""
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    st = os.fstat(fd)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid():
        os.close(fd)
        raise PermissionError(f"{os.fspath(path)} is not a user-owned real directory")
    return fd


@contextmanager
def _dirfd(directory: DirLike) -> Iterator[int]:
    if isinstance(directory, int):
        yield directory
        return
    fd = open_dir(directory)
    try:
        yield fd
    finally:
        os.close(fd)


def _check_name(name: str) -> None:
    if not name or name in (".", "..") or "/" in name or "\0" in name:
        raise ValueError(f"invalid file name: {name!r}")


def read_capped(directory: DirLike, name: str, limit: int) -> bytes | None:
    """Whole-file read bounded to limit bytes; None on any anomaly.

    Refuses symlinks, non-regular files, files not owned by the effective
    user, and files larger than limit (checked by size and by bytes read, so
    a file that grows mid-read is still refused).
    """
    try:
        _check_name(name)
        with _dirfd(directory) as dirfd:
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dirfd)
            try:
                st = os.fstat(fd)
                if not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or st.st_size > limit:
                    return None
                chunks = []
                remaining = limit + 1
                while remaining > 0:
                    chunk = os.read(fd, min(65536, remaining))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    remaining -= len(chunk)
                data = b"".join(chunks)
                return None if len(data) > limit else data
            finally:
                os.close(fd)
    except (OSError, ValueError):
        return None


def publish(directory: DirLike, name: str, data: "str | bytes") -> None:
    """Atomically replace directory/name with data, mode 0600.

    Writes an exclusive same-directory temp file, fsyncs it, then renames it
    over the target. Raises OSError (including for a symlinked or foreign
    directory) and ValueError for a name that is not a plain file name.
    """
    _check_name(name)
    payload = data.encode() if isinstance(data, str) else bytes(data)
    with _dirfd(directory) as dirfd:
        tmp = f".{name}.{os.getpid()}.tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dirfd)
        try:
            try:
                view = memoryview(payload)
                while view:
                    view = view[os.write(fd, view):]
                os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(tmp, name, src_dir_fd=dirfd, dst_dir_fd=dirfd)
        except BaseException:
            try:
                os.unlink(tmp, dir_fd=dirfd)
            except OSError:
                pass
            raise
