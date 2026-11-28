"""Make the public copy of a screenshot taken by shot_call.py: paint boxes over the IDs and cut the empty space below the answer.

The original PNG stays where it is. Nothing else in the picture is changed.
Needs: pip install pillow
"""
import argparse
import hashlib
import json
import pathlib
import sys

from PIL import Image, ImageDraw


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("png", help="screenshot written by shot_call.py (its .rects.json lies next to it)")
    ap.add_argument("out", help="public copy to write")
    ap.add_argument("--margin", type=int, default=40, help="CSS pixels kept below the answer")
    a = ap.parse_args()
    src = pathlib.Path(a.png)
    info = json.loads(src.with_suffix(".rects.json").read_text(encoding="utf-8"))
    scale = info["dpr"]
    img = Image.open(src).convert("RGB")
    draw = ImageDraw.Draw(img)
    for r in info["rects"]:
        draw.rectangle([r["x"] * scale - 2, r["y"] * scale - 1, (r["x"] + r["w"]) * scale + 2, (r["y"] + r["h"]) * scale + 1], fill=(70, 70, 70))
    # The answer ends at the last row that holds dark pixels (text or the frame of the answer box); below it the page is empty.
    grey = img.convert("L")
    last = 0
    for y in range(img.height - 1, -1, -1):
        if grey.crop((0, y, img.width, y + 1)).getextrema()[0] < 90:
            last = y
            break
    bottom = min(img.height, last + int(a.margin * scale))
    img = img.crop((0, 0, img.width, bottom))
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, optimize=True)
    print(json.dumps({"source": src.name, "source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(), "public_copy": out.name,
                      "public_sha256": hashlib.sha256(out.read_bytes()).hexdigest(), "boxes": len(info["rects"]),
                      "size": [img.width, img.height]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
