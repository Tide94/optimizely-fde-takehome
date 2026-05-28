"""Integration + resilience tests: Opal agent -> tool -> output.

These exercise the full HTTP path through FastAPI's TestClient (standing in for
the Opal agent invoking the registered tool) without any live network:
  - the fetch layer is mocked at the api.index boundary for the E2E happy path;
  - the real fetch_*_reviews functions run for resilience cases, with only the
    lowest-level `requests.get` mocked to raise 500s / timeouts.
No live Opal instance is required.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
import requests
from fastapi.testclient import TestClient

from api.index import app
from lib.models import Review
from tests.conftest import FakeResponse

client = TestClient(app)


def _reddit_review() -> Review:
    return Review(
        source="reddit",
        url="https://www.reddit.com/r/marketing/comments/abc/x",
        title="Optimizely is solid",
        body="We migrated and it worked well.",
        rating=None,
        date="2026-05-01T00:00:00Z",
        author_meta="u/tester · r/marketing",
        score=42,
    )


class TestEndToEndAgentToToolToOutput:
    @patch("api.index.fetch_g2_reviews")
    @patch("api.index.fetch_reddit_reviews")
    def test_opal_envelope_trigger_invokes_tool_and_returns_coherent_output(
        self, mock_reddit, mock_g2
    ) -> None:
        mock_reddit.return_value = ([_reddit_review()], None, 0.0)
        mock_g2.return_value = ([], None, 0.0)

        # Structured trigger as the Opal agent would send it.
        response = client.post(
            "/fetch_reviews",
            json={
                "parameters": {
                    "brand": "Optimizely",
                    "sources": ["reddit"],
                    "limit_per_source": 2,
                    "time_window_days": 30,
                },
                "environment": {"execution_mode": "interactive"},
                "chat_metadata": {"thread_id": "thread-xyz"},
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Tool was called with parameters unwrapped from the envelope.
        mock_reddit.assert_called_once_with(
            brand="Optimizely", limit=2, time_window_days=30
        )
        mock_g2.assert_not_called()

        # Output is coherent and non-empty.
        assert data["brand"] == "Optimizely"
        assert len(data["reviews"]) == 1
        assert data["reviews"][0]["body"]
        assert data["stats"]["total_fetched"] == 1
        assert data["stats"]["sources_succeeded"] == ["reddit"]
        assert data["fetched_at"]

    @patch("api.index.fetch_g2_reviews")
    @patch("api.index.fetch_reddit_reviews")
    def test_flat_body_trigger_also_works(self, mock_reddit, mock_g2) -> None:
        mock_reddit.return_value = ([_reddit_review()], None, 0.0)
        response = client.post(
            "/fetch_reviews",
            json={"brand": "Optimizely", "sources": ["reddit"], "limit_per_source": 5},
        )
        assert response.status_code == 200
        mock_reddit.assert_called_once_with(
            brand="Optimizely", limit=5, time_window_days=90
        )


class TestResilience:
    def test_500_from_dependency_surfaces_gracefully(self, monkeypatch) -> None:
        """A 500 from ScrapingBee must yield a 200 with the failure in stats —
        not a crash and not a silent empty success."""
        monkeypatch.setenv("SCRAPINGBEE_API_KEY", "test-key")

        with patch("lib.g2_client.requests.get", return_value=FakeResponse(500)) as mg:
            response = client.post(
                "/fetch_reviews",
                json={"parameters": {"brand": "Optimizely", "sources": ["g2"]}},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["reviews"] == []
        assert data["stats"]["sources_succeeded"] == []
        assert "g2: HTTP 500" in data["stats"]["sources_failed"]
        # Retried once (two underlying calls) before giving up.
        assert mg.call_count == 2

    def test_g2_timeout_returns_promptly_and_surfaces_error(self, monkeypatch) -> None:
        """A timeout must not hang and must surface as a G2 failure."""
        monkeypatch.setenv("SCRAPINGBEE_API_KEY", "test-key")

        with patch(
            "lib.g2_client.requests.get", side_effect=requests.exceptions.Timeout("timed out")
        ) as mg:
            start = time.perf_counter()
            response = client.post(
                "/fetch_reviews",
                json={"parameters": {"brand": "Optimizely", "sources": ["g2"]}},
            )
            elapsed = time.perf_counter() - start

        assert response.status_code == 200
        assert elapsed < 5.0  # does not hang
        data = response.json()
        assert any("g2" in f for f in data["stats"]["sources_failed"])
        # A finite timeout was passed to requests.get, so it can't block forever.
        assert mg.call_args.kwargs["timeout"] == 120

    def test_reddit_timeout_returns_promptly_and_surfaces_error(self, monkeypatch) -> None:
        """A Reddit timeout must not hang and must surface in the output.

        NOTE (observability gap, not fixed): fetch_reddit_reviews catches the
        Timeout per-subreddit and, after all subreddits fail, returns the generic
        'reddit: no results found' rather than a timeout/network-specific label.
        The error DOES surface, but the label does not distinguish a true empty
        result from a network failure. See reddit_client.py:262.
        """
        monkeypatch.setenv("REDDIT_VIA_SCRAPINGBEE", "false")
        monkeypatch.delenv("SCRAPINGBEE_API_KEY", raising=False)

        with patch(
            "lib.reddit_client.requests.get",
            side_effect=requests.exceptions.Timeout("timed out"),
        ) as mr:
            start = time.perf_counter()
            response = client.post(
                "/fetch_reviews",
                json={"parameters": {"brand": "Optimizely", "sources": ["reddit"]}},
            )
            elapsed = time.perf_counter() - start

        assert response.status_code == 200
        assert elapsed < 5.0
        data = response.json()
        assert data["reviews"] == []
        assert len(data["stats"]["sources_failed"]) == 1  # error surfaces
        assert mr.call_args.kwargs["timeout"] == 15  # finite timeout, cannot hang

    @patch("api.index.fetch_g2_reviews")
    @patch("api.index.fetch_reddit_reviews")
    def test_errors_not_silently_swallowed_when_all_sources_fail(
        self, mock_reddit, mock_g2
    ) -> None:
        mock_reddit.return_value = ([], "reddit: no results found", 0.0)
        mock_g2.return_value = ([], "g2: HTTP 500", 0.0)

        response = client.post(
            "/fetch_reviews",
            json={"parameters": {"brand": "Optimizely", "sources": ["reddit", "g2"]}},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["reviews"] == []
        # Both failures reach the caller — not a silent empty 200.
        assert len(data["stats"]["sources_failed"]) == 2
        assert data["stats"]["sources_succeeded"] == []
