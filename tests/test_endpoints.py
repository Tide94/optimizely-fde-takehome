"""Smoke tests for voc_review_fetcher API endpoints."""

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from api.index import _execute_fetch_reviews, app, health  # noqa: E402
from lib.models import FetchReviewsRequest, Review  # noqa: E402

SAMPLE_REDDIT_REVIEW = Review(
    source="reddit",
    url="https://reddit.com/r/marketing/comments/abc/test",
    title="Test post",
    body="Body text",
    rating=None,
    date="2026-04-22T10:30:00Z",
    author_meta="u/tester · r/marketing",
    score=10,
)

SAMPLE_G2_REVIEW = Review(
    source="g2",
    url="https://www.g2.com/products/optimizely/reviews/1",
    title="Great tool",
    body="We love it",
    rating=5,
    date="2026-04-22",
    author_meta="Manager · 201-1000 employees",
    score=None,
)


class TestHealthEndpoint(unittest.TestCase):
    """Tests for GET /health."""

    def test_health_returns_ok(self) -> None:
        result = health()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["version"], "0.1.0")

    def test_health_route_registered(self) -> None:
        routes = [r.path for r in app.routes]
        self.assertIn("/health", routes)


class TestFetchReviewsEndpoint(unittest.TestCase):
    """Tests for POST /fetch_reviews."""

    def test_whitespace_brand_raises_validation_error(self) -> None:
        with self.assertRaises(Exception):
            FetchReviewsRequest(brand="   ")

    @patch("api.index.fetch_reddit_reviews")
    @patch("api.index.fetch_g2_reviews")
    def test_successful_fetch_both_sources(
        self, mock_g2: unittest.mock.MagicMock, mock_reddit: unittest.mock.MagicMock
    ) -> None:
        mock_reddit.return_value = ([SAMPLE_REDDIT_REVIEW], None, 0.0)
        mock_g2.return_value = ([SAMPLE_G2_REVIEW], None, 0.002)

        response = asyncio.run(
            _execute_fetch_reviews(
                FetchReviewsRequest(brand="Optimizely", sources=["reddit", "g2"], limit_per_source=5)
            )
        )

        self.assertEqual(response.brand, "Optimizely")
        self.assertEqual(len(response.reviews), 2)
        self.assertEqual(response.stats.total_fetched, 2)
        self.assertEqual(set(response.stats.sources_succeeded), {"reddit", "g2"})
        self.assertEqual(response.stats.sources_failed, [])
        self.assertAlmostEqual(response.stats.estimated_cost_usd, 0.002)

    @patch("api.index.fetch_reddit_reviews")
    @patch("api.index.fetch_g2_reviews")
    def test_partial_failure_continues(
        self, mock_g2: unittest.mock.MagicMock, mock_reddit: unittest.mock.MagicMock
    ) -> None:
        mock_reddit.return_value = ([SAMPLE_REDDIT_REVIEW], None, 0.0)
        mock_g2.return_value = ([], "g2: SCRAPINGBEE_API_KEY not set", 0.0)

        response = asyncio.run(
            _execute_fetch_reviews(
                FetchReviewsRequest(brand="Optimizely", sources=["reddit", "g2"])
            )
        )

        self.assertEqual(len(response.reviews), 1)
        self.assertEqual(response.stats.sources_succeeded, ["reddit"])
        self.assertEqual(len(response.stats.sources_failed), 1)
        self.assertIn("g2", response.stats.sources_failed[0])

    @patch("api.index.fetch_reddit_reviews")
    @patch("api.index.fetch_g2_reviews")
    def test_all_sources_fail_returns_response(
        self, mock_g2: unittest.mock.MagicMock, mock_reddit: unittest.mock.MagicMock
    ) -> None:
        mock_reddit.return_value = ([], "reddit: missing credentials", 0.0)
        mock_g2.return_value = ([], "g2: SCRAPINGBEE_API_KEY not set", 0.0)

        response = asyncio.run(
            _execute_fetch_reviews(
                FetchReviewsRequest(brand="Optimizely", sources=["reddit", "g2"])
            )
        )

        self.assertEqual(response.reviews, [])
        self.assertEqual(response.stats.sources_succeeded, [])
        self.assertEqual(len(response.stats.sources_failed), 2)

    @patch("api.index.fetch_reddit_reviews")
    def test_reddit_only_source(self, mock_reddit: unittest.mock.MagicMock) -> None:
        mock_reddit.return_value = ([SAMPLE_REDDIT_REVIEW], None, 0.0)

        response = asyncio.run(
            _execute_fetch_reviews(
                FetchReviewsRequest(brand="Optimizely", sources=["reddit"])
            )
        )

        self.assertEqual(len(response.reviews), 1)
        self.assertEqual(response.reviews[0].source, "reddit")


