# Notion noise baseline — annotated

Captured: `2026-05-21T21:10:11Z` against `optimizely-fde-takehome-git-main-trilllabs.vercel.app`

Request: `POST /fetch_reviews` with `{brand:'Notion', sources:['reddit'], limit_per_source:10, time_window_days:90}`

Stats: 10 reviews, cost $0.018, latency 111055ms, `sources_succeeded:['reddit']`

Raw data: [notion_noise_baseline.json](./notion_noise_baseline.json)

## Hand-classified relevance

| # | On-brand | Subreddit | Title (truncated) | Verdict |
|---|---|---|---|---|
| 1 | ✅ | r/productivity | "Who here still uses Notion and who switched to something else?" | Explicit comparison of Notion-the-product vs alternatives |
| 2 | ✅ | r/Notion | "What apps are people using instead of Notion these days?" | Posted in the company subreddit |
| 3 | ✅ | r/ProductivityApps | "I spent 3 years using Notion for everything. Switched to Obsidian" | Long migration write-up |
| 4 | ✅ | r/Notion | "Notion AI is a joke and it always has been" | Direct product critique |
| 5 | ✅ | r/Notion | "what do you guys use notion for" | Use-case discussion |
| 6 | ❌ | r/nba | "[The Athletic] The notion that James would want a farewell tour" | English noun — LeBron James, unrelated |
| 7 | ✅ | r/notioncreations | "Is it just me, or has anyone else slowly stopped using Notion?" | Churn signal from power-user subreddit |
| 8 | ❌ | r/freefolk | "Why do people push the notion that ASOIAF and GoT is cynical" | English noun — Game of Thrones, unrelated |
| 9 | ✅ | r/SaaS | "Notion reportedly has ~1,000 employees" | Discussion of the company itself |
| 10 | ❌ | r/Marathon | "Elliot Gray... claps back at the notion that no one from the Halo days" | English noun — Bungie / Marathon video game |

**Precision: 7/10 = 70%.** All three false positives match the same pattern: the English noun *notion* appearing in posts about unrelated topics (basketball, fantasy fiction, video games), surfaced by Reddit's keyword-relevance ranking which can't distinguish brand-mention from common-word-mention.

## Why this is acceptable for an Opal custom tool

This fetcher is the **recall layer** — its job is to cheaply surface candidate posts containing the brand string. The Opal agent that calls it is an LLM with full access to `title + body` and is well-equipped to discard obvious false positives like "the notion that LeBron…" without further fetcher logic. The architectural choice is **dumb-and-cheap retrieval + downstream classification**, which keeps this service simple, cheap, and reusable across brands without per-brand tuning.

## What would close the precision gap (future work)

| Idea | Cost | Lift |
|---|---|---|
| Query enrichment for ambiguous brands (e.g. `"Notion" software`, `"Notion" review`) | ~1 line | Likely cuts noise 50%+ on common-noun brands |
| Subreddit allow/blocklist (drop `r/nba`, `r/freefolk`, etc. with zero SaaS-discussion signal) | small | Solves this specific failure mode |
| In-body co-occurrence filter (brand within N tokens of `app`/`tool`/`pricing`/`users`) | small | Generalisable across brands without per-brand config |
| Re-rank with an embedding model against a brand description | medium | Highest precision, adds latency + dependency |

None of these were implemented in the take-home — left as deliberate scope cut to keep the tool focused on retrieval and ship within the time box.
