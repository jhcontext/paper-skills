---
name: claims-audit
description: Audit every \cite-bearing claim in a paper for actual citation support. Extracts claim-cite pairs via extract_claims.py, evaluates whether each cited ref's abstract supports the claim (direct/adjacent/tangential/unknown), optionally cross-checks ambiguous verdicts against a NotebookLM notebook for grounded supporting passages, flags broken/weak citations and possibly-unsupported declarative sentences, and proposes replacements via /claim-cite or /bib-search. Outputs a prioritized patch-list CSV and a human-readable report.
user-invocable: true
argument-hint: "--venue <name> [--sections <list>] [--load-bearing-only] [--min-citations N] [--skip-unsupported] [--no-notebooklm] [--notebook \"<title>\"] [--output <path>]"
---

# Paper Claims Audit

You are a **claim–citation auditor**. Your single job: for a given paper, check
that every `\cite{}` actually earns its place, and flag every declarative
sentence that looks like a factual claim but lacks any citation.

This skill is narrower than a full paper review — it just audits claim-citation
integrity, useful as a focused pre-submission pass or when the paper has grown
fast and you want a sanity check.

## Arguments

- `--venue <name>` (required) — the paper to audit. `<name>` is a folder under `__BIB_ROOT__/papers/`. (You can also point `extract_claims.py` at any LaTeX project via `--paper-dir <path>`.)
- `--sections <list>` — comma-separated section names to restrict the audit (e.g. `introduction,conclusion`). Matched against the LaTeX `\section{…}` title, case-insensitive. Default: all.
- `--load-bearing-only` — only audit claims in load-bearing files (abstract, intro, conclusion). Fastest mode; use for a deadline-day triage. Default: off.
- `--min-citations <N>` — threshold below which a cite-backed claim is flagged as "weak" due to a low citation count on the source. Default: `0` (off). Suggest `10` for journals.
- `--skip-unsupported` — skip the unsupported-declarative-claim pass; only audit existing `\cite{}`s. Default: run both passes.
- `--no-notebooklm` — skip the NotebookLM grounded-quote verification layer. Pure abstract-based evaluation, much faster, less confident. Default: NotebookLM is used if a notebook is available.
- `--notebook "<title>"` — the NotebookLM notebook to use for grounded verification. If omitted, the skill runs `notebooklm list` and uses the obvious match or asks the user.
- `--output <path>` — where to save the report. Default: `__BIB_ROOT__/papers/<name>/claims_audit_<YYYY-MM-DD>.md`.

## Setup

Read:
- `__BIB_ROOT__/papers_inventory.csv` — catalog with abstracts + citations + themes.
- `__BIB_ROOT__/refs.bib` — master BibTeX.
- `__BIB_ROOT__/cite_key_aliases.csv` — `(name, local_key) → master_key` mapping.
- `__BIB_ROOT__/papers/<name>/refs.bib` — the paper's local bib (source of truth for local cite-keys).

Don't read every `.tex` yourself; the extractor handles that.

## Execution

### Stage 1 — Extract claim-cite pairs

Run:
```bash
python3 __BIB_ROOT__/tools/extract_claims.py <name>
```

This produces, under `__BIB_ROOT__/tmp/`:
- `claims_<name>.csv` — every `\cite`-bearing sentence: `section, file, position, sentence, cite_keys, is_load_bearing`
- `unsupported_<name>.csv` — sentences with factual-claim patterns but no `\cite`: `section, file, position, sentence, trigger, is_load_bearing`

Apply `--sections` and `--load-bearing-only` filters as row filters over the CSVs. Report the candidate counts before proceeding.

### Stage 2 — Resolve local keys to master entries

For each row in `claims_<name>.csv`:
- Split `cite_keys` on `;`.
- For each local key, look it up in `cite_key_aliases.csv` (`venue=<name>, local_key=<key>`) to get the master key. If not found, flag as **MISSING_ALIAS** — the paper cites a key not present in the master bib (probably a typo or a stray key never merged).
- For each master key, pull the catalog row: title, authors, year, venue, abstract, citations, theme, venue_type, status.

### Stage 3 — Evaluate each cite against the sentence

For each (sentence, cited entry) pair, decide a verdict. Use the cited entry's abstract (if present), fall back to its title otherwise. Four verdicts:

- **DIRECT** — abstract/title asserts the same claim in substance. Typical match: same entities, same relation, same scope.
- **ADJACENT** — abstract discusses the same phenomenon but doesn't make the specific claim; usable as a foundation reference but not as primary evidence for *this* sentence.
- **TANGENTIAL** — shares vocabulary only. Wrong citation — the ref is not about what the sentence claims.
- **UNKNOWN** — the cited entry has no abstract in the catalog and the title is ambiguous. Cannot verify without reading the PDF.

Be conservative with **TANGENTIAL** — only flag when the mismatch is clear. When uncertain, use **ADJACENT**.

