"""BeautifulSoup parsing helpers for G2 review pages."""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from lib.models import Review, truncate_body

logger = logging.getLogger(__name__)

G2_BASE = "https://www.g2.com"

PRODUCT_LINK_SELECTORS = [
    'a[href*="/products/"][href*="/reviews"]',
    'a[href*="/products/"]',
    '[data-testid*="product"] a[href*="/products/"]',
    ".product-card a[href*='/products/']",
]

REVIEW_CONTAINER_SELECTORS = [
    "article",
    '[itemprop="review"]',
    ".review",
    '[data-testid*="review"]',
]

TITLE_SELECTORS = [
    'div[itemprop="name"]',  # G2 microdata — review title
    "h3",
    ".review-title",
    '[itemprop="name"]',  # generic fallback (may match author name meta)
]
BODY_SELECTORS = [".review-body", '[itemprop="reviewBody"]', ".p-lg"]
RATING_SELECTORS = ['meta[itemprop="ratingValue"]', '[aria-label*="star"]']
DATE_SELECTORS = [
    "time[datetime]",
    'meta[itemprop="datePublished"]',
    '[itemprop="datePublished"]',
    "time",
]
AUTHOR_SELECTORS = [".reviewer-name", '[itemprop="author"]', "div[class*='reviewer']"]


def _node_text_or_content(node: Tag) -> str:
    """Return visible text, falling back to `content` attr for meta tags."""
    text = node.get_text(strip=True)
    if text:
        return text
    content = node.get("content")
    return content.strip() if isinstance(content, str) else ""


def _first_text(element: Tag | None, selectors: list[str]) -> str:
    """Try multiple CSS selectors and return the first non-empty text/content."""
    if element is None:
        return ""
    for selector in selectors:
        for found in element.select(selector):
            value = _node_text_or_content(found)
            if value:
                return value
    return ""


def _parse_rating(element: Tag) -> int | None:
    """Extract star rating 1-5 from a review element."""
    for selector in RATING_SELECTORS:
        node = element.select_one(selector)
        if node is None:
            continue
        content = node.get("content") or node.get("aria-label") or node.get_text()
        match = re.search(r"(\d(?:\.\d)?)", str(content))
        if match:
            return max(1, min(5, int(round(float(match.group(1))))))
    return None


def _parse_date(element: Tag) -> str:
    """Extract review date as ISO 8601 or best-effort string."""
    for selector in DATE_SELECTORS:
        for node in element.select(selector):
            datetime_val = node.get("datetime")
            if datetime_val:
                return datetime_val
            content = node.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
            text = node.get_text(strip=True)
            if text:
                return text
    return ""


def _parse_author_meta(element: Tag) -> str:
    """Build author metadata from role and company fields."""
    parts: list[str] = []
    for selector in AUTHOR_SELECTORS:
        for node in element.select(selector):
            text = node.get_text(" ", strip=True)
            if text and text not in parts:
                parts.append(text)
    return " · ".join(parts[:3]) if parts else "G2 reviewer"


def normalize_product_url(href: str) -> str | None:
    """Resolve a G2 product URL from a search result link."""
    if not href or "/products/" not in href:
        return None
    full = urljoin(G2_BASE, href.split("?")[0].rstrip("/"))
    path = urlparse(full).path.rstrip("/")
    if "/reviews" in path:
        path = path.split("/reviews")[0]
    if "/products/" in path:
        return f"{G2_BASE}{path}"
    return None


def find_product_url(soup: BeautifulSoup) -> str | None:
    """Locate the first product page URL from G2 search HTML."""
    for selector in PRODUCT_LINK_SELECTORS:
        for link in soup.select(selector):
            product_url = normalize_product_url(link.get("href", ""))
            if product_url:
                return product_url
    return None


def parse_review_card(card: Tag, product_url: str) -> Review | None:
    """Parse a single G2 review card; return None if parsing fails."""
    try:
        title = _first_text(card, TITLE_SELECTORS)
        body = _first_text(card, BODY_SELECTORS)
        if not title and not body:
            return None
        if not title:
            title = (body[:80] + "...") if len(body) > 80 else body

        review_url = product_url
        link = card.select_one("a[href*='/reviews/']")
        if link and link.get("href"):
            review_url = urljoin(G2_BASE, link["href"])

        return Review(
            source="g2",
            url=review_url,
            title=title,
            body=truncate_body(body or title),
            rating=_parse_rating(card),
            date=_parse_date(card),
            author_meta=_parse_author_meta(card),
            score=None,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        logger.warning("Skipping G2 review card: %s", exc)
        return None


def parse_reviews_html(html: str, product_url: str, limit: int) -> list[Review]:
    """Parse review cards from G2 reviews page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    reviews: list[Review] = []

    for selector in REVIEW_CONTAINER_SELECTORS:
        cards = soup.select(selector)
        if not cards:
            continue
        for card in cards:
            if len(reviews) >= limit:
                break
            review = parse_review_card(card, product_url)
            if review:
                reviews.append(review)
        if reviews:
            break

    return reviews
