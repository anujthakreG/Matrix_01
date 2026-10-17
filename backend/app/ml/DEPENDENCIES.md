# Machine Learning Pipeline Dependencies (Worker 2)

These are the required Python package dependencies for the ML forecasting and data processing pipeline:

```text
scikit-learn>=1.3.0
pandas>=2.0.0
numpy>=1.24.0
joblib>=1.3.0
pydantic>=2.0.0
pytest>=7.0.0
```

> **Note**: These dependencies are maintained independently by Worker 2 for the predictive analytics module (`backend/app/ml/`) and associated tests. Worker 1 maintains the root `backend/requirements.txt`.
