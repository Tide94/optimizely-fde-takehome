"""Reddit review/discussion fetching via the public unauthenticated JSON API.

Uses https://www.reddit.com/search.json and per-subreddit search endpoints —
no OAuth client required, just a descriptive User-Agent. Rate-limited per IP
to roughly 60 requests/minute, which is adequate for this demo's volume.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote_plus

import requests
from requests.exceptions import HTTPError, RequestException

from lib.models import Review, sort_reviews_by_date_desc, truncate_body

logger = logging.getLogger(__name__)

REDDIT_BASE = "https://www.reddit.com"
SUBREDDITS = ["all", "marketing", "SaaS", "Entrepreneur"]
TOP_COMMENTS = 2
DEFAULT_USER_AGENT = (
    "voc-review-fetcher/0.1 (FDE take-home; contact: teddybanjo123@gmail.com)"
)
REQUEST_TIMEOUT = 15

# Reddit's public JSON API silently throttles requests from datacenter IP
# ranges (AWS/Vercel) — returns 200 with empty children arrays. When
# SCRAPINGBEE_API_KEY is set we proxy through it, which costs ~1 credit
# (~$0.001) per request but bypasses the throttling. This is enabled by
# default in production; opt out by setting REDDIT_VIA_SCRAPINGBEE=false.
SCRAPINGBEE_URL = "https://app.scrapingbee.com/api/v1/"


def _user_agent() -> str:
    """Return the User-Agent header for Reddit requests."""
    return os.getenv("REDDIT_USER_AGENT") or DEFAULT_USER_AGENT


def _time_filter_for_window(days: int) -> str:
    """Map time_window_days to Reddit's coarse t= parameter."""
    if days <= 1:
        return "day"
    if days <= 7:
        return "week"
    if days <= 31:
        return "month"
    if days <= 365:
        return "year"
    return "all"


def _utc_iso_from_utc(timestamp: float) -> str:
    """Convert Unix timestamp to ISO 8601 UTC string."""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _should_use_scrapingbee() -> bool:
    """Whether to proxy Reddit calls through ScrapingBee."""
    if os.getenv("REDDIT_VIA_SCRAPINGBEE", "true").lower() in ("false", "0", "no"):
        return False
    return bool(os.getenv("SCRAPINGBEE_API_KEY"))


# ScrapingBee charges 1 credit (~$0.001) per call without JS render.
SCRAPINGBEE_COST_PER_REDDIT_CALL = 0.001

# Module-level counter to attribute Reddit-via-ScrapingBee cost back to the
# orchestrator. Reset at the start of every fetch_reddit_reviews invocation.
_reddit_sb_calls = 0


def _get_json(url: str, params: dict[str, str | int]) -> dict[str, Any]:
    """GET a Reddit JSON endpoint, optionally proxying through ScrapingBee.

    Retries once on ScrapingBee 5xx (their proxy is flaky at peak load).
    """
    global _reddit_sb_calls
    use_sb = _should_use_scrapingbee()
    last_exc: HTTPError | None = None

    for attempt in (1, 2):
        try:
            if use_sb:
                from urllib.parse import urlencode

                target_url = f"{url}?{urlencode(params)}"
                sb_params = {
                    "api_key": os.getenv("SCRAPINGBEE_API_KEY", ""),
                    "url": target_url,
                    "render_js": "false",
                }
                response = requests.get(SCRAPINGBEE_URL, params=sb_params, timeout=30)
                _reddit_sb_calls += 1
            else:
                response = requests.get(
                    url,
                    params=params,
                    headers={"User-Agent": _user_agent()},
                    timeout=REQUEST_TIMEOUT,
                )
            response.raise_for_status()
            return response.json()
        except HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status is not None and 500 <= status < 600 and attempt == 1:
                logger.warning("Reddit fetch %s on attempt %d, retrying", status, attempt)
                last_exc = exc
                continue
            raise
    raise last_exc  # type: ignore[misc]


def _search_subreddit(
    subreddit: str, brand: str, time_filter: str, limit: int
) -> list[dict[str, Any]]:
    """Search one subreddit for the brand, returning raw submission dicts."""
    url = f"{REDDIT_BASE}/r/{subreddit}/search.json"
    params: dict[str, str | int] = {
        "q": brand,
        "restrict_sr": "1" if subreddit != "all" else "0",
        "sort": "relevance",
        "t": time_filter,
        "limit": min(limit, 100),
    }
    payload = _get_json(url, params)
    children = payload.get("data", {}).get("children", [])
    if not children:
        # Log payload shape so we can tell rate-limit responses from real empties.
        logger.warning(
            "r/%s search returned 0 children; payload keys=%s",
            subreddit,
            list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__,
        )
    return [child["data"] for child in children if child.get("data")]


