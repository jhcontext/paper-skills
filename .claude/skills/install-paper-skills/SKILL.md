---
name: install-paper-skills
description: One-shot installer for the paper-skills kit. Installs the NotebookLM skill first (and runs its setup), asks the user for a name for their local bibliography folder, scaffolds that folder from bib-template/, optionally connects cloud PDF sync (S3), then installs the remaining skills (bib-search, bib-snowball, bib-classify, bib-upgrade, claim-cite, claims-audit, bib-sync) into ~/.claude/skills/ — wiring every skill to the chosen bibliography path. Activates on /install-paper-skills or "install the paper skills".
user-invocable: true
argument-hint: "(no arguments — the installer will ask you for a bibliography folder name)"
---

# Install the paper-skills kit

You are the **paper-skills installer**. You set up eight Claude Code skills plus
a local bibliography workspace, so the user can discover papers, organise a
bibliography, sync a shared PDF library, and write papers — and share the exact
same setup with colleagues.

Run the steps below **in order**. Confirm with the user before any step that
overwrites an existing install.

## Step 0 — Locate the repo and the skills directory

This skill file lives at `<repo>/.claude/skills/install-paper-skills/SKILL.md`.

1. Set `REPO` to the repository root — the directory that contains both `skills/`
   and `bib-template/`. It is normally the folder the user opened in their
   editor (the current working directory). Verify by checking that
   `<REPO>/skills/notebooklm/SKILL.md` and `<REPO>/bib-template/tools/` exist. If
   they don't, ask the user where they cloned the `paper-skills` repo.
2. Set `SKILLS_DIR="$HOME/.claude/skills"` and `mkdir -p "$SKILLS_DIR"`.

Tell the user what you're about to install: the `notebooklm`, `bib-search`,
`bib-snowball`, `bib-classify`, `bib-upgrade`, `claim-cite`, `claims-audit`, and
`bib-sync` skills, plus a local bibliography folder.

## Step 1 — Install NotebookLM first (and set it up)

1. Copy the NotebookLM skill:
   ```bash
   mkdir -p "$SKILLS_DIR/notebooklm"
   cp "$REPO/skills/notebooklm/SKILL.md" "$SKILLS_DIR/notebooklm/SKILL.md"
   ```
2. Now perform the NotebookLM setup. Read `$SKILLS_DIR/notebooklm/SKILL.md` and
   follow its **"Step 0: Setup"** section in full: check Python ≥ 3.10, create
   the `~/.notebooklm-venv` virtual environment, `pip install
   "notebooklm-py[browser]"`, run `playwright install chromium`, symlink the CLI
   onto PATH, and walk the user through the browser-based Google sign-in.
3. If the user prefers to defer the Google sign-in, that's fine — the skill is
   installed and they can authenticate later by running `/notebooklm`. Note this
   and continue.

## Step 2 — Ask for the bibliography folder

Ask the user two things (offer the defaults, let them override):

- **Folder name** for their local bibliography. Default suggestion: `paper-bib`.
- **Location** — the parent directory. Default: `~/Repos/` if it exists,
  otherwise `~/`.

Compute `BIB_ROOT` as the absolute path `<location>/<folder-name>` (expand `~`).
Read it back to the user for confirmation, e.g. `/home/<user>/Repos/paper-bib`.

If `BIB_ROOT` already exists and is non-empty, do **not** overwrite it — ask the
user whether to (a) reuse it as-is, (b) pick a different name, or (c) refresh
only the `tools/` folder inside it.

## Step 3 — Scaffold the bibliography folder

Copy the template into the chosen location:

```bash
cp -r "$REPO/bib-template/" "$BIB_ROOT"
```

The bibliography tools resolve their own location relative to `tools/`, so **no
path substitution is needed inside `BIB_ROOT`** — it works wherever the user put
it, even if they later rename or move the folder.

The scaffold includes a `.paper-skills.json` workspace config (local-only by
default). The next step optionally adds cloud sync.

Then offer to initialise it as a git repository so the user can version their
bibliography and share it. **Keep PDFs out of git** (they're heavy and belong in
S3) — the template's `.gitignore` should ignore `pdfs/`:

```bash
git -C "$BIB_ROOT" init && git -C "$BIB_ROOT" add -A && git -C "$BIB_ROOT" commit -m "Initial bibliography scaffold"
```

(Only run this if the user says yes.)

## Step 3b — Optional: connect cloud PDF sync (S3) and NotebookLM profile

PDFs don't travel through git — they sync via S3 so a team shares one library.
Ask the user: **"Do you have a shared S3 bucket for the PDF library?"**

**If yes**, ask for (offer sensible defaults):
- **Bucket name** (e.g. `jhcontext-bib-pdfs`).
- **Region** (default `us-east-1`).
- **Prefix** (default `pdfs/`).
- **AWS profile name** to use (e.g. `jhcontext` for a shared bucket someone gave
  them keys for, or `default`). Stress that this is only a *name* — the secret
  keys are configured separately and never stored here.

