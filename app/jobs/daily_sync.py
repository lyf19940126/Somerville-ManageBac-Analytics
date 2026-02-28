from __future__ import annotations

import logging
from datetime import datetime
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


def _normalize_overall(value):
    if isinstance(value, (int, float)):
        return float(value), None
    if value is None:
        return None, None
    return None, str(value)


def sync() -> None:
    configure_logging()
    settings = load_settings()

    engine = get_engine(settings.database_url)
    Base.metadata.create_all(engine)
    session_factory = get_session_factory(settings.database_url)

    client = ManageBacClient(settings.managebac_base_url, settings.managebac_token)
    service = ManageBacService(client)

    counts = {"students": 0, "snapshots": 0, "behaviour": 0, "attendance": 0, "reports": 0}

    try:
        students = service.list_students_for_homeroom(
            advisor_id=settings.homeroom_advisor_id,
            target_graduating_year=settings.target_graduating_year,
        )
        student_ids = [s["student_id"] for s in students]

        if students:
            sample = students[0]
            logger.info(
                "Homeroom filtering complete: students=%s sample=(id=%s,name=%s,graduating_year=%s)",
                len(students),
                sample.get("student_id"),
                sample.get("full_name") or "",
                sample.get("graduating_year"),
            )
        else:
            logger.warning(
                "Homeroom filtering returned zero students for advisor_id=%s graduating_year=%s",
                settings.homeroom_advisor_id,
                settings.target_graduating_year,
            )

        with session_factory() as session:
            for student in students:
                upsert_student(
                    session,
                    student["student_id"],
                    student.get("full_name") or f"Student {student['student_id']}",
                    student.get("email"),
                )
            counts["students"] = len(students)

            if not settings.term_id:
                logger.error(
                    "TERM_ID is missing. Skipping term-dependent grade/attendance sync, but student filtering succeeded."
                )
            else:
                local_today = datetime.now(ZoneInfo(settings.report_timezone)).date()
                used_student_grade_endpoint = True
                for sid in student_ids:
                    try:
                        grades = service.fetch_student_term_grades(sid, settings.term_id)
                    except FileNotFoundError:
                        used_student_grade_endpoint = False
                        break
                    for grade in grades:
                        overall_value, overall_text = _normalize_overall(grade.get("overall"))
                        course_id = grade.get("class_id") or grade.get("course_id")
                        if course_id is None:
                            continue
                        upsert_overall_snapshot(
                            session,
                            snapshot_date=local_today,
                            student_id=sid,
                            course_id=int(course_id),
                            course_name=str(grade.get("class_name") or grade.get("course_name") or "Unknown Course"),
                            overall_value=overall_value,
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
                            overall_value, overall_text = _normalize_overall(row.get("overall"))
                            upsert_overall_snapshot(
                                session,
                                snapshot_date=local_today,
                                student_id=int(sid),
                                course_id=int(row.get("class_id") or class_id),
                                course_name=str(
                                    row.get("class_name") or cls.get("name") or row.get("course_name") or "Unknown Course"
                                ),
                                overall_value=overall_value,
                                overall_text=overall_text,
                            )
                            counts["snapshots"] += 1

            last_behaviour_sync = get_sync_state(session, "last_behaviour_sync")
            page = 1
            max_updated: datetime | None = None
            while student_ids:
                notes = service.fetch_behaviour_notes(
                    student_ids=student_ids,
                    modified_since=last_behaviour_sync,
                    page=page,
                    per_page=100,
                )
                if not notes:
                    break
                for note in notes:
                    sid = note.get("student_id")
                    external_id = note.get("id")
                    if sid is None or external_id is None:
                        continue
                    updated = parse_datetime(note.get("updated_at"))
                    if updated and (max_updated is None or updated > max_updated):
                        max_updated = updated
                    upsert_observation(
                        session,
                        type_="behaviour",
                        external_id=str(external_id),
                        student_id=int(sid),
                        date_time=parse_datetime(note.get("incident_time") or note.get("created_at")),
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

            if settings.term_id and student_ids:
                attendance_rows = service.fetch_term_attendance(settings.term_id, student_ids)
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

        with session_factory() as session:
            student_rows = session.execute(select(Student)).scalars().all()
            for student in student_rows:
                snapshot_rows = session.execute(
                    select(OverallSnapshot).where(OverallSnapshot.student_id == student.student_id)
                ).scalars().all()
                points = [(str(row.date), row.course_name, row.overall_value) for row in snapshot_rows]
                chart_file = f"output/reports/student_{student.student_id}_trend.png"
                generate_student_trend_chart(student.full_name, points, chart_file)

                behaviour = [
                    {
                        "date_time": row.date_time.isoformat() if row.date_time else "",
                        "category": row.category or "",
                        "content": row.content or "",
                        "source": row.source or "",
                    }
                    for row in session.execute(
                        select(Observation)
                        .where(Observation.student_id == student.student_id, Observation.type == "behaviour")
                        .order_by(Observation.date_time.desc())
                        .limit(20)
                    ).scalars()
                ]
                attendance = [
                    {
                        "date_time": row.date_time.isoformat() if row.date_time else "",
                        "category": row.category or "",
                        "content": row.content or "",
                        "source": row.source or "",
                    }
                    for row in session.execute(
                        select(Observation)
                        .where(Observation.student_id == student.student_id, Observation.type == "attendance")
                        .order_by(Observation.date_time.desc())
                        .limit(20)
                    ).scalars()
                ]

                generate_student_report(
                    student_name=student.full_name,
                    chart_path=f"student_{student.student_id}_trend.png",
                    behaviour=behaviour,
                    attendance=attendance,
                    output_file=f"output/reports/student_{student.student_id}.html",
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
