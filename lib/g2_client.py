"""G2 review fetching via ScrapingBee."""

from __future__ import annotations

import logging
import os
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError, RequestException

from lib.g2_parser import find_product_url, parse_reviews_html
from lib.models import Review, sort_reviews_by_date_desc

logger = logging.getLogger(__name__)

SCRAPINGBEE_URL = "https://app.scrapingbee.com/api/v1/"
# Cost in USD per request at ScrapingBee's $0.001/credit baseline.
# - search page: premium_proxy + render_js = 25 credits = $0.025
# - reviews page: stealth_proxy + render_js = 75 credits = $0.075
# Reviews pages need stealth — premium returns 403 (verified empirically).
COST_PREMIUM = 0.025
COST_STEALTH = 0.075
G2_BASE = "https://www.g2.com"


def _scrapingbee_get(
    api_key: str, url: str, stealth: bool = False, timeout: int = 60
) -> str:
    """Fetch a URL through ScrapingBee with JS rendering.

    Uses premium proxy by default; opt into the more expensive stealth proxy
    when the target page applies aggressive bot detection (G2 reviews pages).
    """
    params: dict[str, str] = {
        "api_key": api_key,
        "url": url,
        "render_js": "true",
        "country_code": "us",
    }
    if stealth:
        params["stealth_proxy"] = "true"
    else:
        params["premium_proxy"] = "true"

    response = requests.get(SCRAPINGBEE_URL, params=params, timeout=timeout)
    response.raise_for_status()
    return response.text


def fetch_g2_reviews(
    brand: str,
    limit: int,
) -> tuple[list[Review], str | None, float]:
    """
    Fetch G2 reviews for a brand via ScrapingBee.

    Returns:
        Tuple of (reviews, failure_reason, estimated_cost_usd).
    """
    api_key = os.getenv("SCRAPINGBEE_API_KEY")
    if not api_key:
        return [], "g2: SCRAPINGBEE_API_KEY not set", 0.0

    cost = 0.0
    search_url = f"{G2_BASE}/search?query={quote_plus(brand)}"

    try:
        logger.info("Fetching G2 search page for brand=%s", brand)
        search_html = _scrapingbee_get(api_key, search_url, stealth=False)
        cost += COST_PREMIUM

        product_url = find_product_url(BeautifulSoup(search_html, "html.parser"))
        if not product_url:
            return [], "g2: product page not found in search results", cost

        reviews_url = f"{product_url}/reviews"
        logger.info("Fetching G2 reviews page: %s", reviews_url)
        reviews_html = _scrapingbee_get(api_key, reviews_url, stealth=True)
        cost += COST_STEALTH

        reviews = parse_reviews_html(reviews_html, product_url, limit)
        if not reviews:
            return [], "g2: no reviews parsed from page", cost

        return sort_reviews_by_date_desc(reviews), None, cost

    except HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "error"
        logger.warning("ScrapingBee HTTP error: %s", exc)
        return [], f"g2: HTTP {status}", cost
    except RequestException as exc:
        logger.warning("ScrapingBee request error: %s", exc)
        return [], f"g2: {exc}", cost
    except (ValueError, AttributeError) as exc:
        logger.warning("G2 parse error: %s", exc)
        return [], f"g2: parse error: {exc}", cost
