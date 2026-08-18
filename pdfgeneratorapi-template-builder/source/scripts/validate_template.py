#!/usr/bin/env python3
"""Validate a PDF Generator API template definition.

Checks, in order:
  1. JSON Schema validation against the bundled official schema.
  2. Lint rules encoding layout requirements (bounds, overlaps, table column
     sums, missing font styling, width/height presence).
  3. Optional: cross-check template placeholders against an example data file.

Exit code 0 = no errors (warnings allowed), 1 = errors found.

Usage:
  python3 validate_template.py template.json
  python3 validate_template.py template.json --data data.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "references" / "template-schema.json"

TEXT_CLS = {"labelComponent", "numberComponent", "dateComponent"}
NO_HEIGHT_CLS = {"hlineComponent", "qrcodeComponent", "symbolComponent",
                 "checkboxComponent", "radioComponent"}
NO_WIDTH_CLS = {"vlineComponent"}
CONTAINER_CLS = {"compositeComponent", "headerComponent", "footerComponent"}

errors, warnings = [], []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


# ---------------------------------------------------------------- schema
def schema_validate(template):
    try:
        import jsonschema
    except ImportError:
        warn("jsonschema not installed (pip install jsonschema --break-system-packages); skipping schema check")
        return
    schema = json.loads(SCHEMA_PATH.read_text())
    validator = jsonschema.Draft202012Validator(schema)
    for e in sorted(validator.iter_errors(template), key=lambda e: list(e.absolute_path)):
        path = "/".join(str(p) for p in e.absolute_path) or "<root>"
        detail = e.message
        # anyOf failures are noisy; re-validate against the exact definition for this cls
        if e.validator == "anyOf" and isinstance(e.instance, dict) and e.instance.get("cls"):
            cls = e.instance["cls"]
            def_name = "headerOrFooterComponent" if cls in ("headerComponent", "footerComponent") else cls
            if def_name in schema.get("$defs", {}):
                sub_schema = {"$defs": schema["$defs"], "$ref": f"#/$defs/{def_name}"}
                sub_val = jsonschema.Draft202012Validator(sub_schema)
                subs = []
                for s in sub_val.iter_errors(e.instance):
                    m = s.message
                    if s.validator == "anyOf" and isinstance(s.instance, dict):
                        cell_cls = s.instance.get("cls")
                        loc = "/".join(str(x) for x in s.absolute_path)
                        if cell_cls is None:
                            m = (f"{loc}: cell has cls=null (editor header-cell export shape; "
                                 f"when authoring, use cls 'tableSimpleColumn')")
                        else:
                            m = f"{loc}: cell (cls={cell_cls}) does not match any cell definition"
                    if len(m) > 200:
                        m = m[:200] + "…"
                    subs.append(m)
                detail = f"(cls={cls}) " + ("; ".join(subs[:6]) if subs else e.message)
            else:
                detail = f"unknown component cls '{cls}'"
        err(f"schema: {path}: {detail}")


# ---------------------------------------------------------------- lint
def page_size(template, page):
    """Return the USABLE content area (page minus margins). Component
    coordinates are relative to the margin box: (0,0) is inside the margins."""
    layout = template.get("layout", {}) or {}
    fmt = str(layout.get("format", "A4")).lower()
    unit = layout.get("unit", "cm")
    sizes_cm = {"a2": (42.0, 59.4), "a3": (29.7, 42.0), "a4": (21.0, 29.7),
                "a5": (14.8, 21.0), "letter": (21.59, 27.94)}
    w = page.get("width") or layout.get("width")
    h = page.get("height") or layout.get("height")
    if (w is None or h is None) and fmt in sizes_cm:
        w, h = sizes_cm[fmt]
        if unit == "in":
            w, h = w / 2.54, h / 2.54
    if layout.get("orientation") == "landscape" and w and h and w < h:
        w, h = h, w
    m = page.get("margins") or layout.get("margins") or {}
    if w:
        w -= (m.get("left", 0) or 0) + (m.get("right", 0) or 0)
    if h:
        h -= (m.get("top", 0) or 0) + (m.get("bottom", 0) or 0)
    return w, h


def geom(c):
    return (c.get("left", 0) or 0, c.get("top", 0) or 0,
            c.get("width", 0) or 0, c.get("height", 0) or 0)


def lint_component(c, path, pw, ph, inside_container=False):
    cls = c.get("cls", "?")
    label = f"{path} ({cls})"

    if cls not in NO_WIDTH_CLS and cls not in {"headerComponent", "footerComponent"} and c.get("width") in (None, ""):
        err(f"{label}: missing width")
    if cls not in NO_HEIGHT_CLS and c.get("height") in (None, ""):
        err(f"{label}: missing height")

    if cls in TEXT_CLS:
        if c.get("fontSize") in (None, ""):
            err(f"{label}: fontSize is required")
        for prop, default in (("fontFamily", "opensans"), ("fontColor", "#000000"), ("fontAlign", "left")):
            if prop not in c:
                warn(f"{label}: {prop} not set — add it explicitly (default '{default}')")
        lint_text_headroom(c, label)

    # bounds (skip header/footer which are positioned by the engine,
    # and children of containers whose coordinates are parent-relative)
    if cls not in {"headerComponent", "footerComponent"} and not inside_container and pw and ph:
        x, y, w, h = geom(c)
        eps = 0.01
        if x + w > pw + eps or y + h > ph + eps or x < -eps or y < -eps:
            err(f"{label}: exceeds usable area (left={x}, top={y}, w={w}, h={h}; "
                f"usable {round(pw,2)}x{round(ph,2)} = page minus margins, origin at margin box)")

    lint_formatter(c, label)

    if cls == "tableComponent":
        lint_table(c, label)

    for i, child in enumerate(c.get("components", []) or []):
        cw, ch = (c.get("width"), c.get("height")) if cls in CONTAINER_CLS else (pw, ph)
        lint_component(child, f"{path}/components[{i}]", cw or pw, ch or ph, inside_container=True)
        # child bounds within container
        if cls in CONTAINER_CLS and c.get("width"):
            x, y, w, h = geom(child)
            if x + w > (c.get("width") or pw) + 0.01:
                warn(f"{path}/components[{i}]: wider than its parent container")


FORMATTER_TYPES = {"text", "html", "system", "date", "number"}


def lint_formatter(c, label):
    """The schema's formatter anyOf has no required fields, so malformed
    formatter objects slip through validation — enforce the real contract:
    null, or {"type": <text|html|system|date|number>, "values": <per-type>}."""
    if "formatter" not in c or c["formatter"] is None:
        return
    f = c["formatter"]
    if not isinstance(f, dict):
        err(f"{label}: formatter must be null or an object")
        return
    ftype = f.get("type")
    if ftype not in FORMATTER_TYPES:
        extra = f" (found keys {sorted(f.keys())})" if "type" not in f else ""
        err(f"{label}: formatter.type must be one of {sorted(FORMATTER_TYPES)}{extra} — "
            f'shape is {{"type": ..., "values": ...}}')
        return
    vals = f.get("values")
    if ftype == "date":
        if not isinstance(vals, dict) or not {"input", "output"} <= set(vals):
            err(f"{label}: date formatter values must be an object with momentjs "
                f'"input" and "output" formats, e.g. {{"input": "YYYY-MM-DD", "output": "DD.MM.YYYY"}}')
    elif ftype == "number":
        allowed = {"decimalPlaces", "decimalSeparator", "thousandsSeparator", "autoIncreaseStep"}
        if not isinstance(vals, dict):
            err(f"{label}: number formatter values must be an object with keys from {sorted(allowed)}")
        else:
            unknown = set(vals) - allowed
            if unknown:
                warn(f"{label}: number formatter has unknown value keys {sorted(unknown)}")
    else:
        if vals is not None and not isinstance(vals, dict):
            err(f"{label}: formatter values must be an object or null")


def lint_text_headroom(c, label):
    """Boxes sized to the exact text width wrap their last character when real
    font metrics run wider than estimated (e.g. replicating a document set in
    another font) — one wrapped colon grows the component, shifts the flow and
    misaligns the page. Estimate the rendered width of STATIC text (opensans
    average advance ≈ 0.50×fontSize, 0.55× for bold) and require headroom.
    Placeholder-bearing values are skipped: their length is data-dependent."""
    v = c.get("value")
    w = c.get("width")
    size = c.get("fontSize")
    if not isinstance(v, str) or not v.strip() or "{" in v or not w or not size:
        return
    if c.get("dynamicFontSize"):
        return  # font shrinks to fit; wrapping is not the failure mode
    factor = 0.55 if "bold" in (c.get("fontType") or []) else 0.50
    longest = max(v.split("\n"), key=len)
    est_px = len(longest) * size * factor
    est = est_px * 2.54 / 96  # px -> cm (geometry unit assumed cm)
    pad = c.get("padding") or {}
    inner = w - (pad.get("left", 0) or 0) - (pad.get("right", 0) or 0)
    if est > inner - 0.1:
        warn(f"{label}: static text {longest!r} is estimated at ~{round(est, 2)} wide in a "
             f"{round(inner, 2)}-wide box — too little right-side headroom. If real metrics run "
             f"slightly wider, the last character wraps to a new line and misaligns the flow. "
             f"Widen the box (≥0.35 slack) or enable dynamicFontSize.")


def lint_table(c, label):
    width = c.get("width")
    rows = c.get("rows") or []
    if not rows:
        err(f"{label}: table has no rows")
        return
    if not c.get("dataIndex"):
        warn(f"{label}: table has no dataIndex — it will not iterate any data")
    if not rows[0].get("isHeader"):
        warn(f"{label}: first row is not marked isHeader: true")
    for ri, row in enumerate(rows):
        cols = row.get("columns") or []
        if not cols:
            err(f"{label}/rows[{ri}]: row has no columns")
            continue
        total = 0
        for ci, col in enumerate(cols):
            cw = col.get("width")
            if cw in (None, ""):
                err(f"{label}/rows[{ri}]/columns[{ci}]: cell missing width")
            else:
                total += cw
            if col.get("fontSize") in (None, ""):
                err(f"{label}/rows[{ri}]/columns[{ci}]: cell missing fontSize")
        if width is not None and abs(total - width) > 0.01:
            err(f"{label}/rows[{ri}]: column widths sum to {round(total, 3)} but table width is {width}")


def rects_overlap(a, b):
    ax, ay, aw, ah = geom(a)
    bx, by, bw, bh = geom(b)
    eps = 0.05  # half a millimeter in cm units: smaller intersections are
    # invisible at print scale and would only produce noise (also guards
    # against float artifacts in adjacent edge coordinates)
    return ax < bx + bw - eps and bx < ax + aw - eps and ay < by + bh - eps and by < ay + ah - eps


def lint_overlaps(components, path):
    positioned = [(i, c) for i, c in enumerate(components)
                  if c.get("cls") not in {"headerComponent", "footerComponent"}]
    for n, (i, a) in enumerate(positioned):
        for j, b in positioned[n + 1:]:
            if not rects_overlap(a, b):
                continue
            # ruled grids require horizontal and vertical rules to cross
            kinds = {a.get("cls"), b.get("cls")}
            if kinds == {"hlineComponent", "vlineComponent"}:
                continue
            za, zb = a.get("zindex", 1) or 1, b.get("zindex", 1) or 1
            decorative = {"rectangleComponent", "imageComponent", "hlineComponent", "vlineComponent"}
            # intentional layering: distinct zindex AND at least one side is a
            # decorative shape (background fill, image, rule) — covers both
            # rect-behind-text and decorative-over-decorative (e.g. a shape
            # overlapping a full-bleed band).
            if za != zb and (a.get("cls") in decorative or b.get("cls") in decorative):
                continue
            warn(f"{path}[{i}] ({a.get('cls')}) overlaps {path}[{j}] ({b.get('cls')}) "
                 f"— separate them or layer a background on a lower zindex")


GAP_LIMIT = 3.0  # units; larger authored gaps below dynamic content are almost always a mistake


def lint_flow(components, path, ph=None):
    """The renderer preserves authored vertical gaps: components below a
    dynamic (iterating/flexing) region shift down as it grows. A large design
    gap between a dynamic table/container and trailing content is therefore
    reproduced verbatim in the render and pushes content onto the next page."""
    # Styled content blocks should be containers, not a rectangle behind
    # separate labels. Flag an unlocked page-level rectangle that has text
    # components sitting on top of it (same region, higher zindex): that is a
    # background-behind-content pattern that will misalign under flow. Suggest
    # a compositeComponent (background + children) as the robust fix, or
    # lockPosition for genuinely decorative rectangles.
    text_cls = {"labelComponent", "numberComponent", "dateComponent",
                "tableComponent", "compositeComponent", "htmlblockComponent"}
    for r in components:
        if r.get("cls") != "rectangleComponent" or r.get("lockPosition"):
            continue
        rx, ry, rw, rh = geom(r)
        rz = r.get("zindex", 1) or 1
        has_overlay = any(
            c.get("cls") in text_cls and (c.get("zindex", 1) or 1) > rz
            and rects_overlap(r, c) for c in components)
        if has_overlay:
            i = components.index(r)
            warn(f"{path}[{i}] (rectangleComponent) has content layered on top of it — a "
                 f"background-behind-labels pattern that misaligns under flow. Prefer a "
                 f"compositeComponent with backgroundColor holding the content as children "
                 f"(flows as one aligned unit). If it is purely decorative, set lockPosition: true.")
        elif any(c.get("cls") in text_cls and (c.get("top", 0) or 0) < ry for c in components):
            i = components.index(r)
            warn(f"{path}[{i}] (rectangleComponent) is unlocked with text components above it in "
                 f"the flow — it will be pushed down and misaligned. Set lockPosition: true, or if "
                 f"it backs content, use a compositeComponent with the content as children instead.")
    dynamic = [c for c in components
               if c.get("cls") in ("tableComponent", "compositeComponent")
               and c.get("dataIndex") not in ("", None)]
    for d in dynamic:
        d_bottom = (d.get("top", 0) or 0) + (d.get("height", 0) or 0)
        below = [c for c in components
                 if c is not d
                 and c.get("cls") not in ("headerComponent", "footerComponent")
                 and not c.get("lockPosition")
                 and (c.get("top", 0) or 0) >= d_bottom]
        if not below:
            continue
        nearest = min(below, key=lambda c: c.get("top", 0) or 0)
        gap = (nearest.get("top", 0) or 0) - d_bottom
        if gap > GAP_LIMIT:
            i = components.index(nearest)
            warn(f"{path}[{i}] ({nearest.get('cls')}) sits {round(gap, 1)} units below the dynamic "
                 f"{d.get('cls')} (dataIndex '{d.get('dataIndex')}') — the renderer preserves this gap "
                 f"as the table grows, pushing the component down (possibly to the next page). "
                 f"Place it just after the table, or pin it in a footer/header.")
        # Fixed design elements below dynamic content get pushed down with the
        # flow, breaking the design. The telltale is bottom-anchored decor: a
        # decorative component whose bottom edge reaches the lower region of
        # the page (footer bars, corner artwork). Backgrounds attached to
        # trailing content (totals bands etc.) shift together with their text
        # and are fine. Design elements belong inside header/footer components,
        # where they hold position and replicate on every overflow page.
        decorative = {"rectangleComponent", "imageComponent", "hlineComponent", "vlineComponent"}
        for c in below:
            c_bottom = (c.get("top", 0) or 0) + (c.get("height", 0) or 0)
            if c.get("cls") in decorative and ph and c_bottom > ph * 0.85:
                i = components.index(c)
                warn(f"{path}[{i}] ({c.get('cls')}) is bottom-anchored design decor positioned below "
                     f"the dynamic {d.get('cls')} — it will be pushed down (and onto the next page) as "
                     f"the table grows. Move it inside a headerComponent/footerComponent so it stays "
                     f"fixed and replicates on overflow pages.")


def lint(template):
    pages = template.get("pages") or []
    if not pages:
        err("template has no pages")
    for pi, page in enumerate(pages):
        pw, ph = page_size(template, page)
        comps = page.get("components") or []
        for ci, c in enumerate(comps):
            lint_component(c, f"pages[{pi}]/components[{ci}]", pw, ph)
        lint_overlaps(comps, f"pages[{pi}]/components")
        lint_flow(comps, f"pages[{pi}]/components", ph)


# ---------------------------------------------------------------- placeholders
PLACEHOLDER_RE = re.compile(r"\{([A-Za-z0-9_.:\- ]+?)\}")


SENTINEL_DATAINDEX = {"", None, "randomDataIndexForFlexHeight"}


def collect_placeholders(node, scope, out):
    """Walk the template; record (field, scope, via_dataindex) triples.

    Two conventions are supported:
    - value contains {field} placeholders resolved against the active scope
      (or, as the renderer also allows, absolutely from the data root)
    - the editor convention: component carries dataIndex (a full :: path) and
      value uses {value} to mean "the dataIndex field"
    """
    if isinstance(node, dict):
        di = node.get("dataIndex")
        iterating = di not in SENTINEL_DATAINDEX and ("rows" in node or "components" in node)
        new_scope = scope + [di] if iterating else scope
        if iterating:
            out.append((di, scope, True))
        v = node.get("value")
        if isinstance(v, str) and node.get("cls") != "pagenumberComponent":
            for m in PLACEHOLDER_RE.finditer(v):
                fld = m.group(1)
                if fld.startswith("$") or "(" in fld:
                    continue  # expression language — skip
                if fld in ("value", "page", "total", "p", "pt"):
                    continue  # system tokens; {value} handled below via dataIndex
                out.append((fld, scope, False))
        if isinstance(v, str) and "{value}" in v and di not in SENTINEL_DATAINDEX and not iterating:
            out.append((di, scope, True))
        for k, child in node.items():
            if k == "value":
                continue
            collect_placeholders(child, new_scope if k in ("components", "rows") else scope, out)
    elif isinstance(node, list):
        for item in node:
            collect_placeholders(item, scope, out)


def resolve(data, scope_chain, field):
    """Check field ('a::b') resolves in data. Descends into the first element
    whenever a list is encountered along the path (matching renderer behavior)."""
    def descend(ctx, path):
        for part in path.split("::"):
            if isinstance(ctx, list):
                if not ctx:
                    return None, False
                ctx = ctx[0]
            if isinstance(ctx, dict) and part in ctx:
                ctx = ctx[part]
            else:
                return None, False
        return ctx, True

    ctx = data
    for idx in scope_chain:
        ctx, ok = descend(ctx, idx)
        if not ok:
            return False
        if isinstance(ctx, list):
            if not ctx:
                return False
            ctx = ctx[0]
    return descend(ctx, field)[1]


def check_placeholders(template, data):
    found = []
    collect_placeholders(template, [], found)
    seen = set()
    for field, scope, via_dataindex in found:
        key = (tuple(scope), field, via_dataindex)
        if key in seen:
            continue
        seen.add(key)
        label = f"dataIndex '{field}'" if via_dataindex else f"placeholder {{{field}}}"
        # renderer accepts scope-relative or absolute-from-root references
        if not resolve(data, list(scope), field) and not resolve(data, [], field):
            err(f"{label} (scope {list(scope) or 'root'}) does not resolve in the data file")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("template")
    ap.add_argument("--data", help="example data JSON to cross-check placeholders")
    args = ap.parse_args()

    template = json.loads(Path(args.template).read_text())
    schema_validate(template)
    lint(template)
    if args.data:
        check_placeholders(template, json.loads(Path(args.data).read_text()))

    for w in warnings:
        print(f"WARN  {w}")
    for e in errors:
        print(f"ERROR {e}")
    print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
