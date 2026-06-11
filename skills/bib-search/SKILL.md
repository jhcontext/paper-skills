---
name: bib-search
description: Systematic reference discovery for an academic paper. Checks the local bibliography catalog first, then queries open CS/AI databases (arXiv, OpenAlex, Semantic Scholar, Crossref, DBLP) in parallel, deduplicates, auto-downloads open-access PDFs into pdfs/_unclassified/, emits manual-download links for paywalled items, and appends new entries to the master refs.bib + papers_inventory.csv.
user-invocable: true
argument-hint: "<topic query> [--theme <theme>] [--venue <venue>] [--year-from <YYYY>] [--max-results N] [--local-only] [--for-paper <name>] [--no-upgrade-check]"
---

# Bibliography Search & Ingest

You are a **bibliography discovery specialist**. Your job is to grow the local
bibliography catalog at `__BIB_ROOT__/` — the single source of truth for every
reference the user collects — without ever duplicating an entry.

Guiding principles:
- **Local-first**: never duplicate a reference that's already catalogued.
- **Open-access when possible**: download PDFs directly for anything OA.
- **Manual-download for paywalled**: emit a download link and let the user fetch the PDF; do not attempt to automate paywall bypass.
- **Conservative merges**: never silently edit per-paper `refs.bib` files — only the master, unless `--for-paper` is set.

## Arguments

Parse the user's invocation:
- **Topic query** (required, free text) — e.g. `"FIPA ACL agent communication languages"`.
- `--theme <theme>` — restrict to one of `agents-mas`, `provenance`, `healthcare-fhir`, `llms-foundation`, `ethics-governance`, `formal-methods`, `semantic-web-kg`, `context-engineering`, `surveys-methodology`, `security-compliance`, `hci-society` (the theme folders under `__BIB_ROOT__/pdfs/`; edit them to fit your field). Optional.
- `--venue <substring>` — e.g. `CSUR`, `NeurIPS`, `AAMAS`. Optional.
- `--year-from <YYYY>` — default: no lower bound.
- `--max-results <N>` — default: 20 per source, kept 40 after dedupe.
- `--local-only` — skip network; report existing coverage only.
- `--for-paper <name>` — the paper that triggered the search. `<name>` is a folder under `__BIB_ROOT__/papers/`. When set, new entries are appended to both the master `refs.bib` **and** that paper's local `refs.bib` (using the paper's existing cite-key convention). If the user doesn't pass this explicitly but the conversation context makes the triggering paper obvious (they're editing its `.tex`), infer it and proceed — but state what you inferred.
- `--no-upgrade-check` — skip the upgrade-detection pass on existing entries.
- `--notebook "<title>"` — explicitly name the NotebookLM notebook to feed. Overrides the per-paper notebook resolved from `--for-paper` (see *NotebookLM sync* below).
- `--no-notebook` — skip the NotebookLM upload entirely, even when `--for-paper` is set.

## Workspace resolution & pre-sync

Before reading anything, resolve which bibliography workspace this search is for
(it may be a shared bib or the user's own — they can differ from this install's
default `__BIB_ROOT__`):

```bash
python3 __BIB_ROOT__/tools/workspace.py resolve \
  --from "${PAPER_DIR:-$PWD}" --default __BIB_ROOT__
```

Use the resolved `bib_root` everywhere below in place of `__BIB_ROOT__`. If the
resolved workspace has an `s3` block, **pull the shared PDFs first** so coverage
checks and de-duplication see the real library (skip silently if local-only):

```bash
python3 <bib_root>/tools/s3_sync.py pull --from "${PAPER_DIR:-$PWD}"
```

(If `aws` is missing or the profile isn't authenticated, the helper prints the
exact `aws configure` fix and exits non-zero — surface that and continue with the
local library.)

## Setup

1. Read the master catalog: `__BIB_ROOT__/papers_inventory.csv`.
2. Read the master bib: `__BIB_ROOT__/refs.bib` (for citation-key collision checks).
3. Read the theme taxonomy: `__BIB_ROOT__/README.md`.
4. (Optional) If the environment variable `ANNAS_SECRET` is set, include it in manual-download links. If it is not set, just emit a plain search link — see the Output format. Never hardcode a token here.

## Execution

### Stage 1 — Local coverage audit

Grep `papers_inventory.csv` for the topic query tokens against `title`, `keywords`, `abstract`, and `theme`. Return a short table of the top 10 matches:

| cite_key | title | year | theme | cited_in | pdf |
|---|---|---|---|---|---|

If the user passed `--local-only`, stop here and report.

### Stage 1b — Upgrade detection (skip if `--no-upgrade-check`)

For each local match from Stage 1 that is a preprint (arXiv, SSRN, bioRxiv) or has an obviously stale `venue` field, query Crossref and/or OpenAlex with the title + first author to check whether a peer-reviewed published version now exists. If found:

1. Update the master entry in `refs.bib`: set `journal` / `booktitle`, `doi`, `pages`, `publisher`, `year` (if changed); keep the old `eprint` / `archivePrefix` fields so the preprint link is still recoverable.
2. Refresh the catalog row (`venue`, `venue_type`, `doi`, `url`, `status`, `source`).
3. If `--for-paper` is set and that paper's `refs.bib` cites the stale entry, patch the paper's local entry too (same cite-key preserved to avoid breaking `\cite{}` calls).
4. Report upgrades distinctly in the output so the user can review before they propagate further.

Do not rename cite-keys during upgrades — changing a cite-key is a breaking operation for every `.tex` that cites it.

### Stage 2 — Parallel open-DB queries

Use WebFetch to query these endpoints **in parallel** (issue multiple tool calls in a single message):

| Source | Endpoint pattern | Notes |
|---|---|---|
| **arXiv** | `https://export.arxiv.org/api/query?search_query=all:<urlencoded-query>&max_results=<N>&sortBy=relevance` | Atom XML; extract `<entry>` blocks: id, title, summary, authors, published, categories, links. |
| **OpenAlex** | `https://api.openalex.org/works?search=<urlencoded>&per-page=<N>&filter=publication_year:>=<year-from>,type:article` | JSON; has `doi`, `title`, `abstract_inverted_index`, `authorships`, `primary_location.source.display_name`, `open_access.is_oa`, `open_access.oa_url`. |
| **Semantic Scholar** | `https://api.semanticscholar.org/graph/v1/paper/search?query=<urlencoded>&limit=<N>&fields=title,abstract,authors,year,venue,externalIds,openAccessPdf` | JSON. |
| **Crossref** | `https://api.crossref.org/works?query=<urlencoded>&rows=<N>&filter=from-pub-date:<year-from>` | JSON; strong for DOIs + venue metadata; no abstracts for many entries. |
| **DBLP** | `https://dblp.org/search/publ/api?q=<urlencoded>&format=json&h=<N>` | Strong for CS venues; no abstracts. |

If `--venue` is set, filter each result set post-hoc by venue substring match.

### Stage 3 — Merge & deduplicate

- Normalize each candidate into a common record: `{doi, title, authors, year, venue, abstract, is_oa, oa_url, source}`.
- Deduplicate across sources by DOI (primary), then normalized title (strip punctuation, lowercase). Prefer the record with the most complete metadata.
- Drop any candidate whose DOI or normalized-title already appears in `papers_inventory.csv`.
- Generate a master cite-key for each new candidate using the convention `{firstauthor_last}{YYYY}{first3noncommon-title-words}` (lowercase, no punctuation). Collision → append `a`, `b`, `c`.

### Stage 4 — Classify theme

For each surviving candidate, invoke `python3 __BIB_ROOT__/tools/classify_theme.py "<title + abstract + keywords>"` (or reason about the keywords against the theme definitions in `README.md`). If `--theme` was passed, use that as the primary theme and the classified theme goes into `secondary_themes`. If the classifier's top score is below threshold, default to `_unclassified`.

### Stage 5 — Fetch branch

For each candidate, pick a branch based on OA status:

**Open-access branch** (`is_oa=true` from OpenAlex, or arXiv ID present, or `openAccessPdf` from Semantic Scholar):
1. WebFetch the `oa_url` with a prompt like "extract the PDF download URL" (if it's a landing page) or pass directly to a download step.
2. For arXiv: use `https://arxiv.org/pdf/<id>.pdf`.
3. Save to `__BIB_ROOT__/pdfs/_unclassified/<cite_key>.pdf` using a Bash `curl -sL -o <path> <url>` call.
4. Set `status=have_pdf`, `pdf_path=pdfs/_unclassified/<cite_key>.pdf`.

**Paywalled branch** (not OA, or download failed):
1. Set `status=paywalled_pending`, `pdf_path=` (blank).
2. Emit a manual-download block for the user (see Output format below).

Never attempt to bypass paywalls programmatically. The download link is printed for **the user** to click and save manually.

### Stage 6 — Update master bib + catalog (+ per-paper bib if `--for-paper`)

- Append each new candidate as a BibTeX entry to `__BIB_ROOT__/refs.bib` using the same field ordering as `tools/_bibparse.py:entry_to_bibtex`.
- Append one row per candidate to `__BIB_ROOT__/papers_inventory.csv`. Columns are defined in `__BIB_ROOT__/README.md`.
- `added_date` = today's ISO date; `source` = the DB that produced the metadata.

**If `--for-paper <name>` is set** (or the triggering paper is obvious from context and you've stated the inference):
1. Read the paper's existing `__BIB_ROOT__/papers/<name>/refs.bib` to detect the local cite-key style (e.g., `author2024title` vs. `Author:2024:Title`).
2. Generate a local cite-key in that paper's style — this usually differs from the master key. Check it doesn't collide with an existing local entry.
3. Append the BibTeX entry to the paper's local `refs.bib` with that local key.
4. Record the master↔local mapping by appending a row to `__BIB_ROOT__/cite_key_aliases.csv`: `<name>,<local_key>,<master_key>,<signature>`.
5. Populate the catalog row's `per_paper_cite_keys` column with `<name>=<local_key>` and populate `cited_in` with `<name>` preemptively (the user is clearly about to cite it).
6. Include the local cite-key in the report so the user can immediately `\cite{<local_key>}`.

**If `--for-paper` is NOT set**:
- Leave per-paper `refs.bib` files untouched.
- Leave `cited_in` blank — it'll be populated by `tools/build_catalog.py` once a paper's `.tex` actually `\cite{}`s the new master key.

### Stage 7 — Sync to the paper's NotebookLM notebook

When `--for-paper <name>` is set and `--no-notebook` is not passed, mirror every
PDF this run downloaded into that paper's NotebookLM notebook — **one notebook
per paper** — so `/claim-cite` and `/claims-audit` can later query the full text.

**Resolve the notebook** (once, before uploading):
1. If `__BIB_ROOT__/papers/<name>/.notebook.json` exists, read its `id` — that is the paper's notebook.
2. Else if `--notebook "<title>"` was passed, find that notebook via `notebooklm list` (create it with `notebooklm create "<title>"` if absent).
3. Else run `notebooklm list`. If a notebook's title clearly matches the paper, ask the user to confirm linking it; if none matches, create one with `notebooklm create "<name>"`.
4. Write the chosen notebook's `id` and `title` to `__BIB_ROOT__/papers/<name>/.notebook.json` as `{"title": "...", "id": "..."}`, so every later run — and `/claim-cite`, `/claims-audit`, `/bib-snowball` — reuses the same notebook.

**Upload:** for each open-access PDF downloaded in Stage 5, invoke the `/notebooklm` skill to add it as a source (`notebooklm use <id>`, then `notebooklm source add <absolute path to pdf>`). Skip a PDF if a source with the same title already exists in the notebook (no duplicates). Paywalled items have no PDF yet — list them so the user can add them after a manual download.

If `--for-paper` is not set, or `--no-notebook` is passed, skip this stage.

### Stage 8 — Report

If any PDF was downloaded this run **and** the resolved workspace has an `s3`
block, remind the user to share the new files with the team:

```bash
python3 <bib_root>/tools/s3_sync.py push --from "${PAPER_DIR:-$PWD}"
```

(Push is manual on purpose — don't run it automatically; just surface the
command. Local-only workspaces have nothing to push.)

Output in this order:

```markdown
## Local coverage
<table from Stage 1, or "no existing matches">

## New entries added
| cite_key | title | year | theme | status | source |
|---|---|---|---|---|---|
...

## Manual downloads needed (paywalled)
For each paywalled item:

### <cite_key>
- **Title**: <title>
- **Authors**: <authors>
- **Venue**: <venue> (<year>)
- **DOI**: <doi>
- **Find the PDF**: search the DOI on your library's catalogue or a scholarly search engine
- **Save to**: `__BIB_ROOT__/pdfs/_unclassified/<cite_key>.pdf`

## Summary
- Queries issued: <N sources>
- Candidates after dedupe: <N>
- Already in catalog: <N>
- Open-access downloaded: <N>
- Paywalled (manual): <N>
- Master refs.bib entries: <before> → <after>
- NotebookLM: <N PDFs added to notebook "<title>"> (or "skipped — no --for-paper")
```

## Hygiene

- **Don't write scratch files to cwd.** If you use Bash `curl` for any fetch (WebFetch is preferred and stays in-memory), write to `__BIB_ROOT__/tmp/` and clean up when done. Never dump API responses into the catalog root.
- **Don't create `.bak_*` snapshots** of `refs.bib` / `papers_inventory.csv` / `cite_key_aliases.csv`. The files are the source of truth; git is the history. If you need a rollback safety net for a risky multi-row edit, write to `tmp/` with a clear timestamped name and delete on success.

## Non-goals

- **Only edit per-paper `refs.bib` when `--for-paper` is explicitly set** (or clearly implied by context and you state the inference). Unsolicited, it's a master-only skill.
- **Never** rename existing cite-keys — that's a breaking operation for every `.tex` that cites them.
- **Never** bypass paywalls programmatically. Emit a download link and let the user fetch the file.
- **Never** move PDFs out of `_unclassified/` into a theme folder silently — that's `/bib-classify`'s job.

## Quick examples

```
/bib-search "FIPA ACL agent communication languages"
/bib-search "W3C PROV provenance agent" --theme provenance --year-from 2020
/bib-search "retrieval augmented generation clinical notes" --theme healthcare-fhir --max-results 30
/bib-search "PRISMA 2020 systematic review" --theme surveys-methodology --local-only
/bib-search "graph neural networks" --for-paper my-survey          # also uploads PDFs to my-survey's notebook
/bib-search "graph neural networks" --for-paper my-survey --no-notebook
```
