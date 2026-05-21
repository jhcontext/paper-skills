#!/usr/bin/env python3
"""Heuristic theme classifier for bibliography entries.

Takes a title + optional abstract + keywords string and returns the most likely
theme folder name. Keyword-based; falls back to `_unclassified` when confidence
is too low.

The theme list below is a starting taxonomy aimed at AI / CS research. Edit the
THEMES list (and the matching folders under pdfs/) to fit your own field.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ordered by specificity — more specific themes first so they win ties.
# Each theme has weighted keywords; higher weight = stronger signal.
# Keywords are matched against title + abstract + keywords + booktitle/journal/note + author.
THEMES: list[tuple[str, dict[str, int]]] = [
    ("healthcare-fhir", {
        "fhir": 5, "hl7": 4, "ehr": 4, "electronic health record": 4,
        "ehds": 5, "clinical": 2, "telemedicine": 3, "telehealth": 3,
        "e-health": 3, "ehealth": 3, "patient": 2, "medical": 2,
        "healthcare": 3, "health data space": 5, "pharmacovigilance": 4,
        "radiology": 3, "diagnostic": 2, "oncology": 3,
        "health": 1, "hospital": 3, "mental health": 3,
    }),
    ("provenance", {
        "provenance": 5, "prov-dm": 5, "prov-o": 5, "prov-agent": 5,
        "lineage": 4, "audit trail": 4, "w3c prov": 5, "data lineage": 4,
        "traceability": 3, "reproducibility": 2, "workflow provenance": 5,
        "audit": 2, "accountability": 2,
    }),
    ("agents-mas", {
        "multi-agent": 5, "multiagent": 5, "mas ": 3, "agent protocol": 5,
        "agent communication": 4, "agent-to-agent": 5, "a2a": 4,
        "mcp": 3, "model context protocol": 5, "fipa": 5, "acl": 3,
        "kqml": 5, "agentic": 3, "agent system": 3, "autonomous agent": 4,
        "agent orchestration": 4, "tool use": 2, "tool-use": 2,
        "llm agent": 4, "ai agent": 3,
    }),
    ("formal-methods", {
        "model checking": 5, "temporal logic": 5, "atl": 3,
        "alternating-time": 5, "formal verification": 5, "theorem proving": 5,
        "proof assistant": 4, "satisfiability": 3, "smt solver": 4,
        "bisimulation": 4, "process calculus": 4,
    }),
    ("semantic-web-kg", {
        "sparql": 5, "owl ": 4, "ontology": 3, "knowledge graph": 4,
        "rdf": 4, "semantic web": 4, "linked data": 4, "description logic": 5,
        "shacl": 5,
    }),
    ("ethics-governance", {
        "ai ethics": 4, "ethical ai": 4, "responsible ai": 4,
        "ai act": 5, "eu ai act": 5, "ai governance": 4, "ai4people": 5,
        "floridi": 5, "coeckelbergh": 5, "mittelstadt": 5, "binns": 4,
        "jobin": 5, "barocas": 4, "buolamwini": 5,
        "trustworthy ai": 4, "algorithmic accountability": 4,
        "algorithmic fairness": 4, "bias": 2, "fairness": 3, "model card": 4,
        "risk management framework": 3, "nist ai rmf": 5,
        "regulation": 2, "policy": 1, "stakeholder": 1,
        "ethics": 3, "moral": 3, "responsibility": 2, "governance": 3,
        "transparency": 2, "oecd ai": 5,
    }),
    ("security-compliance", {
        "gdpr": 5, "privacy": 3, "differential privacy": 4,
        "homomorphic encryption": 5, "federated learning": 3,
        "adversarial attack": 4, "data protection": 3, "compliance": 2,
        "legal framework": 3, "regulatory": 2, "jailbreak": 4,
        "prompt injection": 5, "red team": 3,
        "cybersecurity": 4, "threat model": 3,
    }),
    ("context-engineering", {
        "context window": 5, "prompt caching": 5, "long-context": 4,
        "context management": 4, "context compression": 5,
        "memory architecture": 4, "retrieval-augmented": 3, "rag ": 2,
        "in-context learning": 4, "context engineering": 5,
    }),
    ("llms-foundation", {
        "large language model": 4, "llm": 2, "transformer": 3,
        "foundation model": 4, "gpt-": 3, "bert": 3, "llama": 3,
        "mixture of experts": 4, "scaling law": 4, "pretraining": 3,
        "instruction tuning": 4, "rlhf": 4, "chain-of-thought": 4,
        "reasoning": 1, "benchmark": 1, "representation learning": 4,
        "language model": 2, "pre-trained": 3,
    }),
    ("surveys-methodology", {
        "prisma": 5, "prisma 2020": 5, "prisma-s": 5,
        "systematic review": 4, "systematic literature review": 5,
        "slr ": 3, "scoping review": 4, "meta-analysis": 4,
        "survey": 2, "taxonomy": 2, "state-of-the-art": 2, "state of the art": 2,
    }),
    ("hci-society", {
        "human-ai interaction": 5, "human-computer interaction": 4,
        "hci ": 3, "sociotechnical": 5, "labor": 2, "workforce": 2,
        "participatory design": 4, "user experience": 2, "ux ": 2,
        "cognitive load": 3, "user study": 3, "interaction design": 3,
        "learning analytics": 4, "education": 2, "classroom": 3,
        "co-design": 4, "co-designing": 4,
    }),
]

MIN_CONFIDENCE = 3  # top theme must score at least this much


def classify(text: str) -> tuple[str, dict[str, int]]:
    """Return (theme, per_theme_scores). Theme is `_unclassified` if low signal."""
    t = text.lower()
    scores: dict[str, int] = {}
    for theme, kws in THEMES:
        score = 0
        for kw, w in kws.items():
            if kw in t:
                score += w
        scores[theme] = score

    best = max(scores.items(), key=lambda kv: kv[1])
    if best[1] < MIN_CONFIDENCE:
        return "_unclassified", scores
    return best[0], scores


def classify_entry_fields(fields: dict[str, str]) -> str:
    text = " ".join(
        fields.get(k, "") for k in ("title", "abstract", "keywords", "booktitle", "journal", "note", "author")
    )
    theme, _ = classify(text)
    return theme


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: classify_theme.py '<title + abstract text>'", file=sys.stderr)
        print("   or: classify_theme.py --bibkey <master_key>", file=sys.stderr)
        return 2

    if argv[1] == "--bibkey" and len(argv) >= 3:
        sys.path.insert(0, str(Path(__file__).parent))
        from _bibparse import parse_bibfile  # noqa: E402
        bib_root = Path(__file__).resolve().parent.parent
        entries = parse_bibfile(bib_root / "refs.bib")
        target = argv[2]
        match = next((e for e in entries if e.key == target), None)
        if not match:
            print(f"not found: {target}", file=sys.stderr)
            return 1
        theme = classify_entry_fields(match.fields)
        print(theme)
        return 0

    text = " ".join(argv[1:])
    theme, scores = classify(text)
    print(theme)
    for th, sc in sorted(scores.items(), key=lambda kv: -kv[1])[:5]:
        print(f"  {th:<22} {sc}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
