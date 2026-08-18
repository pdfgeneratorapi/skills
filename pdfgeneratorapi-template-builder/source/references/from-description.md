# Path A: Design a template from a description

The user describes the document ("an invoice with our logo, buyer details and a line-item table", "a shipping label with a barcode"). There is no source to measure, so you are the designer — produce something a professional would ship, not a wireframe.

## 1. Pin down the essentials first

If the description leaves these open, ask once, briefly:
- Page size (default A4 portrait, `cm`) — labels and US documents differ.
- The data model: what fields exist, what repeats? If the user has example JSON from their application, ask for it — the template should be built against their real field names. Otherwise design a clean model — snake_case field names in logical groups, one object per real-world entity plus arrays for repeating content (e.g. `seller`, `buyer`, `invoice`, `line_items` for a transactional document) — and present it clearly, since their application must produce it.
- Branding: logo (URL/base64/none), accent color. If none given, use a restrained neutral: dark gray text `#1A1A1A`, one accent for the table header band.

Don't interrogate — one round of questions maximum, then sensible defaults.

## 2. Layout discipline

Design on a grid. For A4/cm with 1 cm margins the usable area is 19 × 27.7 cm, and **(0, 0) is the top-left inside the margins** — a full-width component is `left: 0, width: 19`, and the rightmost edge is 19, not 21:

- Establish a baseline rhythm: 12px body text ≈ 0.5 cm line, so give single-line labels height 0.6, headings proportionally more.
- Align to a small set of x-positions (e.g. left column at 0, right column at 10). Ragged left edges look amateur.
- Derive the anatomy from what the document is for, then lay it out top-down in reading order: identity/branding first, context blocks next, the main content (tables, charts, body text), summary or closing content after, and repeating elements (page numbers, contact lines) in the footer. Common patterns — e.g. transactional documents running identity → parties → line-item table → summary figures → notes, or reports running title → summary → detail sections — are starting points, not rules.
- **Everything after the table flows down as the table grows** (the renderer preserves authored gaps — see "Vertical flow" in components.md). Position all trailing content (e.g. summary figures, notes, signature or reference blocks) tight after the table (0.5–1 cm gap), and it will trail the table naturally at render time. Anything that must sit at a fixed spot on the page goes in the footer/header instead.
- Summary figures derived from a table go in `numberComponent`s aligned to the relevant column, or as `isStatic` summary rows inside the table itself.
- Leave breathing room — at least 0.3 cm between blocks. Cramped templates read as broken.

## 3. Component choices

- Header/footer components for anything that must repeat on page 2+ (long line-item lists paginate automatically; the table flows, the header/footer repeat).
- Table for uniform line items; container with `dataIndex` when rows need images/barcodes/rich content.
- `useFlexHeight: true` on labels whose content length varies (addresses, notes).
- Numeric values → `numberComponent` with explicit `decimalPlaces` and separators matching the user's locale (e.g. many European locales use `decimalSeparator: ","`, `thousandsSeparator: " "`). Dates → `dateComponent` with an explicit OUTPUT format.
- Give the table header row a `backgroundColor` (accent color) and readable `fontColor`; keep data-row borders light (`borderStyle: "solid"`, thin bottom borders read best).
- Cards, panels, and highlight bands with content on them are `compositeComponent`s: background/border on the container, text as children — aligned by construction, no locking needed. Reserve `rectangleComponent` for content-free decoration, and lock it (`lockPosition: true`) when it sits among flow content.

## 4. Data file

Produce `*-data.json` alongside the template: realistic values (not "test"/"foo"), every placeholder resolvable, arrays with 3–5 items so pagination and zebra effects are visible. This doubles as documentation of the integration contract.

## 5. Verify

`python3 scripts/validate_template.py template.json --data data.json` until clean. Then walk the layout mentally top-to-bottom once more: overlaps, page-edge violations and column-sum mismatches are the three classic failures — the linter catches them, but re-check any warning it raises instead of suppressing it.
