"""Pydantic models for voc_review_fetcher request/response schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

SourceType = Literal["reddit", "g2"]

DEFAULT_SOURCES: list[SourceType] = ["reddit", "g2"]
BODY_MAX_LENGTH = 2000


def truncate_body(text: str, max_len: int = BODY_MAX_LENGTH) -> str:
    """Truncate review body text to the maximum allowed length."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def utc_now_iso() -> str:
    """Return current UTC time as ISO 8601 string with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class FetchReviewsRequest(BaseModel):
    """Request body for POST /fetch_reviews."""

    brand: str = Field(..., min_length=1)
    sources: list[SourceType] = Field(default_factory=lambda: list(DEFAULT_SOURCES))
    limit_per_source: int = Field(default=20, ge=1, le=50)
    time_window_days: int = Field(default=90, ge=1)

    @field_validator("brand")
    @classmethod
    def brand_not_whitespace(cls, value: str) -> str:
        """Reject brands that are only whitespace."""
        if not value.strip():
            raise ValueError("brand must not be empty or whitespace")
        return value.strip()

    @field_validator("sources")
    @classmethod
    def dedupe_sources(cls, value: list[SourceType]) -> list[SourceType]:
        """Preserve order while removing duplicate sources."""
        seen: set[SourceType] = set()
        result: list[SourceType] = []
        for source in value:
            if source not in seen:
                seen.add(source)
                result.append(source)
        return result


class Review(BaseModel):
    """Normalized review or discussion item from any source."""

    source: SourceType
    url: str
    title: str
    body: str
    rating: Optional[int] = None
    date: str
    author_meta: str
    score: Optional[int] = None

    @field_validator("body")
    @classmethod
    def truncate_review_body(cls, value: str) -> str:
        """Ensure body does not exceed maximum length."""
        return truncate_body(value)


class Stats(BaseModel):
    """Aggregate statistics for a fetch operation."""

    total_fetched: int
    sources_succeeded: list[SourceType]
    sources_failed: list[str]
    latency_ms: int
    estimated_cost_usd: float


class FetchReviewsResponse(BaseModel):
    """Response body for POST /fetch_reviews."""

    brand: str
    fetched_at: str
    reviews: list[Review]
    stats: Stats


def parse_date_for_sort(date_str: str) -> datetime:
    """Parse a date string for sorting; unparseable dates sort last."""
    normalized = date_str.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def sort_reviews_by_date_desc(reviews: list[Review]) -> list[Review]:
    """Sort reviews by date descending (newest first)."""
    return sorted(reviews, key=lambda r: parse_date_for_sort(r.date), reverse=True)


class OpalEnvelope(BaseModel):
    """Opal's tool invocation envelope.

    Opal wraps tool parameters under a 'parameters' key and includes optional
    runtime metadata (environment, chat_metadata). The envelope shape was
    discovered empirically from a 422 response — Opal's docs do not describe
    the exact wire format.

    For backwards compatibility the /fetch_reviews route accepts either:
      - The Opal-shaped envelope: {"parameters": {...}, "environment": {...}}
      - A flat FetchReviewsRequest body: {"brand": "...", "sources": [...]}

    This is handled in the route by attempting envelope parse first, then
    falling back to flat-body parse.
    """

    parameters: dict[str, Any] = Field(
        ...,
        description="The actual tool parameters (matches FetchReviewsRequest shape).",
    )
    environment: Optional[dict[str, Any]] = Field(
        default=None,
        description="Opal-provided runtime metadata (e.g., execution_mode).",
    )
    chat_metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Opal-provided chat context (e.g., thread_id) for traceability.",
    )
