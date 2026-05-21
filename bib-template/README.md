# Bibliography catalog

This folder is your **local bibliography workspace**. It is the single source of
truth for every paper you collect — managed by the `paper-skills` Claude Code
skills (`/bib-search`, `/bib-snowball`, `/bib-classify`, `/bib-upgrade`,
`/claim-cite`, `/claims-audit`).

It was created by `/install-paper-skills`. You can rename or move the folder
freely — the tools locate themselves relative to `tools/`, so nothing breaks.

## Layout

```
refs.bib                 master BibTeX — every reference you have collected
papers_inventory.csv     catalog: one row per master entry (schema below)
cite_key_aliases.csv     per-paper local cite_key -> master cite_key
catalog_overrides.csv    manual theme/notes overrides, re-applied on every rebuild
pdfs/<theme>/            PDFs filed by primary theme
pdfs/_unclassified/      staging area for freshly downloaded PDFs
papers/<name>/           your LaTeX paper projects (each with its own refs.bib)
tools/                   maintenance scripts (plain Python, stdlib only)
tmp/                     scratch: API dumps, claim extracts (safe to wipe)
```

`refs.bib` + `papers_inventory.csv` are the **single source of truth**. Edit them
in place — don't keep `.bak` side-copies; use git for history.

## Workflow

- **Find and import a new reference** — `/bib-search "<topic>"`. It checks this
  catalog first, then queries arXiv / OpenAlex / Semantic Scholar / Crossref /
  DBLP, downloads open-access PDFs into `pdfs/_unclassified/`, and appends new
  entries to `refs.bib` + `papers_inventory.csv`.
- **Grow the set by citation snowballing** — `/bib-snowball` starts from papers
  you already trust and follows their reference lists (backward) and the papers
  that cite them (forward) to find related work topic search misses.
- **File the downloaded PDFs** — `/bib-classify` sorts everything in
  `pdfs/_unclassified/` into the right `pdfs/<theme>/` folder and rebuilds the
  catalog.
- **Before a deadline** — `/bib-upgrade` sweeps the catalog for preprint →
  peer-reviewed upgrades (arXiv → journal/conference). Cite-keys are preserved
  so `\cite{}` calls don't break.
- **Find the best citation for a sentence** — `/claim-cite "<claim>"`.
- **Audit a draft's citations** — `/claims-audit --venue <paper-folder-name>`.

To start a new paper, copy the `paper-template/` from the `paper-skills` repo
into `papers/<name>/`. `<name>` is then the venue label used by
`/bib-search --for-paper <name>` and `/claims-audit --venue <name>`.

Each paper gets **one NotebookLM notebook**. The first `/bib-search` or
`/bib-snowball` run with `--for-paper <name>` creates or links it and writes the
link to `papers/<name>/.notebook.json` (`{"title": ..., "id": ...}`); every PDF
the skills download for that paper is then added to the notebook as a source,
and `/claim-cite` and `/claims-audit` query it automatically. To load an
existing paper's references into its notebook in one pass, run
`/bib-classify --sync-notebook --for-paper <name>`.

## Catalog schema (`papers_inventory.csv`)

| Column | Meaning |
|---|---|
| `cite_key` | Master key: `firstauthorYYYYshorttitle`, lowercase |
| `title` | Full title |
| `authors` | `Last, First; Last, First` |
| `year` | 4-digit |
| `venue_type` | conference / journal / book / preprint / report / thesis |
| `venue` | e.g. `ACM Computing Surveys`, `arXiv` |
| `theme` | Primary theme folder name |
| `secondary_themes` | `;`-separated secondary themes |
| `cited_in` | `;`-separated names of `papers/` folders that `\cite` this entry |
| `per_paper_cite_keys` | `;`-separated `venue=localkey` pairs |
| `notebooklm` | `;`-separated NotebookLM notebook names (optional) |
| `pdf_path` | Relative path like `pdfs/provenance/<key>.pdf`, or blank |
| `doi` | DOI if known |
| `url` | Canonical URL |
| `citations` | OpenAlex citation count |
| `abstract` | Full abstract |
| `keywords` | `;`-separated |
| `status` | `have_pdf` / `oa_pending` / `paywalled_pending` / `no_pdf_needed` |
| `source` | arxiv / openalex / semantic_scholar / crossref / acm_dl / ieee / springer / manual |
| `added_date` | ISO date |
| `notes` | Free text |

## Themes

The starting taxonomy is aimed at AI / CS research. Edit `tools/classify_theme.py`
(the `THEMES` list) and the `pdfs/` sub-folders to match your own field.

| Theme | Scope |
|---|---|
| `agents-mas` | Agent protocols, multi-agent systems, agent communication |
| `provenance` | Provenance models, lineage, audit trails |
| `healthcare-fhir` | FHIR, HL7, EHR, clinical AI, telemedicine |
| `llms-foundation` | LLM architectures, transformers, scaling, benchmarks |
| `ethics-governance` | AI ethics, regulation, responsible AI |
| `formal-methods` | Verification, temporal logic, model checking |
| `semantic-web-kg` | SPARQL, OWL, ontologies, knowledge graphs |
| `context-engineering` | Context windows, memory, retrieval augmentation |
| `surveys-methodology` | PRISMA, systematic-review methodology |
| `security-compliance` | Privacy, data protection, legal/regulatory |
| `hci-society` | Human-AI interaction, sociotechnical, labour impact |
| `_unclassified` | Staging for newly fetched PDFs pre-theme assignment |

### catalog_overrides.csv

`tools/build_catalog.py` rebuilds `papers_inventory.csv` from scratch every run.
To make a manual theme choice survive rebuilds, add a row:

```
cite_key,theme,secondary_themes,notes
smith2023exampleentry,ethics-governance,,Pinned — classifier mis-themes this one
```

Blank cells mean "don't override that column".

## Maintenance commands

```bash
# Rebuild the catalog from refs.bib + the pdfs/ tree + papers/*/*.tex cite scans
python3 tools/build_catalog.py

# Re-scan papers/ for \cite{} and report the cited_in map
python3 tools/sync_cited_in.py

# Suggest a theme for some text or an existing entry
python3 tools/classify_theme.py "<title + abstract>"
python3 tools/classify_theme.py --bibkey <master_key>

# Enrich missing metadata (abstracts, citation counts, DOIs) via OpenAlex
python3 tools/enrich_metadata.py

# Pull abstracts straight out of local PDFs (needs the `pdftotext` command)
python3 tools/extract_pdf_abstracts.py

# Extract claim-citation pairs from a paper (input for /claims-audit)
python3 tools/extract_claims.py <paper-folder-name>
```