Write these into `$BIB_ROOT/.paper-skills.json`, merging with the existing file.
The result should look like:

```json
{
  "bib_root": ".",
  "s3": { "bucket": "<bucket>", "prefix": "pdfs/", "region": "<region>",
          "aws_profile": "<profile>" },
  "notebooklm": { "profile": "default" }
}
```

Then tell the user to configure the credentials they were given (Access Key ID +
Secret) and verify:

```bash
aws configure --profile <profile>      # paste the keys; region <region>; output json
python3 "$BIB_ROOT/tools/s3_sync.py" status --bib-root "$BIB_ROOT"   # confirm it lists the diff
```

If they want to **pull the shared library now**:
```bash
python3 "$BIB_ROOT/tools/s3_sync.py" pull --bib-root "$BIB_ROOT"
```

**If no**, leave the config local-only — `/bib-sync` will no-op and they can run
`/bib-sync --setup` any time later to connect a bucket (their own or a shared one).

**NotebookLM profile:** if the user authenticated NotebookLM under a non-default
profile in Step 1, set `"notebooklm": { "profile": "<name>" }` in the same file.
Collaborators querying *shared* notebooks just use their own login here — the
owner shares the notebooks to their Google account (see the `/notebooklm`
skill's **Team access** section).

## Step 4 — Install the remaining skills

For each of `bib-search`, `bib-snowball`, `bib-classify`, `bib-upgrade`,
`claim-cite`, `claims-audit`:

1. Copy the skill folder into `$SKILLS_DIR`.
2. Substitute the bibliography path placeholder. Every distributed skill file
   contains the literal token `__BIB_ROOT__`; replace it with the absolute
   `BIB_ROOT` path:

```bash
for name in bib-search bib-snowball bib-classify bib-upgrade claim-cite claims-audit bib-sync; do
  mkdir -p "$SKILLS_DIR/$name"
  cp "$REPO/skills/$name/SKILL.md" "$SKILLS_DIR/$name/SKILL.md"
  sed -i "s|__BIB_ROOT__|$BIB_ROOT|g" "$SKILLS_DIR/$name/SKILL.md"
done
```

(On macOS the `sed` flag differs: use `sed -i '' "s|...|...|g"`.)

After the loop, confirm the placeholder is gone:

```bash
grep -rl "__BIB_ROOT__" "$SKILLS_DIR" || echo "OK — no placeholders left"
```

## Step 5 — Install this installer skill itself

So `/install-paper-skills` stays available after the repo is closed:

```bash
mkdir -p "$SKILLS_DIR/install-paper-skills"
cp "$REPO/.claude/skills/install-paper-skills/SKILL.md" "$SKILLS_DIR/install-paper-skills/SKILL.md"
```

## Step 6 — Verify and report

1. List the installed skills: `ls "$SKILLS_DIR"` — expect `notebooklm`,
   `bib-search`, `bib-snowball`, `bib-classify`, `bib-upgrade`, `claim-cite`,
   `claims-audit`, `bib-sync`, `install-paper-skills`.
2. Confirm the bibliography tools run against the empty scaffold:
   ```bash
   python3 "$BIB_ROOT/tools/build_catalog.py"
   ```
   It should report `0 rows` and exit cleanly.
3. Print a summary to the user:
   - Where the bibliography folder is (`BIB_ROOT`).
   - Which skills are installed.
   - That they should **restart Claude Code** (or reload the window) so the new
     slash commands appear.
   - Suggested first command: `/bib-search "<a topic you care about>"`.
   - To start writing a paper: copy the repo's `paper-template/` into
     `<BIB_ROOT>/papers/<paper-name>/`.

## Retrofitting an existing install (add S3 / NotebookLM to a folder you already have)

If the user already has a bibliography folder from a previous install and only
wants to **connect cloud sync** (not rescaffold), do the minimal path:

1. Set `BIB_ROOT` to their existing folder.
2. Refresh the helper tools so `workspace.py` + `s3_sync.py` are present:
   ```bash
   cp "$REPO/bib-template/tools/workspace.py" "$REPO/bib-template/tools/s3_sync.py" "$BIB_ROOT/tools/"
   ```
3. Ensure a `.paper-skills.json` exists at `BIB_ROOT` (create
   `{ "bib_root": ".", "notebooklm": { "profile": "default" } }` if missing).
4. Run **Step 3b** to add the `s3` block.
5. Install/refresh the `bib-sync` skill (the Step 4 loop, or just that one name).

Equivalent shortcut once `bib-sync` is installed: `/bib-sync --setup`.

## Notes

- Re-running this installer is safe: it asks before overwriting anything.
- Skills are plain Markdown. The bibliography tools are plain Python (standard
  library only). Nothing here phones home.
- **No credentials are ever stored by the kit.** `.paper-skills.json` holds only
  the bucket/profile *names*; AWS keys live in `~/.aws`, NotebookLM auth in
  `~/.notebooklm`.
- If the user is on a system without `git`, skip Step 3's git init — it is
  optional.
