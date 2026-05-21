# Cover image — generation prompts

Prompts for generating a repository cover / social-preview image for
`paper-skills`. Paste one into an image model (e.g. DALL·E, Midjourney, Imagen,
or NotebookLM's infographic generator). A 16:9 or 1280×640 frame works well for
a GitHub social preview.

Both prompts describe the **same composition** — a five-stage research pipeline
plus a knowledge-base hexagon — and differ only in palette:

- **Prompt 1** — a light, clinical, academic-restrained palette.
- **Prompt 2** — a dark, high-contrast, technical-editorial palette.

Pick whichever reads better at thumbnail size.

Shared style: geometry motif is the **hexagon**; any rendered text uses a clean
geometric sans-serif; flat vector style, crisp edges, generous whitespace, no
photorealism, no 3-D bevels.

---

## Prompt 1 — light clinical palette

### Colours (use exactly these)

| Role | Name | Hex |
|---|---|---|
| Canvas / background | Marble White | `#FAF9F6` |
| Anchor / authority — primary mark fill | Imperial Green | `#004B3C` |
| Body text / dark line work | Deep Slate | `#1F2933` |
| Secondary structure — dividers, faint detail | Steel Silver | `#BCC6CC` |
| Accent / soft highlight (≈5% of surface) | Mist Sage | `#D6E2DA` |

No gold, no institutional blue, no pure black (use Deep Slate instead).

### Prompt

> A clean, modern technical illustration on a soft warm off-white background
> (Marble White, `#FAF9F6`), wide 16:9 format. The scene shows an academic
> research workflow as a left-to-right pipeline built from interlocking
> hexagonal tiles outlined in Steel Silver (`#BCC6CC`).
>
> Five hexagon stages flow across the frame, each holding a simple flat-line
> icon drawn in Imperial Green (`#004B3C`):
> 1. **Discover** — a magnifying glass over a stack of paper documents.
> 2. **Organise** — documents sorting into labelled folders.
> 3. **Refresh** — a circular arrow upgrading a document.
> 4. **Cite** — a quotation mark linking a sentence to a source.
> 5. **Write** — a paper page with neat text lines and a title block.
>
> Above the pipeline, a sixth, larger hexagon represents a knowledge base:
> inside it, small document nodes connected by thin lines into a constellation,
> with faint concentric rings suggesting semantic / vector search radiating
> from a central query point. The knowledge hexagon is filled with a soft Mist
> Sage (`#D6E2DA`) surface, its nodes and rings drawn in Imperial Green
> (`#004B3C`). A thin Imperial Green line connects this knowledge hexagon down
> into the "Cite" and "Write" stages, showing that grounded evidence feeds the
> writing.
>
> Subtle structural lines in Steel Silver (`#BCC6CC`) run faintly through the
> background, barely visible, suggesting structured intelligence. Filled
> surfaces and any labels sit in Deep Slate (`#1F2933`) for text and Imperial
> Green for shapes. High contrast, flat vector style, crisp edges, lots of
> negative space, no photorealism, no 3-D bevels, no gold, no institutional
> blue, no pure black — the only soft glow is a faint Mist Sage halo on the
> knowledge hexagon.
>
> Optional title text, set in a geometric sans-serif, upper area:
> **"paper-skills"** in Deep Slate (`#1F2933`), with a smaller line beneath in
> Imperial Green (`#004B3C`): *"discover · organise · cite · write"*.

---

## Prompt 2 — dark technical palette

### Colours (use exactly these)

| Role | Name | Hex |
|---|---|---|
| Primary background / structure | Deep Circuit Slate | `#1F2933` |
| Primary accent / call-to-action | Context Gold | `#EBB42C` |
| Secondary line work | Structural Blue | `#546E7A` |
| Secondary highlight / glow | Active Glow | `#FBD97D` |
| Deep neutral / shadow | Engineered Ink | `#263238` |
| Light surface / text on dark | Paper White | `#F5F7F9` |

### Prompt

> A clean, modern technical illustration on a deep slate background
> (`#1F2933`), wide 16:9 format. The scene shows an academic research workflow
> as a left-to-right pipeline built from interlocking hexagonal tiles outlined
> in structural blue (`#546E7A`).
>
> Five hexagon stages flow across the frame, each holding a simple flat-line
> icon glowing in Context Gold (`#EBB42C`):
> 1. **Discover** — a magnifying glass over a stack of paper documents.
> 2. **Organise** — documents sorting into labelled folders.
> 3. **Refresh** — a circular arrow upgrading a document.
> 4. **Cite** — a quotation mark linking a sentence to a source.
> 5. **Write** — a paper page with neat text lines and a title block.
>
> Above the pipeline, a sixth, larger hexagon represents a knowledge base:
> inside it, small document nodes connected by thin lines into a constellation,
> with faint concentric rings suggesting semantic / vector search radiating
> from a central query point — rendered in Active Glow (`#FBD97D`). A thin gold
> line connects this knowledge hexagon down into the "Cite" and "Write" stages,
> showing that grounded evidence feeds the writing.
>
> Subtle circuit-trace lines in Engineered Ink (`#263238`) run through the
> background, barely visible, suggesting structured intelligence. Light surfaces
> and any labels are in Paper White (`#F5F7F9`). High contrast, flat vector
> style, crisp edges, lots of negative space, no photorealism, no 3-D bevels,
> no gradients beyond a soft glow on the gold accents.
>
> Optional title text, set in a geometric sans-serif, upper area:
> **"paper-skills"** in Paper White, with a smaller line beneath in Context
> Gold: *"discover · organise · cite · write"*.

---

## Notes

- Keep it readable as a small thumbnail — the five-stage pipeline should still
  parse at social-preview size.
- If the model struggles with six hexagons, drop the title text before dropping
  any pipeline stage; the pipeline is the message.
