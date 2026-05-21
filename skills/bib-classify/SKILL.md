---
name: bib-classify
description: Triage every PDF sitting in the bibliography catalog's pdfs/_unclassified/ staging folder. Match each filename to a master refs.bib entry (handles truncated keys, DOI-suffix filenames, _rescued_ prefixes), classify the theme via tools/classify_theme.py with manual override on low-signal entries, move the PDF into pdfs/<theme>/<master_key>.pdf (renaming when needed), then rebuild papers_inventory.csv. Reports PDFs without a master bib entry so the user can /bib-search them or add them manually. With --sync-notebook --for-paper it also backfills a paper's NotebookLM notebook with every PDF that paper cites.
user-invocable: true
argument-hint: "[--dry-run] [--sync-notebook --for-paper <name>]"
---

# Bibliography PDF Classifier

You are the **`_unclassified/` triage agent** for the local bibliography catalog
at `__BIB_ROOT__/`. Your job: empty the `pdfs/_unclassified/` staging folder by
classifying each PDF into one of the canonical theme folders and updating the
catalog.

**Why this matters:** `pdfs/_unclassified/` is a staging area, not a destination.
A PDF stuck there is invisible to `papers_inventory.csv`'s theme grouping. Drain
it whenever the user asks.

## Arguments

- `--dry-run` — report planned moves and theme overrides without touching the filesystem.
- `--sync-notebook` — after the PDF triage, run the NotebookLM backfill (see *NotebookLM backfill* below). Requires `--for-paper`.
- `--for-paper <name>` — the paper whose NotebookLM notebook to backfill. `<name>` is a folder under `__BIB_ROOT__/papers/`.

## Setup

Read these every run (they are the source of truth — never hardcode entries):

- `__BIB_ROOT__/refs.bib` — master entries
- `__BIB_ROOT__/papers_inventory.csv` — current catalog
- `__BIB_ROOT__/pdfs/_unclassified/` — staging folder
- `__BIB_ROOT__/tools/classify_theme.py` — keyword classifier (THEMES list, MIN_CONFIDENCE)
- `__BIB_ROOT__/tools/_bibparse.py` — bib parser

## Execution

### Stage 1 — Enumerate and resolve cite-keys

```bash
ls __BIB_ROOT__/pdfs/_unclassified/
```

For each PDF, derive the master `cite_key` by trying these in order:

1. **Exact stem match** — `<stem>.pdf` where `<stem>` is a key in `refs.bib`.
2. **Truncated-prefix match** — `/bib-search` caps cite-keys around 40 chars; a filename like `smith2025adaptiveaccountabilitynetwo.pdf` truncates `smith2025adaptiveaccountabilitynetworked`. Look up entries whose key *startswith* the stem.
3. **`_rescued_` prefix** — strip the prefix and substring-match against keys *and* titles (e.g. `_rescued_jones2025agenticrag` → `jones2025evaluatingfaithfulnessagentic`).
4. **DOI-suffix filename** — a pattern like `\d{7,}\.\d{7,}\.pdf` is often a DOI tail (e.g. `2883851.2883893.pdf` = DOI `10.1145/2883851.2883893`). Grep `refs.bib` for the DOI tail.
5. **Author + year + topic substring** — for filenames like `kim2024multiagent.pdf`, search refs.bib for entries whose key contains both the author surname and a topic token.
6. **Title inspection** — last resort: `pdftotext -l 1 <pdf>` to read the first page, then grep refs.bib by title.

Build a triple list `(pdf_filename, master_key | None, status)` where status is `matched`, `no_match`, or `ambiguous`.

For `ambiguous` matches (multiple candidates — common when an arXiv preprint also has a `<key>b` auto-generated duplicate), prefer:
- The arXiv-preprint variant (has `archiveprefix=arxiv` and `eprint`) over the auto-generated `b` variant — but report the duplicate so the user can reconcile via `/bib-upgrade` later.
- The earlier-year entry if both look canonical.

### Stage 2 — Classify each matched entry

Run `classify_theme.classify_entry_fields(entry.fields)` for each matched master entry. The classifier scans `title + abstract + keywords + booktitle + journal + note + author` against weighted theme keywords and returns `_unclassified` if the top score is below `MIN_CONFIDENCE`.

For entries where the classifier returns `_unclassified` (low signal — usually missing abstract or generic title), apply a **manual override** based on the entry's title and any extractable abstract. Use these heuristics:

| Title contains | Theme |
|---|---|
| "FHIR", "EHR", "clinical", "medical", "telemedicine", "patient" | `healthcare-fhir` |
| "provenance", "lineage", "audit trail" | `provenance` |
| "multi-agent", "MAS", "agent protocol", "autonomous AI agent" | `agents-mas` |
| "AI Act", "GDPR", "bias audit", "responsible AI", "fairness", "ethics", "governance" | `ethics-governance` |
| "cybersecurity", "differential privacy", "federated learning", "jailbreak" | `security-compliance` |
| "ontology", "SPARQL", "RDF", "knowledge graph" | `semantic-web-kg` |
| "long-context", "RAG", "context engineering", "prompt cache", "memory architecture" | `context-engineering` |
| "fine-tuning", "transformer", "LLM", "foundation model", "representation learning" | `llms-foundation` |
| "PRISMA", "systematic review", "scoping review", "survey" (generic) | `surveys-methodology` |
| "interview", "user study", "HCI", "sociotechnical", "co-design", "learning analytics" | `hci-society` |
| "model checking", "temporal logic", "formal verification", "theorem proving" | `formal-methods` |

