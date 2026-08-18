# Component Reference

Distilled from the official JSON schema (`template-schema.json`) and the support portal (https://support.pdfgeneratorapi.com/en/category/components-1ffseaj/). Field names below are exact schema names.

## Template skeleton

```json
{
  "name": "My Template",
  "layout": {
    "format": "A4",
    "unit": "cm",
    "orientation": "portrait",
    "rotation": 0,
    "margins": {"top": 1, "right": 1, "bottom": 1, "left": 1}
  },
  "pages": [
    {"components": [ ... ]}
  ]
}
```

- `layout.format`: `A2 A3 A4 A5 letter custom label`. With `custom`, set `layout.width`/`layout.height`. A4 portrait = 21 × 29.7 cm; letter = 8.5 × 11 in.
- `layout.unit`: `cm` (default) or `in`. **All component geometry (width/height/top/left, padding) is in this unit.** Font size, border width: pixels.
- Multiple pages = multiple entries in `pages`. Component `top` is relative to its page.

## Units, positioning, z-order

Every component: `cls` (type discriminator), `top`, `left`, `zindex` (default 1, higher renders on top). **The origin (0, 0) is the top-left corner of the margin box** — margins are applied by the engine, so components position within the usable area of `(page − horizontal margins) × (page − vertical margins)`. A full-width component on A4 with 0.75 cm margins is `left: 0, width: 19.5`. Components inside a container/header/footer position relative to the parent.

## Common style properties

Available on text-type components and most others:

| Property | Values / default |
|---|---|
| `fontFamily` | default `"opensans"` |
| `fontType` | array of `"bold"`, `"italic"`, `"underline"`, `"strike"` (e.g. `["bold"]`) |
| `fontSize` | integer px, **required** on all text-type components; 12 is a sane default |
| `fontColor` | hex, default `"#000000"` |
| `fontAlign` | `left right center justify`, default `left` |
| `fontValign` | `top middle bottom`, default `top` |
| `lineHeight` | relative to font size, default 1.15 |
| `backgroundColor` | hex, default `""` (none) |
| `borderStyle` | `none solid dotted dashed`, default `none` |
| `borderWidth` | px, default 1 |
| `borderColor` | hex, default `"#000000"` |
| `borderStatus` | `{"top": bool, "right": bool, "bottom": bool, "left": bool}` — which sides draw |
| `padding` | `{"top","right","bottom","left"}` in layout units |

To actually show a border you need `borderStyle` ≠ `none` (and optionally `borderStatus` to pick sides).

**`formatter`** is either `null` or `{"type": ..., "values": ...}` — never any other shape. Types: `text`/`html`/`system` with `values: null`, `date` with `values: {"input", "output"}` (momentjs formats), `number` with `values: {"decimalPlaces", "decimalSeparator", "thousandsSeparator", "autoIncreaseStep"}`. Note the schema does not enforce this shape strictly (the generic branch accepts any object), so a malformed formatter validates but breaks in the editor — the lint script checks the real contract.

## Text-type components

All require `cls, width, height, top, left, fontSize`.

- **`labelComponent`** — the Text component. Static text, placeholders, or mixed: `"Invoice {invoice::number}"`. Supports expression language (`${...}`), `textColumns`, `useFlexHeight` (grow with content), `dynamicFontSize` (shrink to fit).
- **`numberComponent`** — numeric data. Formatting goes in the `formatter` object in new templates: `{"type": "number", "values": {"decimalPlaces": 2, "decimalSeparator": ",", "thousandsSeparator": " ", "autoIncreaseStep": 0}}` (`autoIncreaseStep` auto-increments per array record). Root-level `decimalPlaces`/`decimalSeparator`/`thousandsSeparator` are legacy-only. Use for money/quantities so formatting is consistent.
- **`dateComponent`** — date data. Formats via the `formatter` object: `{"type": "date", "values": {"input": "YYYY-MM-DD", "output": "DD.MM.YYYY"}}` — `input` is how the raw data value is parsed, `output` how it's displayed, both in momentjs format syntax.
- **`pagenumberComponent`** — page numbering, typically inside a footer. System tokens: `{page}` (current) and `{total}` (page count), e.g. `value: "{page}/{total}"`.
- **`htmlblockComponent`** — renders HTML but strips inline styles, applying template styles instead. Set `isPlainHTML: true` to keep inline styles.
- **`systemTextComponent`** — technical/preformatted text content.

## Iterating components

- **`tableComponent`** — required `cls, width, top, left`. Set `dataIndex` to the array field (e.g. `"line_items"`). `rows` is an array of row objects: `{"isHeader": bool, "isStatic": bool, "columns": [...]}`.
  - Row 1: `isHeader: true` — rendered once as the header.
  - Row 2: the data row — repeated per array item; cell values use item-relative placeholders (`{sku}`).
  - Rows 3+: rendered after the data rows (summary rows) — set `isStatic: true` for one-off totals rows.
  - Columns are cells: `tableSimpleColumn` (requires `cls, fontSize`) or full `labelComponent` / `numberComponent` / `dateComponent` / `htmlblockComponent` / `systemTextComponent`. Give every cell an explicit `width` (and `height`); **the table `width` must equal the sum of column widths in each row**.
  - Cells cannot contain images, QR codes, checkboxes, or nested components — use a container for that. No cell merging; cell height grows with content.
  - Supports `sortBy`, `filterBy`, `groupBy`, `hideHeaderIfEmpty`. **These three iteration rules are arrays of objects keyed on `dataIndex`, not bare strings**: `groupBy: [{"dataIndex": "phase"}]`, `sortBy: [{"dataIndex": "date", "direction": "ASC"}]` (direction `ASC`/`DESC`), `filterBy: [{"dataIndex": "status", "search": "paid"}]`. Passing a plain string array is a schema error. The same object shapes appear in the template-level `dataSettings`.
- **`compositeComponent`** — the **Container** (editor name). Required `cls, width, height, top, left`. `components` holds any sub-components (including images, barcodes, nested containers/tables), positioned relative to the container. The container itself supports `backgroundColor` and the full border property set — **this makes it the preferred way to build styled content blocks** (cards, panels, boxed sections, summary bands): give the container the background/border and place the text inside as children. Background and content then move through the flow as one unit and can never misalign, with no `lockPosition` needed. With `dataIndex` set, the container acts as a repeating row rendered once per array item — the way to iterate content that tables can't hold. `iterateLeftToRight` lays repetitions horizontally; `autoShrink` collapses unused height.

## Header & footer

- **`headerOrFooterComponent`** — `cls` is `"headerComponent"` or `"footerComponent"`. Required `cls, height` (full page width, fixed position, no top/left/width). Extends the container: `components` array holds sub-items. Content repeats automatically on every rendered page — verified: defining them once on the first authored page applies them to all pages of a multi-page template, including the first (so keep header content unobtrusive if page 1 is a title page). Put the page number component in the footer.

## Graphics

- **`imageComponent`** — required `cls, width, height, top, left, value`. `value` is a public URL, a base64-encoded string (data URI), or a placeholder resolving to either. `autoScale`, `autoRotate` available. For an unresolvable image in a source document, keep the component with correct geometry and `value: ""` as placeholder.
  - **Drawing shapes the template can't**: the format has no curve/polygon primitive, so decorative graphics (curved corner blobs, wave dividers, badges, gradients, organic shapes) can't be built from rectangles/lines. Instead render the shape as an SVG and embed it as a rasterized data URI: write the SVG (transparent background, viewBox aspect ratio equal to the component's width:height, ~100 px/cm for print crispness), then `python3 scripts/svg_to_image.py shape.svg -o uri.txt` and use the resulting `data:image/png;base64,...` string as the image `value`. This keeps the artwork self-contained (no external hosting) and pixel-faithful. Place these on a low `zindex` so content layers over them; a full-bleed decorative shape needs `layout.margins: 0` to reach the page edge.
- **`rectangleComponent`** — box/fill; `backgroundColor` + border props. Reserve it for *purely decorative* shapes with no content of their own (color bands, dividers, full-bleed fills). **For a background behind content, use a `compositeComponent` with `backgroundColor` and the content as children instead** — see the Container entry. If a decorative rectangle must sit at page level among flow content, set `lockPosition: true`, otherwise text above it pushes it down and misaligns it.
- **`hlineComponent`** — horizontal rule; required `cls, width, top, left` (no height). Style via `borderWidth/borderColor/borderStyle`.
- **`vlineComponent`** — vertical rule; required `cls, height, top, left` (no width).

## Codes, marks, charts

- **`barcodeComponent`** — required `cls, width, height, top, left, value, type`. Types include `C128`, `EAN13`, `PDF417`, `DATAMATRIX`, `GS1-128`... (full enum in schema; default `C39E`). `showText` displays the human-readable value.
- **`qrcodeComponent`** — required `cls, width, top, left, value` (square; no height).
- **`checkboxComponent` / `radioComponent`** — required `cls, width, top, left, value`; value is boolean-ish (`true/false/1/0`), often a placeholder. `isEditable` renders a live PDF form field.
- **`signatureComponent`** — PDF signature form field placeholder; required `cls, width, height, top, left`.
- **`symbolComponent`** — single symbol/dingbat glyph; required `cls, width, top, left, value`.
- **`chartComponent`** — required `cls, width, height, top, left, type, xAxisDataIndex`. Types: `bar hbar line scatter radar pie explodedPie donut`. `dataIndex` points at the array; `xAxisDataIndex` is a single field name (string) but **`yAxisDataIndex` is an array of field names** (multi-series support), e.g. `["revenue"]`. For pie/donut, `pieLabel` is an array of enum values from `"amount"`, `"key"`, `"percent"` (e.g. `["key", "percent"]`). `xAxisLabel`/`yAxisLabel` are display strings; `xAxisTextAngle`/`yAxisTextAngle` rotate tick labels. **The renderer expects every chart property to be present** — including `xAxisLabel`/`yAxisLabel` at least as empty strings, angle fields as 0, and `pieLabel`/`yAxisDataIndex` as arrays — the hydrator fills all of them, so never deliver an unhydrated chart. Two verified rendering behaviors: the renderer applies its **own multi-color series palette** — there is no per-series color control in the template, so don't promise chart colors that match the document's design language; and pie/donut labels render **outside the ring**, so long category names need generous whitespace around the chart (a donut half the page width fits ~6 categories comfortably).

## Vertical flow and dynamic height

The renderer lays pages out flow-style: it keeps the authored vertical distance between components, so when a table gains rows or a `useFlexHeight` component grows, everything positioned below moves down by the growth amount (and flows to the next page when it runs out of room — which also means `{total}` page count can exceed 1 even for "one-page" designs).

Consequences:
- Place content that should follow a table (e.g. summary figures, signatures, notes, reference blocks) *immediately* after it with the gap you actually want — e.g. table bottom + 0.5–1 cm. Never park it near the page bottom "for spacing"; the design gap is preserved verbatim.
- Content that must stay put on every page (logos, addresses, page numbers, per-page barcodes) belongs in `headerComponent`/`footerComponent`.
- **Fixed design elements — background shapes, corner artwork, color bands, footer bars — go inside the header/footer components too.** As page-level components they get pushed down by table growth like any other component, breaking the design; inside header/footer they hold position and are replicated automatically on every page the content flows onto. Size the header/footer height to cover the decorated region — this also reserves that space, so flowing content stops before running into the artwork.
- **Fixed design elements — background shapes, corner artwork, color bands, footer bars — go inside the header/footer components too.** As page-level components they get pushed down by table growth like any other component, breaking the design; inside header/footer they hold position and are replicated automatically on every page the content flows onto. Size the header/footer height to cover the decorated region — this also reserves that space, so flowing content stops before running into the artwork.
- `lockPosition: true` pins a component at its coordinates, but a table flowing across pages renders over locked components — use it only when the dynamic content can never reach the locked area.
- **Styled content blocks are containers, not rectangles-behind-labels**: build cards, panels, and boxed sections as a `compositeComponent` with `backgroundColor`/borders holding the content as children — the block flows as one aligned unit. A page-level `rectangleComponent` layered behind separate labels needs `lockPosition: true` to survive flow shifts, and even locked it can be overrun by multi-page tables; use it only for pure decoration.
- **Text fitting semantics** for label/number/date components: `useFlexHeight: true` grows the box with content (shifting everything below — flow behavior); `useFlexHeight: false` keeps the box fixed and **clips** text that doesn't fit; `dynamicFontSize: true` shrinks the font until the content fits the authored box. For fixed-position layouts (replicated documents, forms, certificates) the right combination is `useFlexHeight: false` + `dynamicFontSize: true` — the layout stays intact and overlong data values shrink instead of clipping or pushing. Regardless of mode, give every text box right-side headroom (≥0.35 cm / ~15% beyond the expected text width): a box sized exactly to the text wraps its last character when real font metrics run wider, and one wrapped colon is enough to shift the flow and misalign the page.

## Choosing the right component

- Static or mixed text → label. Pure numeric with formatting → number. Dates → date.
- Repeating rows of text/number/date cells → table. Repeating anything richer (images, barcodes, multi-line blocks) → container with `dataIndex`.
- Same content on every page (logo, address, page number) → header/footer components.
- Visual separators → hline/vline; colored bands/boxes → rectangle behind content (lower zindex).

## Import-safe output (production conventions)

The JSON schema is the floor, not the ceiling: the import endpoint expects components in the fully-hydrated shape the editor exports, with the complete property set present on every component (explicit empty strings, `false`, `[]` — not omitted keys). Sparse-but-schema-valid templates can fail import with a server error. Therefore:

1. **Author sparse, deliver hydrated.** Write readable, minimal JSON while designing, then run `scripts/hydrate_template.py` as a build step before validating and delivering. It fills the full per-component property set, assigns editor-style `zindex` values (1001, 1002, ...), adds top-level fields (`tags`, `isDraft`, `dataSettings`, `editor`, `fontSubsetting`, `barcodeAsImage`, `backgroundPdf`), completes `layout` (`margins`, `emptyLabels`, `repeatLayout`) and page objects (`margins`, `border`, `isTableOfContents`, `conditionalFormats`, `backgroundImage`, `layout: []`), and marks header rows `isStatic: true`.
2. **Margins live in two places**: `layout.margins` AND each page object's `margins`. The hydrator copies layout margins onto pages that lack them.
3. **Data binding, editor convention**: production templates bind single-value components by putting the full `::` path in the component's `dataIndex` and using the literal token `{value}` in `value` — e.g. a QR code with `dataIndex: "order_number"`, `value: "{value}"`; a table cell with `dataIndex: "line_items::sku"`, `value: "{value}"` (full path even inside the table). Mixed text works too: `value: "{shop::currency}{value}"`. Prefer this convention for anything that will be imported and edited in the editor; inline `{field}` placeholders in `value` also render, and inside an iterated scope resolve item-relatively (`{sku}`) or absolutely from the root.
4. **Table header rows** are `isHeader: true` AND `isStatic: true` in production exports, and their cells have `height: 0` with `useFlexHeight: true`.
