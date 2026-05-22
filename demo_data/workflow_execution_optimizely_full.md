# Workflow Summary: Voice of Customer (VoC) Analysis for Optimizely

The Voice of Customer Analyst workflow has successfully completed,
transforming raw customer signal from public forums into a polished,
strategic messaging report for Optimizely.

## Execution Highlights

### Signal Gathering

**Agent:** Signal Gatherer
**Action:** The workflow initiated by crawling public discussions
(specifically Reddit) to identify how customers talk about Optimizely.
**Key Findings:** The agent retrieved high-relevance signals regarding
Optimizely's "SiteSwitch" program for Sitecore migrators and technical
frustrations regarding GDPR consent banners in the audience builder.

### Thematic Mapping

**Agent:** Theme Mapper
**Action:** Raw feedback was clustered into two primary ranked themes,
backed strictly by verbatim customer quotes.

**Themes Identified:**

- **Theme 1: Premier enterprise alternative for Sitecore migrators.**
  Sentiment: *Positive*. Customers view Optimizely as the "less pain"
  alternative to Sitecore.
- **Theme 2: Audience builder struggles with GDPR consent states.**
  Sentiment: *Negative*. Users reported that the audience builder
  "chokes" or gets "confused" when handling European consent states.

### Voice Translation & Messaging Strategy

**Agent:** Voice Translator
**Action:** This step audited the live Optimizely homepage (which
currently focuses on generic "AI-Powered Experiences") and compared
it against the themes.
**Deliverables:** Developed concrete copy recommendations grounded in
verbatim language.
**Key Recommendation:** Pivot from "AI buzzwords" to positioning
Optimizely as the "less pain" migration path from legacy systems, and
explicitly use technical copy to address the reliability of the
audience builder in high-privacy regions.

### Report Rendering

**Agent:** Report Renderer
**Action:** The messaging strategy and gap analysis were rendered into
a professional format.
**Outcome:** A final report was generated in the workspace and exported
as a PDF.

## Final Artifacts

| Field | Value |
|---|---|
| Report Name | Voice of Customer Report: Optimizely |
| Canvas ID | `d87qtia9io6g00dmhhg0` |
| Exported File | `voc_report_Optimizely.pdf` |

The workflow successfully identified a significant disconnect between
Optimizely's generic marketing and the specific "migration relief"
value-add prized by its enterprise customers.

--- EXECUTION METADATA ---
Agents: Signal Gatherer → Theme Mapper → Voice Translator → Report Renderer
Status: COMPLETED
Canvas ID: d87qtia9io6g00dmhhg0
PDF: voc_report_Optimizely.pdf
Run date: 2026-05-22

---

## Note on multiple runs in this folder

This summary describes a **different execution** from the one captured
in [report_renderer_optimizely_run.json](./report_renderer_optimizely_run.json)
(Canvas ID `d87qngq9io6g00dmhheg`). Both runs are real; they surfaced
different themes because Opal's downstream agents see slightly
different upstream data on each call (Reddit/G2 results shift, and
the LLM clustering is non-deterministic).

The two runs together show that the same architecture surfaces
legitimate but distinct VoC angles on the same brand — useful for
demonstrating that the system isn't memorising a canned answer.
Detailed JSON from the *Configured Commerce / SAP* run lives in
[signal_gatherer_optimizely_run.json](./signal_gatherer_optimizely_run.json),
[theme_mapper_optimizely_run.json](./theme_mapper_optimizely_run.json),
and [voice_translator_optimizely_run.json](./voice_translator_optimizely_run.json).
This summary captures the *SiteSwitch / GDPR* run.
