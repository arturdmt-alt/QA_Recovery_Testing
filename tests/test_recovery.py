"""
Recovery testing
TC_001 – Container restart
TC_002 – Database recovery
TC_004 – Full system restart
TC_007 – State persistence
"""

import asyncio
import logging
import os
import pytest

logger = logging.getLogger("pytest-recovery")

FASTAPI_CONTAINER = "recovery_fastapi"
POSTGRES_CONTAINER = "recovery_postgres"

# Skip chaos tests in CI environment
pytestmark = pytest.mark.skipif(
    os.getenv("CI") == "true",
    reason="Docker container restart tests require Docker Compose (local only)",
)


# ------------------------------------------------------------------------------
# TC_001 – FastAPI container restart recovery
# ------------------------------------------------------------------------------
@pytest.mark.recovery
@pytest.mark.asyncio
async def test_container_restart_recovery(
    async_client,
    docker_control,
    wait_for_health,
    clean_database,
):
    """TC_001: Service recovers after FastAPI container restart"""

    # Arrange
    user_payload = {
        "name": "John Doe",
        "email": "john@example.com",
        "is_active": True,
    }
    response = await async_client.post("/users/", json=user_payload)
    assert response.status_code == 201
    user_id = response.json()["id"]

    # Act
    logger.info("Restarting FastAPI container")
    assert docker_control["restart"](FASTAPI_CONTAINER, wait_time=15)

    recovered = await wait_for_health(max_attempts=30)
    assert recovered is True

    # Assert
    response = await async_client.get(f"/users/{user_id}")
    assert response.status_code == 200
    assert response.json()["email"] == "john@example.com"


# ------------------------------------------------------------------------------
# TC_002 – Database connection recovery
# ------------------------------------------------------------------------------
@pytest.mark.recovery
@pytest.mark.asyncio
async def test_database_connection_recovery(
    async_client,
    docker_control,
    wait_for_health,
    clean_database,
):
    """TC_002: Service recovers after PostgreSQL restart"""

    # Pre-check
    response = await async_client.get("/health")
    assert response.status_code == 200

    # Act
    logger.info("Restarting PostgreSQL container")
    assert docker_control["restart"](POSTGRES_CONTAINER, wait_time=15)

    recovered = await wait_for_health(max_attempts=30)
    assert recovered is True

    # Assert
    user_payload = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "is_active": True,
    }
    response = await async_client.post("/users/", json=user_payload)
    assert response.status_code == 201


# ------------------------------------------------------------------------------
# TC_004 – Full system restart
# ------------------------------------------------------------------------------
@pytest.mark.recovery
@pytest.mark.asyncio
async def test_full_system_restart(
    async_client,
    docker_control,
    wait_for_health,
    clean_database,
):
    """TC_004: Full system restart preserves functionality"""

    # Arrange
    users_payload = [
        {
            "name": f"User {i}",
            "email": f"user{i}@example.com",
            "is_active": True,
        }
        for i in range(5)
    ]

    for payload in users_payload:
        response = await async_client.post("/users/", json=payload)
        assert response.status_code == 201

    # Act
    logger.info("Stopping all containers")
    docker_control["stop"](FASTAPI_CONTAINER)
    docker_control["stop"](POSTGRES_CONTAINER)
    await asyncio.sleep(5)

    logger.info("Starting all containers")
    docker_control["start"](POSTGRES_CONTAINER, wait_time=15)
    docker_control["start"](FASTAPI_CONTAINER, wait_time=15)

    recovered = await wait_for_health(max_attempts=40)
    assert recovered is True

    # Assert
    response = await async_client.get("/users/")
    assert response.status_code == 200
    assert len(response.json()) == 5


# ------------------------------------------------------------------------------
# TC_007 – State persistence after restart
# ------------------------------------------------------------------------------
@pytest.mark.recovery
@pytest.mark.asyncio
async def test_state_persistence_after_restart(
    async_client,
    docker_control,
    wait_for_health,
    clean_database,
):
    """TC_007: Application state persists after service + DB restart"""

    # Arrange
    for i in range(10):
        payload = {
            "name": f"Test User {i}",
            "email": f"test{i}@example.com",
            "is_active": True,
        }
        response = await async_client.post("/users/", json=payload)
        assert response.status_code == 201

    # Act
    logger.info("Restarting FastAPI and PostgreSQL containers")
    docker_control["restart"](FASTAPI_CONTAINER, wait_time=5)
    docker_control["restart"](POSTGRES_CONTAINER, wait_time=15)

    recovered = await wait_for_health(max_attempts=40)
    assert recovered is True

    # Assert
    response = await async_client.get("/users/")
    assert response.status_code == 200
    assert len(response.json()) == 10
    