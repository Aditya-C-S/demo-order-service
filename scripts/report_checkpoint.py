"""
report_checkpoint.py — CLI tool to stream CI/CD checkpoint logs to the FastAPI backend.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser(description="Report CI/CD checkpoint logs to predictor backend.")
    parser.add_argument("--depth", type=int, required=True, help="Checkpoint depth percentage (25, 50, 75, 100)")
    parser.add_argument("--step-name", type=str, required=True, help="Name of the CI step")
    parser.add_argument("--stage", type=str, required=True, choices=["setup", "build", "test"], help="Pipeline stage")
    parser.add_argument("--exit-code", type=int, default=0, help="Step exit code (0=success, non-zero=failure)")
    parser.add_argument("--is-final", action="store_true", help="Flag if this is the final checkpoint")
    parser.add_argument("--log-file", type=str, default=None, help="Path to raw step log file")
    parser.add_argument("--fallback-msg", type=str, default="", help="Fallback log text if log file is missing or empty")

    args = parser.parse_args()

    # Load environment variables
    backend_url = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
    demo_run_id = os.environ.get("DEMO_RUN_ID", "demo_run_manual")
    gha_run_id = os.environ.get("GHA_RUN_ID", "")
    api_key = os.environ.get("API_KEY", "")
    commit_sha = os.environ.get("COMMIT_SHA", "")

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
        content = f"Step '{args.step_name}' completed with exit code {args.exit_code}."

    # Construct payload
    payload = {
        "log_chunk": content,
        "step_name": args.step_name,
        "stage": args.stage,
        "is_final": bool(args.is_final),
        "exit_code": int(args.exit_code),
        "ci_run_id": str(gha_run_id) if gha_run_id else None,
        "commit_sha": str(commit_sha) if commit_sha else None,
        "depth": int(args.depth),
    }

    url = f"{backend_url}/api/demo/runs/{demo_run_id}/logs"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")

    print(f"Reporting Checkpoint {args.depth}% ({args.step_name}) to {url}...")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"Checkpoint {args.depth}% delivered successfully (HTTP {resp.status}).")
    except urllib.error.HTTPError as e:
        print(f"Delivery HTTP error {e.code}: {e.reason}", file=sys.stderr)
    except urllib.error.URLError as e:
        print(f"Delivery network error: {e.reason}", file=sys.stderr)
    except Exception as e:
        print(f"Delivery exception: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
