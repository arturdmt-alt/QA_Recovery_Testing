"""
Database configuration and session management
Proyecto 15 A+ - Recovery & Resilience Testing

Objetivos:
- Soportar restarts de PostgreSQL
- Recuperar conexiones después de chaos testing
- Ser determinístico para tests de pool exhaustion
"""

from __future__ import annotations

import logging
import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# ------------------------------------------------------------------------------
# Logging configuration
# ------------------------------------------------------------------------------
logger = logging.getLogger("database")
logger.setLevel(logging.INFO)

# ------------------------------------------------------------------------------
# Database URL configuration (single source of truth)
# ------------------------------------------------------------------------------
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@postgres:5432/recovery_db",
)

# ------------------------------------------------------------------------------
# SQLAlchemy engine
# ------------------------------------------------------------------------------
try:
    engine = create_engine(
        DATABASE_URL,
        pool_size=3,            # Pool pequeño para forzar exhaustion en tests
        max_overflow=5,
        pool_pre_ping=True,     # Detecta conexiones muertas antes de usarlas
        pool_recycle=3600,      # Evita conexiones stale
        echo=False,
        future=True,
    )
    logger.info("Database engine initialized")

except SQLAlchemyError as exc:
    logger.critical("Database engine initialization failed", exc_info=exc)
    raise

# ------------------------------------------------------------------------------
# Session factory
# ------------------------------------------------------------------------------
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)

# ------------------------------------------------------------------------------
# Declarative base
# ------------------------------------------------------------------------------
Base = declarative_base()

# ------------------------------------------------------------------------------
# Dependency: database session
# ------------------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.

    Características clave:
    - No hace commit automático
    - El endpoint controla commit / rollback
    - Maneja recovery real ante fallos operativos
    """
    db: Session = SessionLocal()

    try:
        yield db

    except OperationalError as exc:
        logger.error(
            "Operational database error detected. Resetting connection pool.",
            exc_info=exc,
        )
        db.rollback()

        # Limpia completamente el pool para permitir recovery post-restart
        engine.dispose()

        raise

    except SQLAlchemyError as exc:
        logger.error("Unhandled SQLAlchemy error", exc_info=exc)
        db.rollback()
        raise

    finally:
        db.close()

# ------------------------------------------------------------------------------
# Database initialization
# ------------------------------------------------------------------------------
def init_db() -> None:
    """
    Initialize database schema.
    Must be executed once on application startup.
    """
    try:
        # Importar modelos para que se registren en Base
        from app import models  # noqa: F401

        Base.metadata.create_all(bind=engine)
        logger.info("Database schema initialized")

    except SQLAlchemyError as exc:
        logger.critical("Database initialization failed", exc_info=exc)
        raise
