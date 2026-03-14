#!/usr/bin/env python3

from __future__ import annotations

import fcntl
import json
import os
import plistlib
import shlex
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = Path(os.getenv("PRISM_LOCAL_INGEST_STATE_DIR", ROOT / ".local" / "local-ingest"))
LOG_DIR = STATE_DIR / "logs"
STATUS_PATH = STATE_DIR / "status.json"
STATUS_LOCK_PATH = STATE_DIR / "status.lock"
RUN_LOCK_PATH = STATE_DIR / "run.lock"
SCHEDULER_LOCK_PATH = STATE_DIR / "scheduler.lock"
LAUNCHD_LABEL = "com.prismwire.local-ingest"
LAUNCHD_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"

DEFAULT_STARTUP_DELAY_SECONDS = int(os.getenv("PRISM_LOCAL_INGEST_STARTUP_DELAY_SECONDS", "1800"))
DEFAULT_RAW_INTERVAL_SECONDS = int(os.getenv("PRISM_LOCAL_RAW_INGEST_INTERVAL_SECONDS", "21600"))
DEFAULT_FULL_INTERVAL_SECONDS = int(os.getenv("PRISM_LOCAL_FULL_INGEST_INTERVAL_SECONDS", "43200"))
DEFAULT_RETRY_DELAY_SECONDS = int(os.getenv("PRISM_LOCAL_INGEST_RETRY_DELAY_SECONDS", "3600"))
DEFAULT_HEARTBEAT_SECONDS = 15
DEFAULT_PATH = os.getenv("PATH", "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin")
STATUS_VERSION = 1


def utc_now() -> datetime:
    return datetime.now(UTC)


def isoformat_utc(value: datetime | None = None) -> str:
    timestamp = (value or utc_now()).astimezone(UTC).replace(microsecond=0)
    return timestamp.isoformat().replace("+00:00", "Z")


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def ensure_runtime_dirs() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def file_lock(path: Path, *, blocking: bool) -> Iterator[Path]:
    ensure_runtime_dirs()
    handle = path.open("a+", encoding="utf-8")
    flags = fcntl.LOCK_EX
    if not blocking:
        flags |= fcntl.LOCK_NB
    try:
        fcntl.flock(handle.fileno(), flags)
    except BlockingIOError:
        handle.close()
        raise

    try:
        handle.seek(0)
        handle.truncate()
        handle.write(f"{os.getpid()}\n")
        handle.flush()
        yield path
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def load_status() -> dict[str, Any]:
    if not STATUS_PATH.exists():
        return {
            "stateVersion": STATUS_VERSION,
            "scheduler": None,
            "activeRun": None,
            "jobs": {},
            "history": [],
        }

    try:
        return json.loads(STATUS_PATH.read_text())
    except json.JSONDecodeError:
        return {
            "stateVersion": STATUS_VERSION,
            "scheduler": None,
            "activeRun": None,
            "jobs": {},
            "history": [],
        }


def save_status(payload: dict[str, Any]) -> None:
    ensure_runtime_dirs()
    payload["stateVersion"] = STATUS_VERSION
    temp_path = STATUS_PATH.with_suffix(".tmp")
    temp_path.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n")
    temp_path.replace(STATUS_PATH)


def update_status(mutator) -> dict[str, Any]:
    with file_lock(STATUS_LOCK_PATH, blocking=True):
        status = load_status()
        mutator(status)
        save_status(status)
        return status


def append_history(status: dict[str, Any], *, level: str, message: str) -> None:
    history = status.setdefault("history", [])
    history.append(
        {
            "timestamp": isoformat_utc(),
            "level": level,
            "message": message,
        }
    )
    del history[:-20]


def command_for_mode(mode: str) -> list[str]:
    if mode == "raw":
        return ["npm", "run", "ingest:feeds:raw:direct"]
    if mode == "full":
        return ["npm", "run", "ingest:feeds:direct"]
    raise ValueError(f"unsupported ingest mode: {mode}")


def choose_due_job(
    *,
    now: datetime,
    next_raw_due_at: datetime,
    next_full_due_at: datetime,
) -> str | None:
    if now >= next_full_due_at:
        return "full"
    if now >= next_raw_due_at:
        return "raw"
    return None


