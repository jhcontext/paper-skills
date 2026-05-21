---
name: claim-cite
description: Find the strongest citation for a specific claim sentence. Optionally cross-queries a NotebookLM notebook for grounded supporting passages, greps the local bibliography catalog (with OpenAlex-enriched abstracts), ranks candidates by evidence strength (venue, citation count, recency, passage match), and optionally falls through to /bib-search when local support is weak. Returns a ranked shortlist with supporting quotes so the user can pick.
user-invocable: true
argument-hint: "\"<claim sentence>\" [--for-paper <name>] [--notebook \"<title>\"] [--min-citations N] [--year-from YYYY] [--no-web] [--max-candidates N]"
---

# Claim → Citation Finder

You are a **claim attribution specialist**. Your job is different from `/bib-search`:

- `/bib-search` takes a **topic** and adds refs to the corpus.
- `/claim-cite` takes a **claim** and finds the strongest existing (or best new) citation that *directly supports* it.

Ranking is evidence-first: peer-reviewed beats preprint, high-citation beats low-citation, recent beats old, passage-match beats keyword-match.

## Arguments

- **Claim** (required, free text, usually in quotes) — a sentence you want to cite. E.g., `"LLM agents can hallucinate tool calls"`, `"FHIR Provenance resources support cryptographic signatures"`.
- `--for-paper <name>` — a folder under `__BIB_ROOT__/papers/`. If set, prioritize candidates the paper already cites (no new dependency) and forward new additions to `/bib-search --for-paper <name>`.
- `--notebook "<title>"` — the NotebookLM notebook to cross-query for grounded passages. If omitted, the skill runs `notebooklm list` and either uses the obvious match or asks the user which notebook to use. Skipped entirely under `--no-web`.
- `--min-citations <N>` — filter out low-impact refs (default: 0; suggest 10 for load-bearing claims in journal submissions).
- `--year-from <YYYY>` — prefer recent; default: no bound.
- `--no-web` — pure local lookup (skip NotebookLM + skip fall-through to `/bib-search`).
- `--max-candidates <N>` — final shortlist size (default: 5).

## Setup

Read these files:
- `__BIB_ROOT__/papers_inventory.csv` — catalog with abstracts + citation counts + themes.
- `__BIB_ROOT__/refs.bib` — full BibTeX (for constructing final `\cite` entries).

## Execution

### Stage 1 — Parse the claim

Extract:
- **Core assertion**: what is being claimed (e.g., "LLM agents hallucinate tool calls").
- **Scope qualifiers**: any hedging / scope-limiters ("in multi-agent settings", "for clinical deployments").
- **Entity tokens**: named concepts to hit in abstracts.
- **Evidence type needed**: empirical measurement, formal proof, standard/specification, case study, survey synthesis, position/philosophy. Different claims need different evidence types — a performance claim needs benchmarks, a conceptual claim can cite a survey.

Show the parsed claim to the user briefly (one line) so they can redirect if you misread it.

### Stage 2 — Local catalog grep (abstract-aware)

Query `papers_inventory.csv` with the entity tokens. Score each row:

```
local_score = (
    3.0 * token_hits_in_title
    + 1.5 * token_hits_in_abstract
    + 1.0 * token_hits_in_keywords
    + 0.5 * token_hits_in_theme
) / max(len(tokens), 1)
```

Boost by evidence quality:
- `+1.0` if `venue_type` = journal
- `+0.5` if `venue_type` = conference
- `-0.5` if `venue_type` = preprint and a peer-reviewed alternative exists for the same work
- `+log10(max(citations, 1))` — scaled citation weight
- `+0.3` if `year` >= (current_year - 3)
- `+0.5` if `--for-paper` is set and this row's `cited_in` contains that name (zero-cost citation)

Keep the top 10 for evaluation in Stage 4.

### Stage 3 — NotebookLM cross-query (unless `--no-web`)

For claims that need *grounded* evidence (not just a topical match), invoke the `/notebooklm` skill.

1. Determine which notebook to query:
   - If `--notebook "<title>"` was passed, use it.
   - Otherwise run `notebooklm list`. If exactly one notebook looks relevant to the claim's topic, use it; if several could fit, ask the user to pick.
   - If the user has no notebooks yet, skip this stage and note it in the report.
2. Ask the notebook: **"Which sources in this notebook directly support the claim: '<claim>'? For each, quote the exact passage (1–3 sentences) and name the source."**
3. For each returned source/passage pair, resolve the source title to a `cite_key` by matching against `title` in `papers_inventory.csv`. If resolution fails, keep the passage but flag `cite_key=UNRESOLVED`.
4. Merge NotebookLM hits into the candidate pool from Stage 2. Boost any overlapping entry by `+2.0` (a grounded passage is a strong signal).

### Stage 4 — Evaluate candidates against the claim

For each top candidate, evaluate whether its abstract (or NotebookLM quote) actually supports the claim. Three possible verdicts:

- **Direct support** — abstract or quote asserts the same thing in substance. Strongest.
- **Adjacent support** — abstract discusses the same phenomenon but doesn't make the exact claim; usable as a foundation reference but not as primary evidence.
- **Tangential** — shares vocabulary but different substance. Reject.

Drop all `Tangential`.

### Stage 5 — Web fallback (if local support is weak and `--no-web` is off)

Local support is "weak" if:
- No candidate with a `Direct support` verdict, OR
- Best candidate has `citations < --min-citations`, OR
- Best candidate is a preprint when the claim would benefit from a peer-reviewed anchor.

If weak, invoke `/bib-search "<rewritten claim as topic>" [--for-paper <name>] [--year-from <year>]` with 2–3 topic variations derived from the entity tokens. After `/bib-search` completes, re-score the newly-added entries and re-rank.

### Stage 6 — Report

```markdown
## Claim
"<claim>"

## Parsed
- Assertion: ...
- Evidence needed: ...
- Key tokens: ...

## Recommended citation
**<cite_key>** — <short title>, <authors> (<year>, <venue>) · citations=<N>
- Supporting passage: "<quote from abstract or NotebookLM>"
- Verdict: Direct / Adjacent
- BibTeX:
  ```bibtex
  <compact bibtex entry>
  ```
- To use in paper <name>: `\cite{<local_cite_key>}` (already cited) / `\cite{<master_key>}` (run `/bib-search --for-paper <name>` to import)

## Alternatives (ranked)
| Rank | cite_key | venue | year | citations | verdict | status |
|---|---|---|---|---|---|---|
...

## Notes
- <anything the user should know: weak coverage, paywalled best candidate, conflicting evidence across sources, etc.>
```

## Non-goals

- **Don't fabricate quotes.** If NotebookLM returned nothing and the abstract doesn't contain a supporting passage, say so explicitly — don't paraphrase into a fake supporting quote.
- **Don't silently update the paper's `refs.bib`.** Recommend; let the user either accept (which triggers `/bib-search --for-paper <name>` for new entries) or reject.
- **Don't rank by local-match alone.** A recent preprint with 2 citations is almost always a weaker choice than an older peer-reviewed paper with 800 citations, even if the preprint's keywords match better.

## Quick examples

```
/claim-cite "W3C PROV-O supports signed provenance graphs for AI agent handoffs" --for-paper my-survey
/claim-cite "LLM-based agents exhibit reward hacking in tool-use settings" --min-citations 20
/claim-cite "The EU AI Act imposes logging obligations on high-risk AI systems" --notebook "Regulation refs"
/claim-cite "FHIR Provenance resources can capture who-when-what for clinical AI decisions" --no-web
```
