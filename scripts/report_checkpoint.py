"""
report_checkpoint.py — CLI tool to stream CI/CD checkpoint logs to the FastAPI backend.
Transmits authentic captured stdout/stderr from GitHub Actions runner to the predictor backend.
"""
import argparse
from datetime import datetime, timezone
import json
import os
import sys
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description="Report CI/CD checkpoint logs to predictor backend.")
    parser.add_argument("--depth", type=int, required=True, choices=[25, 50, 75, 100], help="Checkpoint depth percentage (25, 50, 75, 100)")
    parser.add_argument("--step-name", type=str, required=True, help="Name of the CI step")
    parser.add_argument("--stage", type=str, required=True, choices=["setup", "build", "test"], help="Pipeline stage")
    parser.add_argument("--exit-code", type=int, default=None, help="Step exit code (0=success, non-zero=failure; omit if unavailable/skipped)")
    parser.add_argument("--step-outcome", type=str, default=None, choices=["success", "failure", "skipped", "cancelled", "running"], help="GitHub Actions step outcome")
    parser.add_argument("--workflow-outcome", type=str, default=None, choices=["success", "failure"], help="Overall workflow outcome if known")
    parser.add_argument("--is-final", action="store_true", help="Flag if this is the final checkpoint (100%)")
    parser.add_argument("--log-file", type=str, default=None, help="Path to raw step log file")
    parser.add_argument("--fallback-msg", type=str, default="", help="Fallback log text if log file is missing or empty")

    args = parser.parse_args()

    # Load environment variables
    backend_url = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
    demo_run_id = os.environ.get("DEMO_RUN_ID", "demo_run_manual")
    gha_run_id = os.environ.get("GHA_RUN_ID", "")
    api_key = os.environ.get("API_KEY", "")
    commit_sha = os.environ.get("COMMIT_SHA", "")

    # Alert if running on GitHub Actions with localhost backend URL
    if os.environ.get("GITHUB_ACTIONS") == "true":
        if "127.0.0.1" in backend_url or "localhost" in backend_url:
            print(
                f"WARNING: Running in GitHub Actions runner with local backend URL '{backend_url}'. "
                "If your backend is running on a development machine, ensure secrets.BACKEND_URL is configured "
                "with your public HTTPS tunnel (e.g. ngrok).",
                file=sys.stderr,
            )

    # Read authentic log content
    content = ""
    if args.log_file and os.path.exists(args.log_file):
        try:
            with open(args.log_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            print(f"Warning: Could not read log file {args.log_file}: {e}", file=sys.stderr)

    if not content.strip() and args.fallback_msg:
        content = args.fallback_msg

    if not content.strip():
        if args.step_outcome == "skipped":
            content = f"=== Step '{args.step_name}' was skipped due to earlier stage failure. ==="
        elif args.exit_code is not None:
            content = f"Step '{args.step_name}' completed with exit code {args.exit_code} (outcome: {args.step_outcome or 'unknown'})."
        else:
            content = f"Step '{args.step_name}' recorded with outcome: {args.step_outcome or 'unknown'}."

    now_iso = datetime.now(timezone.utc).isoformat()
    telemetry_event_id = f"chk_{demo_run_id}_{int(args.depth)}_{int(time.time()*1000)}"

    # Construct payload preserving authentic values
    payload = {
        "event_id": telemetry_event_id,
        "log_chunk": content,
        "step_name": args.step_name,
        "stage": args.stage,
        "is_final": bool(args.is_final),
        "exit_code": args.exit_code,
        "step_outcome": args.step_outcome,
        "workflow_outcome": args.workflow_outcome,
        "ci_run_id": str(gha_run_id) if gha_run_id else None,
        "commit_sha": str(commit_sha) if commit_sha else None,
        "depth": int(args.depth),
        "timestamp": now_iso,
    }

    url = f"{backend_url}/api/demo/runs/{demo_run_id}/logs"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    data = json.dumps(payload).encode("utf-8")

    print(f"Reporting Checkpoint {args.depth}% ({args.step_name}) to {url} [run_id: {demo_run_id}, outcome: {args.step_outcome or 'N/A'}]...")
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"Checkpoint {args.depth}% delivered successfully (HTTP {resp.status}).")
    except urllib.error.HTTPError as e:
        print(f"Delivery HTTP error {e.code}: {e.reason}", file=sys.stderr)
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            pass
        if e.code == 404:
            print(f"Hint: Run ID '{demo_run_id}' was not found on backend. Ensure DEMO_RUN_ID matches the active run in the dashboard.", file=sys.stderr)
        elif e.code == 401:
            print("Hint: Unauthorized. Ensure DEMO_API_KEY secret matches the backend DEMO_API_KEY.", file=sys.stderr)
        if body:
            print(f"Server response: {body}", file=sys.stderr)
    except urllib.error.URLError as e:
        print(f"Delivery network error: {e.reason}", file=sys.stderr)
        if "127.0.0.1" in backend_url or "localhost" in backend_url:
            print("Hint: Backend URL is localhost. Update secrets.BACKEND_URL with your public tunnel URL (e.g. ngrok).", file=sys.stderr)
    except Exception as e:
        print(f"Delivery exception: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
