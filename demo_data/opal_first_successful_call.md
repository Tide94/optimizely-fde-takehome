# Opal first successful call — annotated

First end-to-end successful call from **Optimizely Opal → live Vercel
deployment → Reddit (via ScrapingBee)** after the envelope-handler patch
landed.

Captured: `2026-05-21T23:06:29Z` against
`optimizely-fde-takehome-git-main-trilllabs.vercel.app/fetch_reviews`.

Raw data: [opal_first_successful_call.json](./opal_first_successful_call.json)

## Why this artifact matters

Confirms three integration questions in one response:

1. **Opal can reach the tool.** Discovery + envelope shape both pass
   validation; the call returns 200 with the expected schema.
2. **The envelope wrapper works.** The `response_type: "application/json"`
   plus the inner `response` object is exactly what Opal returns to the
   calling agent — proving the dual-shape handler unwraps the Opal payload
   correctly and the calling agent sees a normal `FetchReviewsResponse`.
3. **The Reddit-via-ScrapingBee path is alive in production.**
   `stats.sources_succeeded = ["reddit"]`, `cost = $0.004` (≈4 SB credits
   for 2 results), `latency_ms = 15767` — consistent with the local
   smoke-test envelope above.

## Headline result

| Field | Value |
|---|---|
| Brand | Optimizely |
| Total fetched | 2 |
| Sources succeeded | `["reddit"]` |
| Sources failed | `[]` |
| Estimated cost | $0.004 |
| Latency | 15.7s |

Both reviews are real Reddit posts from the search-relevance ranking that
contain the substring "Optimizely". One is genuinely a CRO/Optimizely
discussion (the LP-testing thread from `r/GoogleAdsDiscussion`); the other
is an unrelated meme post that matched on the keyword "optimized". This
is the same precision/recall trade-off documented in
[notion_noise_baseline.json](./notion_noise_baseline.json) — the fetcher
is the recall layer, the calling LLM in Opal is the precision filter.
