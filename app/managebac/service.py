from __future__ import annotations

import logging
from difflib import SequenceMatcher
from typing import Any

import httpx

from app.managebac.client import ManageBacClient

logger = logging.getLogger(__name__)

ENDPOINTS = {
    "year_groups_list": "/v2/year_groups",
    "year_group_students": "/v2/year_groups/{id}/students",  # TODO: verify exact path in live API
    "behaviour_notes": "/v2/behavior/notes",
    "classes_list": "/v2/classes",
    "class_term_grades": "/v2/classes/{id}/term_grades",
    "student_term_grades": "/v2/students/{id}/term_grades",  # optional; 404 fallback supported
    "homeroom_term_attendance": "/v2/homeroom/attendance/term_attendance",  # TODO: verify params/response
}


class ManageBacService:
    def __init__(self, client: ManageBacClient) -> None:
        self.client = client

    def fetch_year_groups(self, page: int = 1, per_page: int = 100) -> list[dict[str, Any]]:
        payload = self.client.request(
            "GET",
            ENDPOINTS["year_groups_list"],
            params={"page": page, "per_page": per_page},
        )
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in ("data", "year_groups", "items"):
                if isinstance(payload.get(key), list):
                    return payload[key]
        return []

    def resolve_homeroom_id(self, homeroom_name: str, homeroom_id_override: int | None = None) -> int:
        if homeroom_id_override is not None:
            return homeroom_id_override

        groups = self.fetch_year_groups(page=1, per_page=200)
        if not groups:
            raise RuntimeError(
                "No year groups returned by API. Set HOMEROOM_ID explicitly or verify ENDPOINTS['year_groups_list']."
            )

        exact = [g for g in groups if str(g.get("name", "")).strip() == homeroom_name]
        if len(exact) == 1:
            return int(exact[0]["id"])

        contains = [
            g
            for g in groups
            if homeroom_name.lower() in str(g.get("name", "")).strip().lower()
        ]
        candidates = exact or contains
        if not candidates:
            raise RuntimeError(
                f"Could not find homeroom '{homeroom_name}'. Set HOMEROOM_ID or adjust HOMEROOM_NAME."
            )

        ranked = sorted(
            candidates,
            key=lambda g: SequenceMatcher(
                None,
                homeroom_name.lower(),
                str(g.get("name", "")).lower(),
            ).ratio(),
            reverse=True,
        )
        chosen = ranked[0]

        if len(ranked) > 1:
            preview = ", ".join(f"{g.get('name')}({g.get('id')})" for g in ranked[:5])
            logger.warning("Multiple homeroom candidates found; selected best match. Candidates: %s", preview)

        return int(chosen["id"])

    def fetch_homeroom_students(self, homeroom_id: int) -> list[dict[str, Any]]:
        payload = self.client.request(
            "GET",
            ENDPOINTS["year_group_students"].format(id=homeroom_id),
        )
        if isinstance(payload, list):
            students = payload
        elif isinstance(payload, dict):
            students = payload.get("students") or payload.get("data") or payload.get("items") or []
        else:
            students = []

        normalized: list[dict[str, Any]] = []
        for student in students:
            sid = student.get("id") or student.get("student_id")
            if sid is None:
                continue
            normalized.append(
                {
                    "student_id": int(sid),
                    "full_name": student.get("full_name")
                    or " ".join(
                        p for p in [student.get("first_name"), student.get("last_name")] if p
                    ).strip(),
                    "email": student.get("email"),
                }
            )
        return normalized

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
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("data") or payload.get("notes") or payload.get("items") or []
        return []

    def fetch_classes(self) -> list[dict[str, Any]]:
        payload = self.client.request("GET", ENDPOINTS["classes_list"], params={"per_page": 200})
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("data") or payload.get("classes") or payload.get("items") or []
        return []

    def fetch_student_term_grades(self, student_id: int, term_id: str) -> list[dict[str, Any]]:
        path = ENDPOINTS["student_term_grades"].format(id=student_id)
        try:
            payload = self.client.request("GET", path, params={"term_id": term_id})
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise FileNotFoundError("student term grades endpoint unavailable") from exc
            raise
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("data") or payload.get("grades") or payload.get("items") or []
        return []

    def fetch_class_term_grades(self, class_id: int, term_id: str) -> list[dict[str, Any]]:
        payload = self.client.request(
            "GET",
            ENDPOINTS["class_term_grades"].format(id=class_id),
            params={"term_id": term_id},
        )
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("data") or payload.get("grades") or payload.get("items") or []
        return []

    def fetch_term_attendance(self, term_id: str, homeroom_id: int) -> list[dict[str, Any]]:
        try:
            payload = self.client.request(
                "GET",
                ENDPOINTS["homeroom_term_attendance"],
                params={"term_id": term_id, "homeroom_id": homeroom_id},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (400, 404):
                logger.warning("Attendance endpoint not configured; TODO verify endpoint mapping and params.")
                return []
            raise

        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            return payload.get("data") or payload.get("attendance") or payload.get("items") or []
        return []
