# Paper template

A minimal LaTeX article, meant to be the starting point for a new paper.

## Use it

1. Copy this folder into your bibliography workspace as a new paper:
   `<bib-root>/papers/<paper-name>/`. The folder name (`<paper-name>`) is the
   label the skills use — e.g. `/bib-search --for-paper <paper-name>` and
   `/claims-audit --venue <paper-name>`.
2. Edit `main.tex` — title, authors, and the section content.
3. Build it:
   - **VS Code:** install the *LaTeX Workshop* extension and just save
     `main.tex` — it builds and shows a live PDF preview.
   - **Command line:** `pdflatex main && bibtex main && pdflatex main && pdflatex main`.

## Bibliography

`refs.bib` holds this paper's references. You rarely edit it by hand — from
Claude Code, run:

```
/bib-search "<topic>" --for-paper <paper-name>
```

It finds the paper, downloads the PDF, and appends a correctly-formatted entry
to both this `refs.bib` and your master catalog. Then cite it in `main.tex` with
`\citep{key}` or `\citet{key}`.

To pressure-test the draft before submission:

```
/bib-upgrade --for-paper <paper-name>     # refresh preprint -> published refs
/claims-audit --venue <paper-name>        # check every \cite actually supports its claim
```
