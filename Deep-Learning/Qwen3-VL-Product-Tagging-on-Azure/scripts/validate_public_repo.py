import json
import re
from pathlib import Path

from PIL import Image
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
README_FILES = [ROOT / "README.md", ROOT / "README-CN.md"]
PRIVATE_BACKEND_MARKER = "Backend-" + "of-david-share"
PRIVATE_WORKSPACE_MARKER = "AI-" + "Super-Agent"
SSH_HELPER_MARKER = "ssh" + "pass"
CLOUDAPP_MARKER = "cloudapp" + r"\.azure\.com"
ROOT_SSH_MARKER = "root" + "@"
G_DRIVE_MARKER = "/mnt/" + "g/"
C_DRIVE_MARKER = "/mnt/" + "c/"
CRED_FIELD_MARKER = "client_" + "secret"
SESSION_FIELD_MARKER = "refresh_" + "token"

SENSITIVE_PATTERNS = [
    CLOUDAPP_MARKER,
    re.escape(SSH_HELPER_MARKER),
    re.escape(ROOT_SSH_MARKER),
    re.escape(G_DRIVE_MARKER),
    re.escape(C_DRIVE_MARKER),
    re.escape(PRIVATE_BACKEND_MARKER),
    re.escape(PRIVATE_WORKSPACE_MARKER),
    r"sk-[A-Za-z0-9]{20,}",
    r"hf_[A-Za-z0-9]{20,}",
    r"Bearer\s+[A-Za-z0-9_\-.]{20,}",
    re.escape(CRED_FIELD_MARKER),
    re.escape(SESSION_FIELD_MARKER),
]


def fail(message: str) -> None:
    raise SystemExit(f"VALIDATION_FAILED: {message}")


def check_sensitive_text() -> None:
    pattern = re.compile("|".join(SENSITIVE_PATTERNS), re.IGNORECASE)
    for path in ROOT.rglob("*"):
        if path.is_dir() or ".git" in path.parts:
            continue
        if path.suffix.lower() not in {".md", ".py", ".json", ".jsonl", ".yaml", ".yml", ".sh", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        match = pattern.search(text)
        if match:
            fail(f"sensitive pattern {match.group(0)!r} in {path.relative_to(ROOT)}")


def check_markdown_assets() -> None:
    image_refs = set()
    asset_refs = set()
    link_pattern = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
    html_img_pattern = re.compile(r"<img\s+[^>]*src=[\"']([^\"']+)[\"']", re.IGNORECASE)
    for readme in README_FILES:
        text = readme.read_text(encoding="utf-8")
        if "TODO" in text or "TBD" in text:
            fail(f"unfinished marker in {readme.name}")
        for target in link_pattern.findall(text):
            if target.startswith(("http://", "https://", "mailto:")) or target.startswith("#"):
                continue
            asset_refs.add(target.split("#", 1)[0])
            target_path = (ROOT / target.split("#", 1)[0]).resolve()
            if not target_path.exists():
                fail(f"broken markdown link {target} in {readme.name}")
            if target.startswith("images/"):
                image_refs.add(target.split("#", 1)[0])
        for target in html_img_pattern.findall(text):
            if target.startswith(("http://", "https://")):
                continue
            asset_refs.add(target.split("#", 1)[0])
    for asset in asset_refs:
        if not (ROOT / asset).exists():
            fail(f"broken local asset reference {asset}")
    if not image_refs:
        fail("README files do not render any local images")
    for image in image_refs:
        with Image.open(ROOT / image) as img:
            width, height = img.size
            if width < 800 or height < 500:
                fail(f"image too small: {image} {width}x{height}")


def check_schema_and_sample() -> None:
    schema = json.loads((ROOT / "schemas/product_tag.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    sample_path = ROOT / "data/sample_products.jsonl"
    records = [json.loads(line) for line in sample_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not records:
        fail("sample_products.jsonl is empty")
    for index, record in enumerate(records):
        image_path = ROOT / record["image"]
        if not image_path.exists():
            fail(f"sample image missing for record {index}: {record['image']}")
        errors = list(validator.iter_errors(record["expected"]))
        if errors:
            fail(f"sample expected output does not match schema: {errors[0].message}")


def main() -> None:
    check_sensitive_text()
    check_markdown_assets()
    check_schema_and_sample()
    print("PUBLIC_REPO_VALIDATION_PASS")


if __name__ == "__main__":
    main()
