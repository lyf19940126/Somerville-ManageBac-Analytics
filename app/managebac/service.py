from __future__ import annotations

import logging
from typing import Any

import httpx

from app.managebac.client import ManageBacClient

logger = logging.getLogger(__name__)

ENDPOINTS = {
    "year_groups_list": "/v2/year-groups",
    "students_list": "/v2/students",
    "behaviour_notes": "/v2/behavior/notes",
    "classes_list": "/v2/classes",
    "class_term_grades": "/v2/classes/{id}/term_grades",
    "student_term_grades": "/v2/students/{id}/term_grades",  # optional; 404 fallback supported
    "homeroom_term_attendance": "/v2/homeroom/attendance/term_attendance",  # TODO: verify params/response
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

    def fetch_year_groups(self, page: int = 1, per_page: int = 100) -> list[dict[str, Any]]:
        payload = self.client.request(
            "GET",
            ENDPOINTS["year_groups_list"],
            params={"page": page, "per_page": per_page},
        )
        return self._extract_list(payload, ("year_groups", "data", "items"))

    def list_students_for_homeroom(
        self,
        advisor_id: int,
        target_graduating_year: int,
        per_page: int = 200,
    ) -> list[dict[str, Any]]:
        page = 1
        selected: list[dict[str, Any]] = []

        while True:
            payload = self.client.request(
                "GET",
                ENDPOINTS["students_list"],
                params={
                    "homeroom_advisor_ids": advisor_id,
                    "page": page,
                    "per_page": per_page,
                },
            )
            students = self._extract_list(payload, ("students", "data", "items"))
            if not students:
                break

            for student in students:
                grad_year = student.get("graduating_year")
                try:
                    grad_year_int = int(grad_year)
                except (TypeError, ValueError):
                    continue
                if grad_year_int != target_graduating_year:
                    continue
                if student.get("archived") is True:
                    continue
                if student.get("graduated_on"):
                    continue

                sid = student.get("id") or student.get("student_id")
                if sid is None:
                    continue
                selected.append(
                    {
                        "student_id": int(sid),
                        "full_name": student.get("full_name")
                        or " ".join(
                            part for part in [student.get("first_name"), student.get("last_name")] if part
                        ).strip(),
                        "email": student.get("email"),
                        "graduating_year": grad_year_int,
                    }
                )

            if len(students) < per_page:
                break
            page += 1

        return selected

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
        return self._extract_list(payload, ("data", "classes", "items"))

    def fetch_student_term_grades(self, student_id: int, term_id: str) -> list[dict[str, Any]]:
        path = ENDPOINTS["student_term_grades"].format(id=student_id)
        try:
            payload = self.client.request("GET", path, params={"term_id": term_id})
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise FileNotFoundError("student term grades endpoint unavailable") from exc
            raise
        return self._extract_list(payload, ("data", "grades", "items"))

    def fetch_class_term_grades(self, class_id: int, term_id: str) -> list[dict[str, Any]]:
        payload = self.client.request(
            "GET",
            ENDPOINTS["class_term_grades"].format(id=class_id),
            params={"term_id": term_id},
        )
        return self._extract_list(payload, ("data", "grades", "items"))

    def fetch_term_attendance(self, term_id: str, student_ids: list[int]) -> list[dict[str, Any]]:
        # TODO: verify endpoint params for tenant-specific attendance API.
        try:
            payload = self.client.request(
                "GET",
                ENDPOINTS["homeroom_term_attendance"],
                params={"term_id": term_id, "student_ids": student_ids},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (400, 404):
                logger.warning("Attendance endpoint not configured; TODO verify endpoint mapping and params.")
                return []
            raise

        return self._extract_list(payload, ("data", "attendance", "items"))
