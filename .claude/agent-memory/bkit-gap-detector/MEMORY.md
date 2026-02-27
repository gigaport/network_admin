# Gap Detector Memory

## Project Context
- Project: network_admin (Django + FastAPI + PostgreSQL)
- Stack: Django 4.x frontend/views, FastAPI backend API, PostgreSQL, Docker Compose, Nginx
- Branch pattern: prod_sync_from_server for production sync

## Key Patterns Observed
- FastAPI CRUD endpoints use `get_connection()` context manager from `fastapi/utils/database.py`
- Django views act as proxy layer calling FastAPI endpoints via `requests` library
- Environment variables centralized in `.env` file, read via `os.environ.get()`
- `FASTAPI_BASE_URL` env var used across Django views for FastAPI communication
- Hardcoded password "Sprtmxm1@3" still present in: YAML device configs, utility scripts, `.env` file, `arista_ptp.py`

## Analysis Findings (2026-02-10)
- 7-item implementation plan analyzed
- Overall match rate: 88%
- Main gaps: hardcoded URL in multicast/views.py, password in peripheral files, no .env.example
