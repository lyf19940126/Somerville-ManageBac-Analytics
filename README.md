# Somerville ManageBac Analytics (MVP)

Enterprise-grade MVP for unattended daily ManageBac sync and reporting on a Windows server.

## What this project does

- Uses **homeroom advisor + graduating year** to determine the target student cohort.
- Syncs students, daily per-course `OVERALL` snapshots, behaviour notes, and attendance stubs.
- Stores data in SQLite.
- Generates student trend charts (`.png`) and HTML reports.

## Environment configuration

Copy `.env.example` to `.env` and fill all required values:

- `MANAGEBAC_TOKEN` (required)
- `MANAGEBAC_BASE_URL` (required)
- `HOMEROOM_ADVISOR_ID` (required, integer)
- `TARGET_GRADUATING_YEAR` (required, integer)
- `TERM_ID` (required)
- `REPORT_TIMEZONE` (optional, default `Asia/Shanghai`)

> Auth header is `auth-token: <token>`. Do not use Bearer auth.

## Quickstart (Windows PowerShell)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# edit .env
```

### Smoke test

Run after `.env` is configured:

```powershell
python -m app.jobs.daily_sync
```

## Daily Task Scheduler (00:00 UTC+8)

1. Set server timezone to UTC+8 (`China Standard Time`).
2. Task Scheduler → Create Task.
3. Action:
   - Program/script: `<repo>\venv\Scripts\python.exe`
   - Add arguments: `-m app.jobs.daily_sync`
   - Start in: `<repo root>`
4. Trigger: Daily at `00:00:00`.

## Useful commands

```powershell
python -m app.db.init_db
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Troubleshooting cohort selection

If no students are selected:

1. Verify `HOMEROOM_ADVISOR_ID` is correct.
2. Verify `TARGET_GRADUATING_YEAR` matches student records.
3. Verify token scope has permission to read `/v2/students`.
4. Check logs for the INFO line printing selected count and preview records.

## Endpoint mapping

All endpoint paths are centralized in `app/managebac/service.py` via `ENDPOINTS`.

## Output locations

- SQLite DB: `data/app.db`
- Logs: `logs/app.log`
- Reports: `output/reports/*.html`
- Charts: `output/reports/*_trend.png`

## Security notes

- `.env` is gitignored and must never be committed.
- Never print tokens in logs.
