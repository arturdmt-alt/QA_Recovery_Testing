"""
Database resilience testing
TC_009 – Transaction rollback on constraint violation
TC_011 – Connection pool exhaustion handling
"""

import asyncio
import logging
import pytest

logger = logging.getLogger("pytest-database")


# ------------------------------------------------------------------------------
# TC_009 – Transaction rollback
# ------------------------------------------------------------------------------
@pytest.mark.database
@pytest.mark.asyncio
async def test_transaction_rollback_on_error(
    async_client,
    clean_database,
):
    """
    TC_009:
    When a database constraint violation occurs, the transaction
    is rolled back and previous data remains consistent.
    """

    # Arrange
    first_user = {
        "name": "User One",
        "email": "user1@example.com",
        "is_active": True,
    }

    duplicate_user = {
        "name": "User Two",
        "email": "user1@example.com",  # duplicate email
        "is_active": True,
    }

    # Act – create first user
    response = await async_client.post("/users/", json=first_user)
    assert response.status_code == 201

    # Act – attempt to create duplicate user
    response = await async_client.post("/users/", json=duplicate_user)
    assert response.status_code == 400

    # Assert – database state is consistent
    response = await async_client.get("/users/")
    assert response.status_code == 200

    users = response.json()
    assert len(users) == 1
    assert users[0]["email"] == "user1@example.com"

    logger.info("Transaction rollback validated successfully")


# ------------------------------------------------------------------------------
# TC_011 – Connection pool exhaustion
# ------------------------------------------------------------------------------
@pytest.mark.database
@pytest.mark.asyncio
async def test_connection_pool_exhaustion_handling(
    async_client,
    clean_database,
):
    """
    TC_011:
    Application remains partially available under concurrent
    database connection pressure.
    """

    async def create_user(index: int) -> int:
        payload = {
            "name": f"User {index}",
            "email": f"user{index}@example.com",
            "is_active": True,
        }
        try:
            response = await async_client.post("/users/", json=payload)
            return response.status_code
        except Exception as exc:
            logger.warning(f"Request failed for user {index}: {exc}")
            return 0

    # Act – simulate concurrent load
    logger.info("Creating users concurrently to stress DB connection pool")
    tasks = [create_user(i) for i in range(10)]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    # Assert – system degrades gracefully, not total failure
    successful_creations = sum(1 for status in results if status == 201)

    logger.info(
        "Connection pool test result: %s/%s successful",
        successful_creations,
        len(results),
    )

    assert successful_creations >= 5
