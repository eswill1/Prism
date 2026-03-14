#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INTERVAL_SECONDS = int(os.getenv("PRISM_LOCAL_INGEST_INTERVAL_SECONDS", "43200"))
DEFAULT_STARTUP_DELAY_SECONDS = int(os.getenv("PRISM_LOCAL_INGEST_STARTUP_DELAY_SECONDS", "1800"))

SERVER_COMMAND = ["npm", "run", "dev:web:connected:web-only"]
INGEST_COMMAND = [
    sys.executable,
    str(ROOT / "tooling" / "run_local_ingest_job.py"),
    "--mode",
    "full",
    "--if-busy",
    "skip",
    "--trigger",
    "connected_dev_loop",
]


def log(message: str) -> None:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[connected-dev-loop] {timestamp} {message}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the connected Next.js dev server and refresh the real Supabase-backed "
            "news pipeline on a fixed interval while the server stays alive."
        )
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=DEFAULT_INTERVAL_SECONDS,
        help="Seconds between completed ingest runs. Defaults to %(default)s.",
    )
    parser.add_argument(
        "--startup-delay-seconds",
        type=int,
        default=DEFAULT_STARTUP_DELAY_SECONDS,
        help="Seconds to wait before the first ingest cycle. Defaults to %(default)s.",
    )
    return parser.parse_args()


def spawn_process(command: list[str], label: str) -> subprocess.Popen[str]:
    log(f"starting {label}: {' '.join(command)}")
    return subprocess.Popen(command, cwd=ROOT, text=True, start_new_session=True)


def interrupt_process(process: subprocess.Popen[str] | None, label: str) -> None:
    if not process or process.poll() is not None:
        return

    log(f"stopping {label}")
    try:
        os.killpg(process.pid, signal.SIGINT)
    except ProcessLookupError:
        return


def kill_process(process: subprocess.Popen[str] | None, label: str) -> None:
    if not process or process.poll() is not None:
        return

    log(f"killing {label}")
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def main() -> int:
    args = parse_args()
    if args.interval_seconds <= 0:
        raise SystemExit("--interval-seconds must be greater than 0")
    if args.startup_delay_seconds < 0:
        raise SystemExit("--startup-delay-seconds must be 0 or greater")

    stop_event = threading.Event()
    shutdown_requested = {"value": False}
    active_lock = threading.Lock()
    active_ingest: dict[str, subprocess.Popen[str] | None] = {"process": None}

    server_process = spawn_process(SERVER_COMMAND, "connected web server")

    def scheduler_loop() -> None:
        if args.startup_delay_seconds > 0:
            log(f"waiting {args.startup_delay_seconds}s before the first ingest cycle")
            if stop_event.wait(args.startup_delay_seconds):
                return

        while not stop_event.is_set():
            ingest_process = spawn_process(INGEST_COMMAND, "real-news ingest cycle")
            with active_lock:
                active_ingest["process"] = ingest_process

            exit_code = ingest_process.wait()

            with active_lock:
                active_ingest["process"] = None

            if stop_event.is_set():
                return

            if exit_code == 0:
                log("ingest cycle completed successfully")
            else:
                log(f"ingest cycle exited with code {exit_code}")

            if stop_event.wait(args.interval_seconds):
                return

    scheduler_thread = threading.Thread(target=scheduler_loop, name="connected-dev-ingest", daemon=True)
    scheduler_thread.start()

    def request_shutdown(_signum: int, _frame: object | None) -> None:
        shutdown_requested["value"] = True
        stop_event.set()
        interrupt_process(server_process, "connected web server")
        with active_lock:
            interrupt_process(active_ingest["process"], "real-news ingest cycle")

    previous_sigint = signal.signal(signal.SIGINT, request_shutdown)
    previous_sigterm = signal.signal(signal.SIGTERM, request_shutdown)

    try:
        server_exit_code = server_process.wait()
    finally:
        stop_event.set()
        with active_lock:
            interrupt_process(active_ingest["process"], "real-news ingest cycle")

        scheduler_thread.join(timeout=10)

        with active_lock:
            lingering_ingest = active_ingest["process"]

        if lingering_ingest and lingering_ingest.poll() is None:
            kill_process(lingering_ingest, "real-news ingest cycle")
            lingering_ingest.wait(timeout=5)

        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)

    if server_exit_code != 0 and not shutdown_requested["value"]:
        log(f"connected web server exited with code {server_exit_code}")

    return 0 if shutdown_requested["value"] else server_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
