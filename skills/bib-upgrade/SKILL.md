---
name: bib-upgrade
description: Standalone sweep across the local bibliography catalog that finds preprint-to-published upgrades (arXiv → journal/conference version). Scans every catalog entry flagged as a preprint, queries Crossref + OpenAlex for a peer-reviewed canonical version, and patches the master refs.bib (plus any paper refs.bib that cites the stale entry) in place — cite-keys preserved so \cite{} calls don't break. Run before every paper deadline.
user-invocable: true
argument-hint: "[--for-paper <name>] [--dry-run] [--since <ISO-date>] [--min-age-days N]"
---

# Bibliography Upgrade Sweep

You are a **bibliography freshness auditor**. A focused companion to
`/bib-search`: you don't add new references, you *upgrade existing ones* when a
better canonical version now exists.

**Why this matters:** arXiv preprints often get published 6–18 months later.
Keeping a stale preprint citation when the peer-reviewed version exists is a
common reviewer objection. Run this skill before every submission deadline.

## Arguments

- `--for-paper <name>` — scope to entries cited by one paper. `<name>` is a folder under `__BIB_ROOT__/papers/`. When set, any upgrade is also propagated to that paper's local `refs.bib`.
- `--dry-run` — report what would change, don't write. Default: apply upgrades.
- `--since <ISO-date>` — only check entries added/updated since this date (for incremental runs).
- `--min-age-days <N>` — only check entries older than N days (new preprints are rarely published yet; default: 180).

## Setup

Read:
- `__BIB_ROOT__/papers_inventory.csv`
- `__BIB_ROOT__/refs.bib`
- `__BIB_ROOT__/cite_key_aliases.csv` (to find which paper bibs cite each master entry)

If the environment variable `CROSSREF_MAILTO` is set, append `&mailto=$CROSSREF_MAILTO` to the Crossref / OpenAlex URLs below — it puts you in the faster "polite pool". It works without it too.

## Execution

### Stage 1 — Build the candidate list

Filter `papers_inventory.csv` rows where **any** of these hold:
- `venue_type == preprint`
- `source == arxiv`
- `doi` is missing AND `url` contains `arxiv.org` / `ssrn.com` / `biorxiv.org` / `medrxiv.org`
- `venue` is empty while `year` is set (orphaned/standalone)

Apply `--for-paper` filter if set: only rows whose `cited_in` contains the name.
Apply `--min-age-days`: skip rows where `added_date` is within the last N days.

Report the candidate count before proceeding.

### Stage 2 — Canonical lookup per candidate

For each candidate, query in order until one resolves:

1. **arXiv API for versions** — `https://export.arxiv.org/api/query?id_list=<arxiv_id>` returns the latest `published` and `updated` dates, and often a `doi` field pointing to the published version.
2. **Crossref by title + first author** — `https://api.crossref.org/works?query.bibliographic=<title>&query.author=<first_last>&rows=5`. Only accept results where:
   - Normalized title overlap ≥ 80%, AND
   - First author last name matches, AND
   - Year ≥ candidate's year (the published version is never earlier than the preprint).
3. **OpenAlex** as a tie-breaker — `https://api.openalex.org/works?search=<title>&filter=authorships.author.display_name.search:<author>`. Also returns `primary_location.source.type` (journal/conference/repository) — reject if still `repository`.

Discard any match whose venue is still a preprint server (we're only upgrading *away* from preprints).

### Stage 3 — Classify each match

For each successful lookup, determine the upgrade type:

- **Full upgrade** — we went from `arXiv preprint` → peer-reviewed venue. Apply full metadata swap.
- **Version refresh** — same arXiv ID but a newer `vN` with meaningful changes (rare; judge by `updated` date delta ≥ 60 days). Note only, usually don't apply.
- **No upgrade** — canonical version is still a preprint, or no match. Leave entry alone.

### Stage 4 — Apply upgrades (skip if `--dry-run`)

For each **Full upgrade**:

1. **Preserve the cite-key.** This is load-bearing — renaming keys breaks every `.tex` that cites them.
2. **Update master `refs.bib`** entry in place:
   - Set `journal` or `booktitle` from the new venue.
   - Set `volume`, `number`, `pages`, `publisher` if Crossref/OpenAlex provided them.
   - Set `doi` to the published DOI.
   - Update `year` if the published year differs.
   - **Keep** `eprint`, `archivePrefix`, `url` (the arXiv link remains useful for open access); add `note = {Preprint available at arXiv}` if the original `note` is empty.
3. **Update the catalog row** — `venue_type`, `venue`, `doi`, `url`, `source`, `status` (preprint → journal/conference), `citations` (refetch from OpenAlex).
4. **Propagate to paper bibs.** For each `(name, local_key)` in `cite_key_aliases.csv` where `master_key` matches, update `__BIB_ROOT__/papers/<name>/refs.bib` with the same field changes — using the paper's existing `local_key` (never rename it).
5. **Skip paper bibs** whose name `!= --for-paper` if `--for-paper` was specified (the user doesn't want changes to papers other than the one they're submitting).
6. **Re-download PDF if the published version is open-access** and the current PDF is the arXiv preprint. Save to the same theme folder under `<master_key>.pdf`; keep a `<master_key>.arxiv.pdf` copy of the original.

### Stage 5 — Report

```markdown
## Upgrade sweep — <date>
Scope: <all / --for-paper <name>>
Candidates: <N>  Looked up: <N>  Upgrades applied: <N>  Dry-run: <yes/no>

## Upgrades applied
| cite_key | old venue (year) | new venue (year) | doi | cited_in | PDF refreshed |
|---|---|---|---|---|---|
...

## No-op (still preprint)
<cite_key list>

## Manual review needed (ambiguous match)
<cite_key>: <why ambiguous — e.g., "title match 72%, first author differs">

## Next steps
- Rebuild the catalog to refresh all derived fields:
  ```bash
  python3 __BIB_ROOT__/tools/build_catalog.py
  ```
- Re-run your LaTeX build on any paper whose bib was patched.
```

## Hygiene

- **Don't write scratch files to cwd.** If you use Bash `curl` or any intermediate artifact, write to `__BIB_ROOT__/tmp/` and clean up when done.
- **Don't create `.bak_*` snapshots** of `refs.bib` / `papers_inventory.csv`. Edits are in-place; the files are the source of truth. `--dry-run` already covers the rollback-safety use case.

## Non-goals

- **Don't add new references.** If Crossref returns a totally different work, reject — that's a `/bib-search` job.
- **Don't rename cite-keys.** Ever. Even if the new venue suggests a prettier key.
- **Don't remove the arXiv metadata.** `eprint` and `archivePrefix` stay so the preprint link remains reachable.
- **Don't modify papers outside `--for-paper`** when that flag is set — the user chose a scope; respect it.

## Quick examples

```
/bib-upgrade --dry-run                                  # audit everything, change nothing
/bib-upgrade --for-paper my-survey                      # pre-submission sweep for one paper
/bib-upgrade --for-paper my-survey --min-age-days 90    # tighter age gate for a large ref corpus
/bib-upgrade --since 2026-01-01                         # incremental since a given date
```
