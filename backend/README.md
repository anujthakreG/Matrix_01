# MATRIX Intel Backend

**Backend API, Database, and Machine Learning Integration Documentation**

The MATRIX Intel backend is a predictive analytics system developed for the **IBM Z Datathon 2026**. It analyzes authorized cybercrime complaint records, transaction flows, and mule-account behavior to forecast candidate cash-withdrawal locations, such as ATM hubs and bank branches, helping cyber-investigation teams prioritize cases.

The application is built with **FastAPI, Pydantic v2, and SQLAlchemy 2.0**, with deployment support for **IBM LinuxONE Community Cloud**.

---

## 1. System Architecture

The backend exposes versioned REST APIs for case management, transaction-network analysis, dashboard metrics, geographic queries, and machine-learning predictions.

| Component | Responsibility |
|---|---|
| Backend API and Database | API routes, request and response schemas, database models, service logic, CORS configuration, and automated tests |
| Machine Learning Pipeline | Data preprocessing, feature engineering, model training, evaluation, and inference |
| Frontend Dashboard | User interface that consumes the backend's versioned API endpoints |

---

## 2. Directory Structure

```text
backend/
├── .env.example
├── requirements.txt
├── README.md
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   └── errors.py
│   ├── db/
│   │   ├── base.py
│   │   ├── session.py
│   │   ├── models.py
│   │   └── init_db.py
│   ├── schemas/
│   │   ├── common.py
│   │   ├── cases.py
│   │   ├── transactions.py
│   │   ├── locations.py
│   │   ├── dashboard.py
│   │   └── predictions.py
│   ├── services/
│   │   ├── case_service.py
│   │   ├── dashboard_service.py
│   │   ├── location_service.py
│   │   ├── transaction_service.py
│   │   └── ml_service.py
│   └── api/
│       └── v1/
│           ├── api.py
│           └── endpoints/
│               ├── health.py
│               ├── dashboard.py
│               ├── cases.py
│               ├── predictions.py
│               ├── locations.py
│               └── transactions.py
└── tests/
    ├── conftest.py
    ├── test_health.py
    ├── test_dashboard.py
    ├── test_cases.py
    ├── test_predictions.py
    ├── test_locations.py
    ├── test_transactions.py
    └── test_cors_and_errors.py
```

*The directory listing represents the intended backend structure. Individual files may vary with the current implementation.*

---

## 3. Installation and Setup

### Prerequisites

- Python 3.10 or later
- Git
- Python virtual environment support (`venv`)

### Step 1: Clone the Repository

```bash
git clone https://github.com/anujthakreG/Matrix_01.git
cd Matrix_01
```

### Step 2: Create and Activate a Virtual Environment

**Linux, macOS, or IBM LinuxONE**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows PowerShell**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies

```bash
pip install -r backend/requirements.txt
```

### Step 4: Configure Environment Variables

Create a local environment configuration file from the example:

**Linux or macOS**

```bash
cp backend/.env.example backend/.env
```

**Windows PowerShell**

```powershell
Copy-Item backend/.env.example backend/.env
```

Review the configuration and set appropriate values for your local environment. Do not commit `.env` files or credentials to the repository.

Example development settings:

```dotenv
ENVIRONMENT=development
DEBUG=true
PORT=8000
HOST=127.0.0.1
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
DATABASE_URL=sqlite:///./data/matrix.db
ML_MODEL_ENABLED=false
```

Ensure these settings match the application's actual configuration requirements before running the backend.

### Step 5: Initialize the Database

Create the database tables:

```bash
python -m backend.app.db.init_db
```

To populate the database with synthetic development data, if supported by the current implementation:

```bash
python -m backend.app.db.init_db --seed
```

### Step 6: Start the API

```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

The local API will be available at `http://localhost:8000`.

| Resource | URL |
|---|---|
| Interactive API documentation | `http://localhost:8000/docs` |
| ReDoc documentation | `http://localhost:8000/redoc` |
| Health check | `http://localhost:8000/api/v1/health` |

Use the development server for local development only. Production deployments should use an appropriately secured configuration.

---

## 4. Database Design

The backend uses SQLAlchemy to manage relational data. SQLite is suitable for local development, while a supported production database can be configured where the application and deployment environment provide the required driver and connection settings.

### Core Entities

