MATRIX Intel Backend
Backend API, database, and machine-learning integration documentation
The MATRIX Intel backend is a predictive analytics system developed for the IBM Z Datathon 2026. It analyzes authorized cybercrime complaint records, transaction flows, and mule account behaviors to forecast candidate cash-withdrawal locations (e.g. ATM hubs, bank branches) to help law-enforcement and cyber-investigation teams prioritize cases.
The application is built with FastAPI, Pydantic v2, and SQLAlchemy 2.0, designed for deployment on IBM LinuxONE Community Cloud (s390x architecture / Red Hat Enterprise Linux / Ubuntu).
1. System Architecture
The backend exposes versioned REST APIs for case management, transaction-network analysis, dashboard metrics, geographic queries, and machine-learning predictions.
Component	Responsibility
Backend API and database	FastAPI routes, request/response schemas, database models, service logic, CORS configuration, and automated tests
Machine-learning pipeline	Data preprocessing, feature engineering, model training and evaluation, artifact management, and inference
Frontend dashboard	User interface that consumes the backend's versioned API endpoints


2. Directory Structure
backend/
├── .env.example                 # Template for environment configuration (no secrets)
├── requirements.txt             # Python dependencies
├── README.md                    # Setup, configuration, and endpoint contracts
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI application entrypoint, lifespan, CORS, error handlers
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py            # Centralized Settings via Pydantic BaseSettings
│   │   └── errors.py            # Custom exceptions and standardized error response formatting
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py              # DeclarativeBase definition
│   │   ├── session.py           # SQLAlchemy engine, session maker, get_db dependency
│   │   ├── models.py            # ORM models (CaseModel, TransactionModel, LocationModel, PredictionRecordModel)
│   │   └── init_db.py           # Table initialization CLI and optional synthetic seed utility
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── common.py            # Generic pagination, error response, and health schemas
│   │   ├── cases.py             # CaseBase, CaseCreate, CaseResponse, CaseDetailResponse
│   │   ├── transactions.py      # TransactionResponse, NetworkNode, NetworkEdge, TransactionNetworkResponse
│   │   ├── locations.py         # LocationResponse schema with mandatory disclaimers
│   │   ├── dashboard.py         # DashboardSummaryResponse (strictly computed from verified data)
│   │   └── predictions.py       # PredictionRequest, CandidateLocation, PredictionResponse, StoredPredictionResponse
│   ├── services/
│   │   ├── __init__.py
│   │   ├── case_service.py      # Case retrieval, filtering, search, and pagination logic
│   │   ├── dashboard_service.py # Aggregated metrics calculation directly from database
│   │   ├── location_service.py  # Geographic query and hotspot filtering service
│   │   ├── transaction_service.py# Transaction network graph topology generator
│   │   └── ml_service.py        # ML interface boundary, model readiness check, and prediction execution
│   └── api/
│       ├── __init__.py
│       └── v1/
│           ├── __init__.py
│           ├── api.py           # Aggregated v1 router
│           └── endpoints/
│               ├── __init__.py
│               ├── health.py    # Health check and dependency diagnostics
│               ├── dashboard.py # Aggregated dashboard metrics
│               ├── cases.py     # Case list, search, details, and creation
│               ├── predictions.py# ML prediction triggering and stored forecast retrieval
│               ├── locations.py # Incident coordinates and candidate withdrawal points
│               └── transactions.py# Case transaction relationship network visualizer
└── tests/
    ├── __init__.py
    ├── conftest.py              # In-memory SQLite fixtures, sample data, and test client
    ├── test_health.py           # Health and root endpoint tests
    ├── test_dashboard.py        # Verification of un-fabricated summary metrics
    ├── test_cases.py            # Pagination, filtering, search, and retrieval tests
    ├── test_predictions.py      # ML unavailable 503 handling, inference execution, and persistence
    ├── test_locations.py        # Location querying and disclaimer verification
    ├── test_transactions.py     # Graph network nodes/edges and empty topology handling
    └── test_cors_and_errors.py  # CORS policy and 422 error schema tests

