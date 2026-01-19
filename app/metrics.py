"""
Application metrics
Proyecto 15 A+ - Recovery & Resilience Testing

Responsabilidades:
- Contabilizar requests
- Detectar fallas
- Verificar conectividad a base de datos
- Exponer estado interno para observabilidad
"""

import time
from typing import Dict

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

# ------------------------------------------------------------------------------
# In-memory metrics storage
# ------------------------------------------------------------------------------
_metrics: Dict[str, float] = {
    "app_requests_total": 0,
    "app_requests_failed": 0,
    "db_connection_ok": 1,
    "db_last_error_timestamp": 0,
}

# ------------------------------------------------------------------------------
# Metrics helpers
# ------------------------------------------------------------------------------
def record_request(success: bool) -> None:
    """
    Records the result of an application request.
    """
    _metrics["app_requests_total"] += 1
    if not success:
        _metrics["app_requests_failed"] += 1


def check_database(db: Session) -> None:
    """
    Verifies database connectivity.
    Sets internal metrics based on result.
    """
    try:
        db.execute(text("SELECT 1"))
        _metrics["db_connection_ok"] = 1
    except SQLAlchemyError:
        _metrics["db_connection_ok"] = 0
        _metrics["db_last_error_timestamp"] = time.time()


def get_metrics() -> Dict[str, float]:
    """
    Returns a snapshot of current metrics.
    """
    return _metrics.copy()
