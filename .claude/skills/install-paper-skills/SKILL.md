---
name: install-paper-skills
description: One-shot installer for the paper-skills kit. Installs the NotebookLM skill first (and runs its setup), asks the user for a name for their local bibliography folder, scaffolds that folder from bib-template/, then installs the remaining skills (bib-search, bib-classify, bib-upgrade, claim-cite, claims-audit) into ~/.claude/skills/ — wiring every skill to the chosen bibliography path. Activates on /install-paper-skills or "install the paper skills".
user-invocable: true
argument-hint: "(no arguments — the installer will ask you for a bibliography folder name)"
---

# Install the paper-skills kit

You are the **paper-skills installer**. You set up six Claude Code skills plus a
local bibliography workspace, so the user can discover papers, organise a
bibliography, and write papers — and share the exact same setup with colleagues.

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
`bib-classify`, `bib-upgrade`, `claim-cite`, and `claims-audit` skills, plus a
local bibliography folder.

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

Then offer to initialise it as a git repository so the user can version their
bibliography and share it:

```bash
git -C "$BIB_ROOT" init && git -C "$BIB_ROOT" add -A && git -C "$BIB_ROOT" commit -m "Initial bibliography scaffold"
```

(Only run this if the user says yes.)

## Step 4 — Install the remaining skills

For each of `bib-search`, `bib-classify`, `bib-upgrade`, `claim-cite`,
`claims-audit`:

1. Copy the skill folder into `$SKILLS_DIR`.
2. Substitute the bibliography path placeholder. Every distributed skill file
   contains the literal token `__BIB_ROOT__`; replace it with the absolute
   `BIB_ROOT` path:

```bash
for name in bib-search bib-classify bib-upgrade claim-cite claims-audit; do
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
   `bib-search`, `bib-classify`, `bib-upgrade`, `claim-cite`, `claims-audit`,
   `install-paper-skills`.
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

## Notes

- Re-running this installer is safe: it asks before overwriting anything.
- Skills are plain Markdown. The bibliography tools are plain Python (standard
  library only). Nothing here phones home.
- If the user is on a system without `git`, skip Step 3's git init — it is
  optional.
