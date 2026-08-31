"""Dashboard API — Phase 7C1.

Endpoints:
    GET /api/v1/dashboard
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.dashboard_service import get_dashboard

router = APIRouter(prefix="/api/v1")


@router.get("/dashboard")
def get_dashboard_endpoint(db: Session = Depends(get_db)):
    """Get aggregated dashboard data."""
    return get_dashboard(db)