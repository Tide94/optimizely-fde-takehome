"""FastAPI application for voc_review_fetcher — Opal custom tool."""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# Ensure project root is on sys.path for lib imports (local + Vercel).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

load_dotenv(_PROJECT_ROOT / ".env")

from lib.discovery import get_manifest
from lib.g2_client import fetch_g2_reviews
from lib.models import (
    FetchReviewsRequest,
    FetchReviewsResponse,
    Review,
    SourceType,
    Stats,
    sort_reviews_by_date_desc,
    utc_now_iso,
)
from lib.reddit_client import fetch_reddit_reviews

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_VERSION = "0.1.0"

app = FastAPI(
    title="voc_review_fetcher",
    description=(
        "Fetches public customer reviews and discussions about a brand from "
        "Reddit and G2. Use this when an agent needs real customer language, "
        "sentiment, or feedback about a product or company. Returns structured "
        "reviews with verbatim text, source URLs, ratings, dates, and aggregate "
        "stats (cost, latency, source success)."
    ),
    version=APP_VERSION,
    servers=[
        {
            "url": "https://optimizely-fde-takehome-git-main-trilllabs.vercel.app",
            "description": "Production (Vercel)",
        }
    ],
)


@app.get(
    "/health",
    operation_id="health",
    summary="Health check",
    description="Returns service status and version. Use to verify the tool is reachable.",
)
def health() -> dict[str, str]:
    """Health check endpoint for monitoring and deploy verification."""
    return {"status": "ok", "version": APP_VERSION}


@app.get(
    "/discovery",
    operation_id="discovery",
    summary="Opal tool manifest",
    description=(
        "Returns the Optimizely Opal tool manifest describing the tools this "
        "service exposes. Called by Opal during tool registry setup. "
        "Not consumed by humans — see /openapi.json for OpenAPI 3.1 instead."
    ),
    response_class=JSONResponse,
)
async def discovery() -> JSONResponse:
    return JSONResponse(
        content=get_manifest(),
        media_type="application/json",
    )


@app.post(
    "/fetch_reviews",
    response_model=FetchReviewsResponse,
    operation_id="fetch_reviews",
    summary="Fetch customer reviews for a brand",
    description=(
        "Fetch public customer reviews and discussions about a brand from "
        "Reddit and G2. Returns up to limit_per_source items per source, "
        "filtered to the last time_window_days. Continues gracefully if "
        "individual sources fail (reports them in stats.sources_failed). "
        "Typical latency: 30s (Reddit only), 90s (G2 only), 100s (both). "
        "Typical cost: $0.01 (Reddit only) to $0.11 (both sources, full limits)."
    ),
)
def fetch_reviews(req: FetchReviewsRequest) -> FetchReviewsResponse:
    """
    Fetch public customer reviews and discussions for a brand.

    Aggregates results from Reddit and G2, continuing when individual sources fail.
    """
    brand = req.brand
    start = time.perf_counter()
    reviews: list[Review] = []
    sources_succeeded: list[SourceType] = []
    sources_failed: list[str] = []
    estimated_cost_usd = 0.0

    logger.info("Fetching reviews for brand=%s sources=%s", brand, req.sources)

    for source in req.sources:
        if source == "reddit":
            reddit_reviews, failure, cost = fetch_reddit_reviews(
                brand=brand,
                limit=req.limit_per_source,
                time_window_days=req.time_window_days,
            )
            estimated_cost_usd += cost
            if failure:
                sources_failed.append(failure)
                logger.warning("Reddit fetch failed: %s", failure)
            else:
                sources_succeeded.append("reddit")
                reviews.extend(reddit_reviews)
                logger.info("Reddit returned %d reviews", len(reddit_reviews))

        elif source == "g2":
            g2_reviews, failure, cost = fetch_g2_reviews(
                brand=brand,
                limit=req.limit_per_source,
            )
            estimated_cost_usd += cost
            if failure:
                sources_failed.append(failure)
                logger.warning("G2 fetch failed: %s", failure)
            else:
                sources_succeeded.append("g2")
                reviews.extend(g2_reviews)
                logger.info("G2 returned %d reviews", len(g2_reviews))

    sorted_reviews = sort_reviews_by_date_desc(reviews)
    latency_ms = int((time.perf_counter() - start) * 1000)

    return FetchReviewsResponse(
        brand=brand,
        fetched_at=utc_now_iso(),
        reviews=sorted_reviews,
        stats=Stats(
            total_fetched=len(sorted_reviews),
            sources_succeeded=sources_succeeded,
            sources_failed=sources_failed,
            latency_ms=latency_ms,
            estimated_cost_usd=round(estimated_cost_usd, 6),
        ),
    )
