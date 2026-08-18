#!/usr/bin/env python3
"""Measure a PDF for template replication: text spans, rectangles, lines and
images with geometry converted to centimeters (PDF points / 72 * 2.54).

Usage:
  pip install pymupdf --break-system-packages
  python3 measure_pdf.py source.pdf -o measurements.json --images-dir imgs/
  python3 measure_pdf.py source.pdf --render page1.png   # rasterize page 1 for visual check
"""
import argparse
import base64
import json
from pathlib import Path

PT_TO_CM = 2.54 / 72.0


def cm(v):
    return round(v * PT_TO_CM, 2)


def color_hex(c):
    if c is None:
        return None
    if isinstance(c, int):  # sRGB int from span colors
        return f"#{c:06X}"
    if isinstance(c, (tuple, list)):
        return "#" + "".join(f"{int(round(x * 255)):02X}" for x in c[:3])
    return None


def measure(pdf_path, images_dir=None):
    import fitz  # pymupdf
    doc = fitz.open(pdf_path)
    result = {"pages": []}
    for pno, page in enumerate(doc):
        pw, ph = page.rect.width, page.rect.height
        pdata = {"number": pno + 1, "page": {"width_cm": cm(pw), "height_cm": cm(ph)},
                 "text_spans": [], "rects": [], "lines": [], "images": []}

        # --- text ---
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if not span["text"].strip():
                        continue
                    x0, y0, x1, y1 = span["bbox"]
                    flags = span.get("flags", 0)
                    pdata["text_spans"].append({
                        "text": span["text"],
                        "left": cm(x0), "top": cm(y0),
                        "width": cm(x1 - x0), "height": cm(y1 - y0),
                        "font": span.get("font"),
                        "size_pt": round(span.get("size", 0), 1),
                        "size_px": round(span.get("size", 0) * 96 / 72),
                        "color": color_hex(span.get("color")),
                        "bold": bool(flags & 16) or "bold" in (span.get("font") or "").lower(),
                        "italic": bool(flags & 2) or "italic" in (span.get("font") or "").lower(),
                    })

        # --- vector drawings: rects and lines ---
        for d in page.get_drawings():
            x0, y0, x1, y1 = d["rect"]
            w, h = x1 - x0, y1 - y0
            entry = {"left": cm(x0), "top": cm(y0), "width": cm(w), "height": cm(h),
                     "fill": color_hex(d.get("fill")), "stroke": color_hex(d.get("color")),
                     "stroke_width_pt": d.get("width")}
            thin = 2.5  # pt — thinner than this in one dimension = a line
            if h <= thin and w > thin:
                entry["kind"] = "hline"
                pdata["lines"].append(entry)
            elif w <= thin and h > thin:
                entry["kind"] = "vline"
                pdata["lines"].append(entry)
            elif w > 1 and h > 1:
                pdata["rects"].append(entry)

        # --- images ---
        for i, info in enumerate(page.get_image_info(xrefs=True)):
            x0, y0, x1, y1 = info["bbox"]
            img = {"left": cm(x0), "top": cm(y0),
                   "width": cm(x1 - x0), "height": cm(y1 - y0)}
            xref = info.get("xref", 0)
            if xref:
                try:
                    pix = fitz.Pixmap(doc, xref)
                    if pix.colorspace and pix.colorspace.n > 3:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    png = pix.tobytes("png")
                    img["base64"] = "data:image/png;base64," + base64.b64encode(png).decode()
                    if images_dir:
                        Path(images_dir).mkdir(parents=True, exist_ok=True)
                        fn = Path(images_dir) / f"p{pno+1}_img{i}.png"
                        fn.write_bytes(png)
                        img["file"] = str(fn)
                except Exception as e:
                    img["extract_error"] = str(e)
            pdata["images"].append(img)

        result["pages"].append(pdata)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out", default="measurements.json")
    ap.add_argument("--images-dir")
    ap.add_argument("--render", help="also rasterize page 1 to this PNG path for visual inspection")
    args = ap.parse_args()

    data = measure(args.pdf, args.images_dir)
    # keep the JSON readable: base64 payloads can be huge — truncate in the report,
    # full images are on disk when --images-dir is given
    for p in data["pages"]:
        for img in p["images"]:
            if "base64" in img and len(img["base64"]) > 200 and img.get("file"):
                img["base64_truncated"] = img.pop("base64")[:80] + "...(full image in file)"
    Path(args.out).write_text(json.dumps(data, indent=1))
    npages = len(data["pages"])
    nspans = sum(len(p["text_spans"]) for p in data["pages"])
    print(f"Wrote {args.out}: {npages} page(s), {nspans} text span(s)")

    if args.render:
        import fitz
        doc = fitz.open(args.pdf)
        pix = doc[0].get_pixmap(dpi=110)
        pix.save(args.render)
        print(f"Rendered page 1 to {args.render}")


if __name__ == "__main__":
    main()
