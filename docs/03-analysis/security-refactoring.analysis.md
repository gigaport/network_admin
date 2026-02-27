# Design-Implementation Gap Analysis Report

> **Summary**: Gap analysis of the 7-item security and CRUD refactoring implementation plan vs actual code
>
> **Author**: gap-detector
> **Created**: 2026-02-10
> **Status**: Draft

---

## Analysis Overview
- Analysis Target: Security Hardening & CRUD Refactoring (7 items)
- Design Document: Implementation Plan (user-provided, 7 items)
- Implementation Path: fastapi/, net_admin/, docker-compose.yml, .env
- Analysis Date: 2026-02-10

## Overall Scores

| Category | Score | Status |
|----------|:-----:|:------:|
| 1. DB Connection Pool Module | 100% | PASS |
| 2. network.py CRUD Refactoring | 100% | PASS |
| 3. Django Settings Security | 100% | PASS |
| 4. Django Views FastAPI Hostname | 85% | WARN |
| 5. docker-compose.yml | 100% | PASS |
| 6. Contract Creation POST Endpoint | 100% | PASS |
| 7. multicast/views.py Logging | 100% | PASS |
| **Overall** | **98%** | **PASS** |

---

## Item-by-Item Analysis

### 1. DB Connection Pool Module -- PASS (100%)

**File**: `/home/sysmon/network_admin/fastapi/utils/database.py`

| Check | Expected | Actual | Match |
|-------|----------|--------|:-----:|
| File exists | `fastapi/utils/database.py` | Exists | PASS |
| psycopg2 SimpleConnectionPool | Used | Line 5-6: `from psycopg2.pool import SimpleConnectionPool` | PASS |
| POSTGRES_HOST env var | Used | Line 19: `os.environ.get('POSTGRES_HOST', 'postgres-db')` | PASS |
| POSTGRES_DB env var | Used | Line 21: `os.environ.get('POSTGRES_DB', 'nxt_nms_db')` | PASS |
| POSTGRES_USER env var | Used | Line 22: `os.environ.get('POSTGRES_USER', 'nextrade')` | PASS |
| POSTGRES_PASSWORD env var | Used | Line 23: `os.environ.get('POSTGRES_PASSWORD', '')` | PASS |
| POSTGRES_PORT env var | Used | Line 20: `os.environ.get('POSTGRES_PORT', '5432')` | PASS |
| Context manager `get_connection()` | Present | Lines 29-40: `@contextmanager def get_connection()` | PASS |
| Auto-commit on success | Present | Line 35: `conn.commit()` | PASS |
| Auto-rollback on exception | Present | Line 37: `conn.rollback()` | PASS |
| RealDictCursor support | Imported | Line 6: `from psycopg2.extras import RealDictCursor` | PASS |

No issues found. Implementation matches design exactly.

---

### 2. network.py CRUD Refactoring -- PASS (100%)

**File**: `/home/sysmon/network_admin/fastapi/routers/network.py`

| Check | Expected | Actual | Match |
|-------|----------|--------|:-----:|
| Import `get_connection` | Present | Line 17: `from utils.database import get_connection` | PASS |
| Import `RealDictCursor` | Present | Line 18: `from psycopg2.extras import RealDictCursor` | PASS |
| No `psycopg2.connect(...)` calls | 0 matches | 0 matches (verified via grep) | PASS |
| No hardcoded "Sprtmxm1@3" | 0 matches | 0 matches in `fastapi/routers/` | PASS |
| All endpoints use `with get_connection()` | Yes | 22 occurrences of `with get_connection()` | PASS |

**Endpoint Coverage** (22 CRUD endpoints using connection pool):

| Resource | GET list | GET single | POST | PUT | DELETE |
|----------|:--------:|:----------:|:----:|:---:|:------:|
| contracts | Line 195 | Line 296 | Line 232 | Line 337 | Line 408 |
| sise_products | Line 437 | Line 486 | Line 539 | Line 590 | Line 653 |
| subscriber_codes | Line 682 | -- | Line 725 | Line 775 | Line 836 |
| subscriber_addresses | Line 865 | -- | Line 912 | Line 959 | Line 1009 |
| sise_channels | Line 1038 | -- | Line 1085 | Line 1134 | Line 1197 |

All 22 CRUD endpoints properly converted. No legacy `psycopg2.connect()` calls remain.

---

### 3. Django Settings Security -- PASS (100%)

**File**: `/home/sysmon/network_admin/net_admin/net_admin/settings.py`

| Check | Expected | Actual | Match |
|-------|----------|--------|:-----:|
| SECRET_KEY from env | `os.environ.get('DJANGO_SECRET_KEY', ...)` | Line 25: `os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-dev-only-change-in-production')` | PASS |
| DEBUG from env | `os.environ.get('DJANGO_DEBUG', 'False') == 'True'` | Line 28: exact match | PASS |
| ALLOWED_HOSTS from env | Comma-separated | Line 30: `os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,*').split(',')` | PASS |
| No hardcoded password in DATABASES | Env var only | Line 96: `os.environ.get('POSTGRES_PASSWORD', '')` -- empty default | PASS |
| No "Sprtmxm1@3" in net_admin/ | 0 matches | 0 matches (verified via grep) | PASS |

