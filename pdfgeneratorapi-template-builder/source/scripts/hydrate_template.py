#!/usr/bin/env python3
"""Hydrate a sparse template definition into the full property shape that the
PDF Generator API editor produces on export. The import endpoint is far more
tolerant of fully-hydrated components than of sparse ones, so run this on
every template before delivering it.

What it does (only ADDS missing keys — never overwrites authored values):
  - fills the complete per-component property set with editor defaults
  - assigns sequential zindex values starting at 1001 (editor convention)
  - fills top-level fields (tags, isDraft, dataSettings, editor, fontSubsetting,
    barcodeAsImage, backgroundPdf) and layout fields (margins, emptyLabels,
    repeatLayout)
  - fills page-level fields (margins, border, isTableOfContents,
    conditionalFormats, backgroundImage, layout)
  - marks table header rows isStatic: true (editor convention)

Usage:
  python3 hydrate_template.py sparse.json -o hydrated.json
  python3 hydrate_template.py template.json --in-place
"""
import argparse
import copy
import json
from pathlib import Path

BORDER_OFF = {"top": False, "right": False, "bottom": False, "left": False}

# Common property set shared by all components (editor export shape,
# constrained to schema-valid values: borderStyle "none" not "", no padding: null)
COMMON = {
    "id": "",
    "className": None,
    "padding": {"top": 0, "right": 0, "bottom": 0, "left": 0},
    "value": "",
    "dataIndex": "",
    "borderStatus": BORDER_OFF,
    "borderWidth": 0,
    "borderColor": "",
    "borderStyle": "none",
    "backgroundColor": "",
    "useFlexHeight": False,
    "isEditable": False,
    "autoShrink": False,
    "isPlainHTML": False,
    "conditionalFormats": [],
    "enableArrayFunctions": False,
    "lockPosition": False,
    "compactHtmlRendering": False,
}

FONT = {
    "fontFamily": "opensans",
    "fontAlign": "left",
    "fontSize": 12,
    "fontType": [],
    "fontColor": "#000000",
    "fontValign": "top",
    "textDirection": "ltr",
    "textType": "normal",
    "textColumns": 1,
    "dynamicFontSize": False,
    "lineHeight": 1.15,
}

TEXT_FORMATTER = {"formatter": {"type": "text", "values": None}}

ITERATION = {"sortBy": [], "sortDir": "ASC", "filterBy": [], "groupBy": []}

PER_CLS = {
    "labelComponent": {**FONT, **TEXT_FORMATTER, "useFlexHeight": True},
    "numberComponent": {**FONT,
                        "formatter": {"type": "number",
                                      "values": {"decimalPlaces": 2, "decimalSeparator": ".",
                                                 "thousandsSeparator": "", "autoIncreaseStep": 0}}},
    "dateComponent": {**FONT,
                      "formatter": {"type": "date",
                                    "values": {"input": "YYYY-MM-DD", "output": "DD.MM.YYYY"}}},
    "pagenumberComponent": {**FONT},
    "htmlblockComponent": {**FONT, **TEXT_FORMATTER},
    "systemTextComponent": {**FONT, **TEXT_FORMATTER},
    "tableComponent": {**FONT, "value": None, "borderWidth": 1,
                       "borderColor": "#000000", "borderStyle": "solid",
                       "useFlexHeight": True, "isDynamic": False,
                       "hideHeaderIfEmpty": True, "pivotOn": [],
                       "pivotColumns": [], "pivotValues": [], **ITERATION},
    "compositeComponent": {"whitespace": 0, "allowRowSplit": False,
                           "iterateLeftToRight": False, "useFlexHeight": True,
                           **ITERATION, "components": []},
    "headerComponent": {"whitespace": 0, "allowRowSplit": False,
                        "iterateLeftToRight": False, "useFlexHeight": True,
                        **ITERATION, "components": [], "top": 0, "left": 0},
    "footerComponent": {"whitespace": 0, "allowRowSplit": False,
                        "iterateLeftToRight": False, "useFlexHeight": True,
                        **ITERATION, "components": [], "left": 0},
    "imageComponent": {"autoScale": True, "autoRotate": False,
                       **TEXT_FORMATTER, "fontAlign": "left", "fontValign": "top"},
    "barcodeComponent": {"type": "C128", "showText": False, "quietZone": False,
                         "scaleText": False, "text": False, "autoIncreaseStep": 0},
    "qrcodeComponent": {"type": "QRCODE,L", "showText": False, "quietZone": False,
                        "scaleText": False, "text": False, "autoIncreaseStep": 0},
    "rectangleComponent": {"borderWidth": 1, "borderColor": "#000000"},
    "hlineComponent": {"borderWidth": 1, "borderColor": "#000000",
                       "borderStyle": "solid",
                       "borderStatus": {"top": True, "right": False, "bottom": False, "left": False}},
    "vlineComponent": {"borderWidth": 1, "borderColor": "#000000",
                       "borderStyle": "solid",
                       "borderStatus": {"top": False, "right": False, "bottom": False, "left": True}},
    "signatureComponent": {},
    "symbolComponent": {**FONT},
    "checkboxComponent": {},
    "radioComponent": {},
    "chartComponent": {**FONT, "type": "bar", "xAxisDataIndex": "",
                       "xAxisLabel": "", "yAxisLabel": "",
                       "xAxisTextAngle": 0, "yAxisTextAngle": 0,
                       "yAxisDataIndex": [], "pieLabel": []},
    "tableSimpleColumn": {**FONT, **TEXT_FORMATTER, "useFlexHeight": True,
                          "top": 0, "left": 0, "height": 0.75},
}


