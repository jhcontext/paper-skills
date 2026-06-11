#!/usr/bin/env python3
"""Sync a workspace's PDF library to/from S3.

Thin, dependency-free wrapper over the `aws s3 sync` CLI (no boto3). Reads the
non-secret S3 settings from the workspace's `.paper-skills.json` (bucket,
prefix, region, aws_profile) and syncs `<bib_root>/pdfs/` against
`s3://<bucket>/<prefix>`. Credentials are never read here — they live in
~/.aws and are selected by the named aws_profile.

Usage:
  s3_sync.py pull   [--bib-root PATH | --from PATH]   # bucket -> local
  s3_sync.py push   [--bib-root PATH | --from PATH]   # local  -> bucket
  s3_sync.py status [--bib-root PATH | --from PATH]   # dry-run diff, both ways

Exit codes:
  0  success (incl. local-only workspace = nothing to do)
  2  misconfig / aws CLI missing / profile not authenticated (prints fix hint)
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from workspace import bib_root_default, resolve, _load_json, CONFIG_NAME  # noqa: E402


def _s3_settings(bib_root: Path) -> dict | None:
    cfg = _load_json(bib_root / CONFIG_NAME)
    return cfg.get("s3")


def _preflight(profile: str | None) -> None:
    if shutil.which("aws") is None:
        print("[s3_sync] AWS CLI not found. Install it: "
              "https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html",
              file=sys.stderr)
        sys.exit(2)
    cmd = ["aws", "sts", "get-caller-identity"]
    if profile:
        cmd += ["--profile", profile]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        hint = f"aws configure --profile {profile}" if profile else "aws configure"
        print(f"[s3_sync] AWS profile not authenticated. Run:\n    {hint}\n"
              f"(aws said: {r.stderr.strip()})", file=sys.stderr)
        sys.exit(2)


def _sync(src: str, dst: str, s3: dict, dryrun: bool) -> int:
    cmd = ["aws", "s3", "sync", src, dst]
    if s3.get("region"):
        cmd += ["--region", s3["region"]]
    if s3.get("aws_profile"):
        cmd += ["--profile", s3["aws_profile"]]
    if dryrun:
        cmd += ["--dryrun"]
    return subprocess.run(cmd).returncode


def main(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Sync workspace PDFs to/from S3.")
    p.add_argument("cmd", choices=["pull", "push", "status"])
    p.add_argument("--bib-root", default=None, help="bib root to sync (skips discovery)")
    p.add_argument("--from", dest="frm", default=None,
                   help="resolve workspace from this path (a paper folder); default CWD")
    args = p.parse_args(argv)

    if args.bib_root:
        bib_root = Path(args.bib_root).expanduser().resolve()
    else:
        start = Path(args.frm).expanduser() if args.frm else Path.cwd()
        info = resolve(start, default=bib_root_default(__file__))
        bib_root = Path(info["bib_root"])

    s3 = _s3_settings(bib_root)
    if not s3 or not s3.get("bucket"):
        print(f"[s3_sync] Workspace {bib_root} is local-only (no \"s3\" block in "
              f"{CONFIG_NAME}). Nothing to sync.")
        return 0

    bucket = s3["bucket"]
    prefix = s3.get("prefix", "pdfs/")
    if not prefix.endswith("/"):
        prefix += "/"
    remote = f"s3://{bucket}/{prefix}"
    local = str(bib_root / "pdfs") + "/"

    _preflight(s3.get("aws_profile"))

    if args.cmd == "pull":
        print(f"[s3_sync] pull  {remote}  ->  {local}")
        return _sync(remote, local, s3, dryrun=False)
    if args.cmd == "push":
        print(f"[s3_sync] push  {local}  ->  {remote}")
        return _sync(local, remote, s3, dryrun=False)
    # status
    print(f"[s3_sync] status for {bib_root} (dry-run; no files transferred)")
    print(f"--- would PULL (remote -> local) {remote} ---")
    _sync(remote, local, s3, dryrun=True)
    print(f"--- would PUSH (local -> remote) {local} ---")
    _sync(local, remote, s3, dryrun=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