def _top_comment_bodies(submission_id: str, count: int) -> list[str]:
    """Fetch top comments for a submission via the public comments endpoint."""
    url = f"{REDDIT_BASE}/comments/{submission_id}.json"
    try:
        payload = _get_json(url, {"limit": count * 5, "sort": "top"})
    except (HTTPError, RequestException) as exc:
        logger.warning("Comment fetch failed for %s: %s", submission_id, exc)
        return []

    if len(payload) < 2:
        return []

    bodies: list[str] = []
    for child in payload[1].get("data", {}).get("children", []):
        if child.get("kind") != "t1":
            continue
        body = child.get("data", {}).get("body", "")
        if body and body not in ("[deleted]", "[removed]"):
            bodies.append(body)
        if len(bodies) >= count:
            break
    return bodies


def _submission_to_review(data: dict[str, Any]) -> Review:
    """Convert a raw Reddit submission dict into a normalized Review."""
    title = data.get("title", "")
    selftext = data.get("selftext", "") or ""
    permalink = data.get("permalink", "")
    submission_id = data.get("id", "")
    author = data.get("author") or "[deleted]"
    subreddit = data.get("subreddit", "")
    score = data.get("score", 0)
    created_utc = data.get("created_utc", 0.0)

    parts = [title]
    if selftext:
        parts.append(selftext)

    comment_bodies = _top_comment_bodies(submission_id, TOP_COMMENTS) if submission_id else []
    if comment_bodies:
        parts.append("\n\n--- Comments ---\n")
        parts.extend(comment_bodies)

    return Review(
        source="reddit",
        url=f"{REDDIT_BASE}{permalink}",
        title=title,
        body=truncate_body("\n\n".join(parts)),
        rating=None,
        date=_utc_iso_from_utc(float(created_utc)),
        author_meta=f"u/{author} · r/{subreddit}",
        score=int(score) if score is not None else 0,
    )


def fetch_reddit_reviews(
    brand: str,
    limit: int,
    time_window_days: int,
) -> tuple[list[Review], str | None, float]:
    """
    Search Reddit for brand mentions and return normalized reviews.

    Returns:
        Tuple of (reviews, failure_reason, estimated_cost_usd).
        failure_reason is None on success. Cost is 0 when calling Reddit
        directly; ~$0.001 per HTTP request when proxying via ScrapingBee.
    """
    global _reddit_sb_calls
    _reddit_sb_calls = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=time_window_days)
    time_filter = _time_filter_for_window(time_window_days)
    seen_ids: set[str] = set()
    reviews: list[Review] = []

    try:
        for subreddit_name in SUBREDDITS:
            if len(reviews) >= limit:
                break

            logger.info("Searching r/%s for '%s'", subreddit_name, brand)
            try:
                submissions = _search_subreddit(
                    subreddit_name, brand, time_filter, limit * 2
                )
            except (HTTPError, RequestException) as exc:
                logger.warning("r/%s search failed: %s", subreddit_name, exc)
                continue

            for data in submissions:
                submission_id = data.get("id")
                if not submission_id or submission_id in seen_ids:
                    continue
                seen_ids.add(submission_id)

                created = datetime.fromtimestamp(
                    float(data.get("created_utc", 0)), tz=timezone.utc
                )
                if created < cutoff:
                    continue

                try:
                    reviews.append(_submission_to_review(data))
                except (KeyError, TypeError, ValueError) as exc:
                    logger.warning("Skipping submission %s: %s", submission_id, exc)
                    continue

                if len(reviews) >= limit:
                    break

    except (HTTPError, RequestException) as exc:
        logger.warning("Network error fetching Reddit reviews: %s", exc)
        if not reviews:
            return [], f"reddit: {exc}", 0.0

    cost = _reddit_sb_calls * SCRAPINGBEE_COST_PER_REDDIT_CALL
    if not reviews:
        return [], "reddit: no results found", cost

    return sort_reviews_by_date_desc(reviews), None, cost


def _quote(value: str) -> str:
    """URL-quote a search term (exposed for testing)."""
    return quote_plus(value)
