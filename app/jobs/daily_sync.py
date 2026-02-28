from __future__ import annotations

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select

from app.analytics.charts import generate_student_trend_chart
from app.config import ConfigError, ensure_directories, load_settings
from app.db.crud import (
    get_sync_state,
    set_sync_state,
    upsert_observation,
    upsert_overall_snapshot,
    upsert_student,
)
from app.db.models import Base, Observation, OverallSnapshot, Student, get_engine, get_session_factory
from app.managebac.client import ManageBacClient
from app.managebac.service import ManageBacService
from app.reports.generator import generate_student_report


logger = logging.getLogger("daily_sync")


def configure_logging() -> None:
    ensure_directories()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=[
            logging.FileHandler("logs/app.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def sync() -> None:
    configure_logging()
    settings = load_settings(require_term_id=True)

    engine = get_engine(settings.database_url)
    Base.metadata.create_all(engine)
    SessionFactory = get_session_factory(settings.database_url)

    client = ManageBacClient(settings.managebac_base_url, settings.managebac_token)
    service = ManageBacService(client)

    counts = {
        "students": 0,
        "snapshots": 0,
        "behaviour": 0,
        "attendance": 0,
        "reports": 0,
    }

    try:
        homeroom_id = service.resolve_homeroom_id(settings.homeroom_name, settings.homeroom_id)
        students = service.fetch_homeroom_students(homeroom_id)

        student_ids = [s["student_id"] for s in students]

        local_today = datetime.now(ZoneInfo(settings.report_timezone)).date()

        with SessionFactory() as session:
            for s in students:
                upsert_student(session, s["student_id"], s.get("full_name") or f"Student {s['student_id']}", s.get("email"))
            counts["students"] = len(students)

            used_student_grade_endpoint = True
            for sid in student_ids:
                try:
                    grades = service.fetch_student_term_grades(sid, settings.term_id)
                except FileNotFoundError:
                    used_student_grade_endpoint = False
                    break
                for g in grades:
                    overall_value = g.get("overall")
                    numeric_val = None
                    overall_text = None
                    if isinstance(overall_value, (int, float)):
                        numeric_val = float(overall_value)
                    elif overall_value is not None:
                        overall_text = str(overall_value)

                    upsert_overall_snapshot(
                        session,
                        snapshot_date=local_today,
                        student_id=sid,
                        course_id=int(g.get("class_id") or g.get("course_id") or 0),
                        course_name=str(g.get("class_name") or g.get("course_name") or "Unknown Course"),
                        overall_value=numeric_val,
                        overall_text=overall_text,
                    )
                    counts["snapshots"] += 1

            if not used_student_grade_endpoint:
                logger.info("Student term grades endpoint returned 404; falling back to class term grades flow.")
                classes = service.fetch_classes()
                student_set = set(student_ids)
                for cls in classes:
                    class_id = cls.get("id")
                    if not class_id:
                        continue
                    rows = service.fetch_class_term_grades(int(class_id), settings.term_id)
                    for row in rows:
                        sid = row.get("student_id")
                        if sid not in student_set:
                            continue
                        overall_value = row.get("overall")
                        numeric_val = None
                        overall_text = None
                        if isinstance(overall_value, (int, float)):
                            numeric_val = float(overall_value)
                        elif overall_value is not None:
                            overall_text = str(overall_value)

                        upsert_overall_snapshot(
                            session,
                            snapshot_date=local_today,
                            student_id=int(sid),
                            course_id=int(row.get("class_id") or class_id),
                            course_name=str(
                                row.get("class_name") or cls.get("name") or row.get("course_name") or "Unknown Course"
                            ),
                            overall_value=numeric_val,
                            overall_text=overall_text,
                        )
                        counts["snapshots"] += 1

            last_behaviour_sync = get_sync_state(session, "last_behaviour_sync")
            page = 1
            max_updated: datetime | None = None

            while True:
                notes = service.fetch_behaviour_notes(
                    student_ids=student_ids,
                    modified_since=last_behaviour_sync,
                    page=page,
                    per_page=100,
                )
                if not notes:
                    break

                for note in notes:
                    external_id = str(note.get("id") or "")
                    sid = note.get("student_id")
                    if not external_id or sid is None:
                        continue
                    dt = parse_datetime(note.get("incident_time") or note.get("created_at"))
                    updated = parse_datetime(note.get("updated_at"))
                    if updated and (max_updated is None or updated > max_updated):
                        max_updated = updated

                    upsert_observation(
                        session,
                        type_="behaviour",
                        external_id=external_id,
                        student_id=int(sid),
                        date_time=dt,
                        category=str(note.get("behavior_type") or "behaviour"),
                        content=str(note.get("notes") or ""),
                        source=str(note.get("reported_by") or "ManageBac"),
                    )
                    counts["behaviour"] += 1

                if len(notes) < 100:
                    break
                page += 1

            if max_updated:
                set_sync_state(session, "last_behaviour_sync", max_updated.isoformat())

            attendance_rows = service.fetch_term_attendance(settings.term_id, homeroom_id)
            for row in attendance_rows:
                sid = row.get("student_id")
                external_id = row.get("id")
                if sid is None or external_id is None:
                    continue
                upsert_observation(
                    session,
                    type_="attendance",
                    external_id=str(external_id),
                    student_id=int(sid),
                    date_time=parse_datetime(row.get("date") or row.get("recorded_at")),
                    category=str(row.get("status") or row.get("type") or "attendance"),
                    content=str(row.get("summary") or row.get("notes") or ""),
                    source=str(row.get("recorded_by") or "ManageBac"),
                )
                counts["attendance"] += 1

            session.commit()

        with SessionFactory() as session:
            student_rows = session.execute(select(Student)).scalars().all()
            for student in student_rows:
                snapshot_rows = session.execute(
                    select(OverallSnapshot).where(OverallSnapshot.student_id == student.student_id)
                ).scalars().all()
                points = [
                    (str(r.date), r.course_name, r.overall_value)
                    for r in snapshot_rows
                ]
                chart_file = f"output/reports/student_{student.student_id}_trend.png"
                generate_student_trend_chart(student.full_name, points, chart_file)

                behaviour = [
                    {
                        "date_time": o.date_time.isoformat() if o.date_time else "",
                        "category": o.category or "",
                        "content": o.content or "",
                        "source": o.source or "",
                    }
                    for o in session.execute(
                        select(Observation)
                        .where(Observation.student_id == student.student_id, Observation.type == "behaviour")
                        .order_by(Observation.date_time.desc())
                        .limit(20)
                    ).scalars().all()
                ]
                attendance = [
                    {
                        "date_time": o.date_time.isoformat() if o.date_time else "",
                        "category": o.category or "",
                        "content": o.content or "",
                        "source": o.source or "",
                    }
                    for o in session.execute(
                        select(Observation)
                        .where(Observation.student_id == student.student_id, Observation.type == "attendance")
                        .order_by(Observation.date_time.desc())
                        .limit(20)
                    ).scalars().all()
                ]

                output_html = f"output/reports/student_{student.student_id}.html"
                generate_student_report(
                    student_name=student.full_name,
                    chart_path=f"student_{student.student_id}_trend.png",
                    behaviour=behaviour,
                    attendance=attendance,
                    output_file=output_html,
                )
                counts["reports"] += 1

        logger.info(
            "Sync complete. students=%s snapshots=%s behaviour=%s attendance=%s reports=%s",
            counts["students"],
            counts["snapshots"],
            counts["behaviour"],
            counts["attendance"],
            counts["reports"],
        )

    finally:
        client.close()


if __name__ == "__main__":
    try:
        sync()
    except (ConfigError, httpx.HTTPError, RuntimeError) as exc:
        logger.error("Daily sync failed: %s", exc)
        raise
