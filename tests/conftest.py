"""Shared pytest fixtures and helpers for the voc_review_fetcher test suite.

Centralizes the project-root sys.path insertion (so individual test modules can
import `api.*` / `lib.*` without repeating boilerplate) and provides a small
`FakeResponse` stand-in for `requests` responses plus an HTTPError factory. All
external HTTP in the suite is mocked through these — no live network calls.
"""

from __future__ import annotations

import json as _json
import sys
from pathlib import Path
from typing import Any

import pytest
from requests.exceptions import HTTPError

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


class FakeResponse:
    """Minimal stand-in for a `requests.Response`.

    Implements just the surface the clients touch: `.status_code`, `.text`,
    `.json()`, and `.raise_for_status()` (which raises `HTTPError` carrying this
    response, mirroring real `requests` behavior for >= 400).
    """

    def __init__(
        self,
        status_code: int = 200,
        json_data: Any = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._json_data = json_data
        self.text = text if text else (_json.dumps(json_data) if json_data is not None else "")

    def json(self) -> Any:
        if self._json_data is None:
            raise ValueError("No JSON payload")
        return self._json_data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise HTTPError(f"HTTP {self.status_code}", response=self)


def make_http_error(status_code: int) -> HTTPError:
    """Build an HTTPError whose `.response.status_code` is `status_code`.

    Matches what `response.raise_for_status()` raises, so client retry/branch
    logic that reads `exc.response.status_code` behaves as in production.
    """
    return HTTPError(f"HTTP {status_code}", response=FakeResponse(status_code=status_code))


@pytest.fixture
def fake_response():
    """Factory fixture returning `FakeResponse(...)` instances."""
    return FakeResponse
