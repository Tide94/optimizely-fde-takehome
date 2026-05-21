"""Smoke tests for voc_review_fetcher API endpoints."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from api.index import app, fetch_reviews, health  # noqa: E402
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

        response = fetch_reviews(
            FetchReviewsRequest(brand="Optimizely", sources=["reddit", "g2"], limit_per_source=5)
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

        response = fetch_reviews(
            FetchReviewsRequest(brand="Optimizely", sources=["reddit", "g2"])
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

        response = fetch_reviews(
            FetchReviewsRequest(brand="Optimizely", sources=["reddit", "g2"])
        )

        self.assertEqual(response.reviews, [])
        self.assertEqual(response.stats.sources_succeeded, [])
        self.assertEqual(len(response.stats.sources_failed), 2)

    @patch("api.index.fetch_reddit_reviews")
    def test_reddit_only_source(self, mock_reddit: unittest.mock.MagicMock) -> None:
        mock_reddit.return_value = ([SAMPLE_REDDIT_REVIEW], None, 0.0)

        response = fetch_reviews(
            FetchReviewsRequest(brand="Optimizely", sources=["reddit"])
        )

        self.assertEqual(len(response.reviews), 1)
        self.assertEqual(response.reviews[0].source, "reddit")


def test_discovery_returns_manifest():
    """The discovery endpoint must return Opal's validator-enforced schema.

    Opal validator requires root key 'functions' (not 'tools') and parameters
    as a keyed object (not array). Confirmed empirically — the docs describe
    a different shape than the validator enforces.
    """
    from fastapi.testclient import TestClient
    from api.index import app

    client = TestClient(app)
    response = client.get("/discovery")

    assert response.status_code == 200
    data = response.json()

    # Root key must be 'functions', not 'tools'
    assert "functions" in data, f"Expected root key 'functions', got: {list(data.keys())}"
    assert "tools" not in data, "Root key 'tools' is rejected by Opal validator"
    assert len(data["functions"]) == 1

    fn = data["functions"][0]
    assert fn["name"] == "fetch_reviews"
    assert fn["endpoint"] == "/fetch_reviews"
    assert fn["method"] == "POST"
    assert len(fn["description"]) > 10, "Opal validator requires meaningful description length"

    # parameters must be a dict (keyed object), not a list
    assert isinstance(fn["parameters"], dict), (
        f"parameters must be a keyed object, got {type(fn['parameters']).__name__}"
    )

    expected_params = {"brand", "sources", "limit_per_source", "time_window_days"}
    assert set(fn["parameters"].keys()) == expected_params

    # brand is the only required parameter
    required = {k for k, v in fn["parameters"].items() if v.get("required")}
    assert required == {"brand"}

    # All types must be valid Opal types
    valid_types = {"string", "number", "boolean", "array", "object"}
    for name, param in fn["parameters"].items():
        assert param["type"] in valid_types, f"Invalid type for {name}: {param['type']}"
        assert len(param["description"]) > 10, (
            f"Parameter '{name}' description too short — validator may reject"
        )


if __name__ == "__main__":
    unittest.main()
