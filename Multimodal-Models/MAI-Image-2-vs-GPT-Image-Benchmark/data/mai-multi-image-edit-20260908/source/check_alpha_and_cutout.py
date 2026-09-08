"""Test whether a returned edit is a real cutout or a regenerated white-background image.

"Cutout" has a specific meaning: the subject is separated from its background and
the background carries no pixels, so the result can be composited onto anything.
A diffusion edit that draws the subject on opaque white looks similar in a viewer
but is a different artifact. Two properties separate them:

1. Alpha channel. A cutout needs PNG colour type 6 (RGBA) or 4, and fully
   transparent background pixels. An opaque image cannot be composited without
   performing the cutout afterwards.
2. Pixel provenance. A cutout preserves the original subject pixels. A
   regenerated subject has new pixels, so it will not match the source crop.

Runs offline against saved PNGs; no model calls.
"""

import pathlib
import struct
import sys
import zlib

WORKSPACE = pathlib.Path(__file__).resolve().parent
CLEAN = WORKSPACE / "runs" / "multi-image-clean-20260908"
EARLIER = WORKSPACE / "runs" / "multi-image-edit-probe-20260908"
ARCHIVE = pathlib.Path("C:/david-share/Multimodal-Models/MAI-Image-2-vs-GPT-Image-Benchmark"
                       "/data/lenovo-web-grounding-20260908")

COLOUR_TYPES = {0: "grayscale", 2: "RGB (no alpha)", 3: "palette",
                4: "grayscale+alpha", 6: "RGBA (has alpha)"}


def png_header(path):
    """Read width, height and colour type from the IHDR chunk."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Not a PNG: {path}")
    width, height, depth, colour = struct.unpack(">IIBB", data[16:26])
    return {"width": width, "height": height, "bit_depth": depth,
            "colour_type": colour, "colour_name": COLOUR_TYPES.get(colour, "unknown"),
            "bytes": len(data)}


def decode_rgba(path):
    """Decode a PNG to RGBA rows using Pillow when present, else report why not."""
    try:
        from PIL import Image
    except ImportError:
        return None, "Pillow not installed"
    with Image.open(path) as image:
        mode = image.mode
        converted = image.convert("RGBA")
        return (converted, mode)


def corner_and_alpha_report(path):
    header = png_header(path)
    result = {"file": path.name, **header}
    decoded, mode = decode_rgba(path)
    if decoded is None:
        result["pixel_check"] = f"SKIPPED: {mode}"
        return result
    result["pillow_mode"] = mode
    width, height = decoded.size
    pixels = decoded.load()
    corners = {
        "top_left": pixels[2, 2],
        "top_right": pixels[width - 3, 2],
        "bottom_left": pixels[2, height - 3],
        "bottom_right": pixels[width - 3, height - 3],
    }
    result["corner_rgba"] = {name: tuple(int(v) for v in value) for name, value in corners.items()}
    alphas = [value[3] for value in corners.values()]
    result["corner_alpha_min"] = min(alphas)
    result["corner_alpha_max"] = max(alphas)
    result["corners_fully_transparent"] = all(a == 0 for a in alphas)
    result["corners_fully_opaque"] = all(a == 255 for a in alphas)
    whiteish = all(min(value[:3]) >= 235 for value in corners.values())
    result["corners_near_white"] = whiteish
    if result["corners_fully_transparent"]:
        result["verdict"] = "TRANSPARENT_BACKGROUND (cutout-style alpha present)"
    elif result["corners_fully_opaque"] and whiteish:
        result["verdict"] = "OPAQUE_WHITE_BACKGROUND (not a transparent cutout)"
    else:
        result["verdict"] = "MIXED_OR_OTHER"
    return result


def main():
    targets = [
        ARCHIVE / "mai-image-2.6-web-off" / "r1" / "01_test.png",
        CLEAN / "01_single_image_matched_prompt.png",
        CLEAN / "02_two_images_matched_prompt.png",
        CLEAN / "03_fixed_prompt_image_two_only.png",
        EARLIER / "01_single_image.png",
    ]
    print("Question: is the returned edit a transparent cutout or an opaque white image?\n")
    for path in targets:
        if not path.is_file():
            print(f"MISSING: {path}")
            continue
        report = corner_and_alpha_report(path)
        print("---", report["file"])
        print("    size        :", report["width"], "x", report["height"],
              "| PNG colour type", report["colour_type"], f"({report['colour_name']})")
        if "pillow_mode" in report:
            print("    decoded mode:", report["pillow_mode"])
            print("    corners RGBA:", report["corner_rgba"])
            print("    alpha range :", report["corner_alpha_min"], "-", report["corner_alpha_max"])
            print("    VERDICT     :", report["verdict"])
        else:
            print("    pixel check :", report["pixel_check"])
        print()
    print("Note: PNG colour type 2 means the file carries no alpha channel at all, so the "
          "background cannot be transparent regardless of how it looks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
