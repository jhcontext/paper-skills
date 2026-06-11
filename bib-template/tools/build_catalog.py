#!/usr/bin/env python3
"""Build papers_inventory.csv from refs.bib + pdfs/ tree + per-paper .tex cite scans.

Idempotent: rebuild from scratch any time. Preserves nothing from a previous
catalog — all authoritative state lives in refs.bib, cite_key_aliases.csv, and
the pdfs/ tree. Manual edits to theme / secondary_themes / notes go in
catalog_overrides.csv (see load_overrides) and are re-applied on every rebuild.
"""
from __future__ import annotations

import csv
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _bibparse import parse_bibfile  # noqa: E402
from classify_theme import classify_entry_fields  # noqa: E402
from sync_cited_in import build_cited_in_map, per_paper_local_keys  # noqa: E402

# Honours PAPER_SKILLS_BIB_ROOT (set by a skill that resolved the target
# workspace); otherwise the bib root this tools/ dir lives in. Falls back
# gracefully on older installs that predate workspace.py.
try:
    from workspace import bib_root_default  # noqa: E402
    BIB_ROOT = bib_root_default(__file__)
except Exception:
    import os
    BIB_ROOT = Path(os.environ.get("PAPER_SKILLS_BIB_ROOT")
                     or Path(__file__).resolve().parent.parent)
PDFS_ROOT = BIB_ROOT / "pdfs"

COLUMNS = [
    "cite_key", "title", "authors", "year",
    "venue_type", "venue",
    "theme", "secondary_themes",
    "cited_in", "per_paper_cite_keys",
    "notebooklm",
    "pdf_path",
    "doi", "url",
    "citations",  # OpenAlex cited_by_count, populated by enrich_metadata.py
    "abstract", "keywords",
    "status", "source",
    "added_date", "notes",
]


OVERRIDES_CSV = BIB_ROOT / "catalog_overrides.csv"
OVERRIDE_COLS = ("theme", "secondary_themes", "notes")


def load_overrides() -> dict[str, dict[str, str]]:
    """Read catalog_overrides.csv if it exists.

    Format: cite_key,theme,secondary_themes,notes
    Blank cell = don't override that column. Unknown cite_keys are reported.
    """
    if not OVERRIDES_CSV.exists():
        return {}
    out: dict[str, dict[str, str]] = {}
    with OVERRIDES_CSV.open() as f:
        for row in csv.DictReader(f):
            key = row.get("cite_key", "").strip()
            if not key:
                continue
            overrides = {c: row[c].strip() for c in OVERRIDE_COLS if row.get(c, "").strip()}
            if overrides:
                out[key] = overrides
    return out


def find_pdf(master_key: str) -> tuple[str, str]:
    """Return (relative_pdf_path, theme_guess_from_folder)."""
    if not PDFS_ROOT.exists():
        return "", ""
    for theme_dir in PDFS_ROOT.iterdir():
        if not theme_dir.is_dir():
            continue
        cand = theme_dir / f"{master_key}.pdf"
        if cand.exists():
            rel = cand.relative_to(BIB_ROOT)
            return str(rel), theme_dir.name
    return "", ""


def venue_type_from(entry_kind: str) -> str:
    return {
        "article": "journal",
        "inproceedings": "conference",
        "conference": "conference",
        "incollection": "book",
        "book": "book",
        "phdthesis": "thesis",
        "mastersthesis": "thesis",
        "techreport": "report",
        "misc": "preprint",
        "unpublished": "preprint",
        "online": "preprint",
    }.get(entry_kind, "preprint")


def venue_name_from(e) -> str:
    for f in ("journal", "booktitle", "howpublished", "publisher", "school",
              "institution", "organization"):
        v = e.fields.get(f, "").strip()
        if v:
            return v
    if e.fields.get("archiveprefix", "").lower() == "arxiv":
        return "arXiv"
    return ""