def fill(target, defaults):
    for k, v in defaults.items():
        if k not in target:
            target[k] = copy.deepcopy(v)


def hydrate_component(c, zcounter):
    cls = c.get("cls", "")
    if "zindex" not in c:
        c["zindex"] = zcounter[0]
        zcounter[0] += 1
    if cls == "numberComponent" and "formatter" not in c:
        legacy = {k: c[k] for k in ("decimalPlaces", "decimalSeparator",
                                    "thousandsSeparator", "autoIncreaseStep") if k in c}
        if legacy:
            c["formatter"] = {"type": "number",
                              "values": {"decimalPlaces": 2, "decimalSeparator": ".",
                                         "thousandsSeparator": "", "autoIncreaseStep": 0, **legacy}}
    # normalize iteration rules: the schema wants arrays of {dataIndex: ...}
    # objects, but they are easy to author as bare field-name strings
    for rule in ("sortBy", "filterBy", "groupBy"):
        if isinstance(c.get(rule), list):
            c[rule] = [{"dataIndex": x} if isinstance(x, str) else x for x in c[rule]]
    fill(c, PER_CLS.get(cls, {}))
    fill(c, COMMON)
    if cls == "tableComponent":
        for row in c.get("rows") or []:
            fill(row, {"isHeader": False, "isStatic": False})
            if row["isHeader"]:
                row["isStatic"] = True  # editor convention
            for cell in row.get("columns") or []:
                fill(cell, PER_CLS.get(cell.get("cls", "tableSimpleColumn"),
                                       PER_CLS["tableSimpleColumn"]))
                fill(cell, COMMON)
                if row["isHeader"]:
                    cell.setdefault("height", 0)
    for child in c.get("components") or []:
        hydrate_component(child, zcounter)


def hydrate(template):
    fill(template, {
        "tags": [],
        "isDraft": False,
        "dataSettings": {"sortBy": [], "filterBy": [], "transform": []},
        "editor": {"heightMultiplier": 1, "defaultFontFamily": "opensans"},
        "fontSubsetting": False,
        "barcodeAsImage": False,
        "backgroundPdf": "",
    })
    layout = template.setdefault("layout", {})
    fill(layout, {
        "format": "A4", "unit": "cm", "orientation": "portrait", "rotation": 0,
        "width": 21, "height": 29.7,
        "margins": {"top": 0, "right": 0, "bottom": 0, "left": 0},
        "emptyLabels": 0, "repeatLayout": None,
    })
    for page in template.get("pages") or []:
        fill(page, {
            "width": layout.get("width"), "height": layout.get("height"),
            "margins": copy.deepcopy(layout.get("margins")),
            "border": False, "isTableOfContents": False,
            "conditionalFormats": [], "backgroundImage": None, "layout": [],
        })
        zcounter = [1001]
        # continue numbering after any authored zindex >= 1001
        existing = [c.get("zindex") for c in page.get("components") or [] if isinstance(c.get("zindex"), int)]
        if existing:
            zcounter[0] = max([1000] + existing) + 1
        for c in page.get("components") or []:
            hydrate_component(c, zcounter)
    return template


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("template")
    ap.add_argument("-o", "--out")
    ap.add_argument("--in-place", action="store_true")
    args = ap.parse_args()

    path = Path(args.template)
    template = hydrate(json.loads(path.read_text()))
    out = path if args.in_place else Path(args.out or path.with_name(path.stem + "-hydrated.json"))
    out.write_text(json.dumps(template, indent=2, ensure_ascii=False))
    print(f"Hydrated template written to {out}")


if __name__ == "__main__":
    main()
