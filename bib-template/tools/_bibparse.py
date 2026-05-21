"""Minimal BibTeX parser — stdlib-only, handles the common entry patterns."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Entry:
    kind: str
    key: str
    fields: dict[str, str] = field(default_factory=dict)
    source_file: str = ""

    @property
    def doi(self) -> str:
        raw = (self.fields.get("doi") or "").strip().lower()
        raw = raw.replace("https://doi.org/", "").replace("http://doi.org/", "")
        raw = raw.replace("http://dx.doi.org/", "").replace("https://dx.doi.org/", "")
        return raw.strip()

    @property
    def title_norm(self) -> str:
        t = self.fields.get("title", "")
        t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
        return re.sub(r"[^a-z0-9]", "", t.lower())

    @property
    def year(self) -> str:
        y = self.fields.get("year", "")
        m = re.search(r"\d{4}", y)
        return m.group(0) if m else ""

    @property
    def first_author_last(self) -> str:
        a = self.fields.get("author", "")
        if not a:
            return ""
        first = re.split(r"\s+and\s+", a, maxsplit=1)[0].strip()
        if "," in first:
            last = first.split(",", 1)[0]
        else:
            parts = first.split()
            last = parts[-1] if parts else ""
        last = unicodedata.normalize("NFKD", last).encode("ascii", "ignore").decode()
        return re.sub(r"[^a-zA-Z]", "", last).lower()

    @property
    def short_title(self) -> str:
        t = self.fields.get("title", "")
        t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
        stop = {"the", "a", "an", "of", "for", "on", "in", "to", "with", "and", "or", "is", "are"}
        words = [w for w in re.findall(r"[a-z0-9]+", t) if w not in stop]
        return "".join(words[:3])

    def master_key(self) -> str:
        return f"{self.first_author_last or 'anon'}{self.year or 'nd'}{self.short_title or 'untitled'}"


def _strip_outer(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == "{" and s[-1] == "}":
        return s[1:-1]
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return s[1:-1]
    return s


def _read_balanced(text: str, i: int, opener: str, closer: str) -> tuple[str, int]:
    """Read from text[i] which is on an opener, return (content_without_outer, new_i_past_closer)."""
    assert text[i] == opener
    depth = 0
    start = i
    while i < len(text):
        c = text[i]
        if c == opener:
            depth += 1
        elif c == closer:
            depth -= 1
            if depth == 0:
                return text[start + 1 : i], i + 1
        i += 1
    raise ValueError(f"Unbalanced {opener}{closer} starting at {start}")


def parse_bibfile(path: Path) -> list[Entry]:
    text = path.read_text(encoding="utf-8", errors="replace")
    # Strip line comments starting with %
    text = re.sub(r"(?m)^%.*$", "", text)

    entries: list[Entry] = []
    i = 0
    n = len(text)

    while i < n:
        # Find next @
        at = text.find("@", i)
        if at == -1:
            break
        # Read entry type: @TYPE{
        m = re.match(r"@(\w+)\s*([\{\(])", text[at:])
        if not m:
            i = at + 1
            continue
        kind = m.group(1).lower()
        opener = m.group(2)
        closer = "}" if opener == "{" else ")"
        body_start = at + m.end() - 1  # index of opener
        try:
            body, new_i = _read_balanced(text, body_start, opener, closer)
        except ValueError:
            i = at + 1
            continue
        i = new_i

        if kind in {"comment", "preamble", "string"}:
            continue

        # Entry body: key, field = value, field = value,
        # Extract key up to first comma
        comma = body.find(",")
        if comma == -1:
            continue
        key = body[:comma].strip()
        rest = body[comma + 1 :]

        fields: dict[str, str] = {}
        j = 0
        m2 = len(rest)
        while j < m2:
            # Skip whitespace and commas
            while j < m2 and rest[j] in " \t\n\r,":
                j += 1
            if j >= m2:
                break
            # Read field name
            name_match = re.match(r"([A-Za-z][A-Za-z0-9_\-]*)\s*=\s*", rest[j:])
            if not name_match:
                break
            fname = name_match.group(1).lower()
            j += name_match.end()
            # Read value
            if j >= m2:
                break
            if rest[j] == "{":
                val, j = _read_balanced(rest, j, "{", "}")
            elif rest[j] == '"':
                # Find matching quote respecting braces
                start = j + 1
                depth = 0
                k = start
                while k < m2:
                    if rest[k] == "{":
                        depth += 1
                    elif rest[k] == "}":
                        depth -= 1
                    elif rest[k] == '"' and depth == 0:
                        break
                    k += 1
                val = rest[start:k]
                j = k + 1
            else:
                # Bareword until comma or end
                k = j
                while k < m2 and rest[k] not in ",\n":
                    k += 1
                val = rest[j:k].strip()
                j = k
            # Normalize whitespace, collapse inner braces
            val = re.sub(r"\s+", " ", val).strip()
            val = val.replace("{", "").replace("}", "")
            fields[fname] = val

        entries.append(Entry(kind=kind, key=key, fields=fields, source_file=str(path)))

    return entries


def entry_to_bibtex(e: Entry) -> str:
    field_order = [
        "author", "title", "booktitle", "journal", "year", "volume", "number",
        "pages", "publisher", "editor", "school", "institution", "address",
        "month", "doi", "url", "isbn", "issn", "eprint", "archiveprefix",
        "primaryclass", "howpublished", "organization", "series", "edition",
        "type", "note",
    ]
    seen = set()
    lines = [f"@{e.kind}{{{e.key},"]
    for fname in field_order:
        if fname in e.fields and e.fields[fname]:
            lines.append(f"  {fname} = {{{e.fields[fname]}}},")
            seen.add(fname)
    for fname, val in e.fields.items():
        if fname in seen or not val:
            continue
        lines.append(f"  {fname} = {{{val}}},")
    lines.append("}")
    return "\n".join(lines)
