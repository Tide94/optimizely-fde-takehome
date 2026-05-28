"""Unit tests for lib/reddit_client.py — Reddit fetch, retries, cost, helpers.

All HTTP is mocked via `lib.reddit_client.requests.get`. Env vars are set
explicitly per-test (the project `.env` may inject SCRAPINGBEE_API_KEY when
api.index is imported elsewhere in the session, so we never rely on ambient env).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from requests.exceptions import RequestException

import lib.reddit_client as rc
from lib.reddit_client import (
    SCRAPINGBEE_COST_PER_REDDIT_CALL,
    _get_json,
    _search_subreddit,
    _should_use_scrapingbee,
    _submission_to_review,
    _time_filter_for_window,
    _top_comment_bodies,
    _user_agent,
    _utc_iso_from_utc,
    fetch_reddit_reviews,
)
from tests.conftest import FakeResponse, make_http_error


@pytest.fixture(autouse=True)
def _force_direct_reddit(monkeypatch):
    """Default every test to the direct (non-ScrapingBee) path unless overridden."""
    monkeypatch.setenv("REDDIT_VIA_SCRAPINGBEE", "false")
    monkeypatch.delenv("SCRAPINGBEE_API_KEY", raising=False)


def _submission(sub_id: str, created_utc: float, title: str = "Great brand") -> dict:
    return {
        "id": sub_id,
        "title": title,
        "selftext": "body text",
        "permalink": f"/r/marketing/comments/{sub_id}/x",
        "author": "tester",
        "subreddit": "marketing",
        "score": 12,
        "created_utc": created_utc,
    }


class TestTimeFilterForWindow:
    @pytest.mark.parametrize(
        "days,expected",
        [(1, "day"), (7, "week"), (31, "month"), (365, "year"), (366, "all")],
    )
    def test_boundaries(self, days: int, expected: str) -> None:
        assert _time_filter_for_window(days) == expected


class TestUtcIsoFromUtc:
    def test_converts_unix_timestamp_to_iso(self) -> None:
        # 2021-01-01T00:00:00Z
        assert _utc_iso_from_utc(1609459200.0) == "2021-01-01T00:00:00Z"


class TestUserAgent:
    def test_falls_back_to_default(self, monkeypatch) -> None:
        monkeypatch.delenv("REDDIT_USER_AGENT", raising=False)
        assert _user_agent() == rc.DEFAULT_USER_AGENT


class TestShouldUseScrapingBee:
    def test_disabled_by_flag(self, monkeypatch) -> None:
        monkeypatch.setenv("REDDIT_VIA_SCRAPINGBEE", "false")
        monkeypatch.setenv("SCRAPINGBEE_API_KEY", "key")
        assert _should_use_scrapingbee() is False

    def test_enabled_when_flag_on_and_key_present(self, monkeypatch) -> None:
        monkeypatch.setenv("REDDIT_VIA_SCRAPINGBEE", "true")
        monkeypatch.setenv("SCRAPINGBEE_API_KEY", "key")
        assert _should_use_scrapingbee() is True

    def test_disabled_when_key_missing(self, monkeypatch) -> None:
        monkeypatch.setenv("REDDIT_VIA_SCRAPINGBEE", "true")
        monkeypatch.delenv("SCRAPINGBEE_API_KEY", raising=False)
        assert _should_use_scrapingbee() is False


class TestGetJson:
    @patch("lib.reddit_client.requests.get")
    def test_direct_path_sets_timeout_and_user_agent(self, mock_get) -> None:
        mock_get.return_value = FakeResponse(200, json_data={"ok": True})
        result = _get_json("https://www.reddit.com/x.json", {"q": "brand"})
        assert result == {"ok": True}
        _, kwargs = mock_get.call_args
        assert kwargs["timeout"] == rc.REQUEST_TIMEOUT
        assert "User-Agent" in kwargs["headers"]

    @patch("lib.reddit_client.requests.get")
    def test_scrapingbee_path_sets_timeout_and_counts_calls(
        self, mock_get, monkeypatch
    ) -> None:
        monkeypatch.setenv("REDDIT_VIA_SCRAPINGBEE", "true")
        monkeypatch.setenv("SCRAPINGBEE_API_KEY", "secret")
        rc._reddit_sb_calls = 0
        mock_get.return_value = FakeResponse(200, json_data={"ok": True})

        result = _get_json("https://www.reddit.com/x.json", {"q": "brand"})

        assert result == {"ok": True}
        args, kwargs = mock_get.call_args
        assert args[0] == rc.SCRAPINGBEE_URL
        assert kwargs["timeout"] == 30
        assert kwargs["params"]["api_key"] == "secret"
        assert rc._reddit_sb_calls == 1

    @patch("lib.reddit_client.requests.get")
    def test_retries_once_on_5xx_then_succeeds(self, mock_get) -> None:
        mock_get.side_effect = [
            FakeResponse(503),
            FakeResponse(200, json_data={"ok": True}),
        ]
        assert _get_json("https://www.reddit.com/x.json", {}) == {"ok": True}
        assert mock_get.call_count == 2

    @patch("lib.reddit_client.requests.get")
    def test_non_5xx_raises_without_retry(self, mock_get) -> None:
        mock_get.return_value = FakeResponse(404)
        with pytest.raises(Exception):
            _get_json("https://www.reddit.com/x.json", {})
        assert mock_get.call_count == 1

    @patch("lib.reddit_client.requests.get")
    def test_5xx_after_retry_raises(self, mock_get) -> None:
        mock_get.side_effect = [FakeResponse(500), FakeResponse(500)]
        with pytest.raises(Exception):
            _get_json("https://www.reddit.com/x.json", {})
        assert mock_get.call_count == 2


class TestSearchSubreddit:
    @patch("lib.reddit_client._get_json")
    def test_restrict_sr_zero_for_all(self, mock_json) -> None:
        mock_json.return_value = {"data": {"children": []}}
        _search_subreddit("all", "brand", "year", 10)
        _, params = mock_json.call_args[0]
        assert params["restrict_sr"] == "0"

    @patch("lib.reddit_client._get_json")
    def test_restrict_sr_one_for_named_subreddit(self, mock_json) -> None:
        mock_json.return_value = {"data": {"children": []}}
        _search_subreddit("marketing", "brand", "year", 10)
        _, params = mock_json.call_args[0]
        assert params["restrict_sr"] == "1"

    @patch("lib.reddit_client._get_json")
    def test_returns_child_data(self, mock_json) -> None:
        mock_json.return_value = {
            "data": {"children": [{"data": {"id": "a"}}, {"data": {"id": "b"}}]}
        }
        result = _search_subreddit("marketing", "brand", "year", 10)
        assert result == [{"id": "a"}, {"id": "b"}]


class TestTopCommentBodies:
    @patch("lib.reddit_client._get_json")
    def test_extracts_t1_bodies_and_skips_deleted(self, mock_json) -> None:
        mock_json.return_value = [
            {},  # index 0 = the submission listing
            {
                "data": {
                    "children": [
                        {"kind": "t1", "data": {"body": "first comment"}},
                        {"kind": "t1", "data": {"body": "[deleted]"}},
                        {"kind": "t1", "data": {"body": "second comment"}},
                    ]
                }
            },
        ]
        bodies = _top_comment_bodies("abc", 5)
        assert bodies == ["first comment", "second comment"]

    @patch("lib.reddit_client._get_json")
    def test_caps_at_count(self, mock_json) -> None:
        mock_json.return_value = [
            {},
            {
                "data": {
                    "children": [
                        {"kind": "t1", "data": {"body": f"c{i}"}} for i in range(10)
                    ]
                }
            },
        ]
        assert _top_comment_bodies("abc", 2) == ["c0", "c1"]

    @patch("lib.reddit_client._get_json")
    def test_short_payload_returns_empty(self, mock_json) -> None:
        mock_json.return_value = [{}]
        assert _top_comment_bodies("abc", 2) == []

    @patch("lib.reddit_client._get_json")
    def test_network_error_swallowed_returns_empty(self, mock_json) -> None:
        # Comment fetch is best-effort: network errors must not abort the review.
        mock_json.side_effect = make_http_error(500)
        assert _top_comment_bodies("abc", 2) == []


class TestSubmissionToReview:
    @patch("lib.reddit_client._top_comment_bodies", return_value=["nice comment"])
    def test_maps_fields(self, _mock_comments) -> None:
        review = _submission_to_review(_submission("abc", 1609459200.0))
        assert review.source == "reddit"
        assert review.url == "https://www.reddit.com/r/marketing/comments/abc/x"
        assert review.title == "Great brand"
        assert "nice comment" in review.body
        assert review.author_meta == "u/tester · r/marketing"
        assert review.date == "2021-01-01T00:00:00Z"
        assert review.score == 12

    @patch("lib.reddit_client._top_comment_bodies", return_value=[])
    def test_none_author_becomes_deleted(self, _mock_comments) -> None:
        data = _submission("abc", 1609459200.0)
        data["author"] = None
        review = _submission_to_review(data)
        assert review.author_meta == "u/[deleted] · r/marketing"


class TestFetchRedditReviews:
    @patch("lib.reddit_client._top_comment_bodies", return_value=[])
    @patch("lib.reddit_client._search_subreddit")
    def test_happy_path_returns_sorted_reviews(self, mock_search, _mc) -> None:
        # Recent submissions across the first subreddit; rest empty.
        now = __import__("time").time()
        mock_search.side_effect = [
            [_submission("a", now - 100), _submission("b", now - 50)],
            [],
            [],
            [],
        ]
        reviews, failure, cost = fetch_reddit_reviews("brand", limit=5, time_window_days=90)
        assert failure is None
        assert len(reviews) == 2
        # Newest first.
        assert reviews[0].date >= reviews[1].date
        assert cost == 0.0  # direct path, no ScrapingBee

    @patch("lib.reddit_client._top_comment_bodies", return_value=[])
    @patch("lib.reddit_client._search_subreddit")
    def test_dedupes_across_subreddits(self, mock_search, _mc) -> None:
        now = __import__("time").time()
        dup = _submission("same", now - 100)
        mock_search.side_effect = [[dup], [dup], [], []]
        reviews, failure, _ = fetch_reddit_reviews("brand", limit=5, time_window_days=90)
        assert failure is None
        assert len(reviews) == 1

    @patch("lib.reddit_client._top_comment_bodies", return_value=[])
    @patch("lib.reddit_client._search_subreddit")
    def test_old_posts_filtered_by_time_window(self, mock_search, _mc) -> None:
        now = __import__("time").time()
        old = _submission("old", now - 60 * 60 * 24 * 200)  # 200 days ago
        mock_search.side_effect = [[old], [], [], []]
        reviews, failure, _ = fetch_reddit_reviews("brand", limit=5, time_window_days=90)
        assert reviews == []
        assert failure == "reddit: no results found"

    @patch("lib.reddit_client._top_comment_bodies", return_value=[])
    @patch("lib.reddit_client._search_subreddit")
    def test_limit_respected(self, mock_search, _mc) -> None:
        now = __import__("time").time()
        many = [_submission(f"id{i}", now - i) for i in range(10)]
        mock_search.side_effect = [many, [], [], []]
        reviews, _, _ = fetch_reddit_reviews("brand", limit=3, time_window_days=90)
        assert len(reviews) == 3

    @patch("lib.reddit_client._top_comment_bodies", return_value=[])
    @patch("lib.reddit_client._search_subreddit")
    def test_per_subreddit_failure_continues(self, mock_search, _mc) -> None:
        now = __import__("time").time()
        mock_search.side_effect = [
            RequestException("rate limited"),
            [_submission("ok", now - 100)],
            [],
            [],
        ]
        reviews, failure, _ = fetch_reddit_reviews("brand", limit=5, time_window_days=90)
        assert failure is None
        assert len(reviews) == 1

    @patch("lib.reddit_client._search_subreddit", return_value=[])
    def test_all_empty_returns_no_results(self, _mock_search) -> None:
        reviews, failure, cost = fetch_reddit_reviews("brand", limit=5, time_window_days=90)
        assert reviews == []
        assert failure == "reddit: no results found"
        assert cost == 0.0

    @patch("lib.reddit_client._top_comment_bodies", return_value=[])
    @patch("lib.reddit_client._search_subreddit")
    def test_cost_accumulates_for_scrapingbee_calls(
        self, mock_search, _mc, monkeypatch
    ) -> None:
        now = __import__("time").time()

        # fetch_reddit_reviews resets _reddit_sb_calls to 0, then each
        # subreddit search would increment it once in production (via _get_json).
        # Emulate that by bumping the module counter inside the search stub.
        def search_side_effect(subreddit, *a, **k):
            rc._reddit_sb_calls += 1
            return [_submission("a", now - 100)] if subreddit == "all" else []

        mock_search.side_effect = search_side_effect
        _, failure, cost = fetch_reddit_reviews("brand", limit=5, time_window_days=90)
        assert failure is None
        # 4 subreddit searches each bumped the counter once.
        assert cost == pytest.approx(4 * SCRAPINGBEE_COST_PER_REDDIT_CALL)
