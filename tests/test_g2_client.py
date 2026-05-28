"""Unit tests for lib/g2_client.py — ScrapingBee fetch, retries, error states.

All HTTP is mocked via `lib.g2_client.requests.get`. SCRAPINGBEE_API_KEY is set
explicitly per-test so behavior never depends on the project `.env`.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from requests.exceptions import RequestException

import lib.g2_client as g2
from lib.g2_client import COST_PREMIUM, COST_STEALTH, _scrapingbee_get, fetch_g2_reviews
from lib.models import Review
from tests.conftest import FakeResponse, make_http_error


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    monkeypatch.setenv("SCRAPINGBEE_API_KEY", "test-key")


def _g2_review(title: str = "Great tool") -> Review:
    return Review(
        source="g2",
        url="https://www.g2.com/products/x/reviews/1",
        title=title,
        body="we love it",
        rating=5,
        date="2026-04-22",
        author_meta="Manager",
        score=None,
    )


class TestScrapingBeeGet:
    @patch("lib.g2_client.requests.get")
    def test_premium_proxy_by_default(self, mock_get) -> None:
        mock_get.return_value = FakeResponse(200, text="<html></html>")
        _scrapingbee_get("key", "https://g2.com/x", stealth=False)
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["premium_proxy"] == "true"
        assert "stealth_proxy" not in kwargs["params"]
        assert kwargs["params"]["render_js"] == "true"
        assert kwargs["params"]["country_code"] == "us"

    @patch("lib.g2_client.requests.get")
    def test_stealth_proxy_when_requested(self, mock_get) -> None:
        mock_get.return_value = FakeResponse(200, text="<html></html>")
        _scrapingbee_get("key", "https://g2.com/x", stealth=True)
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["stealth_proxy"] == "true"
        assert "premium_proxy" not in kwargs["params"]

    @patch("lib.g2_client.requests.get")
    def test_passes_timeout(self, mock_get) -> None:
        mock_get.return_value = FakeResponse(200, text="ok")
        _scrapingbee_get("key", "https://g2.com/x", timeout=120)
        _, kwargs = mock_get.call_args
        assert kwargs["timeout"] == 120

    @patch("lib.g2_client.requests.get")
    def test_retries_once_on_5xx_then_succeeds(self, mock_get) -> None:
        mock_get.side_effect = [FakeResponse(502), FakeResponse(200, text="ok")]
        # Also confirms the returned value is the response text.
        assert _scrapingbee_get("key", "https://g2.com/x") == "ok"
        assert mock_get.call_count == 2

    @patch("lib.g2_client.requests.get")
    def test_non_5xx_raises_without_retry(self, mock_get) -> None:
        mock_get.return_value = FakeResponse(403)
        with pytest.raises(Exception):
            _scrapingbee_get("key", "https://g2.com/x")
        assert mock_get.call_count == 1

    @patch("lib.g2_client.requests.get")
    def test_5xx_after_retry_raises(self, mock_get) -> None:
        mock_get.side_effect = [FakeResponse(500), FakeResponse(500)]
        with pytest.raises(Exception):
            _scrapingbee_get("key", "https://g2.com/x")
        assert mock_get.call_count == 2


class TestFetchG2Reviews:
    def test_missing_api_key_returns_error(self, monkeypatch) -> None:
        monkeypatch.delenv("SCRAPINGBEE_API_KEY", raising=False)
        reviews, failure, cost = fetch_g2_reviews("Optimizely", limit=10)
        assert reviews == []
        assert failure == "g2: SCRAPINGBEE_API_KEY not set"
        assert cost == 0.0

    @patch("lib.g2_client.parse_reviews_html")
    @patch("lib.g2_client.find_product_url")
    @patch("lib.g2_client._scrapingbee_get")
    def test_happy_path_returns_reviews_and_full_cost(
        self, mock_get, mock_find, mock_parse
    ) -> None:
        mock_get.side_effect = ["<search html>", "<reviews html>"]
        mock_find.return_value = "https://www.g2.com/products/optimizely"
        mock_parse.return_value = [_g2_review("A"), _g2_review("B")]

        reviews, failure, cost = fetch_g2_reviews("Optimizely", limit=10)

        assert failure is None
        assert len(reviews) == 2
        assert cost == pytest.approx(COST_PREMIUM + COST_STEALTH)
        # Two fetches: search (premium) then reviews (stealth).
        assert mock_get.call_count == 2
        assert mock_get.call_args_list[0].kwargs.get("stealth", False) is False
        assert mock_get.call_args_list[1].kwargs.get("stealth") is True

    @patch("lib.g2_client.find_product_url", return_value=None)
    @patch("lib.g2_client._scrapingbee_get", return_value="<search html>")
    def test_product_not_found_returns_error_with_premium_cost(
        self, _mock_get, _mock_find
    ) -> None:
        reviews, failure, cost = fetch_g2_reviews("Obscure", limit=10)
        assert reviews == []
        assert failure == "g2: product page not found in search results"
        assert cost == pytest.approx(COST_PREMIUM)

    @patch("lib.g2_client.parse_reviews_html", return_value=[])
    @patch("lib.g2_client.find_product_url", return_value="https://www.g2.com/products/x")
    @patch("lib.g2_client._scrapingbee_get")
    def test_no_reviews_parsed_returns_error(
        self, mock_get, _mock_find, _mock_parse
    ) -> None:
        mock_get.side_effect = ["<search html>", "<reviews html>"]
        reviews, failure, cost = fetch_g2_reviews("X", limit=10)
        assert reviews == []
        assert failure == "g2: no reviews parsed from page"
        assert cost == pytest.approx(COST_PREMIUM + COST_STEALTH)

    @patch("lib.g2_client._scrapingbee_get", side_effect=make_http_error(500))
    def test_http_error_returns_status_in_failure(self, _mock_get) -> None:
        reviews, failure, cost = fetch_g2_reviews("X", limit=10)
        assert reviews == []
        assert failure == "g2: HTTP 500"
        assert cost == 0.0

    @patch("lib.g2_client._scrapingbee_get", side_effect=RequestException("conn reset"))
    def test_request_exception_returns_failure(self, _mock_get) -> None:
        reviews, failure, _ = fetch_g2_reviews("X", limit=10)
        assert reviews == []
        assert failure.startswith("g2: ")
        assert "conn reset" in failure

    @patch("lib.g2_client.find_product_url", side_effect=ValueError("bad parse"))
    @patch("lib.g2_client._scrapingbee_get", return_value="<search html>")
    def test_parse_error_returns_failure(self, _mock_get, _mock_find) -> None:
        reviews, failure, cost = fetch_g2_reviews("X", limit=10)
        assert reviews == []
        assert failure.startswith("g2: parse error")
        assert cost == pytest.approx(COST_PREMIUM)
