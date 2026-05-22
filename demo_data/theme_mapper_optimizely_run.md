# Optimizely theme-mapper — annotated

Output of a **second downstream Opal agent** ("theme_mapper") that takes
the [signal_gatherer's 11 high-relevance signals](./signal_gatherer_optimizely_run.json)
and clusters them into ranked, sentiment-tagged **themes with verbatim
quote evidence and a "so what" recommendation** for each.

This is the **end of the agent pipeline** that the take-home enables.
The full chain:

```
/fetch_reviews         →  signal_gatherer  →  theme_mapper
(our tool)                (filter on-brand)    (cluster + rank + recommend)
25 raw items              11 high-relevance    6 themes, 13 quotes,
                          + verbatim_quotes    + summary, sentiment,
                                               + "so what" each
```

Raw data: [theme_mapper_optimizely_run.json](./theme_mapper_optimizely_run.json)

## Why this artifact matters

It's the **marketing-team-ready output** — what an FDE-built Opal app
actually delivers to a business stakeholder. Themes are scored,
sentiment is labelled, recommendations are concrete:

> *"Differentiate from competitors by showcasing the platform's
> specialized ability to solve intricate B2B product and ordering
> logic."* (so_what for theme #2)

That is the level of synthesis the calling LLM is capable of *once the
fetcher feeds it on-brand quotes*. Our tool doesn't have to be smart —
the chain is.

## Top-line numbers

| Stat | Value |
|---|---|
| Total input signals (from signal_gatherer) | 11 |
| Total verbatim quotes clustered | 13 |
| Themes returned | 6 |
| Themes positive-skewed | 5 |
| Themes mixed-skewed | 1 |
| Themes negative-skewed | 0 |

## Themes by rank

| # | Sentiment | Freq | Theme |
|---|---|---|---|
| 1 | positive | 3 | Unified platform streamlines content and personalization |
| 2 | positive | 2 | Seamless handling of complex B2B workflows |
| 3 | positive | 2 | Developer-friendly customization and commerce management |
| 4 | positive | 2 | Comprehensive features deliver reliable business results |
| 5 | **mixed** | 2 | Solid core foundation with minor UI friction |
| 6 | positive | 2 | Fast implementation and responsive customer support |

The mixed-sentiment theme #5 is the most actionable one for an Optimizely
PM — it pairs *"The foundation is very solid"* with *"a few UI experiences
that aren't the most user friendly"*, exactly the kind of qualified
critique a roadmap conversation needs.

## Self-identified gap (and the all-G2 finding)

The agent's own `coverage.notable_gaps` field flags:

> *"The feedback data is almost exclusively sourced from G2 reviews
> regarding the B2B commerce product line, leaving the CMS and
> experimentation segments underrepresented."*

This is honest, useful self-reporting — and it matches what we see in
the raw data: **all 13 supporting quotes are G2-sourced**, none from
the Reddit signal that the signal_gatherer kept. So the theme_mapper
either (a) dropped the lone Reddit thread (a competitive-comparison
question) because it wasn't substantive enough to anchor a theme, or
(b) couldn't cluster it with G2 reviews about a different product line
(Configured Commerce). Either is defensible behaviour and the agent
flagged it explicitly.

For a real production deployment this is the prompt to either:
1. Increase `limit_per_source` on Reddit (current run capped at low n)
2. Add experimentation-/CMS-specific queries upstream
3. Run a second pass against alternate Optimizely subreddits

None of those require code changes to our fetcher — just config in the
calling Opal app.

## Cross-reference — the complete demo set

| File | Layer | Output |
|---|---|---|
| [notion_noise_baseline.json](./notion_noise_baseline.json) + [.md](./notion_noise_annotated.md) | Fetcher (recall) | 7/10 on-brand raw signal |
| [opal_first_successful_call.json](./opal_first_successful_call.json) + [.md](./opal_first_successful_call.md) | Wire | 200 from Opal, envelope round-trips |
| [signal_gatherer_pliability.json](./signal_gatherer_pliability.json) + [.md](./signal_gatherer_pliability.md) | Agent 1 (precision) | 5→2 filter, German-language signal |
| [signal_gatherer_optimizely_run.json](./signal_gatherer_optimizely_run.json) + [.md](./signal_gatherer_optimizely_run.md) | Agent 1 (full pipeline) | 25→11, both sources |
| **this file** | **Agent 2 (synthesis)** | **11→6 themes with recommendations** |

For the Loom this is the closing exhibit: "here's what the system
*outputs* — the marketing-team-ready brief." Everything upstream
(fetcher, wire integration, filter agent) exists to make this layer
possible.
