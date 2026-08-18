---
name: pdfgeneratorapi-template-builder
description: Create PDF Generator API (pdfgeneratorapi.com) template definitions from a plain-language description OR by replicating an uploaded document (PDF, Word, image). Use this skill whenever the user wants to build, convert, replicate, or fix a PDF Generator API template — including phrases like "create a template", "convert this PDF/invoice/document to a template", "make a pdfgeneratorapi template", "template definition", "template JSON", or when they upload a document and want it reproduced as a data-driven template. Also use it to validate or debug an existing template definition. Contains the official JSON schema, component reference, placeholder notation rules, and a validation script — always consult it before writing any template JSON, even for small edits.
---

# PDF Generator API Template Builder

Build template definitions for PDF Generator API — JSON documents that describe a page layout of positioned components with `{data::field}` placeholders. The API later merges a template with a JSON dataset to produce a PDF.

Every run delivers **two files**: the template definition (`*-template.json`) and a matching example dataset (`*-data.json`) that exercises every placeholder in the template.

## Workflow

1. **Pick the path.** Two entry points, with separate playbooks:
   - User describes what they want in words → read `references/from-description.md`
   - User uploads a document (PDF, Word, image) to replicate → read `references/from-document.md`
2. **Read `references/components.md`** before writing any JSON. It is the distilled component reference: cls names, required fields, units, defaults, and the table/container iteration model. Do not write template JSON from memory of other template systems — the component model here is specific.
3. **Build the template** following the layout rules below.
4. **Build the example data** so that every placeholder in the template resolves, and list arrays have 3+ items so repetition is visible.
5. **Hydrate** with `python3 scripts/hydrate_template.py template.json --in-place`. The import endpoint expects the full editor property shape on every component, not sparse JSON — see "Import-safe output" in components.md. Author sparse for readability, always hydrate before validating.
6. **Validate** with `scripts/validate_template.py` (see Validation below). Fix every error and re-run until clean. Treat warnings seriously — they encode layout-quality rules.
7. Deliver both files and summarize the data fields the user's application must send. File delivery is the default and only path unless the user explicitly asks for MCP delivery (see below).

## MCP delivery (only when explicitly requested)

**Default is always the local workflow above** — bundled schema, local hydration, local validation, file delivery. Do NOT use the pdf-generator-private-api MCP connector, suggest it, or push templates through it unless the user explicitly asks for MCP/API delivery (e.g. "create this via MCP", "push it to my account", "use the pdf-generator-private-api connector"). The connector's presence in the tool list is not a request to use it.

When the user does ask, the verified workflow is: (1) `storeTemplate` with a skeleton — layout, top-level fields, one page with an empty `components` array — passing the raw template definition as `requestBody`; (2) `batchAddComponents` on `pageIndex: 0` in chunks of ~20-25 components; (3) `getTemplateStructure` to verify the count and positions.

Every call requires `organization` and `user` IDs. These are never stored in this skill — ask the user for both at the start of each MCP session before making any call.

Notes for this path: the server fills component defaults itself, so send the **sparse** authored components (skip local hydration — much lighter transfer); the server enforces the canvas-relative coordinate model and rejects out-of-bounds components with a 422, mirroring the local bounds lint; batch responses return only a success message, so IDs come from `getTemplateStructure` afterward; still run the local validator before pushing, since it checks placeholder/data resolution and layout-quality rules the server does not.

## The placeholder notation (memorize this)

Data fields use `{path}` with `::` as the nesting separator:

```json
{"parent": {"child": "test"}, "line_items": [{"sku": "A1", "qty": 2}]}
```

- Access nested value: `{parent::child}`
- A `tableComponent` or `compositeComponent` (container) with `dataIndex: "line_items"` iterates over that array. **Inside** the iterated scope, placeholders are relative to one item: a table cell showing the SKU has `value: "{sku}"` — not `{line_items::sku}`.
- Static text is just plain text in `value`; text can mix both: `"Invoice #{invoice::number}"`.

## Layout rules (non-negotiable)

Geometry is in the template's `layout.unit` (`cm` default, or `in`). Font sizes and border widths are in **pixels**. A4 portrait is 21 × 29.7 cm.

