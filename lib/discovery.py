"""Opal Tool Manifest builder.

Opal's validator enforces an OCP-style function format: root key `functions`,
parameters as an array of `{name, type, description, required}` descriptors.
This shape differs from both the public Opal docs (which describe a `tools`
root key) and JSON Schema conventions (which would key parameters by name);
it was confirmed against the validator itself and via a verbatim example.

Spec context (note: validator is stricter than this doc):
https://support.optimizely.com/hc/en-us/articles/39190444893837
"""

from typing import Any

OPAL_MANIFEST: dict[str, Any] = {
    "functions": [
        {
            "name": "fetch_reviews",
            "description": (
                "Fetch public customer reviews and discussions about a brand "
                "from Reddit and G2. Use this when an agent needs real customer "
                "language, sentiment, or feedback about a product or company. "
                "Returns structured reviews with verbatim text, source URLs, "
                "ratings, dates, and aggregate stats (cost, latency, source "
                "success). Typical latency: 30s (Reddit only), 90s (G2 only), "
                "100s (both). Typical cost: $0.01 to $0.11 per call."
            ),
            "endpoint": "/fetch_reviews",
            "method": "POST",
            "parameters": [
                {
                    "name": "brand",
                    "type": "string",
                    "description": (
                        "Brand or product name to fetch reviews for. "
                        "Examples: 'Optimizely', 'Notion', 'HubSpot'. "
                        "For ambiguous names (common English words), expect "
                        "lower precision — downstream relevance filtering is "
                        "recommended."
                    ),
                    "required": True,
                },
                {
                    "name": "sources",
                    "type": "array",
                    "description": (
                        "Sources to fetch from. Allowed values in the array: "
                        "'reddit', 'g2'. Defaults to both ['reddit', 'g2'] if "
                        "omitted. Reddit returns community discussions; G2 "
                        "returns structured product reviews with star ratings."
                    ),
                    "required": False,
                },
                {
                    "name": "limit_per_source",
                    "type": "number",
                    "description": (
                        "Maximum items to fetch per source. Integer between 1 "
                        "and 50. Defaults to 20. Higher values increase cost "
                        "and latency roughly linearly."
                    ),
                    "required": False,
                },
                {
                    "name": "time_window_days",
                    "type": "number",
                    "description": (
                        "Only return items from the last N days. Integer >= 1. "
                        "Defaults to 90. Applies to Reddit; G2 returns all "
                        "available reviews regardless of this value."
                    ),
                    "required": False,
                },
            ],
        }
    ]
}


def get_manifest() -> dict[str, Any]:
    """Return the Opal tool manifest for this service."""
    return OPAL_MANIFEST
