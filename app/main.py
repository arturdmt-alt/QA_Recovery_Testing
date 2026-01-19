"""
Main application entrypoint
Proyecto 15 A+ - Recovery & Resilience Testing
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, EmailStr

from app.database import get_db, init_db
from app.metrics import record_request, check_database, get_metrics
from app.models import User

# ------------------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("main")

# ------------------------------------------------------------------------------
# FastAPI app
# ------------------------------------------------------------------------------
app = FastAPI(
    title="Recovery & Resilience Testing API",
    version="1.0.0",
)

# ------------------------------------------------------------------------------
# Pydantic schemas
# ------------------------------------------------------------------------------
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    is_active: bool = True


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    is_active: bool
    
    class Config:
        from_attributes = True


# ------------------------------------------------------------------------------
# Startup event
# ------------------------------------------------------------------------------
@app.on_event("startup")
def on_startup() -> None:
    logger.info("Initializing database")
    init_db()
    logger.info("Application startup complete")


# ------------------------------------------------------------------------------
# Health check
# ------------------------------------------------------------------------------
@app.get("/health", tags=["health"])
def health_check(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "database": "reachable",
    }


# ------------------------------------------------------------------------------
# Metrics
# ------------------------------------------------------------------------------
@app.get("/metrics", tags=["metrics"])
def metrics(db: Session = Depends(get_db)) -> dict:
    """
    Exposes internal application metrics.
    Used for recovery and chaos testing.
    """
    try:
        check_database(db)
        record_request(success=True)
    except Exception:
        record_request(success=False)
        raise

    return get_metrics()


# ------------------------------------------------------------------------------
# Users endpoints
# ------------------------------------------------------------------------------
@app.post("/users/", response_model=UserResponse, status_code=201, tags=["users"])
def create_user(user: UserCreate, db: Session = Depends(get_db)) -> User:
    """
    Create a new user.
    Returns 400 if email already exists (constraint violation).
    """
    try:
        db_user = User(
            name=user.name,
            email=user.email,
            is_active=user.is_active,
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")


@app.get("/users/", response_model=list[UserResponse], tags=["users"])
def list_users(db: Session = Depends(get_db)) -> list[User]:
    """
    List all users.
    """
    return db.query(User).all()


@app.get("/users/{user_id}", response_model=UserResponse, tags=["users"])
def get_user(user_id: int, db: Session = Depends(get_db)) -> User:
    """
    Get a single user by ID.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.delete("/users/{user_id}", status_code=200, tags=["users"])
def delete_user(user_id: int, db: Session = Depends(get_db)) -> dict:
    """
    Delete a user by ID.
    Returns 200 with confirmation message.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(user)
    db.commit()
    
    return {"message": "User deleted successfully", "user_id": user_id}


# ------------------------------------------------------------------------------
# Root
# ------------------------------------------------------------------------------
@app.get("/", tags=["root"])
def root() -> dict:
    return {
        "service": "Recovery & Resilience Testing API",
        "status": "running",
    }
