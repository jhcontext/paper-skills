#!/usr/bin/env python3
"""Scan each paper's .tex for \\cite{} macros and return {master_key -> set(venues)}.

Used standalone to update the cited_in column of papers_inventory.csv. Also
callable from build_catalog.py.

A "paper" is any sub-directory of <bib_root>/papers/ that contains a refs.bib.
The directory name is used as the venue label. If papers/ is empty, every
master entry simply gets a blank cited_in column — that is fine.
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

# Matches \cite, \citep, \citet, \parencite, \textcite, \autocite, \footcite,
# \smartcite, \fullcite, \nocite, etc. — any command ending in `cite` (case-sensitive).
CITE_RE = re.compile(r"\\[a-zA-Z]*[Cc]ite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{([^}]+)\}")

BIB_ROOT = Path(__file__).resolve().parent.parent
PAPERS_ROOT = BIB_ROOT / "papers"


def discover_papers() -> dict[str, Path]:
    """Return {venue_name: paper_dir} for every paper folder under papers/."""
    out: dict[str, Path] = {}
    if not PAPERS_ROOT.exists():
        return out
    for d in sorted(PAPERS_ROOT.iterdir()):
        if d.is_dir() and not d.name.startswith("."):
            out[d.name] = d
    return out


def load_aliases() -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    alias_csv = BIB_ROOT / "cite_key_aliases.csv"
    if not alias_csv.exists():
        return out
    with alias_csv.open() as f:
        r = csv.DictReader(f)
        for row in r:
            out[(row["venue"], row["local_key"])] = row["master_key"]
    return out


def scan_paper(venue: str, root: Path) -> set[str]:
    """Return set of local cite keys referenced in .tex files under root."""
    keys: set[str] = set()
    for tex in root.rglob("*.tex"):
        # Skip auxiliary / build artifacts
        if tex.name.endswith(".aux.tex"):
            continue
        try:
            text = tex.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in CITE_RE.finditer(text):
            for k in m.group(1).split(","):
                k = k.strip()
                if k:
                    keys.add(k)
    return keys


def build_cited_in_map() -> dict[str, set[str]]:
    """Return {master_key: set(venue)}."""
    aliases = load_aliases()
    cited: dict[str, set[str]] = defaultdict(set)
    for venue, root in discover_papers().items():
        local_keys = scan_paper(venue, root)
        unresolved = 0
        for lk in local_keys:
            master = aliases.get((venue, lk))
            if master:
                cited[master].add(venue)
            else:
                unresolved += 1
        print(f"[{venue}] {len(local_keys)} cite keys, {unresolved} not in aliases")
    return cited


def per_paper_local_keys() -> dict[str, dict[str, str]]:
    """Return {master_key: {venue: local_key}} — the reverse of the aliases file."""
    out: dict[str, dict[str, str]] = defaultdict(dict)
    alias_csv = BIB_ROOT / "cite_key_aliases.csv"
    if not alias_csv.exists():
        return out
    with alias_csv.open() as f:
        r = csv.DictReader(f)
        for row in r:
            out[row["master_key"]][row["venue"]] = row["local_key"]
    return out


def main() -> int:
    cited = build_cited_in_map()
    print(f"\n[summary] {len(cited)} master entries cited in at least one paper")
    multi = {k: v for k, v in cited.items() if len(v) > 1}
    print(f"[summary] {len(multi)} entries cited in >1 paper")
    for k, venues in sorted(multi.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:15]:
        print(f"  {k:<40} {';'.join(sorted(venues))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