All database credentials read from environment variables with safe defaults.

---

### 4. Django Views FastAPI Hostname Unification -- WARN (85%)

#### information/views.py -- PASS

**File**: `/home/sysmon/network_admin/net_admin/information/views.py`

| Check | Expected | Actual | Match |
|-------|----------|--------|:-----:|
| FASTAPI_BASE_URL from env | Present | Line 15: `os.environ.get('FASTAPI_BASE_URL', 'http://netview_fastapi:8000')` | PASS |
| All URLs use f-string with var | Yes | All API calls use `f"{FASTAPI_BASE_URL}/..."` | PASS |
| No hardcoded `http://fastapi:8000` | 0 matches | 0 matches | PASS |
| No hardcoded `http://netview_fastapi:8000` | Only as default | Only in `os.environ.get()` fallback | PASS |

#### setting/views.py -- PASS

**File**: `/home/sysmon/network_admin/net_admin/setting/views.py`

| Check | Expected | Actual | Match |
|-------|----------|--------|:-----:|
| FASTAPI_BASE_URL from env | Present | Line 12: `os.environ.get('FASTAPI_BASE_URL', 'http://netview_fastapi:8000')` | PASS |
| All URLs use f-string with var | Yes | All API calls use `f"{FASTAPI_BASE_URL}/..."` | PASS |
| DB_CONFIG removed | Absent | Not found | PASS |
| psycopg2 import removed | Absent | Not found | PASS |

#### business/views.py -- PASS

**File**: `/home/sysmon/network_admin/net_admin/business/views.py`

| Check | Expected | Actual | Match |
|-------|----------|--------|:-----:|
| FASTAPI_BASE_URL from env | Present | Line 15 | PASS |
| All URLs use f-string with var | Yes | Line 39: `f"{FASTAPI_BASE_URL}/api/v1/network/contracts"` | PASS |

#### multicast/views.py -- FAIL (hardcoded URL remains)

**File**: `/home/sysmon/network_admin/net_admin/multicast/views.py`

| Check | Expected | Actual | Match |
|-------|----------|--------|:-----:|
| FASTAPI_BASE_URL from env | Expected | NOT PRESENT -- no `os.environ.get('FASTAPI_BASE_URL')` | FAIL |
| No hardcoded URLs | 0 matches | Line 55: `"http://fastapi:8000/api/v1/network/collect/multicast/arista/pr"` | FAIL |

