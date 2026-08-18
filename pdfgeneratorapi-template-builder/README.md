# PDF Generator API Template Builder

An Agent Skill that turns a description — or an existing document — into a valid
[PDF Generator API](https://pdfgeneratorapi.com) template definition, together with the example
dataset your application has to produce.

Without it, an agent writing template JSON guesses at a component model it has never seen: invented
`cls` names, page-absolute coordinates, tables whose columns don't add up, placeholders in the wrong
scope. This skill supplies the official JSON schema, a distilled component reference, two authoring
playbooks and deterministic scripts that measure, hydrate and validate — so the output imports and
renders instead of erroring.

## What you get

Every run delivers two files:

| File | Purpose |
| --- | --- |
| `*-template.json` | The template definition — hydrated into the shape the import endpoint expects, schema-valid and lint-clean. |
| `*-data.json` | A matching example dataset where every placeholder resolves and list arrays hold 3+ items, so repetition and pagination are visible. Doubles as the integration contract for your application. |

Plus a summary of the data fields your application must send.

## Install

### Claude Code

```bash
git clone https://github.com/pdfgeneratorapi/skills.git
mkdir -p ~/.claude/skills
cp -r skills/pdfgeneratorapi-template-builder/source ~/.claude/skills/pdfgeneratorapi-template-builder
```

Use a repository's `.claude/skills/` instead of `~/.claude/skills/` to share it with your team. Start
a new session afterwards; the skill activates by itself when a request matches its description.

### Claude apps (web, desktop)

Upload `pdfgeneratorapi-template-builder.skill` under **Settings → Capabilities → Skills**. The
bundle is a plain zip — rename it to `.zip` if the uploader insists.

## The two paths

The skill picks a path from how you ask.

### Path A — from a description

You describe the document; the skill designs it. Best when there is no source artwork and you want
something that looks professionally laid out.

> *"Create a PDF Generator API template for an A4 invoice: our logo top-left, seller and buyer
> blocks, a line-item table with description / qty / unit price / total, totals under it, payment
> terms in the footer. Accent color #0F62FE."*

> *"Build a shipping label template, 10 × 15 cm, with a Code 128 barcode of the tracking number."*

Expect at most one round of questions — page size, your data model, branding — then it designs
against sensible defaults. **If you already have example JSON from your application, paste it**: the
template gets built against your real field names instead of invented ones.

### Path B — replicate a document

You attach a PDF, Word file or image; the skill reproduces it and turns the variable parts into
placeholders. Fidelity comes from measurement, not eyeballing — geometry is extracted from the PDF in
centimeters, colors and fonts carried over, and a page render is inspected for alignment.

> *"Convert this invoice PDF into a PDF Generator API template — keep the layout exactly, make names,
> dates, amounts and line items data fields."* (attach the PDF)

Input notes: PDFs are measured directly; `.docx` is converted with LibreOffice first; images have no
extractable coordinates, so positions are estimated proportionally and the summary says so.

### Also: validate or fix an existing template

> *"Validate this template definition and fix the layout errors."* (attach or paste the JSON)

Runs the schema check plus the layout lint — bounds, overlaps, table column sums, missing font
styling, malformed formatters, placeholders that don't resolve against your data.

## What happens under the hood

1. Pick the path (description vs. document) and read the matching playbook.
2. Read the component reference — never write the JSON from memory of another template system.
3. Build the template sparse and readable, then the example data.
4. Hydrate: `hydrate_template.py` fills the full editor property shape, editor-style `zindex` values
   and the top-level/page fields. Sparse-but-schema-valid templates can fail import; hydration is the
   build step that prevents it.
5. Validate with `validate_template.py --data ...` and fix until clean — warnings included, they
   encode layout-quality rules.
6. Deliver both files and list the required data fields.

Everything is local. No API key, no network call, no data leaving the machine.

## Using the result

The delivered `*-template.json` is a complete template definition: import it into your PDF Generator
API workspace, or create it through the API and then merge it with your own data to render PDFs. See
the [API documentation](https://docs.pdfgeneratorapi.com). Open it in the editor afterwards — the
output follows editor conventions (hydrated properties, `dataIndex` + `{value}` binding, static
header rows), so it stays editable by hand.

## Running the scripts yourself

The four scripts are ordinary CLIs — useful outside an agent session too.

```bash
cd source
```

| Command | What it does |
| --- | --- |
| `python3 scripts/measure_pdf.py in.pdf -o m.json --images-dir imgs/` | Extracts text spans, rectangles, lines and images from a PDF with geometry in cm, plus embedded images to a folder. Add `--render page1.png` to rasterize page 1 for a visual check. |
| `python3 scripts/validate_template.py t.json --data d.json` | JSON Schema validation, layout lint, and placeholder-vs-data cross-check. Exit 0 = no errors (warnings allowed), 1 = errors. |
| `python3 scripts/hydrate_template.py t.json --in-place` | Fills missing properties with editor defaults — only adds keys, never overwrites authored values. `-o out.json` to write a copy instead. |
| `python3 scripts/svg_to_image.py shape.svg --png preview.png` | Renders an SVG to a base64 PNG data URI for an `imageComponent` — the way to reproduce curves, blobs, wave dividers and badges the format can't draw. Reads stdin with `-`. |

### Requirements

Python 3. Dependencies are optional and per-script; missing ones degrade with a warning rather than
crashing.

| Package | Needed for |
| --- | --- |
| `jsonschema` (4.0+) | the schema half of `validate_template.py` — lint rules still run without it |
| `pymupdf` | `measure_pdf.py` |
| `cairosvg` | `svg_to_image.py` |

```bash
pip install "jsonschema>=4" pymupdf cairosvg
```

Path B with a Word source additionally needs LibreOffice (`soffice`) for the `.docx` → PDF step.

## Three things that trip everyone up

Full detail lives in `source/references/components.md`; these are the ones worth knowing before you
read any generated template.

- **Placeholders nest with `::`.** `{buyer::name}` reads `buyer.name`. Inside a table or container
  that iterates `line_items`, cells are item-relative — `{sku}`, not `{line_items::sku}`.
- **Coordinates start inside the margins.** `top: 0, left: 0` is the top-left of the margin box, so on
  A4 with 1 cm margins the usable area is 19 × 27.7 cm and a full-width component is
  `left: 0, width: 19`. Adding the margin back pushes content off the page.
- **Layout flows vertically.** Authored gaps are preserved, so when a table gains rows everything
  below shifts down by the same amount. Anything that must hold its position — logos, page numbers,
  color bands, background artwork — belongs in a `headerComponent`/`footerComponent`, which also
  repeats automatically on overflow pages.

## What's in the skill

```
source/
├── SKILL.md                        # the workflow the agent follows, and its trigger description
├── references/
│   ├── components.md               # every component: cls names, required fields, units, defaults
│   ├── template-schema.json        # the official template JSON schema
│   ├── from-description.md         # Path A playbook — design discipline, grid, component choices
│   └── from-document.md            # Path B playbook — measure, identify structure, data vs static
├── scripts/
│   ├── measure_pdf.py              # PDF -> geometry in cm
│   ├── hydrate_template.py         # sparse JSON -> import-safe shape
│   ├── validate_template.py        # schema + layout lint + data cross-check
│   └── svg_to_image.py             # SVG -> base64 PNG data URI
└── examples/
    ├── invoice-template.json       # validated reference pair: header/footer, styled line-item
    └── invoice-data.json           # table, nested placeholders, number formatting, page numbers
```

`references/` is loaded on demand, so the skill costs little context until it is actually working.

## Delivery through the API (opt-in)

The default and recommended path is local files. If you have the PDF Generator API MCP connector
configured and explicitly ask — *"push this template to my account via MCP"* — the skill can create
the template in your workspace instead: a skeleton via `storeTemplate`, components added in batches,
then a structure read-back to verify. It asks for your organization and user IDs each session and
never stores them. It will not touch the connector unless you ask.
