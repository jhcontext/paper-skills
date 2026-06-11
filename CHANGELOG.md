# Changelog

All notable changes to `paper-skills` are documented here. This project follows
[Semantic Versioning](https://semver.org). The current version is also shown at
the top of the [README](README.md).

## v0.3.0

### Added

- **Team workflows.** The kit now supports multiple collaborators on the same
  papers and bibliography:
  - New `bib-sync` skill — syncs the PDF library to/from S3 (`pull` / `push` /
    `status` / `--setup`). Heavy PDFs travel through S3; metadata stays in git.
  - New per-workspace config `.paper-skills.json` (non-secret: bucket, prefix,
    region, AWS profile name, NotebookLM profile). No credentials are ever stored
    in the repo — AWS keys live in `~/.aws`, NotebookLM auth in `~/.notebooklm`.
  - New `tools/workspace.py` resolver — skills auto-detect which bibliography
    workspace applies (a shared bib vs. your own), so one machine can run both
    without re-installing. Falls back to the install-time `__BIB_ROOT__` for
    single-workspace setups (backward compatible).
  - New `tools/s3_sync.py` — dependency-free wrapper over `aws s3 sync`.
  - `bib-search` and `bib-classify` auto-pull shared PDFs before they need them
    and remind you to push new/refiled PDFs; metadata-only skills don't sync.
  - `notebooklm` skill documents the `share` command group and adds a **Team
    access** section (share notebooks with a collaborator's Google account as
    editor/viewer) plus a rebuild-from-local-PDFs fallback when access isn't
    granted.
  - Installer gained an optional S3 / NotebookLM-profile step and a retrofit
    path for existing installs.

## v0.2.2

### Changed

- README: added a closing *Part of an active research project* section that
  frames the kit as an extraction from an ongoing research project on
  autonomous scientific research agents, with an image of earlier prototypes.

## v0.2.1

### Changed

- Documentation: clarified that "one NotebookLM notebook per paper" means one
  notebook per **working paper** — the manuscript you are writing for a venue, a
  folder under `papers/<name>/` — and *not* per reference paper you search for.

## v0.2.0

### Added — citation snowballing

- **`bib-snowball` skill.** Grows the bibliography from the *citation graph*
  instead of a topic query (Wohlin's snowballing method). From seed papers you
  already trust, it follows their reference lists (*backward* snowballing) and
  the papers that cite them (*forward* snowballing) via OpenAlex and Semantic
  Scholar, ranks candidates by how many seeds connect to them, and ingests your
  picks through the same path as `/bib-search`. Supports multiple rounds
  (`--rounds N`).

### Added — one NotebookLM notebook per paper

- **`bib-search` and `bib-snowball`** now keep a paper's NotebookLM notebook fed
  automatically. Run either with `--for-paper <name>` and the skill creates (or
  links) a dedicated notebook for that paper, uploads every PDF it downloads to
  it as a source, and records the link in `papers/<name>/.notebook.json`. Use
  `--no-notebook` to opt out, or `--notebook "<title>"` to override.
- **`bib-classify --sync-notebook --for-paper <name>`** — a backfill mode that
  loads every PDF a paper already cites into that paper's notebook in one pass.
- **`claim-cite` and `claims-audit`** now resolve a paper's notebook
  automatically from its `.notebook.json` (via `--for-paper` / `--venue`), so
  grounded citation checks "just work" once a paper has a notebook. `--notebook`
  still works as an explicit override.

### Added — repository

- Issue templates (feature request, bug report) and a *Feedback and feature
  requests* section in the README.

## v0.1.0

Initial release.

- Six skills — `notebooklm`, `bib-search`, `bib-classify`, `bib-upgrade`,
  `claim-cite`, `claims-audit` — plus the `install-paper-skills` one-shot
  installer.
- `bib-template/` bibliography-workspace scaffold with seven standard-library
  Python tools; minimal LaTeX `paper-template/`.
- README covering how NotebookLM and vector search work, VS Code + Claude Code +
  LaTeX setup, and the discover → organise → cite → write workflow.
