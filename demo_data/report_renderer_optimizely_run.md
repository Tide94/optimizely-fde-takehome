# Optimizely report-renderer — annotated

Output of a **fourth downstream Opal agent** ("report_renderer") that
takes the voice_translator's grounded recommendations and renders them
into a polished **Canvas + exported PDF** — the shareable deliverable
a marketing leader can email around or drop into a slide deck without
further editing.

This closes the agent pipeline that the FDE-built Opal app provides
on top of our single `/fetch_reviews` tool:

```
/fetch_reviews  →  signal_gatherer  →  theme_mapper  →  voice_translator  →  report_renderer
(our tool)         filter on-brand     cluster themes    propose copy        render Canvas + PDF
raw VOC items      high-relevance      6 themes          6 grounded recs     shareable report
                   + verbatim quotes   + sentiment       + stakeholder
                                       + so_what         summary
```

Raw data: [report_renderer_optimizely_run.json](./report_renderer_optimizely_run.json)

## Why this artifact matters

It's the **distribution layer** — every previous artifact in `demo_data/`
proves a function (recall, integration, filter, synthesis, translation).
This one proves the system produces an **artifact a human can share**.
A CMO doesn't open a JSON file; they open a PDF.

Two new agent capabilities surface here that weren't in the earlier
chain:

| Tool | What it does |
|---|---|
| `create_canvas` | Renders the structured VoC report as an Opal Canvas (rich-document view) |
| `canvas_to_file` | Exports the Canvas to a PDF file (`voc_report_Optimizely.pdf`) |

Neither lives in our codebase. They're Opal-native tools the downstream
agent uses, but the data they consume is sourced — root to leaf —
from the `/fetch_reviews` endpoint deployed at
`optimizely-fde-takehome-git-main-trilllabs.vercel.app`.

## Execution metadata

| Field | Value |
|---|---|
| Agent | Report Renderer (`report_renderer`) |
| Tools used | `create_canvas` + `canvas_to_file` |
| Status | COMPLETED |
| Execution ID | `b2fd69bb-f81d-4cd3-8fa6-a7d38fcc1a08` |
| Canvas ID | `d87qngq9io6g00dmhheg` |
| PDF filename | `voc_report_Optimizely.pdf` |

The PDF itself is not committed (it's a build artifact — would belong in
GitHub Releases or an Opal-side store), but the Canvas/PDF IDs above let
anyone with access to the Opal workspace pull up the actual rendered
report.

## Cross-reference — the complete seven-artifact demo set

| # | File | Layer | Output |
|---|---|---|---|
| 1 | [notion_noise_baseline.json](./notion_noise_baseline.json) + [.md](./notion_noise_annotated.md) | Fetcher (recall baseline) | 7/10 on-brand raw signal |
| 2 | [opal_first_successful_call.json](./opal_first_successful_call.json) + [.md](./opal_first_successful_call.md) | Wire integration | First 200 from Opal |
| 3 | [signal_gatherer_pliability.json](./signal_gatherer_pliability.json) + [.md](./signal_gatherer_pliability.md) | Agent 1 (filter, ambiguous brand) | 5→2 with German-language signal |
| 4 | [signal_gatherer_optimizely_run.json](./signal_gatherer_optimizely_run.json) + [.md](./signal_gatherer_optimizely_run.md) | Agent 1 (full pipeline) | 25→11, both sources |
| 5 | [theme_mapper_optimizely_run.json](./theme_mapper_optimizely_run.json) + [.md](./theme_mapper_optimizely_run.md) | Agent 2 (synthesis) | 11→6 themes ranked |
| 6 | [voice_translator_optimizely_run.json](./voice_translator_optimizely_run.json) + [.md](./voice_translator_optimizely_run.md) | Agent 3 (translation) | 6 themes → 6 grounded copy recs |
| 7 | [workflow_execution_optimizely_full.md](./workflow_execution_optimizely_full.md) | Workflow execution summary | 3-agent chain, 10s, 38 credits |
| 8 | **this file** | **Agent 4 (rendering/distribution)** | **VoC report → Canvas → PDF** |

For the Loom this is the very last screen — the recruiter sees a PDF,
not a JSON. Then the camera pans back through the chain: PDF → copy
recommendations → themes → quotes → raw VOC → our humble `/fetch_reviews`
tool that started it all. One tool, four downstream agents, one
shareable artifact.
