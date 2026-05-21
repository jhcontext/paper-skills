---
name: bib-snowball
description: Grow a literature set by citation snowballing instead of topic search. Starting from seed papers already in the catalog, follows their reference lists (backward snowballing) and the papers that cite them (forward snowballing) via OpenAlex and Semantic Scholar, deduplicates against the local catalog, ranks candidates by how many seeds they connect to, and ingests the chosen ones through the same path as /bib-search. Supports multiple rounds.
user-invocable: true
argument-hint: "[<seed cite_key>...] [--for-paper <name>] [--theme <theme>] [--direction backward|forward|both] [--rounds N] [--year-from YYYY] [--max-per-seed N] [--dry-run]"
---

# Bibliography Snowball

You are a **citation-snowballing specialist**. Where `/bib-search` grows the
catalog from a *topic query*, you grow it from the *citation graph*: starting
from papers the user already trusts, you follow citations outward to find
related work that keyword search misses.

This implements Wohlin's snowballing guideline:

- **Backward snowballing** — read a seed's *reference list* to find the older,
  foundational work it builds on.
- **Forward snowballing** — find the papers that *cite* a seed to catch newer
  work that extends or responds to it.

A few rounds of this converge on a fairly complete picture of a sub-field.

## Arguments

- **Seed cite-keys** (optional, free positional list) — one or more master
  `cite_key`s already in the catalog, used as the starting set.
- `--for-paper <name>` — use every entry in `__BIB_ROOT__/papers/<name>/refs.bib`
  as the seed set. New finds are appended to that paper's bib too (same as
  `/bib-search --for-paper`).
- `--theme <theme>` — use every catalog entry in that theme as seeds.
- `--direction backward|forward|both` — which way to snowball. Default: `both`.
- `--rounds <N>` — how many iterations. After round 1, the newly-accepted
  papers become seeds for round 2, and so on. Default: `1`.
- `--year-from <YYYY>` — drop candidates older than this (useful to bias the
  forward pass toward recent work). Default: no bound.
- `--max-per-seed <N>` — cap candidates pulled per seed per direction, to keep a
  highly-cited seed from flooding the round. Default: 25.
- `--dry-run` — do the graph walk and ranking, report the candidates, but do
  **not** download PDFs or write to `refs.bib`.
- `--notebook "<title>"` — explicitly name the NotebookLM notebook to feed.
  Overrides the per-paper notebook resolved from `--for-paper`.
- `--no-notebook` — skip the NotebookLM upload even when `--for-paper` is set.

At least one of: seed cite-keys, `--for-paper`, or `--theme` must be given. If
none is given, ask the user which papers to snowball from.

## Setup

1. Read the master catalog: `__BIB_ROOT__/papers_inventory.csv`.
2. Read the master bib: `__BIB_ROOT__/refs.bib` (for cite-key collision checks).
3. Read the theme taxonomy: `__BIB_ROOT__/README.md`.

## Execution

### Stage 1 — Resolve the seed set

Build the list of seed entries from the arguments. For each seed, you need a
resolvable identifier — a DOI, an arXiv ID, or (failing those) a title — from
its catalog row. Report the seed set as a short table:

| seed cite_key | title | year | doi / arxiv id |
|---|---|---|---|

Drop any "seed" with no DOI, no arXiv ID, and no usable title, and say so —
those cannot be walked.

### Stage 2 — Backward pass (skip if `--direction forward`)

For each seed, collect the works it *references*:

- **OpenAlex** — fetch the seed work
  (`https://api.openalex.org/works/doi:<doi>` or `.../works/<openalex_id>`); the
  response has a `referenced_works` array of OpenAlex IDs. Batch-fetch their
  metadata via `https://api.openalex.org/works?filter=openalex_id:<id1>|<id2>|...`
  (chunk the filter so URLs stay short).
- **Semantic Scholar** — `https://api.semanticscholar.org/graph/v1/paper/DOI:<doi>/references?fields=title,abstract,authors,year,venue,externalIds,openAccessPdf&limit=<max-per-seed>`
  (or `ARXIV:<id>` as the paper id).

Use whichever resolves; merge both when both do.

### Stage 3 — Forward pass (skip if `--direction backward`)

For each seed, collect the works that *cite* it:

- **OpenAlex** — `https://api.openalex.org/works?filter=cites:<openalex_id>,publication_year:>=<year-from>&per-page=<max-per-seed>&sort=cited_by_count:desc`.
- **Semantic Scholar** — `https://api.semanticscholar.org/graph/v1/paper/DOI:<doi>/citations?fields=title,abstract,authors,year,venue,externalIds,openAccessPdf&limit=<max-per-seed>`.

Issue these queries **in parallel** (multiple WebFetch calls in one message).

### Stage 4 — Merge, deduplicate, score

- Normalize every candidate into `{doi, title, authors, year, venue, abstract,
  is_oa, oa_url, source}`, the same record shape `/bib-search` uses.
- Deduplicate across seeds and across OpenAlex/Semantic Scholar by DOI, then by
  normalized title.
- **Drop candidates already in `papers_inventory.csv`** (by DOI or normalized
  title) — but record that they were "re-discovered", it is a relevance signal.
