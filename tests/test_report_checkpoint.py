"""
Unit tests for scripts/report_checkpoint.py CLI tool.
"""
import io
import json
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

import pytest

# Add demo-order-service root to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from scripts.report_checkpoint import main


def test_report_checkpoint_success_with_complex_log(monkeypatch):
    """Verify report_checkpoint reads logs with quotes, slashes, and escapes valid JSON."""
    complex_log = (
        '===[ Step: "Test & Lint" ]===\n'
        'Path: C:\\Users\\Runner\\Workspace\n'
        "User 'test-runner' ran command: pytest --tb=short\n"
        'JSON output: {"status": "ok", "passed": 14}\n'
    )
    with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as f:
        f.write(complex_log)
        temp_log = f.name

    try:
        monkeypatch.setenv("BACKEND_URL", "http://testserver:8000")
        monkeypatch.setenv("DEMO_RUN_ID", "run_test_123")
        monkeypatch.setenv("GHA_RUN_ID", "gha_9999")
        monkeypatch.setenv("API_KEY", "secret-test-key")
        monkeypatch.setenv("COMMIT_SHA", "abcdef123456")

        test_args = [
            "report_checkpoint.py",
            "--depth", "25",
            "--step-name", "Runner Environment Initialization",
            "--stage", "setup",
            "--exit-code", "0",
            "--log-file", temp_log,
        ]

        captured_requests = []

        def mock_urlopen(req, timeout=15):
            captured_requests.append(req)
            resp = MagicMock()
            resp.status = 200
            return resp

        with patch("sys.argv", test_args), patch("urllib.request.urlopen", side_effect=mock_urlopen):
            main()

        assert len(captured_requests) == 1
        req = captured_requests[0]
        assert req.get_full_url() == "http://testserver:8000/api/demo/runs/run_test_123/logs"
        assert req.headers["X-api-key"] == "secret-test-key"
        assert req.headers["Content-type"] == "application/json"

        # Decode body and verify valid JSON
        body = json.loads(req.data.decode("utf-8"))
        assert body["depth"] == 25
        assert body["step_name"] == "Runner Environment Initialization"
        assert body["stage"] == "setup"
        assert body["exit_code"] == 0
        assert body["ci_run_id"] == "gha_9999"
        assert body["commit_sha"] == "abcdef123456"
        assert body["is_final"] is False
        assert body["log_chunk"] == complex_log
    finally:
        if os.path.exists(temp_log):
            os.remove(temp_log)


def test_report_checkpoint_fallback_msg_when_file_missing(monkeypatch):
    """Verify report_checkpoint uses fallback-msg when log file does not exist."""
    monkeypatch.setenv("BACKEND_URL", "http://testserver:8000")
    monkeypatch.setenv("DEMO_RUN_ID", "run_test_456")

    test_args = [
        "report_checkpoint.py",
        "--depth", "100",
        "--step-name", "Run Test Suite",
        "--stage", "test",
        "--exit-code", "1",
        "--is-final",
        "--log-file", "/nonexistent/path/missing.log",
        "--fallback-msg", "Pytest execution failed with exit code 1",
    ]

    captured_requests = []

    def mock_urlopen(req, timeout=15):
        captured_requests.append(req)
        resp = MagicMock()
        resp.status = 200
        return resp

    with patch("sys.argv", test_args), patch("urllib.request.urlopen", side_effect=mock_urlopen):
        main()

    assert len(captured_requests) == 1
    req = captured_requests[0]
    body = json.loads(req.data.decode("utf-8"))
    assert body["depth"] == 100
    assert body["is_final"] is True
    assert body["exit_code"] == 1
    assert body["log_chunk"] == "Pytest execution failed with exit code 1"
