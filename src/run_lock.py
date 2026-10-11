"""One pipeline run at a time, whoever starts it (terminal, web app or schedule).

The lock is an exclusive ``flock`` on ``<data dir>/run.lock``, held for the whole
run: the system releases it when the process ends, even after a crash, so a
stale lock cannot block the next run. The file also says who holds it (pid,
start time, origin, log file) for the web app's live view.
"""

import fcntl
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

LOCK_NAME = "run.lock"
ORIGIN_ENV = "LUCIDNEWS_RUN_ORIGIN"
LOG_ENV = "LUCIDNEWS_RUN_LOG"


@contextmanager
def run_lock(data_dir: Path, *, origin: Optional[str] = None, log: Optional[str] = None) -> Iterator[bool]:
    """Yield True while this process holds the lock, False when another run holds it."""
    path = Path(data_dir) / LOCK_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        handle.seek(0)
        handle.truncate()
        json.dump(
            {
                "pid": os.getpid(),
                "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "origin": origin or os.environ.get(ORIGIN_ENV) or "terminal",
                "log": log or os.environ.get(LOG_ENV),
            },
            handle,
        )
        handle.flush()
        try:
            yield True
        finally:
            handle.seek(0)
            handle.truncate()
            handle.flush()
            fcntl.flock(handle, fcntl.LOCK_UN)
    finally:
        handle.close()


def current_holder(data_dir: Path) -> Optional[Dict[str, Any]]:
    """Who holds the lock now, or None when no run is in progress.

    Read without locking, so that checking never delays a run that is starting:
    the holder writes its pid once it has the lock and clears it on release; a
    pid left by a crashed run is ignored because that process no longer exists.
    """
    path = Path(data_dir) / LOCK_NAME
    try:
        holder = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (OSError, json.JSONDecodeError):
        return None
    pid = holder.get("pid") if isinstance(holder, dict) else None
    if not isinstance(pid, int) or not _alive(pid):
        return None
    return holder


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
