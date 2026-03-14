#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta

try:
    from tooling.local_ingest_runtime import (
        DEFAULT_FULL_INTERVAL_SECONDS,
        DEFAULT_HEARTBEAT_SECONDS,
        DEFAULT_RAW_INTERVAL_SECONDS,
        DEFAULT_RETRY_DELAY_SECONDS,
        DEFAULT_STARTUP_DELAY_SECONDS,
        LAUNCHD_LABEL,
        LAUNCHD_PLIST_PATH,
        ROOT,
        SCHEDULER_LOCK_PATH,
        append_history,
        build_launchd_plist,
        choose_due_job,
        ensure_runtime_dirs,
        file_lock,
        format_status_summary,
        isoformat_utc,
        load_status,
        update_status,
        utc_now,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from local_ingest_runtime import (
        DEFAULT_FULL_INTERVAL_SECONDS,
        DEFAULT_HEARTBEAT_SECONDS,
        DEFAULT_RAW_INTERVAL_SECONDS,
        DEFAULT_RETRY_DELAY_SECONDS,
        DEFAULT_STARTUP_DELAY_SECONDS,
        LAUNCHD_LABEL,
        LAUNCHD_PLIST_PATH,
        ROOT,
        SCHEDULER_LOCK_PATH,
        append_history,
        build_launchd_plist,
        choose_due_job,
        ensure_runtime_dirs,
        file_lock,
        format_status_summary,
        isoformat_utc,
        load_status,
        update_status,
        utc_now,
    )


def scheduler_command(mode: str) -> list[str]:
    return [
        sys.executable,
        str(ROOT / "tooling" / "run_local_ingest_job.py"),
        "--mode",
        mode,
        "--if-busy",
        "skip",
        "--trigger",
        "scheduler",
    ]


def log(message: str) -> None:
    print(f"[local-ingest-scheduler] {isoformat_utc()} {message}", flush=True)


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than 0")
    return parsed


def nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be 0 or greater")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run or manage the Prism local always-on ingest scheduler."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the scheduler in the foreground.")
    run_parser.add_argument(
        "--raw-interval-seconds",
        type=positive_int,
        default=DEFAULT_RAW_INTERVAL_SECONDS,
        help="Seconds between raw ingest discovery runs.",
    )
    run_parser.add_argument(
        "--full-interval-seconds",
        type=positive_int,
        default=DEFAULT_FULL_INTERVAL_SECONDS,
        help="Seconds between full ingest/enrich/brief/perspective runs.",
    )
    run_parser.add_argument(
        "--startup-delay-seconds",
        type=nonnegative_int,
        default=DEFAULT_STARTUP_DELAY_SECONDS,
        help="Seconds to wait before the first full ingest run.",
    )
    run_parser.add_argument(
        "--retry-delay-seconds",
        type=positive_int,
        default=DEFAULT_RETRY_DELAY_SECONDS,
        help="Seconds to wait before retrying a skipped or failed run.",
    )
    run_parser.add_argument(
        "--max-runs",
        type=positive_int,
        default=0,
        help="Optional test/debug limit; 0 means run forever.",
    )

    status_parser = subparsers.add_parser("status", help="Print scheduler status.")
    status_parser.add_argument("--json", action="store_true", help="Emit raw status JSON.")

    plist_parser = subparsers.add_parser("launchd-plist", help="Print the launchd plist.")
    plist_parser.add_argument("--raw-interval-seconds", type=positive_int, default=DEFAULT_RAW_INTERVAL_SECONDS)
    plist_parser.add_argument("--full-interval-seconds", type=positive_int, default=DEFAULT_FULL_INTERVAL_SECONDS)
    plist_parser.add_argument("--startup-delay-seconds", type=nonnegative_int, default=DEFAULT_STARTUP_DELAY_SECONDS)
    plist_parser.add_argument("--retry-delay-seconds", type=positive_int, default=DEFAULT_RETRY_DELAY_SECONDS)

    install_parser = subparsers.add_parser("install-launchd", help="Install and load the local launchd agent.")
    install_parser.add_argument("--raw-interval-seconds", type=positive_int, default=DEFAULT_RAW_INTERVAL_SECONDS)
    install_parser.add_argument("--full-interval-seconds", type=positive_int, default=DEFAULT_FULL_INTERVAL_SECONDS)
    install_parser.add_argument("--startup-delay-seconds", type=nonnegative_int, default=DEFAULT_STARTUP_DELAY_SECONDS)
    install_parser.add_argument("--retry-delay-seconds", type=positive_int, default=DEFAULT_RETRY_DELAY_SECONDS)
    install_parser.add_argument("--no-load", action="store_true", help="Write the plist without loading it.")

    subparsers.add_parser("uninstall-launchd", help="Unload and remove the local launchd agent.")
    return parser


def set_scheduler_status(
    *,
    status_name: str,
    raw_interval_seconds: int,
    full_interval_seconds: int,
    startup_delay_seconds: int,
    retry_delay_seconds: int,
    next_raw_due_at: datetime | None,
    next_full_due_at: datetime | None,
) -> None:
    heartbeat = isoformat_utc()

    def mutate(status: dict) -> None:
        scheduler = status.setdefault("scheduler", {}) or {}
        should_reset_started_at = status_name == "running" and scheduler.get("status") != "running"
        scheduler.update(
            {
                "label": LAUNCHD_LABEL,
                "status": status_name,
                "pid": os.getpid(),
                "startedAt": heartbeat if should_reset_started_at else (scheduler.get("startedAt") or heartbeat),
                "heartbeatAt": heartbeat,
                "rawIntervalSeconds": raw_interval_seconds,
                "fullIntervalSeconds": full_interval_seconds,
                "startupDelaySeconds": startup_delay_seconds,
                "retryDelaySeconds": retry_delay_seconds,
                "nextRawDueAt": isoformat_utc(next_raw_due_at) if next_raw_due_at else None,
                "nextFullDueAt": isoformat_utc(next_full_due_at) if next_full_due_at else None,
            }
        )
        if status_name == "stopped":
            scheduler["lastExitedAt"] = heartbeat
        status["scheduler"] = scheduler

    update_status(mutate)


def run_scheduler(args: argparse.Namespace) -> int:
    if args.full_interval_seconds < args.raw_interval_seconds:
        raise SystemExit("--full-interval-seconds must be greater than or equal to --raw-interval-seconds")

    ensure_runtime_dirs()
    first_due_at = utc_now() + timedelta(seconds=args.startup_delay_seconds)
    next_raw_due_at = first_due_at
    next_full_due_at = first_due_at
    completed_runs = 0
    acquired_scheduler_lock = False

    try:
        with file_lock(SCHEDULER_LOCK_PATH, blocking=False):
            acquired_scheduler_lock = True
            set_scheduler_status(
                status_name="running",
                raw_interval_seconds=args.raw_interval_seconds,
                full_interval_seconds=args.full_interval_seconds,
                startup_delay_seconds=args.startup_delay_seconds,
                retry_delay_seconds=args.retry_delay_seconds,
                next_raw_due_at=next_raw_due_at,
                next_full_due_at=next_full_due_at,
            )
            log(
                "scheduler started "
                f"(raw={args.raw_interval_seconds}s, full={args.full_interval_seconds}s, startup={args.startup_delay_seconds}s)"
            )

            while True:
                now = utc_now()
                set_scheduler_status(
                    status_name="running",
                    raw_interval_seconds=args.raw_interval_seconds,
                    full_interval_seconds=args.full_interval_seconds,
                    startup_delay_seconds=args.startup_delay_seconds,
                    retry_delay_seconds=args.retry_delay_seconds,
                    next_raw_due_at=next_raw_due_at,
                    next_full_due_at=next_full_due_at,
                )
                due_mode = choose_due_job(
                    now=now,
                    next_raw_due_at=next_raw_due_at,
                    next_full_due_at=next_full_due_at,
                )
                if not due_mode:
                    next_due_at = min(next_raw_due_at, next_full_due_at)
                    sleep_seconds = max(
                        1.0,
                        min((next_due_at - now).total_seconds(), float(DEFAULT_HEARTBEAT_SECONDS)),
                    )
                    time.sleep(sleep_seconds)
                    continue

                command = scheduler_command(due_mode)
                log(f"starting {due_mode} ingest run")
                completed = subprocess.run(command, cwd=ROOT, check=False)
                completed_runs += 1
                finished_at = utc_now()

                if completed.returncode == 0:
                    log(f"{due_mode} ingest run completed successfully")
                    next_raw_due_at = finished_at + timedelta(seconds=args.raw_interval_seconds)
                    if due_mode == "full":
                        next_full_due_at = finished_at + timedelta(seconds=args.full_interval_seconds)
                    append_level = "info"
                    append_message = f"{due_mode} scheduler run completed"
                elif completed.returncode == 3:
                    log(f"{due_mode} ingest run skipped because another ingest run already holds the local lock")
                    retry_due_at = finished_at + timedelta(seconds=args.retry_delay_seconds)
                    if due_mode == "full":
                        next_full_due_at = retry_due_at
                    else:
                        next_raw_due_at = retry_due_at
                    append_level = "warning"
                    append_message = f"{due_mode} scheduler run skipped because the ingest lock was busy"
                else:
                    log(f"{due_mode} ingest run exited with code {completed.returncode}")
                    retry_due_at = finished_at + timedelta(seconds=args.retry_delay_seconds)
                    if due_mode == "full":
                        next_full_due_at = retry_due_at
                    else:
                        next_raw_due_at = retry_due_at
                    append_level = "warning"
                    append_message = f"{due_mode} scheduler run failed with exit code {completed.returncode}"

                def mutate(status: dict) -> None:
                    append_history(status, level=append_level, message=append_message)

                update_status(mutate)

                if args.max_runs and completed_runs >= args.max_runs:
                    break

    except BlockingIOError:
        log("another local ingest scheduler instance is already running")
        return 2
    finally:
        if acquired_scheduler_lock:
            set_scheduler_status(
                status_name="stopped",
                raw_interval_seconds=args.raw_interval_seconds,
                full_interval_seconds=args.full_interval_seconds,
                startup_delay_seconds=args.startup_delay_seconds,
                retry_delay_seconds=args.retry_delay_seconds,
                next_raw_due_at=None,
                next_full_due_at=None,
            )

    return 0


def print_status(as_json: bool) -> int:
    status = load_status()
    if as_json:
        print(json.dumps(status, indent=2, sort_keys=True))
    else:
        print(format_status_summary(status))
    return 0


def print_launchd_plist(args: argparse.Namespace) -> int:
    plist_bytes = build_launchd_plist(
        raw_interval_seconds=args.raw_interval_seconds,
        full_interval_seconds=args.full_interval_seconds,
        startup_delay_seconds=args.startup_delay_seconds,
        retry_delay_seconds=args.retry_delay_seconds,
    )
    sys.stdout.buffer.write(plist_bytes)
    return 0


def install_launchd(args: argparse.Namespace) -> int:
    ensure_runtime_dirs()
    LAUNCHD_PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    plist_bytes = build_launchd_plist(
        raw_interval_seconds=args.raw_interval_seconds,
        full_interval_seconds=args.full_interval_seconds,
        startup_delay_seconds=args.startup_delay_seconds,
        retry_delay_seconds=args.retry_delay_seconds,
    )
    LAUNCHD_PLIST_PATH.write_bytes(plist_bytes)
    print(f"installed launchd plist at {LAUNCHD_PLIST_PATH}")

    if args.no_load:
        return 0

    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", domain, str(LAUNCHD_PLIST_PATH)], check=False)
    subprocess.run(["launchctl", "bootstrap", domain, str(LAUNCHD_PLIST_PATH)], check=True)
    subprocess.run(["launchctl", "kickstart", "-k", f"{domain}/{LAUNCHD_LABEL}"], check=True)
    print(f"loaded and started {LAUNCHD_LABEL}")
    return 0


def uninstall_launchd() -> int:
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", domain, str(LAUNCHD_PLIST_PATH)], check=False)
    if LAUNCHD_PLIST_PATH.exists():
        LAUNCHD_PLIST_PATH.unlink()
        print(f"removed {LAUNCHD_PLIST_PATH}")
    else:
        print(f"no plist found at {LAUNCHD_PLIST_PATH}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "run":
        return run_scheduler(args)
    if args.command == "status":
        return print_status(args.json)
    if args.command == "launchd-plist":
        return print_launchd_plist(args)
    if args.command == "install-launchd":
        return install_launchd(args)
    if args.command == "uninstall-launchd":
        return uninstall_launchd()
    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
