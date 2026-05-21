#!/usr/bin/env python3
"""Fetch abstract, citation count, and venue metadata from OpenAlex for every master entry.

Writes back directly into refs.bib (idempotent: skips entries that already have
both `abstract` and `citations`).

OpenAlex serves faster, more reliably, and to a higher rate limit when you
identify yourself via the "polite pool". Set the CROSSREF_MAILTO environment
variable to your email to opt in:

    export CROSSREF_MAILTO="you@example.com"

It works without the variable too — just anonymously.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _bibparse import entry_to_bibtex, parse_bibfile  # noqa: E402

BIB_ROOT = Path(__file__).resolve().parent.parent
OPENALEX = "https://api.openalex.org/works"
MAILTO = os.environ.get("CROSSREF_MAILTO", "").strip()
UA = f"paper-skills/1.0 (mailto:{MAILTO})" if MAILTO else "paper-skills/1.0"
REQ_DELAY = 0.11  # ~9 req/s, under the polite-pool limit

_WS = re.compile(r"\s+")


def _mailto(params: dict) -> dict:
    """Add the mailto param only when an email is configured."""
    if MAILTO:
        params = dict(params)
        params["mailto"] = MAILTO
    return params


def reconstruct_abstract(inv_idx: dict | None) -> str:
    if not inv_idx:
        return ""
    positions: dict[int, str] = {}
    for word, ps in inv_idx.items():
        for p in ps:
            positions[p] = word
    if not positions:
        return ""
    return _WS.sub(" ", " ".join(positions.get(i, "") for i in range(max(positions) + 1))).strip()


def http_get(url: str) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        if e.code == 429:
            time.sleep(2.0)
            return http_get(url)  # one retry
        return None
    except Exception:
        return None


def lookup_by_doi(doi: str) -> dict | None:
    clean = doi.strip().lower()
    clean = re.sub(r"^https?://(dx\.)?doi\.org/", "", clean)
    qs = urllib.parse.urlencode(_mailto({}))
    url = f"{OPENALEX}/doi:{urllib.parse.quote(clean, safe='/')}"
    if qs:
        url += f"?{qs}"
    return http_get(url)


def norm_title(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def lookup_by_title(title: str, year: str = "", author_last: str = "") -> dict | None:
    q_title = title[:180]
    params = {"search": q_title, "per-page": 5}
    if year:
        params["filter"] = f"publication_year:{year}"
    url = f"{OPENALEX}?{urllib.parse.urlencode(_mailto(params))}"
    data = http_get(url)
    if not data:
        return None
    results = data.get("results", [])
    if not results:
        return None
    nq = norm_title(q_title)
    # Rank: exact-ish title match, then first result
    for r in results:
        if norm_title(r.get("title") or "") == nq:
            return r
    # Soft prefix match (>=75% overlap) with author sanity check
    for r in results:
        nt = norm_title(r.get("title") or "")
        if not nt or not nq:
            continue
        overlap = len(set(nq[i:i + 6] for i in range(len(nq) - 5)) &
                      set(nt[i:i + 6] for i in range(len(nt) - 5)))
        if overlap >= 3:
            if author_last:
                authors = " ".join(
                    (a.get("author") or {}).get("display_name", "")
                    for a in r.get("authorships", [])[:3]
                ).lower()
                if author_last.lower() in authors:
                    return r
            else:
                return r
    return None


def main() -> int:
    bib_path = BIB_ROOT / "refs.bib"
    entries = parse_bibfile(bib_path)
    print(f"[enrich] {len(entries)} entries in {bib_path}")

    stats = {"already": 0, "doi_hit": 0, "title_hit": 0, "miss": 0}
    for i, e in enumerate(entries):
        has_abs = bool(e.fields.get("abstract"))
        has_cite = bool(e.fields.get("citations"))
        if has_abs and has_cite:
            stats["already"] += 1
            continue

        work = None
        if e.doi:
            work = lookup_by_doi(e.doi)
            time.sleep(REQ_DELAY)
            if work:
                stats["doi_hit"] += 1
        if not work and e.fields.get("title"):
            work = lookup_by_title(
                e.fields["title"],
                year=e.year,
                author_last=e.first_author_last,
            )
            time.sleep(REQ_DELAY)
            if work:
                stats["title_hit"] += 1
        if not work:
            stats["miss"] += 1
            if i % 25 == 0:
                print(f"  [{i+1:>3}/{len(entries)}] miss: {e.key}")
            continue

        # Abstract
        if not has_abs:
            a = reconstruct_abstract(work.get("abstract_inverted_index"))
            if a:
                e.fields["abstract"] = a[:4000]
        # Citation count
        if work.get("cited_by_count") is not None:
            e.fields["citations"] = str(work["cited_by_count"])
        # Venue (only fill if missing)
        ploc = work.get("primary_location") or {}
        src = ploc.get("source") or {}
        src_name = src.get("display_name") or ""
        if src_name and not (e.fields.get("journal") or e.fields.get("booktitle")):
            # Entry kind heuristic
            src_type = (src.get("type") or "").lower()
            if src_type in {"journal", "series"}:
                e.fields["journal"] = src_name
            else:
                e.fields["booktitle"] = src_name
        # Backfill DOI if OpenAlex has one and we didn't
        if not e.fields.get("doi") and work.get("doi"):
            e.fields["doi"] = work["doi"].replace("https://doi.org/", "")
        # Backfill authors if missing
        if not e.fields.get("author"):
            names = [(a.get("author") or {}).get("display_name", "")
                     for a in work.get("authorships", [])]
            names = [n for n in names if n]
            if names:
                e.fields["author"] = " and ".join(names)
        # Backfill year if missing
        if not e.fields.get("year") and work.get("publication_year"):
            e.fields["year"] = str(work["publication_year"])

        if (i + 1) % 25 == 0:
            print(f"  [{i+1:>3}/{len(entries)}] "
                  f"doi_hit={stats['doi_hit']} title_hit={stats['title_hit']} "
                  f"already={stats['already']} miss={stats['miss']}")

    # Write back, sorted
    sorted_entries = sorted(entries, key=lambda x: x.key)
    with bib_path.open("w", encoding="utf-8") as f:
        f.write("% Master bibliography — managed by the paper-skills bib tools, "
                f"enriched {time.strftime('%Y-%m-%d')} by tools/enrich_metadata.py\n")
        f.write(f"% {len(sorted_entries)} unique entries\n\n")
        for e in sorted_entries:
            f.write(entry_to_bibtex(e))
            f.write("\n\n")

    print(f"\n[summary] {stats}")
    print(f"  entries now with abstract:  {sum(1 for e in entries if e.fields.get('abstract'))}/{len(entries)}")
    print(f"  entries now with citations: {sum(1 for e in entries if e.fields.get('citations'))}/{len(entries)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