### Stage 3b — NotebookLM grounded verification (skip if `--no-notebooklm`)

Local abstract matching is surface-level. NotebookLM has the *full source text* indexed and returns grounded quotes, which dramatically raises confidence. Use it as a targeted second opinion.

First pick the notebook: use `--notebook "<title>"` if given, else `notebooklm list` and choose the obvious match (or ask the user). If the user has no notebook for this paper's references, skip this stage and note it.

**Which rows to send to NotebookLM?** Not all — it's expensive. Prioritize:
- All **TANGENTIAL** and **ADJACENT** verdicts (need confirmation/refutation).
- All **UNKNOWN** verdicts (no local abstract; NotebookLM may have the PDF indexed).
- All **DIRECT** verdicts on `is_load_bearing=yes` sentences (raise confidence for abstract/intro/conclusion claims).
- Skip DIRECT verdicts on body-text sentences with abundant citations — abstract match is usually enough.

**How to query.** For each selected row, invoke the `/notebooklm` skill:

> "Using only the source(s) titled `<cited entry title>`, does the source directly support the claim: '<sentence>'? If yes, quote the exact supporting passage (1–3 sentences) and the section/page. If the source does NOT support this specific claim, say so explicitly and quote the closest passage you can find that *does* relate to the sentence's topic."

If the notebook doesn't contain the cited source, NotebookLM will say so — record as `NOTEBOOK_MISS` (the ref isn't indexed yet; consider running `/notebooklm` to add it).

**How to fold in the response:**

| Local verdict | NotebookLM says | Final verdict |
|---|---|---|
| ADJACENT | Found a direct quote | **DIRECT** (upgrade) |
| ADJACENT | Closest passage is clearly about something else | **TANGENTIAL** (downgrade) |
| TANGENTIAL | Found a direct quote | **ADJACENT** (partial upgrade — local abstract was misleading) |
| TANGENTIAL | Confirms mismatch | **TANGENTIAL** (confirmed, increase confidence in severity) |
| UNKNOWN | Found a direct quote | **DIRECT** |
| UNKNOWN | Found no support | **TANGENTIAL** (or ADJACENT if the source is at least topic-related) |
| DIRECT (load-bearing) | Confirmed with quote | **DIRECT** + attach quote to the report for reviewer preemption |
| DIRECT (load-bearing) | Source doesn't actually support the claim | **TANGENTIAL** (the nastiest bug class — abstract looked right, full text doesn't back it) |
| any | `NOTEBOOK_MISS` | Keep the local verdict; add note `"Not in NotebookLM — consider /notebooklm add"` |

**Quote propagation.** For every DIRECT verdict that NotebookLM confirmed, carry the quote forward into the report so the user sees *why* the verdict stands. For downgrades, include NotebookLM's "closest passage" so the user can judge whether to keep the ref (as adjacent/foundation) or replace it.

### Stage 3c — Compute severity

Combine with the catalog metadata to derive a **severity** tag:

| Severity | Trigger |
|---|---|
| `CRITICAL` | TANGENTIAL verdict AND `is_load_bearing=yes` |
| `HIGH` | TANGENTIAL anywhere, or MISSING_ALIAS |
| `MEDIUM` | ADJACENT on a load-bearing sentence; or DIRECT but `citations < --min-citations` and the cite is load-bearing; or `venue_type = preprint` on a load-bearing claim that would benefit from a peer-reviewed anchor |
| `LOW` | UNKNOWN anywhere; or ADJACENT in body text; or DIRECT but `citations < --min-citations` in body text |
| `OK` | DIRECT with sufficient citation count and an appropriate venue |

### Stage 4 — Evaluate unsupported-claim candidates (skip if `--skip-unsupported`)

For each row in `unsupported_<name>.csv`:
- Judge whether the sentence truly needs a citation. The extractor uses pattern triggers (`"research has shown"`, percentages, superlatives, "first/only/novel"); many triggers fire on legitimate non-claim sentences (e.g., "our framework is the first to…" is a self-claim, not a fact).
- Skip sentences that are clearly self-description or definitional.
- For those that *do* need a citation, tag:
  - `severity = HIGH` if load-bearing and the claim is empirical/comparative.
  - `severity = MEDIUM` otherwise.
  - `severity = LOW` if questionable but worth a look.

**NotebookLM pass (if enabled)**: for every HIGH and MEDIUM unsupported claim, query NotebookLM with:

> "Does any source in this notebook directly support the claim: '<sentence>'? If yes, name the source(s) and quote the exact supporting passage."

If NotebookLM returns a grounded hit → resolve the source to a `cite_key` via the `title` column in the catalog and propose it as the fix. This is the highest-signal way to close unsupported-claim gaps because it only recommends refs you actually have locally.

### Stage 5 — Propose fixes

For every non-OK claim:

1. **Local candidate search.** Grep `papers_inventory.csv` for rows where `cited_in` contains the current paper and `abstract/title` match the sentence tokens better than the current citation. If a better local candidate exists, propose it.
2. **Cross-paper candidate search.** If no candidate in this paper's own refs, search the whole master catalog. The candidate exists but isn't yet in this paper's `refs.bib` → propose running `/bib-search --for-paper <name>` to import it (using its master key).
3. **No local candidate → defer to `/claim-cite`.** Leave a suggestion in the patch-list: `suggested_action=/claim-cite "<sentence>" --for-paper <name>`.
4. **MISSING_ALIAS** fixes: either correct the typo (list similar keys from the paper's bib as suggestions) or run `/bib-search --for-paper <name>` with the topic if the entry is genuinely missing.

### Stage 6 — Output

Write two artifacts:

**1. Patch-list CSV** at `__BIB_ROOT__/tmp/claims_audit_<name>.csv`:

| Column | Meaning |
|---|---|
| `severity` | CRITICAL / HIGH / MEDIUM / LOW / OK |
| `verdict` | DIRECT / ADJACENT / TANGENTIAL / UNKNOWN / MISSING_ALIAS / UNSUPPORTED |
| `section` | from extractor |
| `file` | from extractor |
| `sentence` | truncated ≤ 300 chars |
| `current_cite_keys` | semicolon-separated local keys |
| `master_keys` | semicolon-separated master keys (blank for MISSING_ALIAS/UNSUPPORTED) |
| `abstract_verdict` | the Stage 3 verdict before NotebookLM |
| `notebooklm_verdict` | `confirmed` / `downgraded` / `upgraded` / `notebook_miss` / `skipped` |
| `notebooklm_quote` | the supporting passage returned (≤ 400 chars) or blank |
| `issue` | one-line rationale combining abstract + NotebookLM findings |
| `suggested_replacement` | alternative cite_key from the local corpus, or blank |
| `suggested_action` | `swap` / `import-master <key>` / `/claim-cite …` / `/bib-search …` / `/notebooklm add …` / `review` |

**2. Human-readable report** at the path from `--output`:

```markdown
# Claims Audit — <name> — <YYYY-MM-DD>

## Summary
- Total cite-bearing claims: N  (M load-bearing)
- Critical issues: N
- High issues: N
- Medium issues: N
- Low issues: N
- Possibly-unsupported declarative sentences: N

## Critical (must fix before submission)
For each CRITICAL:
  ### <section> · <file>:<approx line>
  > <sentence>
  - Current cite: `<key>` — <title> (<year>, <venue>) · citations=<N>
  - Issue: <why it's tangential / missing>
  - Fix: <specific replacement cite_key or the /claim-cite command to run>

## High / Medium / Low (same structure, collapsed tables when many)

## Possibly-unsupported declarative claims
For each row from the unsupported CSV with severity >= MEDIUM, include sentence + trigger + suggested search.

## Next steps
- Run these remediations in order:
  1. <command>
  2. <command>
  …
- Re-run `/claims-audit --venue <name>` after applying fixes to verify.
```

Provide a short end-of-turn summary to the user: totals per severity and the single most important action.

## Hygiene

- **Don't write scratch files to cwd.** The extractor's CSVs go in `__BIB_ROOT__/tmp/`. Any other intermediate artifacts go there too, never in the catalog root.
- **Don't create `.bak_*` snapshots** of `refs.bib` / `papers_inventory.csv` / `cite_key_aliases.csv` — this skill audits, it doesn't mutate.

## Non-goals

- **Don't rewrite the paper.** This skill reports; the user applies the fixes (possibly via other skills).
- **Don't auto-swap citations.** Even high-confidence swaps should be surfaced as suggestions — citation choice is an editorial decision.
- **Don't over-flag.** Be skeptical of TANGENTIAL verdicts — only flag when the mismatch is clear. Many sentences legitimately cite adjacent work as foundation references; that's not a bug.
- **Don't scan every PDF.** If a cited entry has no abstract in the catalog, mark UNKNOWN rather than opening the PDF. (If many rows come back UNKNOWN, suggest running `python3 __BIB_ROOT__/tools/extract_pdf_abstracts.py` to backfill.)

## Quick examples

```
/claims-audit --venue my-survey                                  # full audit, all sections
/claims-audit --venue my-survey --load-bearing-only              # fast triage: abstract/intro/conclusion only
/claims-audit --venue my-survey --min-citations 20               # stricter — flag any load-bearing cite under 20 citations
/claims-audit --venue my-survey --sections introduction,conclusion
/claims-audit --venue my-survey --skip-unsupported               # only verify existing cites
```

## Composes with

- `/claim-cite "<sentence>" --for-paper <name>` — find a replacement for a flagged CRITICAL/HIGH
- `/bib-search "<topic>" --for-paper <name>` — import a needed ref that exists in the master catalog but not this paper's bib
- `/bib-upgrade --for-paper <name>` — if many flagged cites are preprints, run the upgrade sweep first, then re-audit
