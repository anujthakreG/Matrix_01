"""Aggregation of all API Version 1 routers."""

from fastapi import APIRouter
from backend.app.api.v1.endpoints import (
    health,
    dashboard,
    cases,
    predictions,
    locations,
    transactions,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(dashboard.router)
api_router.include_router(cases.router)
api_router.include_router(predictions.router)
api_router.include_router(locations.router)
api_router.include_router(transactions.router)
