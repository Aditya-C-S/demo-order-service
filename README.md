# Demo Order Service (`demo-order-service`)

A lightweight Python microservice engineered for end-to-end demonstration of the **AI-Powered CI/CD Pipeline Failure Predictor & Assisted Root Cause Analysis** capstone project.

This repository serves as a target service to demonstrate real Git commits, static AST call-graph extraction into Neo4j, pre-build metadata risk scoring, GitHub Actions workflow execution, live log chunk ingestion at 4 progressive checkpoints (25%, 50%, 75%, 100%), Parser V2 failure classification, and automated RCA/remediation generation.

---

## 1. Module Architecture & Dependencies

```text
demo-order-service/
├── .github/
│   └── workflows/
│       └── demo_pipeline.yml       # 4-stage streaming GitHub Actions workflow
├── src/
│   ├── __init__.py                 # Package root
│   ├── config.py                   # Currency, regional tax, and failure switch
│   ├── exceptions.py               # Custom domain exceptions (OrderServiceError)
│   ├── validator.py                # Line-item validation & schema gatekeeper
│   ├── processor.py                # Total, tax, and discount computation
│   └── order_service.py            # Orchestrator API for create/cancel order
├── tests/
│   ├── __init__.py
│   ├── test_validator.py           # Unit tests for schema and tax lookup
│   └── test_order_service.py       # Integration tests & controlled failure assertion
├── requirements.txt                # pytest dependency
├── .gitignore
└── README.md
```

### Static Call Relationships for AST Blast Radius
- `order_service.create_order()` calls `validator.validate_order_payload()` and `processor.compute_order_totals()`.
- `processor.compute_order_totals()` calls `validator.validate_item_structure()` and `validator.calculate_tax_rate()`.
- `tests/test_order_service.py` calls `order_service.create_order()`.
- When changes are introduced to `src/validator.py`, the Neo4j blast radius engine discovers direct callers across `src/processor.py`, `src/order_service.py`, and the test suite.

---

## 2. Local Testing

Run unit and integration tests using pytest:

```bash
# Standard baseline run (100% Passing)
pytest tests/ -v
```

Expected output:
```text
tests/test_validator.py::test_validate_item_structure_success PASSED
tests/test_validator.py::test_validate_item_structure_invalid_sku PASSED
...
tests/test_order_service.py::test_create_order_end_to_end_success PASSED
tests/test_order_service.py::test_controlled_failure_scenario PASSED
============================== 14 passed in 0.12s ==============================
```

---

## 3. Controlled Failure Scenarios for Demo

You can demonstrate both a successful build and a controlled failure without rewriting codebase logic:

### Option A: Environment Variable Switch (Recommended for Workflow Dispatch)
When triggering the workflow manually in GitHub Actions, set the input:
- `inject_failure`: `1`

Or run locally:
```bash
# Windows PowerShell
$env:INJECT_DEMO_FAILURE="1"; pytest tests/ -v; Remove-Item Env:\INJECT_DEMO_FAILURE

# Linux / Bash
INJECT_DEMO_FAILURE=1 pytest tests/ -v
```
This forces `test_controlled_failure_scenario` and `validate_order_payload` to reject execution with a clear `ValidationError` and `AssertionError`.

### Option B: Real Code Change (Demonstrating Pull Request Gatekeeping)
Modify `src/validator.py` (e.g., modifying `validate_item_structure` or `calculate_tax_rate` to raise an unexpected exception or change a return value). Commit this change to a demo branch:
```bash
git checkout -b demo/failing-change
# edit src/validator.py
git commit -am "fix(validator): update line item validation rules"
git push origin demo/failing-change
```

---

## 4. AST Graph Inspection

The repository structure can be inspected using the Neo4j Code Blast Radius engine:
1. Open the dashboard at `http://127.0.0.1:8000`.
2. Under the **Unified Demo** tab, select **demo-order-service** in the repository dropdown.
3. Set the changed file to `src/validator.py`.
4. Click **Start Demo Run**.
5. Click **Open Full Graph** to view the interactive full-screen Cytoscape graph showing file, function, and class nodes.

---

## 5. GitHub Actions Live Log Delivery

The workflow `.github/workflows/demo_pipeline.yml` reports 4 sequential checkpoints to the FastAPI backend:

| Checkpoint | Pipeline Stage | Step Name | Content Reported |
| :---: | :---: | :---: | :--- |
| **25%** | `setup` | `Runner Initialization` | OS, Python version, runner ID, and commit SHA. |
| **50%** | `build` | `Install Dependencies` | Pip package installation outcome and exit code. |
| **75%** | `build` | `Validate Environment` | Static syntax verification of all `src/` modules. |
| **100%** | `test` | `Run Test Suite` | Full pytest stdout/stderr, test counts, exit code, and failure traceback. Triggers Parser V2 & RCA. |

### Required GitHub Repository Secrets (Configured on GitHub)

When pushing this repository to GitHub, configure these repository secrets under **Settings → Secrets and variables → Actions**:

| Secret Name | Example Value | Description |
| :--- | :--- | :--- |
| `BACKEND_URL` | `https://xxxx.ngrok-free.app` | The public HTTPS tunnel forwarding traffic to your local FastAPI backend (`http://127.0.0.1:8000`). |
| `DEMO_RUN_ID` | `demo_run_20261027_...` | Optional default run ID if not triggering via `workflow_dispatch`. |

---

## 6. Run Correlation

Correlation connects the remote GitHub runner with your active dashboard session:
1. **Demo Run ID (`demo_run_id`)**: Created by the dashboard when clicking "Start Demo Run" (e.g. `demo_run_20261027_143012_abc123`).
2. **GitHub Actions Run ID (`ci_run_id`)**: Generated by GitHub (`${{ github.run_id }}`), transmitted in every POST request.
3. **Commit SHA (`commit_sha`)**: Extracted from `${{ github.sha }}` and logged against the run.

---

## 7. Remaining Manual Steps for Live Demonstration

1. Create a remote GitHub repository named `demo-order-service`.
2. Add the remote and push:
   ```bash
   git remote add origin https://github.com/<your-username>/demo-order-service.git
   git branch -M main
   git push -u origin main
   ```
3. Start a secure tunnel to your local backend:
   ```bash
   ngrok http 8000
   ```
4. Copy the resulting HTTPS forwarding URL (e.g. `https://xxxx.ngrok-free.app`) and save it as secret `BACKEND_URL` in the GitHub repository.
5. In the dashboard, click **Start Demo Run**, copy the generated `Run ID`, and trigger the GitHub Actions workflow using `workflow_dispatch` with that `demo_run_id`.