def build_launchd_plist(
    *,
    raw_interval_seconds: int,
    full_interval_seconds: int,
    startup_delay_seconds: int,
    retry_delay_seconds: int,
) -> bytes:
    ensure_runtime_dirs()
    command = " ".join(
        [
            f"cd {shlex.quote(str(ROOT))}",
            "&&",
            "exec",
            "python3",
            "tooling/run_local_ingest_scheduler.py",
            "run",
            f"--raw-interval-seconds {raw_interval_seconds}",
            f"--full-interval-seconds {full_interval_seconds}",
            f"--startup-delay-seconds {startup_delay_seconds}",
            f"--retry-delay-seconds {retry_delay_seconds}",
        ]
    )
    plist = {
        "Label": LAUNCHD_LABEL,
        "ProgramArguments": ["/bin/zsh", "-lc", command],
        "WorkingDirectory": str(ROOT),
        "EnvironmentVariables": {
            "PATH": DEFAULT_PATH,
            "PRISM_LOCAL_INGEST_STATE_DIR": str(STATE_DIR),
        },
        "KeepAlive": True,
        "RunAtLoad": True,
        "ProcessType": "Background",
        "StandardOutPath": str(LOG_DIR / "scheduler.stdout.log"),
        "StandardErrorPath": str(LOG_DIR / "scheduler.stderr.log"),
    }
    return plistlib.dumps(plist)


def describe_result(job: dict[str, Any] | None) -> str:
    if not job:
        return "never"
    status = job.get("status", "unknown")
    finished_at = job.get("finishedAt") or job.get("startedAt") or "unknown time"
    duration = job.get("durationSeconds")
    detail = f"{status} at {finished_at}"
    if isinstance(duration, (int, float)):
        detail += f" in {duration:.1f}s"
    reason = job.get("reason")
    if isinstance(reason, str) and reason:
        detail += f" ({reason})"
    return detail


def scheduler_health(status: dict[str, Any]) -> tuple[str, str]:
    scheduler = status.get("scheduler") or {}
    heartbeat = parse_timestamp(scheduler.get("heartbeatAt"))
    if not scheduler:
        return ("stopped", "no scheduler status recorded yet")
    if scheduler.get("status") == "stopped":
        return ("stopped", "scheduler is not currently running")
    if not heartbeat:
        return ("unknown", "scheduler heartbeat missing")

    age = utc_now() - heartbeat
    if age <= timedelta(seconds=DEFAULT_HEARTBEAT_SECONDS * 3):
        return ("running", f"heartbeat {int(age.total_seconds())}s ago")
    return ("stale", f"last heartbeat {int(age.total_seconds())}s ago")


def format_status_summary(status: dict[str, Any]) -> str:
    scheduler = status.get("scheduler") or {}
    health, detail = scheduler_health(status)
    active_run = status.get("activeRun")
    raw_job = (status.get("jobs") or {}).get("raw")
    full_job = (status.get("jobs") or {}).get("full")

    lines = [
        "Prism local ingest scheduler",
        f"state file: {STATUS_PATH}",
        f"scheduler: {health} ({detail})",
    ]

    if scheduler:
        lines.append(
            "cadence: "
            f"raw every {scheduler.get('rawIntervalSeconds', 'unknown')}s, "
            f"full every {scheduler.get('fullIntervalSeconds', 'unknown')}s, "
            f"startup delay {scheduler.get('startupDelaySeconds', 'unknown')}s"
        )
        if scheduler.get("nextRawDueAt") or scheduler.get("nextFullDueAt"):
            lines.append(
                "next due: "
                f"raw {scheduler.get('nextRawDueAt', 'unknown')}, "
                f"full {scheduler.get('nextFullDueAt', 'unknown')}"
            )

    if active_run:
        lines.append(
            "active run: "
            f"{active_run.get('mode', 'unknown')} started {active_run.get('startedAt', 'unknown')} "
            f"via {active_run.get('trigger', 'unknown')}"
        )
    else:
        lines.append("active run: none")

    lines.append(f"last raw: {describe_result(raw_job)}")
    lines.append(f"last full: {describe_result(full_job)}")
    return "\n".join(lines)
