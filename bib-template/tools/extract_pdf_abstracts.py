#!/usr/bin/env python3
"""Extract abstracts from PDFs when OpenAlex enrichment didn't yield one.

Walks pdfs/ for every <cite_key>.pdf, looks up the matching master bib entry,
and if it lacks an abstract, runs pdftotext on the first 3 pages and greps for
the abstract block. Writes any findings back into refs.bib.

After enrichment, re-runs classify_theme and MOVES pdfs out of _unclassified/
into the right theme folder if the classifier now has enough signal.

Requires the `pdftotext` command (part of poppler-utils).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _bibparse import entry_to_bibtex, parse_bibfile  # noqa: E402
from classify_theme import classify_entry_fields  # noqa: E402

BIB_ROOT = Path(__file__).resolve().parent.parent
PDFS_ROOT = BIB_ROOT / "pdfs"

ABSTRACT_HEADS = re.compile(r"(?im)^\s*(abstract|summary)\s*[:\.\-—]?\s*$")
INLINE_HEAD = re.compile(r"(?is)\babstract[\s:\.\-—]+(.{150,2500}?)(?=\n\s*(?:1\.?\s+introduction|keywords|ccs concepts|categories and subject|index terms|acm reference|references|\d+\s+introduction)\b)")
KEYWORDS_END = re.compile(r"(?im)^\s*(keywords|ccs concepts|categories and subject descriptors|index terms|acm reference format|1\.?\s+introduction|\d+\.?\s+introduction)\b")


def pdftotext_front_pages(pdf: Path) -> str:
    try:
        proc = subprocess.run(
            ["pdftotext", "-l", "3", "-layout", str(pdf), "-"],
            capture_output=True, text=True, timeout=20,
        )
        return proc.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def extract_abstract(text: str) -> str:
    # Strategy 1: block after a line that's just "Abstract"
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ABSTRACT_HEADS.match(ln):
            # Collect subsequent lines until we hit keywords/intro
            buf = []
            for j in range(i + 1, min(i + 80, len(lines))):
                if KEYWORDS_END.match(lines[j]):
                    break
                buf.append(lines[j].strip())
            candidate = " ".join(b for b in buf if b).strip()
            candidate = re.sub(r"\s+", " ", candidate)
            if 200 < len(candidate) < 3500:
                return candidate
    # Strategy 2: inline "Abstract: ..." pattern
    m = INLINE_HEAD.search(text)
    if m:
        candidate = re.sub(r"\s+", " ", m.group(1)).strip()
        if 200 < len(candidate) < 3500:
            return candidate
    return ""


def main() -> int:
    bib_path = BIB_ROOT / "refs.bib"
    entries = parse_bibfile(bib_path)
    by_key = {e.key: e for e in entries}

    # Enumerate all PDFs
    pdfs = list(PDFS_ROOT.rglob("*.pdf")) if PDFS_ROOT.exists() else []
    print(f"[scan] {len(pdfs)} PDFs under pdfs/")

    filled = 0
    skipped = 0
    failed = 0
    for pdf in pdfs:
        key = pdf.stem
        e = by_key.get(key)
        if not e:
            continue
        if e.fields.get("abstract"):
            skipped += 1
            continue
        text = pdftotext_front_pages(pdf)
        if not text:
            failed += 1
            continue
        abstract = extract_abstract(text)
        if abstract:
            e.fields["abstract"] = abstract
            filled += 1
            print(f"  [ok] {key} ({len(abstract)} chars)")
        else:
            failed += 1

    # Write back
    sorted_entries = sorted(entries, key=lambda x: x.key)
    with bib_path.open("w", encoding="utf-8") as f:
        f.write("% Master bibliography — PDF abstracts merged by "
                "tools/extract_pdf_abstracts.py\n")
        f.write(f"% {len(sorted_entries)} entries\n\n")
        for e in sorted_entries:
            f.write(entry_to_bibtex(e))
            f.write("\n\n")

    print(f"\n[summary] filled={filled} skipped={skipped} failed={failed}")

    # Re-classify _unclassified/ PDFs now that we have more signal
    unclassified = PDFS_ROOT / "_unclassified"
    if unclassified.exists():
        moves = 0
        stayed = 0
        for pdf in sorted(unclassified.glob("*.pdf")):
            key = pdf.stem
            e = by_key.get(key)
            if not e:
                continue
            theme = classify_entry_fields(e.fields)
            if theme == "_unclassified":
                stayed += 1
                continue
            dest = PDFS_ROOT / theme / pdf.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                stayed += 1
                continue
            shutil.move(str(pdf), str(dest))
            moves += 1
            print(f"  [move] {pdf.name} -> {theme}/")
        print(f"\n[reclassify] moved={moves} stayed_in_unclassified={stayed}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
