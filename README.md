# QA Recovery & Resilience Testing Framework

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Pytest](https://img.shields.io/badge/Pytest-7.4.3-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-teal)
![Docker](https://img.shields.io/badge/Docker-Compose-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

> **Portfolio Project #15** - Advanced QA Automation & Resilience Testing

Professional testing framework demonstrating chaos engineering, recovery patterns, and resilience testing using FastAPI, PostgreSQL, Docker, and Locust.

## Project Context

This was one of the most challenging projects in my QA automation portfolio. Unlike typical functional testing frameworks, this project required:

- Deep understanding of Docker container orchestration
- Database connection pool management and recovery patterns
- Async Python testing patterns (pytest-asyncio, httpx)
- Integration of multiple technologies (FastAPI, PostgreSQL, Locust)
- Debugging production-like failure scenarios

The complexity came from simulating real infrastructure failures (container crashes, database restarts) while maintaining test determinism and reliability. Many challenges encountered during development are documented in the "Challenges & Lessons Learned" section.

## Project Overview

This framework validates system behavior under failure conditions through:
- **Chaos Engineering**: Random container failures during load
- **Recovery Testing**: Automatic service recovery validation
- **Database Resilience**: Connection pool exhaustion and rollback handling
- **Load Testing**: Sustained traffic with infrastructure failures

## Technical Stack

**Core Technologies**
- FastAPI 0.104.1 - REST API framework
- PostgreSQL 15-alpine - Database
- Docker Compose 3.9 - Container orchestration

**Testing & Automation**
- pytest 7.4.3 + pytest-asyncio 0.21.1 - Test framework
- Locust 2.17.0 - Load testing
- httpx 0.25.2 - Async HTTP client
- SQLAlchemy 2.0.23 - ORM and database toolkit

## Project Structure
```
QA_Recovery_Testing/
├── app/                        # FastAPI application
│   ├── main.py                 # API endpoints (users CRUD)
│   ├── database.py             # DB connection & session management
│   ├── models.py               # SQLAlchemy models
│   └── metrics.py              # Application metrics
├── tests/                      # Test suites
│   ├── conftest.py             # Fixtures & Docker control
│   ├── test_recovery.py        # Container restart tests (4)
│   ├── test_database.py        # DB resilience tests (2)
│   └── test_chaos_load.py      # Load + chaos test (1)
├── docker/
│   ├── Dockerfile              # FastAPI container
│   └── docker-compose.yml      # Orchestration config
├── locust_tests/
│   └── locustfile.py           # Load testing scenarios
├── reports/
│   └── test_report.html        # HTML test report
└── docs/images/                # Screenshots
```

## Test Coverage (7 Tests)

> **Note:** Test case IDs reflect internal tracking and are intentionally non-sequential.

### Recovery Tests (4)
- **TC_001**: FastAPI container restart recovery
- **TC_002**: PostgreSQL connection recovery
- **TC_004**: Full system restart (both containers)
- **TC_007**: State persistence after restart

### Database Tests (2)
- **TC_009**: Transaction rollback on error
- **TC_011**: Connection pool exhaustion handling

### Chaos + Load Test (1)
- **TC_017+025**: Sustained load + random container failure
  - 10 concurrent users, 60 seconds
  - Random container kill at 30s mark
  - Validates automatic recovery under load

**Total execution time**: ~4-5 minutes (includes container restarts)

## Features

- Async Testing: Full async/await patterns with httpx.AsyncClient
- Docker Control: Tests directly control container lifecycle
- Real Infrastructure: PostgreSQL database (not mocks)
- Health Checks: Service recovery validation
- Load Testing: Locust integration for concurrent users
- Chaos Engineering: Random failures during load
- HTML Reports: pytest-html with detailed results
- Database Cleanup: Automatic pre/post-test isolation

## Installation

### Prerequisites
- Python 3.11+
- Docker Desktop
- Git

### Setup
```bash
# Clone repository
git clone https://github.com/arturdmt-alt/QA_Recovery_Testing.git
cd QA_Recovery_Testing

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Start Infrastructure
```bash
cd docker
docker compose up -d
cd ..

# Verify containers are running
docker ps --filter "name=recovery"

# Check health
curl http://localhost:8000/health
# Expected: {"status":"ok","database":"reachable"}
```

## Running Tests

> **Warning:** Chaos tests intentionally kill containers. Do not run on shared or production environments.

### Run All Tests (7 tests)
```bash
pytest tests/test_recovery.py tests/test_database.py tests/test_chaos_load.py -v
```

### Run with HTML Report
```bash
pytest --html=reports/test_report.html --self-contained-html -v
```

### Run Specific Test Categories
```bash
# Recovery tests only
pytest tests/test_recovery.py -v

# Database tests only
pytest tests/test_database.py -v

# Chaos + load test only
pytest tests/test_chaos_load.py -v -s
```

### Run by Markers
```bash
pytest -m recovery -v
pytest -m database -v
pytest -m load -v
```

---

## CI/CD Limitations

> **Important:** Chaos and container-restart tests are intentionally **excluded** from GitHub Actions CI.

**Why?**
- Require privileged Docker daemon access
- Need to kill and restart containers
- Designed for local or dedicated chaos engineering environments

**CI Pipeline Scope:**

**Included in CI:**
- Database resilience tests (`test_database.py`)
- Functional API tests

**Excluded from CI:**
- Container restart tests (`test_recovery.py`)
- Chaos load tests (`test_chaos_load.py`)

**Local execution** remains the primary testing environment for this project.

---

## Challenges & Lessons Learned

### 1. Docker Compose Configuration
**Problem**: `docker compose up --build` failed with "no configuration file provided"

**Cause**: `docker-compose.yml` was in `docker/` subdirectory, not root

**Solution**: Always specify `-f` flag:
```bash
docker compose -f docker/docker-compose.yml up --build
```

**Lesson**: In real projects, structure matters. Always specify config file path explicitly.

---

### 2. Docker Networking vs localhost
**Problem**: Application tried connecting to PostgreSQL using `localhost`, but inside Docker, `localhost` points to the container itself

**Cause**:
```python
DB_HOST = os.getenv("DB_HOST", "localhost")  # Wrong
```

**Solution**: Use service name from docker-compose.yml:
```python
DATABASE_URL = "postgresql+psycopg2://postgres:postgres@postgres:5432/recovery_db"
```

**Lesson**: In Docker, always use service names as hostnames, not `localhost`.

---

### 3. SQLAlchemy 2.0 Breaking Changes
**Problem**: `conn.execute("SELECT 1")` raised errors in SQLAlchemy 2.0+

**Solution**:
```python
from sqlalchemy import text
conn.execute(text("SELECT 1"))
```

**Lesson**: Major version upgrades break "classic" code patterns. Always read release notes.

---

### 4. Critical Bug: Auto-commit in Dependency
**Problem**: Database tests failed intermittently. Rollbacks didn't work correctly.

**Root Cause**:
```python
def get_db():
    yield db
    db.commit()  # NEVER do this
```

**Solution**: Remove transaction control from dependencies:
```python
def get_db():
    try:
        yield db
    except:
        db.rollback()
        raise
    finally:
        db.close()
```

**Lesson**: Dependencies should NOT manage transactions. This error happens frequently in production.

---

### 5. PostgreSQL Restart & Connection Pool
**Problem**: After PostgreSQL restart, FastAPI didn't recover (dead connections in pool)

**Solution**:
```python
except OperationalError:
    engine.dispose()  # Critical for recovery
```

**Lesson**: `pool_pre_ping` alone isn't enough for chaos testing. Disposing the pool is mandatory for real recovery.

---

### 6. Hot Reload + Docker Volumes
**Problem**: Code changes didn't reflect, phantom `NameError: Generator not defined` errors

**Cause**: Cached code in containers + inconsistent volume state

**Solution**:
```bash
docker compose down -v
docker compose up --build
```

**Lesson**: Always do full reset after import errors, especially before database tests.

---

## Architecture Decisions

### Why `pool_size=3`?
Intentionally small to simulate realistic pool exhaustion in tests. Production uses larger pools, but testing requires deterministic failure scenarios.

### Why Real PostgreSQL?
Mocks hide production issues. Real database testing reveals:
- Connection pool behavior
- Transaction isolation
- Rollback mechanics
- Recovery patterns

### Why Docker Control from Tests?
Chaos engineering requires actual infrastructure failures. Mocking container restarts doesn't validate real recovery behavior.

### Why Async Patterns?
Modern Python applications use async. Tests should match production patterns (async/await, httpx.AsyncClient, pytest-asyncio).

---

## Screenshots

### Test Execution (7 Tests Passed)
![Pytest Terminal](docs/images/01_pytest_terminal_7tests_passed.jpg)

### Chaos Test Detailed Logs
![Chaos Test Logs](docs/images/02_chaos_test_detailed_logs.jpg)

### HTML Report - Summary
![HTML Report Summary](docs/images/04_html_report_summary_7tests.jpg)

### HTML Report - Environment
![HTML Report Environment](docs/images/03_html_report_environment.jpg)

---

## Configuration

### Docker Compose
```yaml
services:
  postgres:
    image: postgres:15-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
  
  fastapi:
    build: .
    depends_on:
      postgres:
        condition: service_healthy
```

### Pytest Markers
```ini
[pytest]
markers =
    recovery: recovery and chaos testing
    database: database resilience tests
    load: load and stress tests
asyncio_mode = strict
```

---

## Author

**Artur Dmytriyev** - QA Automation Engineer

[![GitHub](https://img.shields.io/badge/GitHub-arturdmt--alt-black?logo=github)](https://github.com/arturdmt-alt)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?logo=linkedin)](https://www.linkedin.com/in/arturdmytriyev)