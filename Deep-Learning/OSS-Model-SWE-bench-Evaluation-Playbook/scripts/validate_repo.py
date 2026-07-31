#!/usr/bin/env python3
import argparse
import collections
import os
import re
import struct
from pathlib import Path


REQUIRED = {
    "README.md",
    "README-CN.md",
    "requirements.txt",
    "requirements-lock.txt",
    "configs/oss-model.yaml",
    "docs/methodology.md",
    "docs/troubleshooting.md",
    "docs/validation.md",
    "docs/sources.md",
    "images/swebench_workflow.png",
    "scripts/run_generation.sh",
    "scripts/run_official_harness.sh",
    "scripts/setup_environment.sh",
    "scripts/build_dispute_manifest.py",
    "scripts/finalize_frozen_disputes.py",
    "tests/test_frozen_disputes.py",
}

FORBIDDEN = {
    "absolute workspace path": re.compile(r"/mnt/[a-z]/|[A-Z]:\\"),
    "unsafe remote access": re.compile(r"sshpass|root@"),
    "credential value": re.compile(
        r"(?:sk|ghp|github_pat)_[A-Za-z0-9_]{20,}|Bearer\s+[A-Za-z0-9._-]{20,}"
    ),
}

EXCLUDED_PARTS = {
    ".dependencies",
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "logs",
    "outputs",
    "runs",
}


def repo_files(root: Path):
    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        for directory in directories:
            path = current_path / directory
            if path.is_symlink() and directory not in EXCLUDED_PARTS:
                raise SystemExit(
                    f"Symbolic links are not allowed in the public subtree: {path.relative_to(root)}"
                )
        directories[:] = [directory for directory in directories if directory not in EXCLUDED_PARTS]
        for filename in filenames:
            path = current_path / filename
            if path.is_symlink():
                raise SystemExit(
                    f"Symbolic links are not allowed in the public subtree: {path.relative_to(root)}"
                )
            yield path


def code_blocks(text: str):
    return [
        (match.group(1).strip(), match.group(2).strip())
        for match in re.finditer(r"```([^\n]*)\n(.*?)```", text, re.S)
    ]


def bilingual_tokens(text: str) -> dict[str, collections.Counter]:
    prose = re.sub(r"```.*?```", "", text, flags=re.S)
    return {
        "external URLs": collections.Counter(re.findall(r"https?://[^) >]+", text)),
        "numeric tokens": collections.Counter(
            re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?(?:%|GB|MB|s)?", text)
        ),
        "inline code": collections.Counter(
            re.findall(r"(?<!`)`([^`\n]+)`(?!`)", prose)
        ),
        "HTML image references": collections.Counter(
            re.findall(r'<img\s+[^>]*src="([^"]+)"', text)
        ),
    }


def local_links(path: Path):
    text = path.read_text()
    for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
        clean = target.split("#", 1)[0]
        if not clean or re.match(r"^[a-z]+://", clean):
            continue
        yield target, (path.parent / clean).resolve()


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) != 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Invalid PNG: {path}")
    return struct.unpack(">II", data[16:24])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, nargs="?", default=Path("."))
    args = parser.parse_args()
    root = args.root.resolve()

    missing = sorted(path for path in REQUIRED if not (root / path).is_file())
    if missing:
        raise SystemExit(f"Missing required files: {missing}")

    readme = (root / "README.md").read_text()
    readme_cn = (root / "README-CN.md").read_text()
    h2_en = [line for line in readme.splitlines() if line.startswith("## ")]
    h2_cn = [line for line in readme_cn.splitlines() if line.startswith("## ")]
    if len(h2_en) != len(h2_cn):
        raise SystemExit(f"Bilingual H2 mismatch: {len(h2_en)} != {len(h2_cn)}")
    blocks_en = code_blocks(readme)
    blocks_cn = code_blocks(readme_cn)
    if len(blocks_en) != len(blocks_cn):
        raise SystemExit("Bilingual code-block count mismatch")
    for index, ((lang_en, body_en), (lang_cn, body_cn)) in enumerate(
        zip(blocks_en, blocks_cn), 1
    ):
        if lang_en != lang_cn:
            raise SystemExit(f"Code-block language mismatch at block {index}")
        if lang_en != "mermaid" and body_en != body_cn:
            raise SystemExit(f"Executable code-block mismatch at block {index}")
    tokens_en = bilingual_tokens(readme)
    tokens_cn = bilingual_tokens(readme_cn)
    for label in tokens_en:
        if tokens_en[label] != tokens_cn[label]:
            only_en = dict(tokens_en[label] - tokens_cn[label])
            only_cn = dict(tokens_cn[label] - tokens_en[label])
            raise SystemExit(
                f"Bilingual {label} mismatch: only_en={only_en} only_cn={only_cn}"
            )

    files = list(repo_files(root))
    for markdown in (path for path in files if path.suffix.lower() == ".md"):
        for target, resolved in local_links(markdown):
            if not resolved.exists():
                raise SystemExit(f"Broken local link in {markdown}: {target}")

    text_extensions = {".md", ".py", ".sh", ".yaml", ".yml", ".json", ".txt"}
    scanner_allowlist = {
        (root / "scripts" / "validate_repo.py").resolve(),
        (root / "docs" / "validation.md").resolve(),
    }
    for path in files:
        if path.suffix.lower() not in text_extensions:
            continue
        if path.resolve() in scanner_allowlist:
            continue
        text = path.read_text(errors="replace")
        for label, pattern in FORBIDDEN.items():
            match = pattern.search(text)
            if match:
                raise SystemExit(f"Forbidden {label} in {path}: {match.group(0)!r}")

    width, height = png_size(root / "images" / "swebench_workflow.png")
    if (width, height) != (1280, 720):
        raise SystemExit(f"Unexpected workflow image size: {width}x{height}")

    requirements = (root / "requirements.txt").read_text()
    requirements_lock = (root / "requirements-lock.txt").read_text()
    setup_script = (root / "scripts" / "setup_environment.sh").read_text()
    generation_script = (root / "scripts" / "run_generation.sh").read_text()
    model_config = (root / "configs" / "oss-model.yaml").read_text()
    if "mini-swe-agent==2.4.6" not in requirements:
        raise SystemExit("mini-swe-agent is not pinned to v2.4.6")
    if "mini-swe-agent==2.4.6" not in requirements_lock:
        raise SystemExit("Dependency lock does not contain mini-swe-agent v2.4.6")
    if re.search(r"(?:^|\n)(?:-e\s+)?(?:git\+|.*swebench\s*@)", requirements_lock):
        raise SystemExit("Dependency lock must not install SWE-bench as a VCS wheel")
    if "f7bbbb2ccdf479001d6467c9e34af59e44a840f9" not in setup_script:
        raise SystemExit("SWE-bench source commit is not pinned")
    if "model.model_kwargs.api_key" in generation_script or re.search(
        r"^\s*api_key\s*:", model_config, re.M
    ):
        raise SystemExit("Model API key must not be passed through config or process argv")

    print(
        "REPO_VALIDATION=PASS "
        f"h2={len(h2_en)} code_blocks={len(blocks_en)} image={width}x{height}"
    )


if __name__ == "__main__":
    main()
