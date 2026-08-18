# Path B: Replicate an uploaded document (PDF, Word, image)

Goal: a template definition that renders visually indistinguishable from the source, with the variable parts (names, dates, amounts, line items) replaced by data placeholders. Fidelity beats speed — measure, don't eyeball.

## 1. Normalize the input

- **PDF** → measure directly (step 2).
- **Word (.docx)** → convert first: `soffice --headless --convert-to pdf file.docx --outdir /tmp/` (LibreOffice). Then treat as PDF.
- **Image (PNG/JPG/scan)** → there are no extractable coordinates. Look at the image, estimate the page size (assume A4 unless proportions say otherwise), and lay out components by proportional measurement: a block starting 30% down a 29.7 cm page is at top ≈ 8.9. State in the summary that positions are estimated from an image.

## 2. Measure the PDF

Run the bundled extractor:

```bash
pip install pymupdf --break-system-packages -q   # once per session
python3 scripts/measure_pdf.py source.pdf -o measurements.json --images-dir extracted_images/
```

Output (all geometry already converted to **cm**):
- `page`: width/height in cm → set `layout` accordingly (match to A4/letter if within 0.2 cm, else `custom`).
- **Coordinates**: the script measures from the page edge, but template coordinates are relative to the margin box. Simplest correct approach for replication: set `layout.margins` to all zeros, then measured page-absolute coordinates transfer 1:1 into the template. If the user wants real margins (e.g. so header/footer flow behaves like their other templates), subtract the margin offsets from every measured left/top instead.
- `text_spans`: each with text, left/top/width/height, font name, size (px), color (hex), bold/italic flags.
- `rects`: filled/stroked rectangles with fill and stroke colors — table header bands, section backgrounds, boxes.
- `lines`: thin rects and drawn lines classified as horizontal/vertical → `hlineComponent`/`vlineComponent`.
- `images`: extracted to `--images-dir` as files plus base64 in the JSON, with placement geometry.

Also render a page image for visual ground truth (`measure_pdf.py --render page1.png`) and *look at it* — the render tells you about alignment, grouping and colors that raw numbers hide.

## 3. Identify structure before writing components

Work top-down through the measurements:

1. **Repeated bands across pages** → header/footer components.
2. **Tabular regions** — rows of aligned spans, often with a colored band above them → one `tableComponent`. The colored band's fill becomes the header row `backgroundColor`; light-colored header text keeps its `fontColor`. Column x-boundaries come from the span alignment; column widths must sum exactly to the table width.
3. **Everything else** → labels/numbers/dates, images, rectangles, lines, barcodes/QR (a square black-and-white blob in a corner is usually a QR — ask the user what it encodes if unclear).

## 4. Decide what is data vs static

Anything that would change per document becomes a placeholder: names, addresses, document numbers, dates, amounts, line items. Everything else (column headings, the document title, boilerplate text, field labels) stays static. Choose clean snake_case field names grouped into logical objects — one object per real-world entity, arrays for repeating content (e.g. `seller`, `buyer`, `invoice`, `line_items` in a transactional document). When the source clearly implies a repeating list, model it as an array + table/container `dataIndex` even if the sample shows one row.

Use `numberComponent` for amounts (mirror the source's decimal/thousand separators) and `dateComponent` for dates (set the OUTPUT format to match the source, e.g. `DD.MM.YYYY`).

Mixed-weight lines ("Label:" regular + **value** bold) need two adjacent labels, since one label has one font weight. Put the separator and space at the *start of the value label* (`" {field}"`), not at the end of the prefix. **Never size a label to the exact measured span width** — measurements come from the source font, and opensans renders wider or narrower; a box one character too tight wraps that character (typically the colon) onto a second line, which grows the component and cascades misalignment through the flow. Size every prefix label at measured width + 0.35 cm minimum (or +15%), and start the value label at that widened edge. The same slack applies to any static text: headroom on the right is cheap, a wrapped character is not.

## 5. Conversion rules (hard requirements)

- Include **all** static text and graphical elements from the source.
- Every hex color observed (text, fills, borders, header bands) is carried into `fontColor` / `backgroundColor` / `borderColor`.
- Images: embed as base64 data URIs in `imageComponent.value`. If extraction fails, keep an empty-value image component at the correct geometry as a placeholder and tell the user.
- Decorative vector graphics the format can't draw (curved corner shapes, wave dividers, badges, organic blobs): don't approximate them with rectangles — recreate the shape as an SVG and rasterize it to a base64 data URI with `scripts/svg_to_image.py`, then embed via `imageComponent` on a low `zindex`. Match the SVG viewBox aspect ratio to the component's width:height and set `layout.margins: 0` for full-bleed shapes.
- **All fixed design elements (the shapes above, plus color bands and bars) go inside `headerComponent`/`footerComponent`**, sized to cover the decorated top/bottom regions. Page-level decor gets pushed down when tables grow; header/footer decor stays fixed and repeats on every overflow page, so a multi-page render keeps the source document's design.
- Horizontal rules → `hlineComponent`, vertical rules → `vlineComponent`, boxes/fills → `rectangleComponent`.
- No component exceeds the page; no overlaps except backgrounds on lower `zindex`.
- Explicit `width`/`height` on everything; explicit font styling on every label/number/date (fall back to schema defaults when the source doesn't say).
- Replicated documents are fixed layouts: on label/number/date components set `useFlexHeight: false` (fixed box) plus `dynamicFontSize: true` so overlong data values shrink to fit instead of being clipped or growing the box, and build any filled/bordered block that carries content as a `compositeComponent` (background on the container, text as children) rather than a rectangle behind labels; a content-free decorative rectangle among flow content gets `lockPosition: true`. Reserve `useFlexHeight: true` for blocks that genuinely should grow (addresses, notes).
- Font mapping: the API renders `opensans` and standard families — map serif sources to a serif family if available, otherwise use `opensans` and note the substitution. Convert PDF font sizes (pt) to the px value measured by the script.

## 6. Verify

1. `python3 scripts/validate_template.py template.json --data data.json` — fix until clean.
2. Compare component count and positions against `measurements.json`: every measured span/rect/line/image should be accounted for.
3. If the user has API credentials and asks, they can render the template and compare against the source; offer this as a final check.
