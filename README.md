# Somerville ManageBac Analytics (MVP)

Enterprise-grade MVP for unattended daily ManageBac sync and reporting on a Windows server.

## What this project does

- Uses **homeroom advisor + graduating year** to auto-build Somerville student scope.
- Syncs students, daily per-course `OVERALL` snapshots, behaviour notes, and attendance stubs.
- Stores data in SQLite.
- Generates student trend charts (`.png`) and HTML reports.

## Environment configuration

Copy `.env.example` to `.env` and set:

- `MANAGEBAC_TOKEN` (required)
- `MANAGEBAC_BASE_URL` (required, e.g. `https://api.managebac.cn`)
- `HOMEROOM_ADVISOR_ID` (required, integer)
- `TARGET_GRADUATING_YEAR` (required, integer, e.g. `2028`)
- `TERM_ID` (recommended; default `106673` in example)
- `REPORT_TIMEZONE` (optional, default `Asia/Shanghai`)

> Auth header is `auth-token: <token>`. Do not use Bearer auth.

## Quickstart (Windows PowerShell)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# fill .env values
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
python scripts/resolve_homeroom.py
python -m app.db.init_db
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Endpoint mapping

All endpoint paths are centralized in `app/managebac/service.py` via `ENDPOINTS`.

- Year groups path uses `/v2/year-groups` (URL uses hyphen).
- Parsing supports `year_groups` (underscore key) and fallback keys.

## Output locations

- SQLite DB: `data/app.db`
- Logs: `logs/app.log`
- Reports: `output/reports/*.html`
- Charts: `output/reports/*_trend.png`

## Security notes

- `.env` is gitignored and must never be committed.
- Never print tokens in logs.