def main() -> int:
    bib_path = BIB_ROOT / "refs.bib"
    entries = parse_bibfile(bib_path) if bib_path.exists() else []
    entries_by_key = {e.key: e for e in entries}
    cited_map = build_cited_in_map()
    local_keys = per_paper_local_keys()
    overrides = load_overrides()

    today = dt.date.today().isoformat()

    rows: list[dict] = []
    unknown_overrides = set(overrides) - set(entries_by_key)
    for e in sorted(entries, key=lambda x: x.key):
        cited = cited_map.get(e.key, set())
        cited_sorted = sorted(cited)

        # PDF lookup
        pdf_path, pdf_theme = find_pdf(e.key)

        # Theme: prefer folder placement when available, else classify from fields
        theme = pdf_theme if pdf_theme and pdf_theme != "_unclassified" else classify_entry_fields(e.fields)

        # per_paper_cite_keys: "venue=localkey" pairs
        per_paper = local_keys.get(e.key, {})
        pp_str = ";".join(f"{v}={lk}" for v, lk in sorted(per_paper.items()))

        status = "have_pdf" if pdf_path else ("no_pdf_needed" if e.kind in {"misc"} and e.fields.get("url") else "oa_pending")

        source = ""
        if e.fields.get("archiveprefix", "").lower() == "arxiv" or "arxiv.org" in e.fields.get("url", "").lower():
            source = "arxiv"
        elif e.fields.get("doi", "").startswith("10.1145/"):
            source = "acm_dl"
        elif e.fields.get("doi", "").startswith("10.1109/"):
            source = "ieee"
        elif e.fields.get("doi", "").startswith("10.1007/"):
            source = "springer"
        elif e.fields.get("doi", ""):
            source = "crossref"

        row = {
            "cite_key": e.key,
            "title": e.fields.get("title", ""),
            "authors": e.fields.get("author", "").replace(" and ", "; "),
            "year": e.year,
            "venue_type": venue_type_from(e.kind),
            "venue": venue_name_from(e),
            "theme": theme,
            "secondary_themes": "",
            "cited_in": ";".join(cited_sorted),
            "per_paper_cite_keys": pp_str,
            "notebooklm": "",
            "pdf_path": pdf_path,
            "doi": e.fields.get("doi", ""),
            "url": e.fields.get("url", ""),
            "citations": e.fields.get("citations", ""),
            "abstract": e.fields.get("abstract", ""),
            "keywords": e.fields.get("keywords", ""),
            "status": status,
            "source": source,
            "added_date": today,
            "notes": "",
        }
        # Apply manual overrides (theme / secondary_themes / notes)
        for col, val in overrides.get(e.key, {}).items():
            row[col] = val
        rows.append(row)

    out = BIB_ROOT / "papers_inventory.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # Summary stats
    with_pdf = sum(1 for r in rows if r["pdf_path"])
    with_abstract = sum(1 for r in rows if r["abstract"])
    uncited = sum(1 for r in rows if not r["cited_in"])
    theme_counts: dict[str, int] = {}
    for r in rows:
        theme_counts[r["theme"]] = theme_counts.get(r["theme"], 0) + 1

    print(f"[write] {out}: {len(rows)} rows")
    if overrides:
        print(f"[overrides] applied {len(overrides) - len(unknown_overrides)} from {OVERRIDES_CSV.name}")
    if unknown_overrides:
        print(f"[overrides] WARN: {len(unknown_overrides)} overrides reference unknown cite_keys:")
        for k in sorted(unknown_overrides): print(f"    {k}")
    print(f"\n[summary]")
    print(f"  with_pdf:      {with_pdf}/{len(rows)}")
    print(f"  with_abstract: {with_abstract}/{len(rows)}")
    print(f"  uncited:       {uncited}/{len(rows)}  (in master bib but no \\cite in any paper)")
    print(f"\n[themes]")
    for th, c in sorted(theme_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {th:<22} {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
