# Changelog

All notable changes to `paper-skills` are documented here. This project follows
[Semantic Versioning](https://semver.org). The current version is also shown at
the top of the [README](README.md).

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