- Drop candidates that are themselves seeds.
- Score each remaining candidate:

  ```
  snowball_score =
      2.0 * (number of distinct seeds that reached this candidate)
    + 1.0 if it appeared in BOTH a backward and a forward pass
    + log10(max(citations, 1))          # impact
    + 0.3 if year >= (current_year - 3) # recency
  ```

  The first term is the heart of snowballing: a paper reached from several
  seeds is far more likely to be on-topic than one reached from a single seed.

Rank by `snowball_score` descending.

### Stage 5 — Present and select

Show the ranked candidate table:

| rank | score | title | year | venue | citations | seeds reached | OA? |
|---|---|---|---|---|---|---|---|

If `--dry-run`, stop here.

Otherwise let the user choose what to ingest — by default propose the top
candidates whose `snowball_score` clears a sensible bar (e.g. reached by ≥ 2
seeds, or a single seed plus high citations). Ask before ingesting a large set.

### Stage 6 — Ingest accepted candidates

For each accepted candidate, follow the **same ingest path as `/bib-search`**:

1. Generate a master cite-key (`{firstauthor_last}{YYYY}{first3title}`,
   lowercase; collision → suffix `a`/`b`/`c`).
2. Classify the theme with
   `python3 __BIB_ROOT__/tools/classify_theme.py "<title + abstract>"`
   (or `--theme` if the user passed one).
3. **Open-access** → download the PDF to
   `__BIB_ROOT__/pdfs/_unclassified/<cite_key>.pdf`; **paywalled** → leave
   `pdf_path` blank, `status=paywalled_pending`, and list it for manual download.
4. Append a BibTeX entry to `__BIB_ROOT__/refs.bib` and a row to
   `__BIB_ROOT__/papers_inventory.csv` (`source` = `snowball`,
   `added_date` = today).
5. If `--for-paper <name>` is set, also append to
   `__BIB_ROOT__/papers/<name>/refs.bib` with a local cite-key and record the
   alias in `__BIB_ROOT__/cite_key_aliases.csv` — exactly as `/bib-search
   --for-paper` does.
6. **NotebookLM sync** — if `--for-paper <name>` is set and `--no-notebook` is
   not, mirror each downloaded PDF into that paper's NotebookLM notebook (**one
   notebook per paper**). Resolve the notebook once: read
   `__BIB_ROOT__/papers/<name>/.notebook.json` for its `id`; if that file is
   absent, fall back to `--notebook "<title>"`, or `notebooklm list` + confirm a
   match, or `notebooklm create "<name>"` — then write the chosen `id` and
   `title` back to `.notebook.json`. Upload via the `/notebooklm` skill
   (`notebooklm use <id>`, then `notebooklm source add <absolute pdf path>`),
   skipping any PDF whose title is already a source. This is the same mechanism
   `/bib-search` uses, so the notebook stays consistent across both skills.

Never rename existing cite-keys. Never bypass paywalls.

### Stage 7 — Iterate (`--rounds`)

If `--rounds > 1`, take the candidates accepted this round as the **new seed
set** and repeat Stages 2–6. Stop early when a round adds nothing. Keep a
running set of every cite-key already seen so the walk cannot loop.

### Stage 8 — Report

```markdown
## Snowball — round <r> of <rounds>
Seeds: <N>   Direction: <both/backward/forward>

## Candidates found
| rank | cite_key (new) | title | year | seeds reached | score | status |
|---|---|---|---|---|---|---|
...

## Re-discovered (already in catalog)
<cite_key list — these confirm the seed set is coherent>

## Ingested this run
- Open-access PDFs downloaded: <N>
- Paywalled (manual download needed): <N>
- Master refs.bib entries: <before> → <after>
- NotebookLM: <N PDFs added to notebook "<title>"> (or "skipped")

## Manual downloads needed
<per-item: title, authors, venue, DOI, save-to path>

## Next
- Run /bib-classify to file the new PDFs into theme folders.
- Re-run /bib-snowball on the new entries for another round, or raise --rounds.
```

## Hygiene

- Issue the citation-graph queries in parallel; if you use Bash `curl` for any
  fetch, write scratch to `__BIB_ROOT__/tmp/` and clean up.
- Don't create `.bak_*` snapshots of `refs.bib` / `papers_inventory.csv` —
  `--dry-run` already covers the rollback-safety case.

## Non-goals

- **Don't snowball without seeds the user trusts.** Snowballing amplifies the
  seed set's biases — a bad seed set produces a bad corpus. If the seeds look
  thin, suggest a `/bib-search` topic sweep first.
- **Don't rename cite-keys**, and don't bypass paywalls — same rules as
  `/bib-search`.
- **Don't auto-accept everything.** Citation graphs are noisy; surface the
  ranked list and let the user prune. The `snowball_score` is a sort key, not a
  verdict.

## Composes with

- `/bib-search "<topic>"` — build the initial seed set if you don't have one.
- `/bib-classify` — file the PDFs this skill drops into `pdfs/_unclassified/`.
- `/bib-upgrade` — refresh any preprints the snowball pulled in.

## Quick examples

```
/bib-snowball smith2023exampleentry jones2024anotherone
/bib-snowball --for-paper my-survey --direction backward
/bib-snowball --theme provenance --direction forward --year-from 2022
/bib-snowball --for-paper my-survey --rounds 2 --dry-run
```
