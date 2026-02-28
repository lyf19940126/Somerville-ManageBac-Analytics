# Somerville ManageBac Analytics (MVP)

Enterprise-grade MVP for unattended daily ManageBac sync and reporting on a Windows server.

## What this project does

- Automatically resolves homeroom by name (`HOMEROOM_NAME=Somerville`) without manual ID input (unless optional override is set).
- Syncs Somerville students.
- Captures daily per-course `OVERALL` snapshots.
- Syncs behaviour notes incrementally from `/v2/behavior/notes`.
- Includes attendance sync placeholder mapping and storage.
- Stores everything in SQLite.
- Generates student trend charts (`.png`) and HTML reports.

## Quickstart

1. Create and activate virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
3. Copy environment template:
   ```powershell
   copy .env.example .env
   ```
4. Fill `.env`:
   - `MANAGEBAC_TOKEN` (required)
   - `MANAGEBAC_BASE_URL` (required, e.g. `https://api.managebac.com`)
   - `TERM_ID` (required)
   - `HOMEROOM_ID` optional override
5. Run daily sync once:
   ```powershell
   python -m app.jobs.daily_sync
   ```

## Health endpoint

Start API server:
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Health check:
- `GET /health` returns `{ "status": "ok" }`.

## Windows Server Task Scheduler (daily 00:00, UTC+8)

1. Ensure Windows timezone is set to UTC+8 (`China Standard Time`) if you want local 00:00 trigger alignment.
2. Open **Task Scheduler** → **Create Task**.
3. General:
   - Run whether user is logged on or not.
   - Run with highest privileges (recommended).
4. Trigger:
   - Daily
   - Start: `00:00:00`
5. Action: **Start a program**
   - **Program/script**: `<repo>\venv\Scripts\python.exe`
   - **Add arguments**: `-m app.jobs.daily_sync`
   - **Start in**: `<repo root>`
6. Conditions/Settings:
   - Enable retries on failure (recommended).

## Useful commands

Resolve homeroom and count students:
```powershell
python scripts/resolve_homeroom.py
```

Initialize DB tables:
```powershell
python -m app.db.init_db
```

## Output locations

- SQLite DB: `data/app.db`
- Logs: `logs/app.log`
- Reports: `output/reports/*.html`
- Charts: `output/reports/*_trend.png`

## Security notes

- `.env` is gitignored and must never be committed.
- Token is sent as `auth-token` header.
- Logs avoid secrets and focus on aggregate sync counts.

## Endpoint mapping

Endpoint paths are centralized in `app/managebac/service.py` via `ENDPOINTS` dictionary so you can adjust for tenant-specific API differences.
