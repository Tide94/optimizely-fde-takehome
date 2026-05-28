"""Schema / contract tests for the Opal tool definition.

Covers three contracts:
  1. The /discovery manifest shape Opal's validator enforces.
  2. The input schema (FetchReviewsRequest) — rejects bad input, accepts valid.
  3. The output schema (FetchReviewsResponse/Stats/Review) — required keys the
     agent depends on.
Plus a manifest<->model consistency check so the two never drift.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lib.discovery import get_manifest
from lib.models import FetchReviewsRequest, FetchReviewsResponse, Review, Stats

VALID_PARAM_TYPES = {"string", "number", "boolean", "array", "object"}


class TestManifestShape:
    def test_parameters_is_a_list_not_a_dict(self) -> None:
        # The critical Opal gotcha: a keyed dict triggers AttributeError in
        # Opal's parser. Parameters must be an array of descriptors.
        fn = get_manifest()["functions"][0]
        assert isinstance(fn["parameters"], list)

    def test_each_parameter_well_formed(self) -> None:
        fn = get_manifest()["functions"][0]
        for param in fn["parameters"]:
            assert "name" in param
            assert "type" in param
            assert "description" in param
            assert param["type"] in VALID_PARAM_TYPES
            assert len(param["description"]) > 10


class TestInputSchemaContract:
    def test_rejects_missing_required_brand(self) -> None:
        with pytest.raises(ValidationError):
            FetchReviewsRequest(sources=["reddit"])

    def test_rejects_invalid_type_for_limit(self) -> None:
        with pytest.raises(ValidationError):
            FetchReviewsRequest(brand="X", limit_per_source="not-a-number")

    def test_rejects_invalid_source_enum(self) -> None:
        with pytest.raises(ValidationError):
            FetchReviewsRequest(brand="X", sources=["facebook"])

    def test_valid_example_input_passes(self) -> None:
        req = FetchReviewsRequest(
            brand="Optimizely",
            sources=["reddit", "g2"],
            limit_per_source=20,
            time_window_days=90,
        )
        assert req.brand == "Optimizely"


class TestOutputSchemaContract:
    def test_response_has_required_top_level_keys(self) -> None:
        keys = set(FetchReviewsResponse.model_fields.keys())
        assert {"brand", "fetched_at", "reviews", "stats"}.issubset(keys)

    def test_stats_has_required_keys(self) -> None:
        keys = set(Stats.model_fields.keys())
        assert {
            "total_fetched",
            "sources_succeeded",
            "sources_failed",
            "latency_ms",
            "estimated_cost_usd",
        }.issubset(keys)

    def test_review_has_required_keys(self) -> None:
        keys = set(Review.model_fields.keys())
        assert {
            "source",
            "url",
            "title",
            "body",
            "rating",
            "date",
            "author_meta",
            "score",
        }.issubset(keys)


class TestManifestModelConsistency:
    def test_manifest_params_map_to_model_fields(self) -> None:
        fn = get_manifest()["functions"][0]
        manifest_names = {p["name"] for p in fn["parameters"]}
        model_names = set(FetchReviewsRequest.model_fields.keys())
        assert manifest_names == model_names

    def test_required_flag_matches_model(self) -> None:
        fn = get_manifest()["functions"][0]
        manifest_required = {p["name"] for p in fn["parameters"] if p.get("required")}
        model_required = {
            name
            for name, field in FetchReviewsRequest.model_fields.items()
            if field.is_required()
        }
        assert manifest_required == model_required
