from __future__ import annotations

import time
from typing import Any

import httpx


class ManageBacClient:
    def __init__(self, base_url: str, token: str, timeout: float = 30.0) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={"auth-token": token},
        )

    def close(self) -> None:
        self._client.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        max_retries: int = 3,
    ) -> Any:
        backoff_seconds = 1.0
        for attempt in range(max_retries + 1):
            response = self._client.request(method=method, url=path, params=params, json=json)
            if response.status_code < 400:
                return response.json() if response.content else None

            should_retry = response.status_code == 429 or 500 <= response.status_code < 600
            if should_retry and attempt < max_retries:
                retry_after = response.headers.get("Retry-After")
                sleep_for = float(retry_after) if retry_after and retry_after.isdigit() else backoff_seconds
                time.sleep(sleep_for)
                backoff_seconds *= 2
                continue

            response.raise_for_status()

        raise RuntimeError("Unexpected retry loop exit")
