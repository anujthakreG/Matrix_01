# MATRIX Intel — Cybercrime Spatial Forecasting & Tactical Triage Console

**IBM Z Datathon 2026**

MATRIX Intel is an end-to-end intelligence and investigation console designed to predict cash-out withdrawal hotspots for cybercrime syndicates across India. Running natively on **IBM LinuxONE Community Cloud (`s390x`)**, MATRIX Intel integrates database transaction graph analysis, machine learning spatio-temporal forecasting, and an operational tactical triage dashboard.

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                        IBM LinuxONE (s390x)                            │
│                                                                        │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │               CYBER-TRAC Tactical Dashboard                    │   │
│   │          (Vanilla HTML5 / Modern CSS / ES Modules)             │   │
│   │         Served directly at /dashboard or standalone            │   │
│   └───────────────────────────────┬────────────────────────────────┘   │
│                                   │ Fetch API / JSON                   │
│   ┌───────────────────────────────▼────────────────────────────────┐   │
│   │                    FastAPI Backend Engine                      │   │
│   │                  (Uvicorn ASGI / Port 8000)                    │   │
│   │   - GET /api/v1/health                                         │   │
│   │   - GET /api/v1/cases (Filter, pagination)                     │   │
│   │   - GET /api/v1/dashboard/summary (Executive telemetry)        │   │
│   │   - GET /api/v1/transactions/{id}/network (Directed DAG)       │   │
│   │   - POST /api/v1/predictions (ML Inference Trigger)           │   │
│   │   - GET /api/incidents (Compatibility route)                   │   │
│   └───────────────────────┬───────────────────┬────────────────────┘   │
│                           │                   │                        │
│            SQLAlchemy 2.0 │                   │ Model Loader Hook      │
│                           ▼                   ▼                        │
│             ┌───────────────────┐   ┌──────────────────────────────┐   │
│             │  SQLite Database  │   │   ML Pipeline                │   │
│             │  data/matrix.db   │   │  (Scikit-Learn / joblib)     │   │
│             │  (Preserved Cases)│   │  Withdrawal Hotspot Forecast │   │
│             └───────────────────┘   └──────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Live Deployment (IBM LinuxONE)

- **Tactical Dashboard:** `http://148.100.112.215:8000/dashboard/`
- **Interactive OpenAPI Documentation:** `http://148.100.112.215:8000/docs`
- **System Health & Hardware Telemetry:** `http://148.100.112.215:8000/api/v1/health`
- **Architecture:** IBM LinuxONE `s390x` (Ubuntu 24.04 LTS, CPACF Accelerated)
- **Daemon Management:** `systemd` unit `matrix-intel.service` (auto-restarting on reboot)

---

## Key Capabilities & Integration Points

1. **Deterministic Database Engine:**
   - Path resolution anchored via `PROJECT_ROOT` relative to `backend/app/db/session.py`, preventing working-directory drift.
   - Synthetic ground truth case `SYN-CASE-2026-001` preserved intact with linked financial transactions and coordinates.
2. **Predictive ML Inference Engine (`POST /api/v1/predictions`):**
   - Seamlessly calls `predict_candidate_locations` pipeline.
   - Computes probability distribution over withdrawal hotspots, assessed risk level (`low`, `medium`, `high`, `critical`), and model explanations.
   - Fully persisted in `predictions` table for historical auditability.
3. **Directed Money Mule DAG Visualizer:**
   - Visualizes multi-hop layering transfers from victim accounts through intermediate suspect mule nodes to flagged cash-out endpoints (`GET /api/v1/transactions/{id}/network`).
4. **Tactical GIS & Interactive Map:**
   - Renders 5-10 minute movement perimeters and predicted cash-out cluster hotspots on Leaflet with vector patrol lines and schematic offline fallback.
5. **Simulation Safeguards:**
   - Dispatches and switch-hold requests remain simulation-only, labeled with clear operational caveats to prevent unauthorized external action.

---

## Directory Structure

```
Matrix_01/
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/       # FastAPI routes (cases, predictions, transactions, dashboard)
│   │   ├── core/                   # Configuration & error handlers (CORS, jsonable_encoder)
│   │   ├── db/                     # Models, Base, SessionLocal, and table initializers
│   │   ├── ml/                     # ML inference, model loader, preprocessing, training
│   │   ├── schemas/                # Strict Pydantic contracts
│   │   ├── services/               # Case, dashboard, and ML prediction business logic
│   │   └── main.py                 # FastAPI application factory, static mount, and routes
│   ├── artifacts/                  # Trained ML binaries (withdrawal_predictor.joblib, metadata.json)
│   ├── requirements.txt            # Python dependencies
│   └── tests/                      # 50 automated pytest contract and integration tests
├── data/
│   └── matrix.db                   # SQLite database (preserved synthetic cases)
├── frontend/
│   ├── index.html                  # Cyber-TRAC tactical situational awareness console
│   ├── css/                        # Design tokens, layout, and component styling
│   ├── js/                         # API client, app orchestrator, map engine, mule graph
│   └── data/                       # Supplementary demo records (mock-incidents.json)
└── README.md                       # Complete project and deployment documentation
```

---

## Local Development & Startup

### 1. Environment Setup

```bash
# Clone the repository
git clone -b feature/ml-backend-integration https://github.com/anujthakreG/Matrix_01.git
cd Matrix_01

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r backend/requirements.txt pytest
```

### 2. Verify Database & Generate ML Model (if training locally)

```bash
# Generate training data & train ML predictor
python -m backend.app.ml.synthetic --rows 5000 --seed 42 --force
python -m backend.app.ml.train

# Run automated test suite (50 tests)
pytest backend/tests -v
```

### 3. Launch Local Server

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

- Access API documentation: `http://localhost:8000/docs`
- Access Tactical Dashboard: `http://localhost:8000/dashboard/`

---

## Verification Summary

- **Automated Pytest Suite:** 50 passed in 2.60s on IBM LinuxONE `s390x`.
- **API Health:** HTTP 200 OK (`{"status":"healthy","database":"connected","ml_service":"ready"}`).
- **Synthetic Ground Truth:** `SYN-CASE-2026-001` retrieved with 2 linked transactions and candidate locations.
- **ML Pipeline:** Live inference verified returning ranked candidate locations, risk assessment, and reporting delay.
- **Tactical Dashboard:** Accessible remotely on `http://148.100.112.215:8000/dashboard/`.
