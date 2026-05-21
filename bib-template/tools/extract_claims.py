#!/usr/bin/env python3
r"""Extract every \cite-bearing sentence from a paper's .tex files.

Usage:
  extract_claims.py <venue>            # a folder name under <bib_root>/papers/
  extract_claims.py --paper-dir <path> # any LaTeX project directory

Output: CSV at <bib_root>/tmp/claims_<venue>.csv with columns:
  section, file, position, sentence, cite_keys, is_load_bearing

Also detects unsupported-looking declarative claims (sentences with assertion
patterns but no \cite) and emits them in <bib_root>/tmp/unsupported_<venue>.csv.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

BIB_ROOT = Path(__file__).resolve().parent.parent
PAPERS_ROOT = BIB_ROOT / "papers"
TMP_ROOT = BIB_ROOT / "tmp"

CITE_RE = re.compile(r"\\[a-zA-Z]*[Cc]ite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{([^}]+)\}")
SECTION_RE = re.compile(r"\\(section|subsection|subsubsection)\*?\{([^}]+)\}")

LOAD_BEARING_FILES = {
    "abstract", "01intro", "01_introduction", "01_intro",
    "07conclusion", "08_conclusion", "10conclusion", "conclusion",
    "main",  # main.tex often holds the abstract
}

# Sentences that look like factual claims (candidates for "unsupported" check).
UNSUPPORTED_PATTERNS = [
    re.compile(r"\b(studies|research|prior work|recent work|literature) (have|has) (shown|demonstrated|found|revealed)\b", re.I),
    re.compile(r"\b(it is|are) (well[- ]?known|widely accepted|well[- ]?established|known) that\b", re.I),
    re.compile(r"\b\d{1,3}(\.\d+)?%\b"),  # percentages
    re.compile(r"\b(most|many|several|numerous) (\w+ ){0,3}(systems|studies|models|frameworks|approaches|papers|authors)\b", re.I),
    re.compile(r"\b(outperforms?|exceeds|surpasses|improves upon)\b", re.I),
    re.compile(r"\b(first|only|novel|unprecedented)\b", re.I),

    # Empirical-action duration claims — a duration paired with a verb that asserts a
    # real-world process took/lasted that long.
    re.compile(r"\b(?:take(?:s|n)?|took|last(?:s|ed)?|spans?|spanned|reach(?:es|ed)?\s+(?:after|in)|require(?:s|d)?|need(?:s|ed)?|consum(?:es|ed))\s+(?:roughly|approximately|about|over|nearly|at\s+least|currently)?\s*(?:\d{1,3}|eighteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|nineteen|several|many)\s+(?:months?|years?|weeks?|days?|hours?|minutes?)\b", re.I),

    # "in (current) practice" / "currently" / "today" + negative or empirical predicate
    re.compile(r"\b(?:in (?:current )?practice|currently|today|in production)\b[^.]{0,80}\b(?:does not|do not|cannot|fail(?:s|ed)? to|lack(?:s|ed)?|absent|missing|unavailable|unaddressed|no |without |short of )", re.I),

    # Causal / relational verbs on bias / harm / disparity vocab
    re.compile(r"\b(?:cause(?:s|d)?|lead(?:s|ing)?\s+to|result(?:s|ed)?\s+in|produce(?:s|d)?|generate(?:s|d)?|amplif(?:y|ies|ied)|reinforce(?:s|d)?|redistribute(?:s|d)?|concentrate(?:s|d)?|introduce(?:s|d)?)\s+(?:bias|discrimination|harm|disparate|exclusion|inequit\w*|opacity|asymmetr\w*)\b", re.I),

    # Prevalence / state assertions (X exhibits/displays bias)
    re.compile(r"\b(?:exhibit(?:s|ed)?|display(?:s|ed)?|reveal(?:s|ed)?|expose(?:s|d)?)\s+(?:bias|discrimination|inequit\w*|opacity|disparate)\w*\b", re.I),
]

# Sentences we should NOT flag even if they look factual (methodology / self-description).
SKIP_PATTERNS = [
    re.compile(r"\b(we (propose|introduce|present|describe|argue|show|prove|demonstrate|claim|characterise|characterize|name|recast|derive))\b", re.I),
    re.compile(r"\b(this (paper|work|section|chapter|study))\b", re.I),
    re.compile(r"\b(our (approach|method|framework|protocol|substrate|design|contribution))\b", re.I),
    re.compile(r"^\s*(figure|table|equation|algorithm) \d+", re.I),
    # Paper-internal label tokens (C1..C9, P1..P9, DO1..DO9, L1..L9, RQ1..RQ9)
    re.compile(r"\b(?:C[1-9]|P[1-9]|DO[1-9]|L[1-9]|RQ[1-9])\b"),
    # Explicit own-method comparative ("specific to our framework", ...)
    re.compile(r"\b(?:are\s+unique\s+to|specific\s+to|exclusive\s+to)\s+(?:our|the\s+present|this\s+work)\b", re.I),
    # Self-scoping ("the contribution is bounded by", ...)
    re.compile(r"\b(?:the\s+contribution|the\s+scope|the\s+claim)\s+(?:is|are)\s+bounded\b", re.I),
    # Inline regulatory references — Art./Recital/Annex/§ are primary-source pinpoints,
    # not factual claims requiring a separate citation.
    re.compile(r"\b(?:Art\.|Article|Recital|Annex|§|Sec\.|Section)\s*~?\s*\d+", re.I),
    # LaTeX inline-math regulatory thresholds ("$\geq$ N months").
    re.compile(r"\\(?:geq|leq|ge|le)\b\s*(?:\d+|\w+)\s+(?:months?|years?|weeks?|days?|hours?)", re.I),
]

_WS = re.compile(r"\s+")


def strip_comments(text: str) -> str:
    # Remove % line comments but preserve \% escapes
    out = []
    for line in text.splitlines():
        idx = -1
        i = 0
        while i < len(line):
            if line[i] == "%" and (i == 0 or line[i - 1] != "\\"):
                idx = i
                break
            i += 1
        out.append(line if idx < 0 else line[:idx])
    return "\n".join(out)


def section_tracker(text: str) -> list[tuple[int, str]]:
    return [(m.start(), m.group(2).strip()) for m in SECTION_RE.finditer(text)]


def section_at(pos: int, spans: list[tuple[int, str]]) -> str:
    current = ""
    for p, n in spans:
        if p <= pos:
            current = n
        else:
            break
    return current


def _nearest(s: str, *needles: str) -> int:
    """Return the largest index of any needle in s, or -1."""
    best = -1
    for n in needles:
        i = s.rfind(n)
        if i > best:
            best = i
    return best


def _earliest(s: str, *needles: str) -> int:
    """Return the smallest non-negative index of any needle in s, or len(s)."""
    positions = [s.find(n) for n in needles]
    positions = [p for p in positions if p >= 0]
    return min(positions) if positions else len(s)


def extract_sentence_around(text: str, pos: int, end: int) -> str:
    before = text[max(0, pos - 500):pos]
    after = text[end:end + 400]
    b_start = _nearest(before, ". ", "! ", "? ", "\n\n")
    b_start = b_start + 2 if b_start >= 0 else 0
    a_end = _earliest(after, ". ", "! ", "? ", "\n\n")
    a_end = min(a_end + 1, len(after))
    sentence = before[b_start:] + text[pos:end] + after[:a_end]
    return _WS.sub(" ", sentence).strip()


def is_load_bearing(tex_path: Path) -> bool:
    stem = tex_path.stem.lower()
    return any(k in stem for k in LOAD_BEARING_FILES)


def extract_cites_from(tex_path: Path) -> list[dict]:
    try:
        text = tex_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    text = strip_comments(text)
    spans = section_tracker(text)
    results = []
    load_bearing = is_load_bearing(tex_path)
    for m in CITE_RE.finditer(text):
        sentence = extract_sentence_around(text, m.start(), m.end())
        keys = [k.strip() for k in m.group(1).split(",") if k.strip()]
        if not keys:
            continue
        results.append({
            "section": section_at(m.start(), spans),
            "file": tex_path.name,
            "position": m.start(),
            "sentence": sentence[:800],
            "cite_keys": ";".join(keys),
            "is_load_bearing": "yes" if load_bearing else "no",
        })
    return results


def extract_unsupported_from(tex_path: Path) -> list[dict]:
    try:
        text = tex_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    text = strip_comments(text)
    spans = section_tracker(text)
    load_bearing = is_load_bearing(tex_path)

    # Split into rough sentences
    sentences: list[tuple[int, str]] = []
    pos = 0
    for m in re.finditer(r"[.!?]\s+(?=[A-Z\\])|\n\n", text):
        s = text[pos:m.start() + 1]
        sentences.append((pos, s))
        pos = m.end()
    if pos < len(text):
        sentences.append((pos, text[pos:]))

    results = []
    for spos, s in sentences:
        clean = _WS.sub(" ", s).strip()
        if len(clean) < 40:
            continue
        if CITE_RE.search(clean):
            continue  # has a cite; not unsupported
        if any(p.search(clean) for p in SKIP_PATTERNS):
            continue
        if not any(p.search(clean) for p in UNSUPPORTED_PATTERNS):
            continue
        results.append({
            "section": section_at(spos, spans),
            "file": tex_path.name,
            "position": spos,
            "sentence": clean[:800],
            "trigger": next((p.pattern for p in UNSUPPORTED_PATTERNS if p.search(clean)), ""),
            "is_load_bearing": "yes" if load_bearing else "no",
        })
    return results


def walk_paper(root: Path) -> list[Path]:
    excludes = {"versions", "_archive", "build", "out", ".git"}
    out = []
    for tex in sorted(root.rglob("*.tex")):
        parts = set(tex.relative_to(root).parts)
        if parts & excludes:
            continue
        if tex.name.endswith(".aux.tex"):
            continue
        out.append(tex)
    return out


def resolve_paper(argv: list[str]) -> tuple[str, Path] | None:
    """Return (venue_label, paper_dir) from argv, or None on error."""
    if len(argv) >= 3 and argv[1] == "--paper-dir":
        root = Path(argv[2]).expanduser().resolve()
        return root.name, root
    venue = argv[1]
    root = PAPERS_ROOT / venue
    return venue, root


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        print("usage: extract_claims.py <venue>", file=sys.stderr)
        print("   or: extract_claims.py --paper-dir <path>", file=sys.stderr)
        if PAPERS_ROOT.exists():
            venues = sorted(d.name for d in PAPERS_ROOT.iterdir() if d.is_dir())
            print(f"  papers/ folders: {', '.join(venues) or '(none)'}", file=sys.stderr)
        return 2

    resolved = resolve_paper(sys.argv)
    if not resolved:
        return 1
    venue, root = resolved
    if not root.exists():
        print(f"missing paper directory: {root}", file=sys.stderr)
        return 1

    tex_files = walk_paper(root)
    cited = []
    unsupported = []
    for tex in tex_files:
        cited.extend(extract_cites_from(tex))
        unsupported.extend(extract_unsupported_from(tex))

    TMP_ROOT.mkdir(parents=True, exist_ok=True)

    out_cited = TMP_ROOT / f"claims_{venue}.csv"
    with out_cited.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["section", "file", "position", "sentence",
                                           "cite_keys", "is_load_bearing"])
        w.writeheader()
        for r in cited:
            w.writerow(r)

    out_unsup = TMP_ROOT / f"unsupported_{venue}.csv"
    with out_unsup.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["section", "file", "position", "sentence",
                                           "trigger", "is_load_bearing"])
        w.writeheader()
        for r in unsupported:
            w.writerow(r)

    print(f"[write] {out_cited}: {len(cited)} cite-bearing claims "
          f"({sum(1 for r in cited if r['is_load_bearing']=='yes')} load-bearing)")
    print(f"[write] {out_unsup}: {len(unsupported)} possibly-unsupported claims "
          f"({sum(1 for r in unsupported if r['is_load_bearing']=='yes')} load-bearing)")
    print(f"[scanned] {len(tex_files)} .tex files under {root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
