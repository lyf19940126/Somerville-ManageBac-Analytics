from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observation, OverallSnapshot, Student, SyncState


def upsert_student(session: Session, student_id: int, full_name: str, email: str | None) -> None:
    existing = session.get(Student, student_id)
    if existing:
        existing.full_name = full_name
        existing.email = email
        existing.updated_at = datetime.utcnow()
    else:
        session.add(
            Student(
                student_id=student_id,
                full_name=full_name or f"Student {student_id}",
                email=email,
                updated_at=datetime.utcnow(),
            )
        )


def upsert_overall_snapshot(
    session: Session,
    *,
    snapshot_date,
    student_id: int,
    course_id: int,
    course_name: str,
    overall_value: float | None,
    overall_text: str | None,
) -> None:
    stmt = select(OverallSnapshot).where(
        OverallSnapshot.date == snapshot_date,
        OverallSnapshot.student_id == student_id,
        OverallSnapshot.course_id == course_id,
    )
    row = session.execute(stmt).scalar_one_or_none()
    if row:
        row.course_name = course_name
        row.overall_value = overall_value
        row.overall_text = overall_text
    else:
        session.add(
            OverallSnapshot(
                date=snapshot_date,
                student_id=student_id,
                course_id=course_id,
                course_name=course_name,
                overall_value=overall_value,
                overall_text=overall_text,
            )
        )


def upsert_observation(
    session: Session,
    *,
    type_: str,
    external_id: str,
    student_id: int,
    date_time,
    category: str | None,
    content: str | None,
    source: str | None,
) -> None:
    stmt = select(Observation).where(Observation.type == type_, Observation.external_id == external_id)
    row = session.execute(stmt).scalar_one_or_none()
    now = datetime.utcnow()
    if row:
        row.student_id = student_id
        row.date_time = date_time
        row.category = category
        row.content = content
        row.source = source
        row.updated_at = now
    else:
        session.add(
            Observation(
                type=type_,
                external_id=external_id,
                student_id=student_id,
                date_time=date_time,
                category=category,
                content=content,
                source=source,
                created_at=now,
                updated_at=now,
            )
        )


def get_sync_state(session: Session, key: str) -> str | None:
    row = session.get(SyncState, key)
    return row.value if row else None


def set_sync_state(session: Session, key: str, value: str) -> None:
    row = session.get(SyncState, key)
    if row:
        row.value = value
    else:
        session.add(SyncState(key=key, value=value))
