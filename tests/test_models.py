"""Unit tests for lib/models.py — normalization helpers and Pydantic schemas."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from lib.models import (
    BODY_MAX_LENGTH,
    DEFAULT_SOURCES,
    FetchReviewsRequest,
    OpalEnvelope,
    Review,
    parse_date_for_sort,
    sort_reviews_by_date_desc,
    truncate_body,
    utc_now_iso,
)


def _review(date: str, body: str = "x") -> Review:
    return Review(
        source="reddit",
        url="https://reddit.com/x",
        title="t",
        body=body,
        rating=None,
        date=date,
        author_meta="u/x",
        score=0,
    )


class TestTruncateBody:
    def test_truncates_with_ellipsis_when_over_limit(self) -> None:
        text = "a" * (BODY_MAX_LENGTH + 50)
        result = truncate_body(text)
        assert len(result) == BODY_MAX_LENGTH
        assert result.endswith("...")

    def test_respects_custom_max_len(self) -> None:
        assert truncate_body("abcdefghij", max_len=5) == "ab..."

    def test_empty_string_returns_empty(self) -> None:
        assert truncate_body("") == ""


class TestUtcNowIso:
    def test_returns_iso8601_with_z_suffix(self) -> None:
        value = utc_now_iso()
        assert value.endswith("Z")
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        assert parsed.tzinfo is not None


class TestParseDateForSort:
    def test_parses_iso_with_z(self) -> None:
        result = parse_date_for_sort("2026-04-22T10:30:00Z")
        assert result == datetime(2026, 4, 22, 10, 30, tzinfo=timezone.utc)

    def test_naive_date_assumed_utc(self) -> None:
        result = parse_date_for_sort("2026-04-22")
        assert result.tzinfo == timezone.utc
        assert result.year == 2026 and result.month == 4 and result.day == 22

    def test_unparseable_date_sorts_last(self) -> None:
        assert parse_date_for_sort("not a date") == datetime.min.replace(
            tzinfo=timezone.utc
        )


class TestSortReviewsByDateDesc:
    def test_orders_newest_first(self) -> None:
        older = _review("2026-01-01T00:00:00Z")
        newer = _review("2026-05-01T00:00:00Z")
        assert sort_reviews_by_date_desc([older, newer]) == [newer, older]

    def test_unparseable_dates_sort_to_end(self) -> None:
        dated = _review("2026-05-01T00:00:00Z")
        undated = _review("garbage")
        assert sort_reviews_by_date_desc([undated, dated]) == [dated, undated]


class TestFetchReviewsRequest:
    def test_valid_minimal_input_applies_defaults(self) -> None:
        req = FetchReviewsRequest(brand="Optimizely")
        assert req.brand == "Optimizely"
        assert req.sources == DEFAULT_SOURCES
        assert req.limit_per_source == 20
        assert req.time_window_days == 90

    def test_whitespace_only_brand_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FetchReviewsRequest(brand="   ")

    def test_brand_is_stripped(self) -> None:
        assert FetchReviewsRequest(brand="  Notion  ").brand == "Notion"

    def test_sources_deduped_preserving_order(self) -> None:
        req = FetchReviewsRequest(brand="X", sources=["g2", "reddit", "g2"])
        assert req.sources == ["g2", "reddit"]

    def test_limit_below_minimum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FetchReviewsRequest(brand="X", limit_per_source=0)

    def test_limit_above_maximum_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FetchReviewsRequest(brand="X", limit_per_source=51)

    def test_time_window_below_one_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FetchReviewsRequest(brand="X", time_window_days=0)


class TestReview:
    def test_long_body_truncated_on_construction(self) -> None:
        review = _review("2026-01-01T00:00:00Z", body="a" * (BODY_MAX_LENGTH + 100))
        assert len(review.body) == BODY_MAX_LENGTH
        assert review.body.endswith("...")


class TestOpalEnvelope:
    def test_parses_full_envelope(self) -> None:
        env = OpalEnvelope(
            parameters={"brand": "Optimizely"},
            environment={"execution_mode": "interactive"},
            chat_metadata={"thread_id": "abc-123"},
        )
        assert env.parameters["brand"] == "Optimizely"
        assert env.environment == {"execution_mode": "interactive"}
        assert env.chat_metadata == {"thread_id": "abc-123"}

    def test_parses_with_optional_fields_omitted(self) -> None:
        env = OpalEnvelope(parameters={"brand": "X"})
        assert env.environment is None
        assert env.chat_metadata is None

    def test_missing_parameters_rejected(self) -> None:
        with pytest.raises(ValidationError):
            OpalEnvelope(environment={"execution_mode": "interactive"})
