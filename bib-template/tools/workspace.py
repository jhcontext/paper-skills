#!/usr/bin/env python3
"""Workspace resolution for the paper-skills kit.

A *workspace* is a bibliography folder (the "bib root") plus optional linked
papers folders. Each bib root carries a non-secret `.paper-skills.json` that
says where its PDFs sync (S3) and which NotebookLM profile to use. A papers
folder carries a tiny `.paper-skills.json` whose only job is to point at its
bib root via the "bib_root" key.

Two ways this module is used:

  * Imported by the other tools to choose the right BIB_ROOT. They honour an
    optional PAPER_SKILLS_BIB_ROOT env override, else fall back to the folder
    the tool itself lives in (parent.parent) — so single-workspace installs
    keep working with zero config.

  * Run as a CLI by the SKILL.md files to resolve, from the user's current task
    (a --from paper folder or CWD), which workspace applies and print its merged
    config as JSON.

NO SECRETS ever live in .paper-skills.json — only bucket / profile *names*.
AWS credentials stay in ~/.aws ; NotebookLM auth stays in ~/.notebooklm.

Config shape (bib root):
    {
      "bib_root": ".",
      "s3": { "bucket": "...", "prefix": "pdfs/", "region": "us-east-1",
              "aws_profile": "jhcontext" },
      "notebooklm": { "profile": "default" }
    }
Config shape (papers folder):
    { "bib_root": "../jhcontext-bib" }
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

CONFIG_NAME = ".paper-skills.json"


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def find_config_dir(start: Path) -> Path | None:
    """Walk up from `start` until a directory containing CONFIG_NAME is found."""
    start = start.resolve()
    cur = start if start.is_dir() else start.parent
    for d in [cur, *cur.parents]:
        if (d / CONFIG_NAME).is_file():
            return d
    return None


def bib_root_default(tool_file: str) -> Path:
    """BIB_ROOT a tool should operate on when invoked directly.

    Honours PAPER_SKILLS_BIB_ROOT (set by a skill that already resolved the
    target workspace); otherwise the folder two levels up from the tool, i.e.
    the bib root this tools/ dir was scaffolded into.
    """
    override = os.environ.get("PAPER_SKILLS_BIB_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path(tool_file).resolve().parent.parent


def resolve(start: Path, default: Path | None = None) -> dict:
    """Resolve the workspace that applies to `start`.

    Returns a dict: {workspace_dir, bib_root, s3, notebooklm, source}.
    `source` is "config" (found a .paper-skills.json), "fallback" (used the
    provided default bib root), or "none".
    The bib root's own config is authoritative for s3 / notebooklm.
    """
    cfg_dir = find_config_dir(start)
    if cfg_dir is not None:
        cfg = _load_json(cfg_dir / CONFIG_NAME)
        bib_root = (cfg_dir / cfg.get("bib_root", ".")).resolve()
        bib_cfg = _load_json(bib_root / CONFIG_NAME)
        return {
            "workspace_dir": str(cfg_dir),
            "bib_root": str(bib_root),
            "s3": bib_cfg.get("s3") or cfg.get("s3"),
            "notebooklm": bib_cfg.get("notebooklm") or cfg.get("notebooklm") or {"profile": "default"},
            "source": "config",
        }
    if default is not None:
        bib_root = Path(default).expanduser().resolve()
        bib_cfg = _load_json(bib_root / CONFIG_NAME)
        return {
            "workspace_dir": None,
            "bib_root": str(bib_root),
            "s3": bib_cfg.get("s3"),
            "notebooklm": bib_cfg.get("notebooklm") or {"profile": "default"},
            "source": "fallback",
        }
    return {"workspace_dir": None, "bib_root": None, "s3": None,
            "notebooklm": {"profile": "default"}, "source": "none"}


def _main(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Resolve the active paper-skills workspace.")
    p.add_argument("cmd", nargs="?", default="resolve", choices=["resolve"])
    p.add_argument("--from", dest="frm", default=None,
                   help="path to resolve from (a paper folder or file); default CWD")
    p.add_argument("--default", dest="default", default=None,
                   help="fallback bib root if no .paper-skills.json is found")
    p.add_argument("--field", default=None,
                   help="print just one resolved field (e.g. bib_root) instead of JSON")
    args = p.parse_args(argv)

    start = Path(args.frm).expanduser() if args.frm else Path.cwd()
    default = Path(args.default).expanduser() if args.default else None
    info = resolve(start, default)

    if args.field:
        val = info.get(args.field)
        if val is None:
            return 1
        print(val if isinstance(val, str) else json.dumps(val))
        return 0
    print(json.dumps(info, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