3. Quickstart & Installation
Prerequisites
- Python 3.10+ (tested on Python 3.13)
- Git
- Virtual environment tool (venv)
1. Create and Activate Virtual Environment
# On Linux / macOS / IBM LinuxONE:
python3 -m venv .venv
source .venv/bin/activate

# On Windows (PowerShell):
python -m venv .venv
.venv\Scripts\Activate.ps1
2. Install Dependencies
pip install -r backend/requirements.txt
3. Configure Environment Variables
# Copy example configuration
cp backend/.env.example backend/.env
Review and adjust backend/.env:
ENVIRONMENT=development
DEBUG=true
PORT=8000
HOST=0.0.0.0
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
DATABASE_URL=sqlite:///./data/matrix.db
ML_MODEL_ENABLED=false
4. Initialize Database Schema
# Create empty tables:
python -m backend.app.db.init_db

# (Optional) Seed minimal synthetic development sample data:
python -m backend.app.db.init_db --seed
5. Run the API Server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
The interactive OpenAPI documentation will be available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health check: http://localhost:8000/api/v1/health
4. Database Integration & Production Compatibility
Local Development vs Production
- Local Development: Uses SQLite (sqlite:///./data/matrix.db). Fast, zero-setup, and automatically creates the local storage directory.
- IBM LinuxONE Production: Compatible with PostgreSQL (postgresql+psycopg2://...) or IBM Db2 (ibm_db_sa://...) via standard SQLAlchemy connection strings.
- Testing: Automated tests run against isolated in-memory SQLite instances (sqlite:///:memory: with StaticPool), ensuring zero pollution of disk databases.
Relational Schema Design
1. cases table: Stores cybercrime complaint records (title, description, category, status, priority, reported amount, victim location, incident timestamps).
   - Indexed on: case_number (unique), status, priority, category, incident_date, victim_state, victim_district.
2. transactions table: Stores financial money flows between victim and suspect mule accounts.
   - Indexed on: case_id, receiver_account, transaction_time.
3. locations table: Stores geographic coordinates for reported incident locations and forecasted withdrawal candidate points.
   - Indexed on: case_id, location_type, is_predicted, state, district.
4. predictions table: Persists audit logs of ML inference executions, input features, and forecasted candidate coordinates.
   - Indexed on: prediction_uuid (unique), case_id.
5. Machine-Learning Interface
The API layer in backend/app/services/ml_service.py is decoupled from the model implementation and uses the following inference contract:
1. Function / Callable Signature
The inference module should expose a callable such as backend.app.ml.inference:
def predict_candidate_locations(features: dict) -> dict:
    ...
2. Input Features Payload
{
  "case_id": 1,
  "case_number": "CASE-2026-0001",
  "reported_amount": 150000.0,
  "category": "vishing",
  "victim_state": "Delhi",
  "victim_district": "New Delhi",
  "complaint_narrative": "Victim received call asking for KYC verification...",
  "source_channel": "UPI",
  "mule_accounts": ["ACC-MULE-3301", "ACC-MULE-8840"],
  "origin_latitude": 28.6315,
  "origin_longitude": 77.2167,
  "overrides": {}
}
3. Expected Return Payload
{
  "model_version": "v1.0-lightgbm-geo",
  "risk_score": 0.88,
  "risk_level": "high",
  "candidate_locations": [
    {
      "name": "ATM Cluster #18 - Noida Sector 18",
      "latitude": 28.5708,
      "longitude": 77.3271,
      "district": "Gautam Buddha Nagar",
      "state": "Uttar Pradesh",
      "confidence_score": 0.84,
      "withdrawal_window_hours": 3.0
    }
  ],
  "key_risk_factors": [
    "Rapid multi-hop transfer velocity",
    "Known mule account cluster",
    "Out-of-state withdrawal pattern"
  ],
  "explanation": "High velocity multi-hop transfer indicates immediate cash-out intent."
}
4. Availability & Error Handling
- When ML model is not ready: If ML_MODEL_ENABLED=false or the model is not initialized, POST /api/v1/predictions returns HTTP 503 Service Unavailable:{
    "status": "error",
    "error_code": "ML_MODEL_UNAVAILABLE",
    "detail": "ML inference model is currently not ready or unavailable. The ML inference model is not yet initialized or available.",
    "path": "/api/v1/predictions",
    "timestamp": "2026-10-17T11:00:00Z"
  }
  The API never fabricates dummy scores or claims a prediction succeeded when the model is not ready.
- Mandatory Disclaimers: All candidate withdrawal locations are explicitly labeled: "Predicted candidate location only - not confirmed cash withdrawal or proof of criminal activity."
6. Frontend Developer Integration Guide
Base URL & Versioning
All API endpoints are versioned under /api/v1. Base URL: http://localhost:8000/api/v1
CORS Policy
CORS origins are configured via CORS_ORIGINS in .env. By default, Vite (http://localhost:5173) and React (http://localhost:3000) dev servers are allowed. Wildcard (*) is strictly rejected in production environments.
Standard Response Schemas
Pagination Envelope (PaginatedResponse[T])
Used by list endpoints (e.g. GET /api/v1/cases):
{
  "items": [ ... ],
  "total": 42,
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
Error Envelope (ErrorResponse)
Returned on 4xx and 5xx errors:
{
  "status": "error",
  "error_code": "RESOURCE_NOT_FOUND",
  "detail": "Case with identifier '999' was not found.",
  "path": "/api/v1/cases/999",
  "timestamp": "2026-10-17T11:00:00Z",
  "meta": null
}
7. API Endpoint Reference
1. GET /api/v1/health
- Purpose: Diagnostic health check reporting backend, DB, and ML service status.
- Query / Body: None.
- Status Codes: 200 OK.
- Example Response:{
    "status": "healthy",
    "app_name": "MATRIX Intel API",
    "version": "1.0.0",
    "environment": "development",
    "database": "connected",
    "ml_service": "uninitialized",
    "timestamp": "2026-10-17T11:00:00Z"
  }
2. GET /api/v1/dashboard/summary
- Purpose: Aggregated cybercrime summary indicators derived strictly from verified database records.
- Query / Body: None.
- Status Codes: 200 OK.
- Example Response:{
    "total_cases": 12,
    "total_cases_open": 8,
    "total_cases_under_investigation": 3,
    "total_cases_closed": 1,
    "high_risk_cases_count": 5,
    "total_defrauded_amount": 1850000.0,
    "total_suspect_accounts": 19,
    "total_transactions_flagged": 27,
    "total_candidate_withdrawal_locations": 9,
    "cases_by_category": {
      "phishing": 5,
      "vishing": 4,
      "investment_scam": 3
    },
    "cases_by_priority": {
      "high": 4,
      "critical": 1,
      "medium": 7
    },
    "last_updated": "2026-10-17T11:00:00Z"
  }
3. GET /api/v1/cases
- Purpose: List cases with pagination, search, and multi-field filtering.
- Query Parameters:
  - page (int, default 1, ge=1): Page number.
  - page_size (int, default 20, ge=1, le=100): Page limit.
  - status (string, optional): Filter by open, under_investigation, closed.
  - priority (string, optional): Filter by low, medium, high, critical.
  - category (string, optional): Filter by category substring (e.g. phishing).
  - search (string, optional): Search keyword matched across case number, title, description, district, or state.
  - date_from (ISO 8601 datetime, optional): Earliest incident timestamp.
  - date_to (ISO 8601 datetime, optional): Latest incident timestamp.
- Status Codes: 200 OK, 422 Validation Error.
- Example Response:{
    "items": [
      {
        "id": 1,
        "case_number": "SYN-CASE-2026-001",
        "title": "Unauthorized UPI Transfer via Vishing",
        "description": "Victim deceived by fake automated KYC renewal call.",
        "category": "vishing",
        "status": "open",
        "priority": "high",
        "reported_amount": 150000.0,
        "currency": "INR",
        "victim_state": "Delhi",
        "victim_district": "New Delhi",
        "incident_date": "2026-10-17T08:00:00Z",
        "reported_at": "2026-10-17T10:00:00Z",
        "created_at": "2026-10-17T10:05:00Z",
        "updated_at": "2026-10-17T10:05:00Z",
        "transactions_count": 2,
        "locations_count": 2
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20,
    "total_pages": 1
  }
4. GET /api/v1/cases/{case_id}
- Purpose: Retrieve complete case dossier including linked transactions and coordinates.
- Path Parameter: case_id (int, ge=1).
- Status Codes: 200 OK, 404 Not Found, 422 Validation Error.
- Example Response:{
    "id": 1,
    "case_number": "SYN-CASE-2026-001",
    "title": "Unauthorized UPI Transfer via Vishing",
    "description": "Victim deceived by fake automated KYC renewal call.",
    "category": "vishing",
    "status": "open",
    "priority": "high",
    "reported_amount": 150000.0,
    "currency": "INR",
    "victim_state": "Delhi",
    "victim_district": "New Delhi",
    "incident_date": "2026-10-17T08:00:00Z",
    "reported_at": "2026-10-17T10:00:00Z",
    "created_at": "2026-10-17T10:05:00Z",
    "updated_at": "2026-10-17T10:05:00Z",
    "transactions_count": 2,
    "locations_count": 2,
    "transactions": [
      {
        "id": 1,
        "case_id": 1,
        "sender_account": "ACC-VICTIM-9912",
        "receiver_account": "ACC-MULE-3301",
        "amount": 150000.0,
        "currency": "INR",
        "channel": "UPI",
        "transaction_time": "2026-10-17T08:15:00Z",
        "is_suspicious": true,
        "mule_risk_score": 0.88,
        "created_at": "2026-10-17T10:05:00Z"
      }
    ],
    "locations": [
      {
        "id": 1,
        "case_id": 1,
        "name": "Candidate ATM Hub - Sector 18",
        "location_type": "candidate_withdrawal",
        "address": "Sector 18 Commercial Belt",
        "district": "Gautam Buddha Nagar",
        "state": "Uttar Pradesh",
        "latitude": 28.5708,
        "longitude": 77.3271,
        "risk_score": 0.84,
        "is_predicted": true,
        "confidence": 0.81,
        "disclaimer": "Predicted candidate location only - not confirmed cash withdrawal or proof of criminal activity.",
        "created_at": "2026-10-17T10:05:00Z"
      }
    ]
  }
5. POST /api/v1/predictions
- Purpose: Request cash-withdrawal location forecasts and risk evaluation from ML module.
- Request Body (PredictionRequest):{
    "case_id": 1,
    "reported_amount": 150000.0,
    "complaint_narrative": "Victim reports unauthorized UPI debits to suspect accounts.",
    "source_channel": "UPI",
    "mule_accounts": ["ACC-MULE-3301", "ACC-MULE-8840"],
    "origin_latitude": 28.6315,
    "origin_longitude": 77.2167
  }
- Status Codes: 200 OK, 404 Not Found (Case missing), 422 Validation Error, 503 Service Unavailable (Model not ready).
- Example Response:{
    "prediction_id": "PRED-8A3F2C10E45B",
    "case_id": 1,
    "model_version": "v1.0-lightgbm-geo",
    "risk_score": 0.88,
    "risk_level": "high",
    "candidate_locations": [
      {
        "name": "Candidate ATM Hub - Sector 18",
        "latitude": 28.5708,
        "longitude": 77.3271,
        "district": "Gautam Buddha Nagar",
        "state": "Uttar Pradesh",
        "confidence_score": 0.84,
        "withdrawal_window_hours": 3.0,
        "disclaimer": "Predicted candidate location only - not confirmed cash withdrawal or proof of criminal activity."
      }
    ],
    "key_risk_factors": [
      "Rapid multi-hop transfer velocity",
      "Known mule account hub"
    ],
    "disclaimer": "Predicted candidate location only - not confirmed cash withdrawal or proof of criminal activity.",
    "created_at": "2026-10-17T11:00:00Z"
  }
6. GET /api/v1/predictions/{prediction_id}
- Purpose: Retrieve a previously computed and stored prediction record by UUID or ID.
- Path Parameter: prediction_id (string).
- Status Codes: 200 OK, 404 Not Found.
7. GET /api/v1/locations
- Purpose: Query reported incident points and candidate cash-withdrawal locations for map visualizers.
- Query Parameters:
  - case_id (int, optional): Filter by case.
  - location_type (string, optional): reported, candidate_withdrawal, atm, branch, pos.
  - state (string, optional): State name.
  - district (string, optional): District name.
  - min_risk (float, optional, 0.0 to 1.0): Minimum risk score filter.
  - limit (int, default 50, max 200): Point limit.
  - offset (int, default 0): Pagination offset.
- Status Codes: 200 OK.
8. GET /api/v1/transactions/{case_id}/network
- Purpose: Retrieve graph topology (nodes and directed edges) representing financial flow from victim to mule accounts and candidate ATMs.
- Path Parameter: case_id (int, ge=1).
- Status Codes: 200 OK, 404 Not Found (if case does not exist).
- Example Response:{
    "case_id": 1,
    "case_number": "SYN-CASE-2026-001",
    "nodes": [
      {
        "id": "ACC-VICTIM-9912",
        "label": "Origin: ACC-VICTIM-9912",
        "node_type": "victim_account",
        "risk_score": 0.1,
        "metadata": { "channel": "UPI" }
      },
      {
        "id": "ACC-MULE-3301",
        "label": "Mule: ACC-MULE-3301",
        "node_type": "suspect_mule",
        "risk_score": 0.88,
        "metadata": { "channel": "UPI", "flagged": true }
      },
      {
        "id": "LOC-ATM-2",
        "label": "Candidate ATM: Candidate ATM Hub - Sector 18",
        "node_type": "atm_node",
        "risk_score": 0.84,
        "metadata": {
          "district": "Gautam Buddha Nagar",
          "state": "Uttar Pradesh",
          "is_predicted": true,
          "confidence": 0.81
        }
      }
    ],
    "edges": [
      {
        "id": "tx-1",
        "source": "ACC-VICTIM-9912",
        "target": "ACC-MULE-3301",
        "amount": 150000.0,
        "currency": "INR",
        "channel": "UPI",
        "timestamp": "2026-10-17T08:15:00Z",
        "is_suspicious": true
      }
    ],
    "total_flow_amount": 150000.0,
    "suspicious_flow_amount": 150000.0,
    "total_nodes": 3,
    "total_edges": 1
  }
8. Running Automated Tests
Run the complete test suite using pytest:
python -m pytest backend/tests -v
Coverage Highlights
- Health check & root discovery: Verifies app startup, DB connection, and ML status.
- Case pagination & multi-criteria filtering: Verifies bounds, category, priority, status, date ranges, and text search.
- Truthful dashboard metrics: Tests that zero-records produce zeros (not fabricated numbers), and populated databases aggregate counts correctly.
- ML interface readiness & error contracts: Ensures 503 is returned when the model is uninitialized, tests 404 on missing cases, tests full prediction generation with registered inference hooks, and verifies prediction persistence.
- Transaction networks: Validates node-edge graph structures, mule classification, and empty flow handling.
- CORS & Error handling: Confirms origin validation and standardized 422 JSON payloads.
9. Implementation Notes and Limitations
1. ML Model Integration: The API layer provides a pluggable inference interface (MLPredictionService.register_predictor) and can load the inference module from backend.app.ml.inference. By design, when the inference model is not available, the endpoint returns HTTP 503 with an honest explanation rather than fabricating predictions.
2. Database Migration Framework: The current implementation uses SQLAlchemy's declarative table creation (create_tables()) which supports SQLite, PostgreSQL, and IBM Db2 out of the box. If schema migrations across production deployments are required, Alembic can be configured on top of the existing Base.metadata.
3. Data Anonymization: In compliance with security and privacy requirements, all sample data and test fixtures use synthetic, pseudonymized identifiers (ACC-MULE-XXXX, SYN-CASE-XXXX). No real citizen complaints or banking credentials are ever stored.
