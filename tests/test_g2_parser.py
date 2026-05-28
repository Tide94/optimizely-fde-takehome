"""Unit tests for lib/g2_parser.py — URL normalization and HTML parsing.

Uses small hand-built HTML fixtures; no live fetching. find_product_url takes a
BeautifulSoup; parse_reviews_html / parse_review_card take a product_url.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from lib.g2_parser import (
    G2_BASE,
    _parse_author_meta,
    _parse_date,
    _parse_rating,
    find_product_url,
    normalize_product_url,
    parse_review_card,
    parse_reviews_html,
)

PRODUCT_URL = "https://www.g2.com/products/optimizely"


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


class TestNormalizeProductUrl:
    def test_valid_product_href(self) -> None:
        assert (
            normalize_product_url("/products/optimizely")
            == f"{G2_BASE}/products/optimizely"
        )

    def test_strips_reviews_suffix(self) -> None:
        assert (
            normalize_product_url("/products/optimizely/reviews")
            == f"{G2_BASE}/products/optimizely"
        )

    def test_empty_href_returns_none(self) -> None:
        assert normalize_product_url("") is None

    def test_non_product_href_returns_none(self) -> None:
        assert normalize_product_url("/categories/ab-testing") is None


class TestFindProductUrl:
    def test_finds_first_product_link(self) -> None:
        html = """
        <a href="/categories/x">Category</a>
        <a href="/products/optimizely/reviews">Optimizely Reviews</a>
        """
        assert find_product_url(_soup(html)) == f"{G2_BASE}/products/optimizely"

    def test_returns_none_when_no_product_link(self) -> None:
        assert find_product_url(_soup("<a href='/about'>About</a>")) is None

    def test_returns_none_for_empty_html(self) -> None:
        assert find_product_url(_soup("")) is None


class TestParseRating:
    def test_clamps_to_max_five(self) -> None:
        card = _soup('<div aria-label="9 stars">x</div>')
        assert _parse_rating(card) == 5

    def test_returns_none_when_absent(self) -> None:
        assert _parse_rating(_soup("<div>no rating</div>")) is None


class TestParseDate:
    def test_prefers_datetime_attribute(self) -> None:
        card = _soup('<time datetime="2026-04-22T00:00:00Z">Apr 22</time>')
        assert _parse_date(card) == "2026-04-22T00:00:00Z"

    def test_returns_empty_when_absent(self) -> None:
        assert _parse_date(_soup("<div>nothing</div>")) == ""


class TestParseAuthorMeta:
    def test_default_when_absent(self) -> None:
        assert _parse_author_meta(_soup("<div>x</div>")) == "G2 reviewer"


class TestParseReviewCard:
    def test_full_card_returns_review(self) -> None:
        html = """
        <article>
          <h3>Excellent platform</h3>
          <div class="review-body">It scaled well for our team.</div>
          <meta itemprop="ratingValue" content="5">
          <time datetime="2026-04-22T00:00:00Z">Apr 22</time>
          <div class="reviewer-name">Product Manager</div>
        </article>
        """
        card = _soup(html).select_one("article")
        review = parse_review_card(card, PRODUCT_URL)
        assert review is not None
        assert review.source == "g2"
        assert review.title == "Excellent platform"
        assert review.body == "It scaled well for our team."
        assert review.rating == 5
        assert review.date == "2026-04-22T00:00:00Z"
        assert review.author_meta == "Product Manager"

    def test_title_falls_back_to_body(self) -> None:
        html = '<article><div class="review-body">Body only, no title here.</div></article>'
        card = _soup(html).select_one("article")
        review = parse_review_card(card, PRODUCT_URL)
        assert review is not None
        assert review.title == "Body only, no title here."

    def test_no_title_no_body_returns_none(self) -> None:
        card = _soup("<article><span>irrelevant</span></article>").select_one("article")
        assert parse_review_card(card, PRODUCT_URL) is None

    def test_uses_review_specific_link_when_present(self) -> None:
        html = """
        <article>
          <h3>Title</h3>
          <div class="review-body">Body</div>
          <a href="/products/optimizely/reviews/12345">permalink</a>
        </article>
        """
        card = _soup(html).select_one("article")
        review = parse_review_card(card, PRODUCT_URL)
        assert review is not None
        assert review.url.endswith("/reviews/12345")


class TestParseReviewsHtml:
    def test_parses_multiple_cards(self) -> None:
        html = """
        <article><h3>One</h3><div class="review-body">First review body.</div></article>
        <article><h3>Two</h3><div class="review-body">Second review body.</div></article>
        """
        reviews = parse_reviews_html(html, PRODUCT_URL, limit=10)
        assert len(reviews) == 2
        assert {r.title for r in reviews} == {"One", "Two"}

    def test_respects_limit(self) -> None:
        html = "".join(
            f'<article><h3>R{i}</h3><div class="review-body">Body {i}.</div></article>'
            for i in range(5)
        )
        assert len(parse_reviews_html(html, PRODUCT_URL, limit=2)) == 2

    def test_empty_html_returns_empty_list(self) -> None:
        assert parse_reviews_html("", PRODUCT_URL, limit=10) == []