| Entity | Purpose |
|---|---|
| Cases | Cybercrime complaint metadata, case status, priority, category, reported amount, and incident details |
| Transactions | Transaction relationships, amounts, channels, timestamps, and suspicious-activity indicators |
| Locations | Reported incident locations and predicted candidate locations |
| Predictions | Stored prediction results and associated metadata |

Database indexes support common filtering and retrieval operations. Automated tests use isolated database fixtures where configured.

---

## 5. Machine Learning Interface

The backend separates API functionality from the machine-learning implementation through the ML service layer.

The inference interface may expose a function similar to:

```python
def predict_candidate_locations(features: dict) -> dict:
    ...
```

The actual function name, input schema, output schema, and model-loading mechanism must match the implemented inference module.

### Example Input

```json
{
  "case_id": 1,
  "reported_amount": 150000.0,
  "category": "vishing",
  "victim_state": "Delhi",
  "victim_district": "New Delhi",
  "source_channel": "UPI",
  "mule_accounts": [
    "ACC-MULE-3301",
    "ACC-MULE-8840"
  ],
  "origin_latitude": 28.6315,
  "origin_longitude": 77.2167
}
```

This is an illustrative payload using synthetic identifiers and example values.

### Model Availability

When the model is disabled or unavailable, the prediction endpoint should return an appropriate error response rather than fabricate prediction results.

Predicted candidate locations are estimates for investigation support only. They must not be interpreted as confirmed withdrawals or proof of criminal activity.

---

## 6. Frontend Integration

The backend exposes versioned endpoints under `/api/v1`.

For local development, the frontend should use the configured backend base URL:

```text
http://localhost:8000/api/v1
```

CORS origins should be configured explicitly for the frontend environments that need access. Avoid wildcard origins in production when credentials or protected resources are involved.

### Response Formats

List endpoints may return paginated results containing:

- `items`
- `total`
- `page`
- `page_size`
- `total_pages`

Error responses should use the standardized response schema implemented by the API.

---

## 7. API Endpoint Reference

The following endpoints describe the intended API surface. Confirm availability and exact behavior against the running application and its OpenAPI documentation.

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Check service health |
| GET | `/api/v1/dashboard/summary` | Retrieve dashboard summary metrics |
| GET | `/api/v1/cases` | List and filter cases |
| GET | `/api/v1/cases/{case_id}` | Retrieve case details |
| POST | `/api/v1/predictions` | Request a machine-learning prediction |
| GET | `/api/v1/predictions/{prediction_id}` | Retrieve a stored prediction |
| GET | `/api/v1/locations` | Retrieve incident and candidate location data |
| GET | `/api/v1/transactions/{case_id}/network` | Retrieve transaction-network relationships |

Interactive API documentation is available at `/docs` when enabled.

---

## 8. Testing

Run the backend test suite from the repository root:

```bash
python -m pytest backend/tests -v
```

The test suite is intended to cover areas such as:

- Health checks and service initialization
- Case retrieval, pagination, and filtering
- Dashboard summary calculations
- Prediction request validation and model availability
- Location queries and prediction disclaimers
- Transaction-network responses
- CORS and error handling

Test results depend on the current implementation and environment. Run the suite before submitting changes and report the actual results.

---

## 9. Security and Privacy

- Never commit passwords, API keys, access tokens, private keys, or `.env` files.
- Use synthetic data for public demonstrations and automated tests.
- Do not publish real financial records, personal identifiers, or confidential investigation details.
- Validate and authorize requests according to the application's deployment requirements.
- Restrict CORS origins to trusted frontend applications.
- Keep production credentials and environment-specific configuration outside version control.
- Use HTTPS and appropriate access controls for public deployments.
- Treat model predictions as decision-support estimates, not conclusive evidence.

---

## 10. Implementation Notes and Limitations

- **Model availability:** Prediction requests depend on the configured inference service and model artifacts.
- **Database migrations:** If schema changes must be managed across production releases, adopt a migration tool such as Alembic after verifying compatibility with the current database setup.
- **Synthetic data:** Public examples and demonstration fixtures should use fictional identifiers and values.
- **Model evaluation:** Report measured performance using the actual evaluation dataset and methodology. Do not present experimental metrics as validated real-world accuracy.
- **Deployment:** Production settings must be reviewed for security, reliability, resource limits, and monitoring before use.

---

## Project

**MATRIX Intel — IBM Z Datathon 2026**

Built with FastAPI, Pydantic, SQLAlchemy, and Python.
