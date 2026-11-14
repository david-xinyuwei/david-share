"""Where does a low silhouette IoU of an engineering render come from: the render, or the segmentation that measures it?

    python tools/segmentation_check.py <dir> [--save <file.json>]

<dir> is what `python pregen_engineering.py <ids> --out <dir>` wrote. For each scenario it reads <id>_engineering.png (the
render) and <id>_engineering_cad.png (the same picture with the STEP outline and edges drawn in cyan from the same camera):
  STEP silhouette   = the area enclosed by the cyan lines (composite minus render, holes filled)
  segmented area    = part_area() from studio/pregen_render_cad.py, the segmentation behind iou_pct in <id>_check.json
and prints how much of the silhouette the segmentation found and how much of the segmented area lies inside the silhouette.
Approximate: the lines have a width, and filling closes the openings of open frames, so the IoU it prints is close to,
not equal to, the recorded one. Needs `pip install -r requirements-dev.txt` (numpy, scipy and Pillow come with CadQuery).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "studio"))
import pregen_render_cad as prc  # noqa: E402


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("dir", type=Path)
    ap.add_argument("--save", type=Path)
    a = ap.parse_args()
    rows = []
    for check in sorted(a.dir.glob("*_check.json")):
        sid = check.name[: -len("_check.json")]
        render = Image.open(a.dir / f"{sid}_engineering.png").convert("RGB")
        composite = np.asarray(Image.open(a.dir / f"{sid}_engineering_cad.png").convert("RGB"), np.int16)
        lines = np.abs(composite - np.asarray(render, np.int16)).max(axis=2) > 30
        step = ndimage.binary_fill_holes(lines)
        seg = prc.part_area(render)
        both = int(np.logical_and(seg, step).sum())
        rows.append({"scenario": sid, "recorded_iou_pct": json.loads(check.read_text(encoding="utf-8"))["iou_pct"],
                     "approx_iou_pct": round(100 * prc.iou(seg, step), 1),
                     "silhouette_found_pct": round(100 * both / max(int(step.sum()), 1), 1),
                     "segmented_inside_silhouette_pct": round(100 * both / max(int(seg.sum()), 1), 1)})
    if not rows:
        print(f"no <id>_check.json in {a.dir}: run pregen_engineering.py --out {a.dir} first")
        return 1
    print(f"{'scenario':<17} {'IoU recorded':>12} {'IoU approx':>10} {'silhouette found':>16} {'segmented inside':>16}")
    for r in rows:
        print(f"{r['scenario']:<17} {r['recorded_iou_pct']:>11.1f}% {r['approx_iou_pct']:>9.1f}% {r['silhouette_found_pct']:>15.1f}% "
              f"{r['segmented_inside_silhouette_pct']:>15.1f}%")
    if a.save:
        a.save.write_text(json.dumps({"generated_by": "tools/segmentation_check.py", "input": "pregen_engineering.py --out pictures",
                                      "rows": rows}, indent=1) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
