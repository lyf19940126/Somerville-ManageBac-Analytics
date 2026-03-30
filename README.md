# Somerville ManageBac Analytics (MVP)

Enterprise-grade MVP for unattended daily ManageBac sync and reporting on a Windows server.

## What this project does

- Uses **advisor_id + graduating_year** to determine the student cohort.
- Syncs students, per-class term grades snapshots, behaviour notes, and attendance stubs.
- Uses ManageBac CN class-term-grades endpoint:
  - `GET /v2/classes/{class_id}/assessments/term/{term_id}/term-grades`
- Stores data in SQLite and generates per-student trend charts + HTML reports.

## Environment configuration

Copy `.env.example` to `.env` and fill values:

- `MANAGEBAC_BASE_URL` (default CN: `https://api.managebac.cn`)
- `MANAGEBAC_TOKEN` (required)
- `HOMEROOM_ADVISOR_ID` (required int)
- `TARGET_GRADUATING_YEAR` (required int)
- `TERM_ID` (required int, e.g. `106673`)
- `REPORT_TIMEZONE` (optional, default `Asia/Shanghai`)

Authentication header is:

- `auth-token: <MANAGEBAC_TOKEN>`

> Do **not** use Bearer Authorization for this project.

## Quickstart (Windows PowerShell)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
# edit .env
python -m app.jobs.daily_sync
```

## Smoke test

After configuring `.env`:

```powershell
python -m app.jobs.daily_sync
```

Expected behavior:
- logs selected student count by advisor/year
- calls class assessments term-grades endpoint
- if `term_grade` is null for new term, sync still succeeds (stored as null/text fallback)

Quick cohort check:

```powershell
python scripts/resolve_advisor_students.py
```

## Windows timezone note

If Windows Python cannot resolve `Asia/Shanghai` with `ZoneInfo`, install:

```powershell
pip install tzdata
```

The job will log a warning and fall back to UTC if timezone data is unavailable.

## Scheduler (00:00 UTC+8)

1. Set server timezone to UTC+8 (`China Standard Time`).
2. Task Scheduler → Create Task.
3. Action:
   - Program/script: `<repo>\venv\Scripts\python.exe`
   - Add arguments: `-m app.jobs.daily_sync`
   - Start in: `<repo root>`
4. Trigger: Daily at `00:00:00`.

## Output locations

- SQLite DB: `data/app.db`
- Logs: `logs/app.log`
- Reports: `output/reports/*.html`
- Charts: `output/reports/*_trend.png`

## Security notes

- `.env` is gitignored and must never be committed.
- Never print API tokens in logs.
