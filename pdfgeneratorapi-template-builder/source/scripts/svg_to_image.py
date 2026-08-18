#!/usr/bin/env python3
"""Render an SVG (file or inline string) to a base64-encoded PNG data URI,
ready to drop into an imageComponent's `value`. Useful for reproducing
decorative graphics the template format can't draw natively — curved corner
blobs, wave dividers, badges, organic shapes — since the schema has no curve
primitive but imageComponent.value accepts a data URI.

Usage:
  pip install cairosvg --break-system-packages
  python3 svg_to_image.py shape.svg                 # prints data URI to stdout
  python3 svg_to_image.py shape.svg -o uri.txt       # writes data URI to file
  python3 svg_to_image.py shape.svg --png shape.png  # also save decoded PNG to eyeball it
  echo '<svg ...>...</svg>' | python3 svg_to_image.py -   # read SVG from stdin

Sizing: render at ~100 px/cm so the raster is crisp at print size — e.g. a
6.5 cm blob → width/height ~650 in the SVG. Keep the SVG viewBox aspect ratio
equal to the imageComponent width:height so nothing distorts. Use a transparent
background (don't paint a full-canvas rect) so the shape composites over
whatever is behind it.
"""
import argparse
import base64
import sys
from pathlib import Path


def svg_to_data_uri(svg_bytes):
    import cairosvg
    png = cairosvg.svg2png(bytestring=svg_bytes)
    return "data:image/png;base64," + base64.b64encode(png).decode(), png


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("svg", help="path to .svg file, or '-' for stdin")
    ap.add_argument("-o", "--out", help="write the data URI to this file instead of stdout")
    ap.add_argument("--png", help="also write the decoded PNG here for visual inspection")
    args = ap.parse_args()

    svg_bytes = sys.stdin.buffer.read() if args.svg == "-" else Path(args.svg).read_bytes()
    uri, png = svg_to_data_uri(svg_bytes)

    if args.png:
        Path(args.png).write_bytes(png)
    if args.out:
        Path(args.out).write_text(uri)
        print(f"Wrote data URI ({len(uri)} chars) to {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(uri)


if __name__ == "__main__":
    main()
