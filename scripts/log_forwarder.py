"""
log_forwarder.py — Continuous Incremental Log Streaming Forwarder for CI/CD Runners.

Executes subprocess commands with real-time stdout/stderr capture and delivers log
chunks to the FastAPI backend using standard library urllib (zero external dependencies).

Features:
- Subprocess execution with unbuffered stdout/stderr (PYTHONUNBUFFERED=1)
- LogBuffer with dual flush triggers: 25 lines or 3.0 seconds
- Background timer thread to ensure idle periods flush promptly
- Idempotent delivery with unique event IDs and retry logic
- Final flush order: finishes process, flushes all remaining buffer, ensures delivery
- Preserves command exit code exactly
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Dict, List, Optional

RUN_ID_CACHE_FILE = Path("/tmp/demo_run_id.txt")


def get_headers(api_key: str = "") -> dict:
    headers = {
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true",
    }
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def resolve_run_id(candidate_id: str = "") -> str:
    """Resolve active run ID from candidate, environment, or cache file."""
    if candidate_id and candidate_id != "demo_run_manual":
        return candidate_id.strip()

    env_id = os.environ.get("DEMO_RUN_ID")
    if env_id and env_id != "demo_run_manual":
        return env_id.strip()

    if RUN_ID_CACHE_FILE.exists():
        try:
            with open(RUN_ID_CACHE_FILE, "r", encoding="utf-8") as f:
                cached = f.read().strip()
                if cached:
                    return cached
        except Exception:
            pass

    return candidate_id or "demo_run_manual"


class LogBuffer:
    """Thread-safe log buffer flushing on line count or time threshold."""

    def __init__(
        self,
        max_lines: int = 25,
        max_seconds: float = 3.0,
        on_chunk_ready = None,
    ):
        self.max_lines = max_lines
        self.max_seconds = max_seconds
        self.on_chunk_ready = on_chunk_ready

        self.lines: List[str] = []
        self.last_flush_time = time.time()
        self.lock = threading.Lock()
        self.chunk_sequence = 0

    def add(self, text: str) -> None:
        """Add line to buffer and check if line-count flush condition is met."""
        with self.lock:
            self.lines.append(text)
            if len(self.lines) >= self.max_lines:
                self._flush_locked()

    def check_timer_flush(self) -> None:
        """Called by background thread to flush if time threshold exceeded."""
        with self.lock:
            if self.lines and (time.time() - self.last_flush_time >= self.max_seconds):
                self._flush_locked()

    def flush(self) -> None:
        """Force flush all buffered lines."""
        with self.lock:
            if self.lines:
                self._flush_locked()

    def _flush_locked(self) -> None:
        if not self.lines:
            return
        chunk_text = "".join(self.lines)
        self.chunk_sequence += 1
        seq = self.chunk_sequence
        self.lines = []
        self.last_flush_time = time.time()

        if self.on_chunk_ready:
            self.on_chunk_ready(chunk_text, seq)


class StreamingLogForwarder:
    """Manages subprocess execution and streaming log chunk delivery to backend."""

    def __init__(
        self,
        backend_url: str,
        run_id: str,
        api_key: str = "",
        step_name: str = "Execute Step",
        stage: str = "execution",
        ci_run_id: Optional[str] = None,
        commit_sha: Optional[str] = None,
        max_lines: int = 25,
        max_seconds: float = 3.0,
    ):
        self.backend_url = backend_url.rstrip("/")
        self.run_id = run_id
        self.api_key = api_key
        self.step_name = step_name
        self.stage = stage
        self.ci_run_id = ci_run_id
        self.commit_sha = commit_sha
        self.headers = get_headers(api_key)

        self.buffer = LogBuffer(
            max_lines=max_lines,
            max_seconds=max_seconds,
            on_chunk_ready=self._deliver_chunk,
        )
        self.stop_timer = threading.Event()
        self.timer_thread: Optional[threading.Thread] = None
        self.delivery_errors: List[str] = []
        self.total_chunks_sent = 0

    def _start_timer(self) -> None:
        def _ticker():
            while not self.stop_timer.is_set():
                time.sleep(0.5)
                self.buffer.check_timer_flush()

        self.timer_thread = threading.Thread(target=_ticker, daemon=True)
        self.timer_thread.start()

    def _stop_timer(self) -> None:
        self.stop_timer.set()
        if self.timer_thread and self.timer_thread.is_alive():
            self.timer_thread.join(timeout=1.0)

    def _deliver_chunk(self, chunk_text: str, seq: int) -> bool:
        """Deliver a log chunk to the backend with retry logic."""
        now_iso = datetime.now(timezone.utc).isoformat()
        event_id = f"stream_{self.run_id}_{seq}_{int(time.time()*1000)}"

        payload = {
            "event_id": event_id,
            "log_chunk": chunk_text,
            "is_milestone": False,  # Continuous streaming chunk
            "step_name": self.step_name,
            "stage": self.stage,
            "is_final": False,
            "exit_code": None,
            "step_outcome": "running",
            "ci_run_id": self.ci_run_id,
            "commit_sha": self.commit_sha,
            "timestamp": now_iso,
        }

        url = f"{self.backend_url}/api/demo/runs/{self.run_id}/logs"
        data = json.dumps(payload).encode("utf-8")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, data=data, headers=self.headers, method="POST")
                with urllib.request.urlopen(req, timeout=12) as resp:
                    if resp.status in (200, 201):
                        self.total_chunks_sent += 1
                        lines_count = len(chunk_text.splitlines())
                        print(f"[Forwarder] Chunk #{seq} delivered ({lines_count} lines, HTTP {resp.status})", file=sys.stderr)
                        return True
            except urllib.error.HTTPError as e:
                err_msg = f"HTTP {e.code}: {e.reason}"
                print(f"[Forwarder] Warning: Delivery of chunk #{seq} failed ({err_msg})", file=sys.stderr)
                if e.code in (400, 401, 403, 404):
                    self.delivery_errors.append(err_msg)
                    return False
            except Exception as e:
                print(f"[Forwarder] Warning: Network error on chunk #{seq} attempt {attempt+1}: {e}", file=sys.stderr)

            if attempt < max_retries - 1:
                time.sleep(1.0 * (attempt + 1))

        self.delivery_errors.append(f"Failed to deliver chunk #{seq} after {max_retries} retries")
        return False

    def run_command(self, cmd: str) -> int:
        """Execute command, stream output in real-time, flush remaining, and return exit code."""
        print(f"[Forwarder] Starting command: {cmd}", file=sys.stderr)
        print(f"[Forwarder] Streaming to run_id: {self.run_id} at {self.backend_url}", file=sys.stderr)

        self._start_timer()

        # Safeguard 2: Ensure child process does not block-buffer stdout
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"

        try:
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )

            # Read line-by-line in real time
            for line in iter(process.stdout.readline, ""):
                if line:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    self.buffer.add(line)

            exit_code = process.wait()

        finally:
            self._stop_timer()

            # Safeguard 1: FINAL FLUSH ORDER:
            # 1. Finish subprocess
            # 2. Flush remaining buffer
            # 3. Ensure all pending chunks delivered
            self.buffer.flush()

        print(f"[Forwarder] Process finished with exit code {exit_code}. Total chunks streamed: {self.total_chunks_sent}", file=sys.stderr)
        if self.delivery_errors:
            print(f"[Forwarder] Note: Encountered {len(self.delivery_errors)} delivery warnings.", file=sys.stderr)

        return exit_code


def main():
    parser = argparse.ArgumentParser(description="Real-time CI/CD log streaming forwarder.")
    parser.add_argument("--step-name", type=str, default="Execute Step", help="CI step name")
    parser.add_argument("--stage", type=str, default="execution", help="Pipeline stage")
    parser.add_argument("--max-lines", type=int, default=25, help="Flush threshold lines (default: 25)")
    parser.add_argument("--max-seconds", type=float, default=3.0, help="Flush threshold seconds (default: 3.0)")
    parser.add_argument("--api-key", type=str, default="", help="Backend API Key")
    parser.add_argument("--cmd", type=str, default="", help="Command to execute (or pass command after --)")
    parser.add_argument("remainder", nargs=argparse.REMAINDER, help="Command arguments when using --")

    args = parser.parse_args()

    # Determine command to run
    if args.cmd:
        command = args.cmd
    elif args.remainder:
        remainder = args.remainder
        if remainder and remainder[0] == "--":
            remainder = remainder[1:]
        command = " ".join(remainder)
    else:
        parser.error("No command specified. Provide --cmd '...' or trailing command after --")

    backend_url = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
    api_key = args.api_key or os.environ.get("API_KEY") or os.environ.get("DEMO_API_KEY", "")
    commit_sha = os.environ.get("COMMIT_SHA") or os.environ.get("GITHUB_SHA", "")
    gha_run_id = os.environ.get("GHA_RUN_ID") or os.environ.get("GITHUB_RUN_ID", "")
    raw_demo_run_id = os.environ.get("DEMO_RUN_ID", "").strip()

    run_id = resolve_run_id(raw_demo_run_id)

    forwarder = StreamingLogForwarder(
        backend_url=backend_url,
        run_id=run_id,
        api_key=api_key,
        step_name=args.step_name,
        stage=args.stage,
        ci_run_id=gha_run_id,
        commit_sha=commit_sha,
        max_lines=args.max_lines,
        max_seconds=args.max_seconds,
    )

    exit_code = forwarder.run_command(command)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
