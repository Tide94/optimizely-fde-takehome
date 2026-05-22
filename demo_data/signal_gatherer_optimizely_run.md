# Optimizely signal-gatherer — annotated

The flagship demo artifact: the **same downstream Opal agent** that
produced [signal_gatherer_pliability.json](./signal_gatherer_pliability.json),
run against the eponymous brand "Optimizely" — and crucially, the
first run where **both Reddit and G2 paths returned data** to the
calling agent.

Raw data: [signal_gatherer_optimizely_run.json](./signal_gatherer_optimizely_run.json)

## Why this artifact matters

It closes the loop on the architectural thesis with the largest n and
the most complete source coverage we've captured:

| Stat | Value | Notes |
|---|---|---|
| Raw items fetched | 25 | combined Reddit + G2 |
| Kept high-relevance | 11 | 1 Reddit + 10 G2 |
| Dropped (off-topic entity mismatch) | 14 | all 14 from `off_topic_entity_mismatch` |
| Drop rate | 56% | consistent with the 60% on Pliability and 30% on Notion |
| `sources_succeeded` | `["reddit", "g2"]` | **both sources, no failures** |
| `sources_failed` | `[]` | end-to-end happy path |

The agent's filter recovers exactly the kind of split we'd want:
- 1 Reddit thread (`r/GoogleAdsDiscussion` — "Optimizely or other LP
  testing tool?") — exactly the kind of competitive-comparison VOC the
  ICP marketing team would want
- 10 G2 reviews spanning Configured Commerce's full review history
  (2022 → 2025), with ratings 2–5, surfacing both praise and friction

Across all four demo artifacts, the drop-rate range (30–60%) is
predictable noise pattern, not signal of fetcher misbehaviour.

## High-signal kept items

A few that translate directly into VOC story beats:

- **Praise — developer empathy.** *"Built in commerce manager is a huge
  help for both product managers and developers"* (Kevin J., rating 4)
- **Praise — B2B fit.** *"how this platform truly understands complex
  B2B needs … handles our intricate product configurations and bulk
  ordering workflows effortlessly"* (Gustavo L., rating 5)
- **Mixed signal — value at a cost.** *"There are still just a few UI
  experiences that aren't the most user friendly."* (Verified User in
  Construction, rating 4)
- **Negative — price/value friction.** Rating 2 review from a Consulting
  reviewer focused on cost-to-personalisation ratio
- **Competitive intent — churn / comparison.** Reddit OP asks for
  alternatives by name — the most actionable Reddit signal here

## Cross-reference

Four artifacts now form the complete demo set:

| File | Layer | What it proves |
|---|---|---|
| [notion_noise_baseline.json](./notion_noise_baseline.json) + [.md](./notion_noise_annotated.md) | Fetcher | The recall side: 7/10 on-brand, the rest English-word collisions |
| [opal_first_successful_call.json](./opal_first_successful_call.json) + [.md](./opal_first_successful_call.md) | Wire | Opal's first 200 — the envelope wrapping works |
| [signal_gatherer_pliability.json](./signal_gatherer_pliability.json) + [.md](./signal_gatherer_pliability.md) | Agent | The precision side: 5→2 with German-language signal and a churn thread |
| **this file** | **Agent + Wire + Fetcher** | **Both sources succeed, 25→11, full pipeline end-to-end** |

For the Loom narrative this is the closer: "given the architecture, here's
what happens with real data on the brand you're hiring me to think about."
