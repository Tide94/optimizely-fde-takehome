# Optimizely voice-translator — annotated

Output of a **third downstream Opal agent** ("voice_translator") that:

1. Reads the brand's current homepage messaging
2. Reads the theme-mapper's clustered themes + quotes
3. Identifies gaps between current marketing and customer language
4. Generates 6 grounded copy recommendations (hero / subhead / ad_headline /
   email_subject), each traceable back to a specific theme and a verbatim
   customer quote
5. Closes with a stakeholder-ready summary

This is the **terminal node** of the agent pipeline. The full chain
that the take-home enables:

```
/fetch_reviews  →  signal_gatherer  →  theme_mapper  →  voice_translator
(our tool)         filter on-brand     cluster themes   propose copy
25 raw items       11 high-relevance   6 themes,        6 recommendations,
                   + verbatim_quotes   13 quotes,       grounded in
                                       sentiment,       customer language
                                       so_what
```

Raw data: [voice_translator_optimizely_run.json](./voice_translator_optimizely_run.json)

## Why this artifact matters

It's the **business-shippable output** — what a CMO or growth marketer
can act on Monday morning. Every recommendation is grounded:

> **Recommendation:** *"A platform that truly understands complex B2B needs."*
> **Grounded in theme:** Seamless handling of complex B2B workflows
> **Customer quote:** *"how this platform truly understands complex B2B needs"*
> **Rationale:** Swapping generic growth claims for a direct customer
> validation of B2B expertise targets the high-intent enterprise audience…

That traceability — copy → theme → quote → source URL → original
Reddit/G2 post — is the FDE win condition. Marketing can defend
every line in front of legal, leadership, or the customer base.

## The big gap call

The agent's `gap_analysis` field is the headline insight:

> *"Optimizely's current homepage leads with abstract AI-driven 'growth'
> and 'clever' marketing concepts, whereas customers specifically value
> the platform's ability to solve the 'intricate' and 'complex' pain
> points of B2B commerce."*

That is a real, defensible, business-actionable observation —
generated from real customer quotes, not from a brainstorming session.
The hero swap recommendation (from *"AI-powered digital experiences
that drive growth"* → *"A platform that truly understands complex
B2B needs"*) is concrete enough to A/B test.

## Coverage of upstream themes

5 of the 6 themes from
[theme_mapper_optimizely_run.json](./theme_mapper_optimizely_run.json)
made it into marketing recommendations:

| Theme | Used in recommendation? |
|---|---|
| 1. Unified platform streamlines content and personalization | ✅ subhead |
| 2. Seamless handling of complex B2B workflows | ✅ 2× hero |
| 3. Developer-friendly customization and commerce management | ✅ email_subject |
| 4. Comprehensive features deliver reliable business results | ✅ ad_headline |
| 5. Solid core foundation with minor UI friction (**mixed**) | ❌ excluded |
| 6. Fast implementation and responsive customer support | ✅ ad_headline |

The mixed-sentiment theme #5 was correctly excluded — you don't put
"a few UI experiences that aren't the most user friendly" in a hero
or ad. That's the agent making a sensible editorial decision: themes
flow into theme_mapper, but voice_translator picks only the
positive-skewed ones for top-of-funnel copy. The negative half of
that theme still belongs in a product-roadmap deck, just not on a
landing page.

## Recommendation mix

| Type | Count |
|---|---|
| hero | 2 |
| ad_headline | 2 |
| subhead | 1 |
| email_subject | 1 |

Two hero options give the team A/B-test ammunition out of the box.

## Cross-reference — the complete six-artifact demo set

| # | File | Layer | Output |
|---|---|---|---|
| 1 | [notion_noise_baseline.json](./notion_noise_baseline.json) + [.md](./notion_noise_annotated.md) | Fetcher (recall baseline) | 7/10 on-brand raw signal |
| 2 | [opal_first_successful_call.json](./opal_first_successful_call.json) + [.md](./opal_first_successful_call.md) | Wire integration | First 200 from Opal |
| 3 | [signal_gatherer_pliability.json](./signal_gatherer_pliability.json) + [.md](./signal_gatherer_pliability.md) | Agent 1 (filter) | 5→2 with German-language signal |
| 4 | [signal_gatherer_optimizely_run.json](./signal_gatherer_optimizely_run.json) + [.md](./signal_gatherer_optimizely_run.md) | Agent 1 (full pipeline) | 25→11, both sources |
| 5 | [theme_mapper_optimizely_run.json](./theme_mapper_optimizely_run.json) + [.md](./theme_mapper_optimizely_run.md) | Agent 2 (synthesis) | 11→6 themes ranked |
| 6 | **this file** | **Agent 3 (translation)** | **6 themes → 6 grounded copy recommendations + stakeholder summary** |

For the Loom narrative: this is the very last screen. *"Here is what
the FDE-built Opal application delivers to the customer of the
customer — copy that ships, grounded in real voice-of-customer data,
traceable back to source URLs."*
