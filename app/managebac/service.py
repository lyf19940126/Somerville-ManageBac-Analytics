from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

import httpx

from app.managebac.client import ManageBacClient

logger = logging.getLogger(__name__)

ENDPOINTS = {
    "students_list": "/v2/students",
    "student_memberships": "/v2/students/{id}/memberships",
    "classes_list": "/v2/classes",
    "class_term_assessment_grades": "/v2/classes/{id}/assessments/term/{term_id}/term-grades",
    "behaviour_notes": "/v2/behavior/notes",
    "term_attendance": "/v2/homeroom/attendance/term_attendance",  # TODO: verify tenant-specific params
}


class ManageBacService:
    def __init__(self, client: ManageBacClient) -> None:
        self.client = client

    @staticmethod
    def _extract_list(payload: Any, keys: tuple[str, ...]) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in keys:
                value = payload.get(key)
                if isinstance(value, list):
                    return value
        return []

    def fetch_students_by_advisor(self, advisor_id: int, page: int = 1, per_page: int = 200) -> list[dict[str, Any]]:
        payload = self.client.request(
            "GET",
            ENDPOINTS["students_list"],
            params={"homeroom_advisor_ids": advisor_id, "page": page, "per_page": per_page},
        )
        return self._extract_list(payload, ("students", "data", "items"))

    def filter_students_by_graduating_year(self, students: list[dict[str, Any]], target_year: int) -> list[dict[str, Any]]:
        filtered: list[dict[str, Any]] = []
        for student in students:
            try:
                if int(student.get("graduating_year")) == target_year:
                    filtered.append(student)
            except (TypeError, ValueError):
                continue
        return filtered

    def select_target_students(
        self,
        advisor_id: int,
        target_graduating_year: int,
        include_archived: bool | None = None,
        per_page: int = 200,
    ) -> list[dict[str, Any]]:
        page = 1
        collected: list[dict[str, Any]] = []

        while True:
            chunk = self.fetch_students_by_advisor(advisor_id=advisor_id, page=page, per_page=per_page)
            if not chunk:
                break
            collected.extend(chunk)
            if len(chunk) < per_page:
                break
            page += 1

        filtered = self.filter_students_by_graduating_year(collected, target_graduating_year)
        if include_archived is False:
            filtered = [s for s in filtered if s.get("archived") is not True]
        return filtered

    def fetch_student_memberships(self, student_id: int) -> list[dict[str, Any]]:
        try:
            payload = self.client.request(
                "GET",
                ENDPOINTS["student_memberships"].format(id=student_id),
                params={"per_page": 200},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (403, 404):
                logger.warning("Membership endpoint unavailable for student_id=%s (status=%s)", student_id, exc.response.status_code)
                return []
            raise
        return self._extract_list(payload, ("memberships", "data", "items"))

    def build_class_student_map(self, student_ids: list[int]) -> dict[int, set[int]]:
        class_student_map: dict[int, set[int]] = defaultdict(set)

        for sid in student_ids:
            memberships = self.fetch_student_memberships(sid)
            for membership in memberships:
                class_id = (
                    membership.get("class_id")
                    or (membership.get("class") or {}).get("id")
                    or (membership.get("klass") or {}).get("id")
                )
                if class_id is None:
                    continue
                class_student_map[int(class_id)].add(int(sid))

        if class_student_map:
            return class_student_map

        logger.warning("No class memberships resolved; trying classes list fallback.")
        classes = self.fetch_classes()
        target = set(student_ids)
        for cls in classes:
            class_id = cls.get("id")
            if class_id is None:
                continue
            roster = cls.get("students") or cls.get("student_ids") or []
            ids: set[int] = set()
            if isinstance(roster, list):
                for item in roster:
                    if isinstance(item, dict):
                        value = item.get("id") or item.get("student_id")
                    else:
                        value = item
                    if value is None:
                        continue
                    try:
                        parsed = int(value)
                    except (TypeError, ValueError):
                        continue
                    if parsed in target:
                        ids.add(parsed)
            if ids:
                class_student_map[int(class_id)] = ids

        return class_student_map

    def fetch_class_term_assessment_grades(
        self,
        class_id: int,
        term_id: int,
        student_ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if student_ids:
            params["student_ids"] = ",".join(str(sid) for sid in sorted(set(student_ids)))

        payload = self.client.request(
            "GET",
            ENDPOINTS["class_term_assessment_grades"].format(id=class_id, term_id=term_id),
            params=params,
        )
        return self._extract_list(payload, ("students", "data", "items"))

    def fetch_behaviour_notes(
        self,
        student_ids: list[int],
        modified_since: str | None,
        page: int,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "page": page,
            "per_page": per_page,
            "student_ids": student_ids,
        }
        if modified_since:
            params["modified_since"] = modified_since
        payload = self.client.request("GET", ENDPOINTS["behaviour_notes"], params=params)
        return self._extract_list(payload, ("data", "notes", "items"))

    def fetch_classes(self) -> list[dict[str, Any]]:
        payload = self.client.request("GET", ENDPOINTS["classes_list"], params={"per_page": 200})
        return self._extract_list(payload, ("classes", "data", "items"))

    def fetch_term_attendance(self, term_id: int, student_ids: list[int]) -> list[dict[str, Any]]:
        try:
            payload = self.client.request(
                "GET",
                ENDPOINTS["term_attendance"],
                params={"term_id": term_id, "student_ids": ",".join(str(sid) for sid in student_ids)},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (400, 403, 404):
                logger.warning("Attendance endpoint not configured or unauthorized; skipping (status=%s)", exc.response.status_code)
                return []
            raise
        return self._extract_list(payload, ("attendance", "data", "items"))