def test_discovery_returns_manifest():
    """The discovery endpoint must return Opal's validator-enforced schema.

    Root key 'functions'. Parameters as ARRAY of objects (each with its own
    `name` field). Content-Type must be application/json — text/plain confuses
    Opal's parser and causes AttributeError on iteration.
    """
    from fastapi.testclient import TestClient
    from api.index import app

    client = TestClient(app)
    response = client.get("/discovery")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json"), (
        f"Content-Type must be application/json, got: {response.headers['content-type']}"
    )

    data = response.json()

    # Root key must be 'functions', not 'tools'
    assert "functions" in data
    assert "tools" not in data
    assert len(data["functions"]) == 1

    fn = data["functions"][0]
    assert fn["name"] == "fetch_reviews"
    assert fn["endpoint"] == "/fetch_reviews"
    assert fn["method"] == "POST"
    assert len(fn["description"]) > 10

    # parameters must be a LIST of objects, not a dict
    assert isinstance(fn["parameters"], list), (
        f"parameters must be an array, got {type(fn['parameters']).__name__} — "
        f"keyed dict triggers AttributeError in Opal's parser"
    )

    # Each parameter must have its own name, type, description, required
    param_names = {p["name"] for p in fn["parameters"]}
    assert param_names == {"brand", "sources", "limit_per_source", "time_window_days"}

    required_params = {p["name"] for p in fn["parameters"] if p.get("required")}
    assert required_params == {"brand"}

    valid_types = {"string", "number", "boolean", "array", "object"}
    for p in fn["parameters"]:
        assert "name" in p
        assert "type" in p
        assert "description" in p
        assert p["type"] in valid_types
        assert len(p["description"]) > 10


def test_fetch_reviews_accepts_opal_envelope(monkeypatch):
    """The handler must unwrap Opal's envelope shape correctly."""
    from fastapi.testclient import TestClient
    from api.index import app

    # Patch the actual fetcher so the test doesn't hit Reddit/G2
    async def fake_execute(req):
        from lib.models import FetchReviewsResponse, Stats
        return FetchReviewsResponse(
            brand=req.brand,
            fetched_at="2026-05-21T00:00:00Z",
            reviews=[],
            stats=Stats(
                total_fetched=0,
                sources_succeeded=[],
                sources_failed=[],
                latency_ms=0,
                estimated_cost_usd=0.0,
            ),
        )

    monkeypatch.setattr("api.index._execute_fetch_reviews", fake_execute)

    client = TestClient(app)
    response = client.post(
        "/fetch_reviews",
        json={
            "parameters": {
                "brand": "Optimizely",
                "sources": ["reddit"],
                "limit_per_source": 2,
                "time_window_days": 90,
            },
            "environment": {"execution_mode": "interactive"},
            "chat_metadata": {"thread_id": "abc-123"},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["brand"] == "Optimizely"


def test_fetch_reviews_accepts_flat_body(monkeypatch):
    """The handler must still accept a flat body for direct/local use."""
    from fastapi.testclient import TestClient
    from api.index import app

    async def fake_execute(req):
        from lib.models import FetchReviewsResponse, Stats
        return FetchReviewsResponse(
            brand=req.brand,
            fetched_at="2026-05-21T00:00:00Z",
            reviews=[],
            stats=Stats(
                total_fetched=0,
                sources_succeeded=[],
                sources_failed=[],
                latency_ms=0,
                estimated_cost_usd=0.0,
            ),
        )

    monkeypatch.setattr("api.index._execute_fetch_reviews", fake_execute)

    client = TestClient(app)
    response = client.post(
        "/fetch_reviews",
        json={
            "brand": "Optimizely",
            "sources": ["reddit"],
            "limit_per_source": 2,
            "time_window_days": 90,
        },
    )

    assert response.status_code == 200


def test_fetch_reviews_rejects_invalid_inner_params():
    """If the inner params fail validation, return 422 with field details."""
    from fastapi.testclient import TestClient
    from api.index import app

    client = TestClient(app)
    # Envelope-shaped but missing required `brand`
    response = client.post(
        "/fetch_reviews",
        json={"parameters": {"sources": ["reddit"]}},
    )
    assert response.status_code == 422


if __name__ == "__main__":
    unittest.main()