- **Coordinates are relative to the margin box, not the page.** `top: 0, left: 0` is the top-left corner *inside* the margins. The usable area is `(page width − left margin − right margin) × (page height − top margin − bottom margin)`: with A4 and 1 cm margins that is 19 × 27.7 cm, so a full-width component is `left: 0, width: 19`. Positioning content at `left: 1` to "account for" a 1 cm margin double-counts it and pushes right-side components off the page.
- Every component gets explicit `width` and `height` (except the cls-specific exceptions in components.md, e.g. hline has no height, vline no width).
- Nothing may exceed the usable area: `left + width ≤ usable width`, `top + height ≤ usable height`.
- **Vertical flow: the renderer preserves authored gaps.** When a dynamic region grows (a table iterating rows, a flex-height container or label), every component below it shifts down by the same amount — the distance between components stays as designed. So position trailing content by the *gap* you want after the table, not at an absolute "bottom of page" spot: whitespace you leave in the design is whitespace in the render, and a large gap will push trailing content onto the next page. To pin something in place regardless of growth, put it in a `headerComponent`/`footerComponent` (fixed, repeats every page), or set `lockPosition: true` — but a table that flows across pages can overlap a locked component, so prefer header/footer for pinning. **This applies especially to fixed design elements** — background shapes, color bands, full-bleed artwork, footer bars: place them inside the header/footer components, never as page-level components. Page-level decor below a dynamic region gets pushed down with everything else, while header/footer decor stays put AND automatically replicates on every overflow page, keeping the design intact when the table grows.
- Components must not overlap. Styled content blocks (cards, panels, boxed sections) are built as a `compositeComponent` with `backgroundColor`/border holding its content as children — one flowing, always-aligned unit. The only legitimate page-level overlap is a *purely decorative* `rectangleComponent` or image on a lower `zindex`, which must carry `lockPosition: true` so text flow above it cannot push it out of place.
- Text fitting: `useFlexHeight: true` grows a text box with content; `useFlexHeight: false` clips overflow; `dynamicFontSize: true` shrinks the font to fit. In fixed-position layouts use `useFlexHeight: false` + `dynamicFontSize: true` on label/number/date components so overlong values shrink instead of clipping or distorting the layout.
- **Every text/number/date component needs right-side headroom**: never size the box to the exact expected text width. Rendered widths differ from estimates (font metric differences, especially when replicating a document set in another font), and a box even one character too narrow wraps that character to a new line — a single wrapped colon grows the component, shifts the flow, and misaligns the whole page. Add at least 0.35 cm (or ~15%) of slack to the right of the expected text — short prefix labels (e.g. any "Label:" preceding a value) are the most vulnerable.
- Every label, number and date component carries explicit font styling: `fontSize` (required by schema), plus `fontFamily`, `fontColor`, `fontAlign`. When the source gives no styling cue, use schema defaults: `opensans`, `#000000`, `left`, fontSize 12, lineHeight 1.15.
- Table width must equal the sum of its column widths — exactly, in every row.
- If the source document colors table headers, the template's header row cells get that `backgroundColor` (and a matching `fontColor` if the original header text is light). Colors anywhere in the source map to `fontColor`, `backgroundColor`, `borderColor` in the template.
- Reproduce all static text and graphics: horizontal rules as `hlineComponent`, vertical rules as `vlineComponent`, boxes/fills as `rectangleComponent`, images as `imageComponent` with base64 data — or an empty-value image placeholder of the correct size if extraction fails.

## Validation

```bash
python3 scripts/validate_template.py path/to/template.json                    # schema + lint rules
python3 scripts/validate_template.py template.json --data path/to/data.json   # also cross-check placeholders vs data
```

Decorative shapes the template format can't draw — curved corner blobs, wave dividers, badges, organic graphics — are reproduced by rendering an SVG to a base64 PNG with `scripts/svg_to_image.py` (needs `pip install cairosvg`) and embedding it in an `imageComponent` on a low `zindex`; see components.md.

Validation is fully local: the JSON schema check (against `references/template-schema.json`) plus lint rules enforcing the layout rules above (bounds, overlaps, table column sums, missing font styles). Always run with `--data` once the data file exists. (The API's `/templates/validate` endpoint requires authentication, so it is not part of this workflow; if the user has credentials and wants a server-side check, they can POST the template there themselves.)

Never hand over a template that fails validation. If a schema error is confusing, open `references/template-schema.json` and read the failing component's definition directly.

## Working example

`examples/invoice-template.json` + `examples/invoice-data.json` are a validated invoice pair demonstrating: header/footer components, a styled line-item table with header row, nested placeholders, number formatting, hlines and a page number. When unsure how something fits together, pattern-match against the example rather than guessing.
