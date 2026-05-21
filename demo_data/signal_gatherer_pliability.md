# Pliability signal-gatherer — annotated

Output of a **downstream Opal agent** ("signal_gatherer") that:

1. Resolves the brand entity (definition, competitors, exclusion signals)
2. Calls our `/fetch_reviews` tool
3. LLM-filters the raw results, keeping only on-brand items and emitting
   `verbatim_quotes` + a `relevance_reason` for each

Captured: 2026-05-22, brand "Pliability" (mobility/recovery app),
90-day window. Raw data:
[signal_gatherer_pliability.json](./signal_gatherer_pliability.json)

## Why this artifact matters

This is the **architectural-thesis proof point**. The
[Notion noise analysis](./notion_noise_annotated.md) argued for
*dumb-and-cheap retrieval in the fetcher + LLM precision in the calling
agent*. Here's that pattern running end-to-end against a real brand,
with quantified results from the agent layer itself:

| Stat | Value |
|---|---|
| Raw items fetched | 5 |
| Kept high-relevance | 2 |
| Dropped (off-topic entity mismatch) | 3 |
| Drop rate | 60% |
| `sources_succeeded` | `["reddit"]` |
| `sources_failed` | `["g2"]` |

The 60% drop rate is consistent with the ~30% noise rate observed on a
strict-ambiguity brand ("Notion"). "Pliability" is much more ambiguous as
an English word (medical, mechanical, metaphorical) so the agent has to
filter harder — but the architecture handles it without changes to the
fetcher.

`g2` in `sources_failed` is the graceful-degradation path we built in:
the agent still got useful signal from Reddit-only, the run was not
aborted, and a downstream consumer would see the failure surfaced
explicitly in `run_stats`.

## High-signal kept items

1. **r/hundeschule — German-language thread on a yoga-for-dogs app.**
   The user volunteers their own routine and praises Pliability:
   > *"Was ich an der App gut finde (und warum ich sie seit fast 2 Jahren
   > fast jeden Tag nutze) ist, dass ich jeden Morgen einfach 'Play'
   > drücke und es losgeht."*
   This is the kind of in-the-wild VOC that brand-monitoring tools
   miss — the post isn't *about* Pliability but mentions it as a daily
   habit. Reddit search surfaced it; the agent kept it because the
   `verbatim_quotes` are unmistakably product-discussion.

2. **r/flexibility — "Pliability Alternative" churn thread.**
   Explicit churn-intent signal: *"I absolutely love Pliability, but
   I can't afford it right now."* — the most actionable kind of VOC
   for a pricing/positioning team.

## Cross-reference

Three artifacts now live in this directory:
- [notion_noise_baseline.json](./notion_noise_baseline.json) — raw
  fetcher output, 7/10 on-brand baseline
- [opal_first_successful_call.json](./opal_first_successful_call.json) —
  Opal's first 200 response (envelope wrapping our schema)
- this file — Opal *agent's* filtered output, showing the recall +
  precision architecture in production
