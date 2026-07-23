"""Shared HTTP client for the OCPF REST API.

All network access to `https://api.ocpf.us/` funnels through `get_json`, so
commands stay testable (mock one function) and error handling lives in one
place. Failures surface as `OcpfApiError` rather than raw library exceptions.
"""

from __future__ import annotations

from typing import Any

import httpx

BASE_URL = "https://api.ocpf.us/"

# Default per-request timeout in seconds. The OCPF API is generally fast, but
# some report-page endpoints return hundreds of rows.
DEFAULT_TIMEOUT = 30.0


class OcpfApiError(Exception):
    """A failure talking to the OCPF API.

    Carries the requested `path` and, for HTTP errors, the `status_code`.
    Network and timeout failures leave `status_code` as None.
    """

    def __init__(
        self,
        message: str,
        *,
        path: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.path = path
        self.status_code = status_code


def get_json(
    path: str,
    params: dict[str, Any] | None = None,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    """GET `path` from the OCPF API and return the parsed JSON body.

    `path` is joined onto `BASE_URL`; a leading slash is tolerated. Raises
    `OcpfApiError` on any HTTP 4xx/5xx status, network failure, timeout, or
    unparseable body.
    """
    url = BASE_URL + path.lstrip("/")
    try:
        response = httpx.get(url, params=params, timeout=timeout)
    except httpx.TimeoutException as exc:
        raise OcpfApiError(
            f"Request to {path} timed out after {timeout:g}s",
            path=path,
        ) from exc
    except httpx.HTTPError as exc:
        raise OcpfApiError(
            f"Network error requesting {path}: {exc}",
            path=path,
        ) from exc

    if response.status_code >= 400:
        raise OcpfApiError(
            f"OCPF API returned HTTP {response.status_code} for {path}",
            path=path,
            status_code=response.status_code,
        )

    try:
        return response.json()
    except ValueError as exc:
        raise OcpfApiError(
            f"OCPF API returned a non-JSON response for {path}",
            path=path,
            status_code=response.status_code,
        ) from exc