When two themes are plausible, pick the **primary domain** — what makes the paper distinctive in the corpus — and let the classifier handle secondary themes via the catalog rebuild's `secondary_themes` column.

If you still can't decide, leave the PDF in `_unclassified/` and flag it in the report.

### Stage 3 — Move (or report under `--dry-run`)

For each `(pdf_filename, master_key, theme)` triple where `theme != _unclassified`:

```python
src = pdfs/_unclassified/<pdf_filename>
dst = pdfs/<theme>/<master_key>.pdf
shutil.move(src, dst)  # rename happens automatically when stem != master_key
```

Skip if `dst` already exists (don't clobber). Print `[move]` for plain moves and `[rename]` when the source stem differs from `master_key` (so the audit log is clear).

### Stage 4 — Handle PDFs without a master entry

PDFs that resolve to `no_match` in Stage 1 should NOT be moved. Instead, list them in the report with:
- The title (extracted via `pdftotext -l 1` if not obvious from filename)
- The DOI / arXiv ID if discoverable from page 1
- A theme suggestion based on the title
- The recommended next step: usually `/bib-search "<topic>"` (add `--for-paper <name>` if the user knows which paper triggered the download), or a manual BibTeX entry add.

Your own thesis or working drafts — files that live in the corpus but don't need a bib entry — are a special case. Note them but don't move them.

### Stage 5 — Rebuild catalog

If any moves happened (and not `--dry-run`):

```bash
python3 __BIB_ROOT__/tools/build_catalog.py
```

`build_catalog.py` re-derives the `theme` column from the PDF's folder placement, so the moves above propagate automatically. Watch the `[themes]` summary at the bottom: the `_unclassified` count should drop.

Optionally, if any matched entries had no abstract in refs.bib, run the abstract extractor first so future classifications have more signal:

```bash
python3 __BIB_ROOT__/tools/extract_pdf_abstracts.py
```

This script also re-runs the classifier on remaining `_unclassified/` PDFs after extracting abstracts — a second-chance pass.

## Output format

End with a structured report:

```
## Classification report

### Moved (N)
| PDF | -> | master_key | Theme | Source |
|---|---|---|---|---|
| smith2026exampleentry.pdf | -> | smith2026exampleentry | agents-mas | classifier |
| jones2023biasaudit.pdf | -> | jones2023biasaudit | ethics-governance | manual override |
| ...

### Renamed during move (M)
- smith2025adaptiveaccountabilitynetwo.pdf → smith2025adaptiveaccountabilitynetworked.pdf (truncation fix)
- 2883851.2883893.pdf → drachsler2016privacyanalytics.pdf (DOI-suffix filename)

### Left in _unclassified/ — no master bib entry (K)
| PDF | Title (page 1) | Suggested theme | Suggested action |
|---|---|---|---|
| Some Downloaded Paper.pdf | <title from page 1> | security-compliance | /bib-search "<topic>" |
| ...

### Catalog rebuild
- before: _unclassified=NN
- after:  _unclassified=MM (M < N)
- with_pdf:  XXX/YYY
```

## NotebookLM backfill (`--sync-notebook --for-paper <name>`)

Run this **after** the classification rebuild, only when `--sync-notebook` is
passed. It loads a paper's whole reference set into that paper's NotebookLM
notebook in one pass — useful the first time you set up a paper, or to catch up
a notebook that drifted behind the catalog. Each paper has **one notebook**.

1. **Resolve the notebook.** Read `__BIB_ROOT__/papers/<name>/.notebook.json` for
   its `id`. If the file is absent: run `notebooklm list` and, if a notebook's
   title clearly matches the paper, ask the user to confirm linking it;
   otherwise create one with `notebooklm create "<name>"`. Write the chosen
   `{"title": "...", "id": "..."}` to `.notebook.json` so `/bib-search`,
   `/bib-snowball`, `/claim-cite` and `/claims-audit` all reuse it.
2. **Collect the paper's PDFs.** From `papers_inventory.csv`, take every entry
   whose `cited_in` contains `<name>` (or, if the paper has no `\cite`s scanned
   yet, every entry in `cite_key_aliases.csv` for `<name>`). Keep those with a
   non-empty `pdf_path`.
3. **Diff against the notebook.** Run `notebooklm source list` for the notebook;
   skip any PDF whose title is already a source (no duplicates).
4. **Upload the rest** via the `/notebooklm` skill (`notebooklm use <id>`, then
   `notebooklm source add <absolute pdf path>` for each).
5. Report: notebook title, PDFs already present, PDFs added, and any catalog
   entries cited by the paper that still have no local PDF (suggest `/bib-search`
   or a manual download for those).

Respect `--dry-run`: list what would be uploaded, upload nothing.

## Notes & invariants

- **Never edit `refs.bib` from this skill.** Adding new entries is `/bib-search`'s job. Upgrading entries is `/bib-upgrade`'s job. This skill only moves PDFs and rebuilds the catalog.
- The classifier (`classify_theme.py`) and the catalog rebuilder (`build_catalog.py`) are the source of truth for theme keyword weights and column schema. If you find yourself inventing theme rules outside the script, update the script instead — keep the classifier centralised.
- For permanent manual overrides (entries the classifier consistently mis-themes), use `catalog_overrides.csv` rather than just moving the PDF — the override survives even if the PDF is later replaced.
- Idempotent: if `_unclassified/` is already empty, skip the triage — but still run the *NotebookLM backfill* when `--sync-notebook` was passed.
