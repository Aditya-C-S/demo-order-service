"""
report_checkpoint.py — CLI tool to stream CI/CD checkpoint logs to the FastAPI backend.
Transmits authentic captured stdout/stderr from GitHub Actions runner to the predictor backend.
Handles automatic run registration, connectivity checks, and idempotent retries.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

RUN_ID_CACHE_FILE = Path("/tmp/demo_run_id.txt")


def get_headers(api_key: str = "") -> dict:
    headers = {
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true",
    }
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def check_backend_health(backend_url: str, api_key: str = "") -> bool:
    """Verify backend connectivity and health."""
    health_url = f"{backend_url}/health"
    headers = get_headers(api_key)
    try:
        req = urllib.request.Request(health_url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                print(f"Backend connectivity verified: {body.get('service', 'FastAPI')} (v{body.get('version', '2.0')})")
                return True
    except Exception as e:
        print(f"ERROR: Cannot reach backend health check at {health_url}: {e}", file=sys.stderr)
        return False
    return False


def register_run_on_backend(
    backend_url: str,
    repo_id: str,
    commit_sha: str,
    branch: str = "main",
    gha_run_id: str = "",
    preferred_run_id: str = "",
    api_key: str = "",
) -> str:
    """Register or validate run on the backend and return the active run_id."""
    # 1. If preferred_run_id is specified, verify if it already exists
    headers = get_headers(api_key)
    if preferred_run_id and preferred_run_id != "demo_run_manual":
        verify_url = f"{backend_url}/api/demo/runs/{preferred_run_id}"
        try:
            req = urllib.request.Request(verify_url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    print(f"Confirmed existing active run ID on backend: {preferred_run_id}")
                    return preferred_run_id
        except Exception:
            pass  # Will register below

    # 2. Register run with backend
    create_url = f"{backend_url}/api/demo/runs"
    payload = {
        "repo_id": repo_id or "Aditya-C-S/demo-order-service",
        "commit_sha": commit_sha or "HEAD",
        "branch": branch or "main",
        "is_pr": False,
        "runtime_model": "logistic_regression",
        "auto_advance": False,
    }
    data = json.dumps(payload).encode("utf-8")
    try:
        req = urllib.request.Request(create_url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status in (200, 201):
                res_data = json.loads(resp.read().decode("utf-8"))
                new_run_id = res_data.get("run_id")
                print(f"Successfully registered new run on backend: {new_run_id}")
                return new_run_id
    except Exception as e:
        print(f"WARNING: Run registration request failed: {e}", file=sys.stderr)

    return preferred_run_id or "demo_run_manual"


def persist_run_id(run_id: str) -> None:
    """Persist run ID to file and GITHUB_ENV so subsequent steps inherit it."""
    try:
        RUN_ID_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(RUN_ID_CACHE_FILE, "w", encoding="utf-8") as f:
            f.write(run_id.strip())
    except Exception:
        pass

    github_env = os.environ.get("GITHUB_ENV")
    if github_env and os.path.exists(github_env):
        try:
            with open(github_env, "a", encoding="utf-8") as f:
                f.write(f"\nDEMO_RUN_ID={run_id.strip()}\n")
            print(f"Exported DEMO_RUN_ID={run_id.strip()} to $GITHUB_ENV")
        except Exception as e:
            print(f"Warning: Could not append to GITHUB_ENV: {e}", file=sys.stderr)


def resolve_run_id(candidate_id: str) -> str:
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


def main():
    parser = argparse.ArgumentParser(description="Report CI/CD checkpoint logs to predictor backend.")
    parser.add_argument("--init-run", action="store_true", help="Initialize/register run with backend and check connectivity")
    parser.add_argument("--depth", type=int, choices=[25, 50, 75, 100], help="Checkpoint depth percentage (25, 50, 75, 100)")
    parser.add_argument("--step-name", type=str, default="Execute Step", help="Name of the CI step")
    parser.add_argument("--stage", type=str, default="execution", choices=["setup", "build", "test", "execution"], help="Pipeline stage")
    parser.add_argument("--exit-code", type=int, default=None, help="Step exit code (0=success, non-zero=failure)")
    parser.add_argument("--step-outcome", type=str, default=None, choices=["success", "failure", "skipped", "cancelled", "running"], help="Step outcome")
    parser.add_argument("--workflow-outcome", type=str, default=None, choices=["success", "failure"], help="Overall workflow outcome")
    parser.add_argument("--is-final", action="store_true", help="Flag if this is the final checkpoint (100%)")
    parser.add_argument("--api-key", type=str, default="", help="API key for authentication")
    parser.add_argument("--log-file", type=str, default=None, help="Path to raw step log file")
    parser.add_argument("--fallback-msg", type=str, default="", help="Fallback log text if log file is missing or empty")

    args = parser.parse_args()

    backend_url = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000").rstrip("/")
    api_key = args.api_key or os.environ.get("API_KEY") or os.environ.get("DEMO_API_KEY", "")
    commit_sha = os.environ.get("COMMIT_SHA") or os.environ.get("GITHUB_SHA", "")
    gha_run_id = os.environ.get("GHA_RUN_ID") or os.environ.get("GITHUB_RUN_ID", "")
    branch = os.environ.get("BRANCH") or os.environ.get("GITHUB_REF_NAME", "main")
    repo_id = os.environ.get("REPO") or os.environ.get("GITHUB_REPOSITORY", "Aditya-C-S/demo-order-service")
    raw_demo_run_id = os.environ.get("DEMO_RUN_ID", "").strip()

    # Pre-flight check on runner environment
    if os.environ.get("GITHUB_ACTIONS") == "true":
        if "127.0.0.1" in backend_url or "localhost" in backend_url:
            print(
                f"WARNING: Running in GitHub Actions runner with local backend URL '{backend_url}'. "
                "Ensure secrets.BACKEND_URL is configured with your public HTTPS tunnel.",
                file=sys.stderr,
            )

    # 1. Handle Run Initialization Mode
    if args.init_run:
        print("=== Initializing Predictor Run Handshake ===")
        healthy = check_backend_health(backend_url, api_key)
        if not healthy:
            print("WARNING: Backend health check failed. Subsequent checkpoint delivery may be affected.", file=sys.stderr)

        active_run_id = register_run_on_backend(
            backend_url=backend_url,
            repo_id=repo_id,
            commit_sha=commit_sha,
            branch=branch,
            gha_run_id=gha_run_id,
            preferred_run_id=raw_demo_run_id,
            api_key=api_key,
        )
        persist_run_id(active_run_id)
        print(f"Predictor Handshake Complete. Active Run ID: {active_run_id}")
        return

    # 2. Checkpoint Delivery Mode
    if args.depth is None:
        parser.error("--depth is required when not using --init-run")

    demo_run_id = resolve_run_id(raw_demo_run_id)

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
    headers = get_headers(api_key)
    data = json.dumps(payload).encode("utf-8")

    print(f"Reporting Checkpoint {args.depth}% ({args.step_name}) to {url} [run_id: {demo_run_id}, outcome: {args.step_outcome or 'N/A'}]...")

    def _deliver(target_url, target_id):
        nonlocal data
        if target_id != demo_run_id:
            payload["event_id"] = f"chk_{target_id}_{int(args.depth)}_{int(time.time()*1000)}"
            data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(target_url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status

    try:
        status_code = _deliver(url, demo_run_id)
        print(f"Checkpoint {args.depth}% delivered successfully (HTTP {status_code}).")
    except urllib.error.HTTPError as e:
        print(f"Delivery HTTP error {e.code}: {e.reason}", file=sys.stderr)
        if e.code == 404:
            # Self-healing: auto-register run and retry delivery once!
            print(f"Run ID '{demo_run_id}' not found on backend. Auto-registering and retrying...", file=sys.stderr)
            recovered_id = register_run_on_backend(
                backend_url=backend_url,
                repo_id=repo_id,
                commit_sha=commit_sha,
                branch=branch,
                gha_run_id=gha_run_id,
                preferred_run_id="",  # Request new valid ID
                api_key=api_key,
            )
            persist_run_id(recovered_id)
            retry_url = f"{backend_url}/api/demo/runs/{recovered_id}/logs"
            try:
                retry_code = _deliver(retry_url, recovered_id)
                print(f"Checkpoint {args.depth}% delivered successfully on retry to run '{recovered_id}' (HTTP {retry_code}).")
            except Exception as retry_err:
                print(f"Retry delivery failed: {retry_err}", file=sys.stderr)
        elif e.code == 401:
            print("Hint: Unauthorized. Ensure DEMO_API_KEY secret matches the backend DEMO_API_KEY.", file=sys.stderr)
    except urllib.error.URLError as e:
        print(f"Delivery network error: {e.reason}", file=sys.stderr)
    except Exception as e:
        print(f"Delivery exception: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
