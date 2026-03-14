#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import UTC, datetime

try:
    from tooling.local_ingest_runtime import (
        ROOT,
        RUN_LOCK_PATH,
        append_history,
        command_for_mode,
        file_lock,
        isoformat_utc,
        update_status,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from local_ingest_runtime import ROOT, RUN_LOCK_PATH, append_history, command_for_mode, file_lock, isoformat_utc, update_status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a lock-aware Prism ingest job so local manual and scheduled runs cannot overlap."
    )
    parser.add_argument("--mode", choices=("raw", "full"), required=True)
    parser.add_argument("--if-busy", choices=("wait", "skip", "fail"), default="wait")
    parser.add_argument("--trigger", default="operator", help="Short label for status reporting.")
    return parser.parse_args()


def update_running_status(*, mode: str, trigger: str, command: list[str]) -> None:
    started_at = isoformat_utc()

    def mutate(status: dict) -> None:
        status["activeRun"] = {
            "mode": mode,
            "trigger": trigger,
            "startedAt": started_at,
            "command": command,
            "pid": os.getpid(),
        }
        append_history(status, level="info", message=f"started {mode} ingest via {trigger}")

    update_status(mutate)


def update_finished_status(
    *,
    mode: str,
    trigger: str,
    command: list[str],
    started_at: datetime,
    status_name: str,
    exit_code: int,
    reason: str | None = None,
    clear_active_run: bool = True,
) -> None:
    finished_at = datetime.now(UTC)
    duration_seconds = round((finished_at - started_at).total_seconds(), 3)

    def mutate(status: dict) -> None:
        if clear_active_run:
            status["activeRun"] = None
        status.setdefault("jobs", {})[mode] = {
            "mode": mode,
            "trigger": trigger,
            "command": command,
            "status": status_name,
            "startedAt": isoformat_utc(started_at),
            "finishedAt": isoformat_utc(finished_at),
            "durationSeconds": duration_seconds,
            "exitCode": exit_code,
            "reason": reason or "",
        }
        append_history(
            status,
            level="info" if exit_code == 0 else "warning",
            message=f"{mode} ingest {status_name} via {trigger}",
        )

    update_status(mutate)


def main() -> int:
    args = parse_args()
    command = command_for_mode(args.mode)
    blocking = args.if_busy == "wait"

    try:
        with file_lock(RUN_LOCK_PATH, blocking=blocking):
            started_at = datetime.now(UTC)
            update_running_status(mode=args.mode, trigger=args.trigger, command=command)
            completed = subprocess.run(command, cwd=ROOT, check=False)
            status_name = "success" if completed.returncode == 0 else "failed"
            update_finished_status(
                mode=args.mode,
                trigger=args.trigger,
                command=command,
                started_at=started_at,
                status_name=status_name,
                exit_code=completed.returncode,
            )
            return completed.returncode
    except BlockingIOError:
        if args.if_busy == "fail":
            return_code = 2
            status_name = "busy"
        else:
            return_code = 3
            status_name = "skipped"

        now = datetime.now(UTC)
        update_finished_status(
            mode=args.mode,
            trigger=args.trigger,
            command=command,
            started_at=now,
            status_name=status_name,
            exit_code=return_code,
            reason="another ingest run already holds the local lock",
            clear_active_run=False,
        )
        return return_code


if __name__ == "__main__":
    raise SystemExit(main())
