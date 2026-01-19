"""
Pytest configuration and shared fixtures
Proyecto 15 A+ - Recovery & Resilience Testing
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from typing import AsyncGenerator, Callable, Dict, List

import httpx
import pytest
import pytest_asyncio

# ------------------------------------------------------------------------------
# Global configuration
# ------------------------------------------------------------------------------
BASE_URL: str = "http://localhost:8000"
DOCKER_WAIT_SECONDS: int = 10
HTTP_TIMEOUT: float = 60.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("pytest-recovery")

# ------------------------------------------------------------------------------
# Base fixtures
# ------------------------------------------------------------------------------
@pytest.fixture(scope="session")
def base_url() -> str:
    """Base URL for the FastAPI service under test."""
    return BASE_URL


@pytest_asyncio.fixture(scope="function")
async def async_client(base_url: str) -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Async HTTP client with extended timeout.
    Function-scoped to ensure proper test isolation.
    """
    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(HTTP_TIMEOUT),
    ) as client:
        yield client


# ------------------------------------------------------------------------------
# Database cleanup helpers
# ------------------------------------------------------------------------------
async def _delete_all_users(base_url: str) -> None:
    """
    Deletes all users from the API.
    Ensures deterministic test isolation.
    """
    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(HTTP_TIMEOUT),
    ) as client:
        try:
            response = await client.get("/users/")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(f"Unable to fetch users for cleanup: {exc}")
            return

        users = response.json()
        for user in users:
            user_id = user.get("id")
            if not user_id:
                continue

            try:
                await client.delete(f"/users/{user_id}")
            except httpx.RequestError as exc:
                logger.warning(f"Failed to delete user {user_id}: {exc}")


@pytest_asyncio.fixture(scope="function")
async def clean_database(base_url: str) -> AsyncGenerator[None, None]:
    """
    Cleans database before and after each test.
    Critical for recovery and chaos testing.
    """
    logger.info("Cleaning database (pre-test)")
    await _delete_all_users(base_url)

    yield

    logger.info("Cleaning database (post-test)")
    await _delete_all_users(base_url)


# ------------------------------------------------------------------------------
# Docker helpers (Chaos Engineering)
# ------------------------------------------------------------------------------
def _run_docker_command(
    command: List[str],
    wait_time: int = 0,
) -> bool:
    """
    Executes a Docker command safely with logging.
    Returns True if successful, False otherwise.
    """
    try:
        logger.info("Running docker command: %s", " ".join(command))
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
        if wait_time > 0:
            time.sleep(wait_time)
        return True

    except subprocess.CalledProcessError as exc:
        logger.error("Docker command failed: %s", exc.stderr or "Unknown error")
        return False


def restart_container(
    container_name: str,
    wait_time: int = DOCKER_WAIT_SECONDS,
) -> bool:
    """Restart a Docker container and wait for stability."""
    return _run_docker_command(
        ["docker", "restart", container_name],
        wait_time=wait_time,
    )


def stop_container(container_name: str) -> bool:
    """Stop a Docker container."""
    return _run_docker_command(["docker", "stop", container_name])


def start_container(
    container_name: str,
    wait_time: int = DOCKER_WAIT_SECONDS,
) -> bool:
    """Start a Docker container and wait for stability."""
    return _run_docker_command(
        ["docker", "start", container_name],
        wait_time=wait_time,
    )


@pytest.fixture(scope="function")
def docker_control() -> Dict[str, Callable[[str], bool]]:
    """
    Provides Docker chaos actions to tests.
    Example:
        docker_control["restart"]("api-container")
    """
    return {
        "restart": restart_container,
        "stop": stop_container,
        "start": start_container,
    }


# ------------------------------------------------------------------------------
# Health-check wait helper (Recovery critical path)
# ------------------------------------------------------------------------------
@pytest.fixture(scope="function")
def wait_for_health(base_url: str) -> Callable[..., asyncio.Future]:
    """
    Waits until the /health endpoint returns HTTP 200.
    Used to validate service recovery after failures.
    """

    async def _wait(
        max_attempts: int = 30,
        delay_seconds: float = 1.0,
    ) -> bool:
        async with httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(5.0),
        ) as client:
            for attempt in range(1, max_attempts + 1):
                try:
                    response = await client.get("/health")
                    if response.status_code == 200:
                        logger.info(
                            "Service healthy after %d attempts",
                            attempt,
                        )
                        return True
                except httpx.RequestError:
                    logger.warning(
                        "Health check attempt %d failed",
                        attempt,
                    )

                await asyncio.sleep(delay_seconds)

        logger.error(
            "Service did not recover after %d attempts",
            max_attempts,
        )
        return False

    return _wait