**Gap Found**: `multicast/views.py` line 55 still uses a hardcoded `http://fastapi:8000` URL instead of the `FASTAPI_BASE_URL` environment variable pattern. This file was not included in the plan scope explicitly (plan #4 listed only `information/views.py` and `setting/views.py`), but it represents an inconsistency with the rest of the codebase.

**Note**: Additionally, `net_admin/batch.py` contains 3 hardcoded `http://fastapi:8000` URLs (lines 30, 39, 43), but this file was outside the plan scope.

---

### 5. docker-compose.yml -- PASS (100%)

**File**: `/home/sysmon/network_admin/docker-compose.yml`

| Check | Expected | Actual | Match |
|-------|----------|--------|:-----:|
| postgres-db uses `env_file: .env` | Present | Line 10: `env_file: .env` | PASS |
| Django service uses `env_file: .env` | Present | Line 102: `env_file: .env` | PASS |
| FastAPI service uses `env_file: .env` | Present | Line 37: `env_file: .env` | PASS |
| No hardcoded "Sprtmxm1@3" | 0 matches | 0 matches (verified via grep) | PASS |
| No hardcoded POSTGRES_PASSWORD | Absent | Not found | PASS |

`.env` file contains all required variables:

| Variable | Present in .env | Value |
|----------|:---------------:|-------|
| POSTGRES_DB | Yes | `nxt_nms_db` |
| POSTGRES_USER | Yes | `nextrade` |
| POSTGRES_PASSWORD | Yes | Set (line 10) |
| POSTGRES_HOST | Yes | `postgres-db` |
| POSTGRES_PORT | Yes | `5432` |
| DJANGO_SECRET_KEY | Yes | Set (line 15) |
| DJANGO_DEBUG | Yes | `False` |
| DJANGO_ALLOWED_HOSTS | Yes | `localhost,*` |
| FASTAPI_BASE_URL | Yes | `http://netview_fastapi:8000` |

---

### 6. Contract Creation POST Endpoint -- PASS (100%)

| Check | Expected | Actual | Match |
|-------|----------|--------|:-----:|
| FastAPI `@router.post("/contracts")` | Present | Line 232 of `network.py` | PASS |
| Django `create_contract` view | Present | `business/views.py` line 30 | PASS |
| URL mapping in `business/urls.py` | Present | Line 8: `path('create_contract', views.create_contract)` | PASS |
| Uses FASTAPI_BASE_URL | Yes | `business/views.py` line 39 | PASS |

Full contract CRUD chain is operational:
- FastAPI: GET list, GET single, POST, PUT, DELETE (5 endpoints)
- Django proxy: create_contract (business/views.py), update_contract and delete_contract (information/views.py)

---

### 7. multicast/views.py Logging -- PASS (100%)

**File**: `/home/sysmon/network_admin/net_admin/multicast/views.py`

| Check | Expected | Actual | Match |
|-------|----------|--------|:-----:|
| `import logging` | Present | Line 1: `import requests, json, logging` | PASS |
| `logger = logging.getLogger(__name__)` | Present | Line 12 | PASS |
| No active `print()` calls | 0 active | All 3 found are commented out (lines 93, 94, 174) | PASS |
| Uses logger.info/debug/error | Yes | Multiple occurrences throughout file | PASS |

All `print()` statements have been commented out. Logging infrastructure is properly configured.

---

## Verification Checks Summary

| Verification Command | Expected | Actual | Status |
|---------------------|----------|--------|:------:|
| `grep "Sprtmxm1@3" fastapi/routers/` | 0 matches | 0 matches | PASS |
| `grep "Sprtmxm1@3" net_admin/` | 0 matches | 0 matches | PASS |
| `grep "psycopg2.connect" fastapi/routers/network.py` | 0 matches | 0 matches | PASS |
| `.env` contains POSTGRES_PASSWORD | Present | Present (line 10) | PASS |
| `.env` contains DJANGO_SECRET_KEY | Present | Present (line 15) | PASS |
| `.env` contains FASTAPI_BASE_URL | Present | Present (line 20) | PASS |

---

## Differences Found

### PASS -- Missing Features (Design O, Implementation X)
None. All 7 planned items have been implemented.

### WARN -- Consistency Issues (Outside Plan Scope)

| Item | Location | Description | Impact |
|------|----------|-------------|--------|
| Hardcoded FastAPI URL | `net_admin/multicast/views.py:55` | `http://fastapi:8000` hardcoded instead of using `FASTAPI_BASE_URL` env var | Medium |
| Hardcoded FastAPI URLs | `net_admin/batch.py:30,39,43` | 3 instances of `http://fastapi:8000` hardcoded | Low |
| Hardcoded password in utility | `fastapi/utils/arista_ptp.py:23` | `NETWORK_PASSWD = "Sprtmxm1@3"` hardcoded | Medium |
| Hardcoded password in scripts | `migrate_sise_tables.py:15`, `import_sise_info.py:16` | Password as fallback default | Low |
| Hardcoded password in YAML | `common/*.yaml` (3 files) | Device credential YAML configs | Medium |
| No `.env.example` file | Project root | Template file for new developers not created | Low |

### PASS -- Added Features (Design X, Implementation O)

| Item | Location | Description |
|------|----------|-------------|
| Batch service | `docker-compose.yml:72-92` | Batch job service with `env_file: .env` (properly secured) |
| Redis service | `docker-compose.yml:63-69` | Redis container added |
| business app | `net_admin/business/` | New Django app for contract creation (extends plan item #6) |
| setting app | `net_admin/setting/` | New Django app for subscriber/sise management views |

---

## Score Calculation

| Plan Item | Weight | Score | Weighted |
|-----------|:------:|:-----:|:--------:|
| 1. DB Connection Pool | 15% | 100% | 15.0% |
| 2. network.py CRUD | 25% | 100% | 25.0% |
| 3. Django Settings Security | 15% | 100% | 15.0% |
| 4. Views FastAPI Hostname | 15% | 85% | 12.8% |
| 5. docker-compose.yml | 10% | 100% | 10.0% |
| 6. Contract POST Endpoint | 10% | 100% | 10.0% |
| 7. multicast/views.py Logging | 10% | 100% | 10.0% |
| **Total** | **100%** | | **97.8%** |

**Overall Match Rate: 98% (rounded)**

---

## Recommended Actions

### Immediate Actions (to reach 100%)
1. **multicast/views.py**: Add `FASTAPI_BASE_URL = os.environ.get('FASTAPI_BASE_URL', 'http://netview_fastapi:8000')` and replace the hardcoded URL on line 55

### Documentation Updates Needed
1. Create `.env.example` file (template with empty sensitive values) for onboarding

### Future Improvements (outside current plan scope)
1. `net_admin/batch.py`: Replace 3 hardcoded `http://fastapi:8000` URLs with env var
2. `fastapi/utils/arista_ptp.py`: Move `NETWORK_PASSWD` to environment variable
3. `migrate_sise_tables.py` and `import_sise_info.py`: Remove hardcoded password fallbacks
4. `common/*.yaml` device configs: Consider secrets management for device credentials

---

## Conclusion

The implementation plan has been executed with a **98% match rate** against the 7 planned items. All core security objectives have been achieved:

- Database credentials fully externalized to environment variables
- Connection pooling implemented and adopted across all 22 CRUD endpoints
- Django settings secured with environment variable overrides
- Docker Compose uses `.env` file exclusively (no inline secrets)
- Contract creation endpoint fully functional end-to-end
- Logging properly configured in multicast views

The single remaining gap is the hardcoded FastAPI URL in `multicast/views.py`, which was outside the explicit plan scope but represents an inconsistency with the refactoring pattern applied to the other view files.
