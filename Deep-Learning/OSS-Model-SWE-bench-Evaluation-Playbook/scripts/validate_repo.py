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
    "images/swebench_workflow.png",
    "scripts/run_generation.sh",
    "scripts/preflight_provider.py",
    "scripts/run_scored_canary.sh",
    "scripts/provider_compat.py",
    "scripts/provider_model.py",
    "scripts/swebench_outcomes.py",
    "scripts/run_official_harness.sh",
    "scripts/setup_environment.sh",
    "scripts/build_dispute_manifest.py",
    "scripts/compare_run_contracts.py",
    "scripts/finalize_frozen_disputes.py",
    "scripts/shard_instance_manifest.py",
    "tests/test_frozen_disputes.py",
    "tests/test_parity_contract.py",
    "tests/test_shard_manifest.py",
    "tests/test_validation_tools.py",
    "examples/instance-manifest.tsv",
    "examples/parity-reference.toml",
    "examples/parity-candidate.toml",
    "examples/live-foundry-direct-deepseek-v4-flash-scored-canary.yaml",
    "examples/live-foundry-fw-glm51-scored-canary.yaml",
    "examples/live-foundry-managed-compute-pending.yaml",
}

FORBIDDEN = {
    "absolute workspace path": re.compile(r"/mnt/[a-z]/|[A-Z]:\\"),
    "unsafe remote access": re.compile(r"sshpass|root@"),
    "resource UUID": re.compile(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
    ),
    "non-example email": re.compile(
        r"\b[A-Za-z0-9._%+-]+@(?!example\.com\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    ),
    "non-placeholder Azure endpoint": re.compile(
        r"https://(?!(?:<resource-name>|example)\.)[A-Za-z0-9.-]+\."
        r"(?:services\.ai\.azure\.com|openai\.azure\.com)"
    ),
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
        "external URLs": collections.Counter(
            url.rstrip(".,;:")
            for url in re.findall(
                r"https?://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+", text
            )
        ),
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
    if re.search(r"\]\(docs/", readme + readme_cn):
        raise SystemExit("Customer-facing content must stay in the bilingual README files")
    allowed_markdown = {
        (root / "README.md").resolve(),
        (root / "README-CN.md").resolve(),
    }
    extra_markdown = sorted(
        str(path.relative_to(root))
        for path in root.rglob("*.md")
        if path.resolve() not in allowed_markdown
    )
    if extra_markdown:
        raise SystemExit(f"Standalone customer Markdown is not allowed: {extra_markdown}")
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

    text_extensions = {
        ".json",
        ".md",
        ".py",
        ".sh",
        ".toml",
        ".txt",
        ".yaml",
        ".yml",
    }
    scanner_allowlist = {(root / "scripts" / "validate_repo.py").resolve()}
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
    diagram_requirements = (root / "requirements-diagrams.txt").read_text()
    setup_script = (root / "scripts" / "setup_environment.sh").read_text()
    generation_script = (root / "scripts" / "run_generation.sh").read_text()
    model_config = (root / "configs" / "oss-model.yaml").read_text()
    if "mini-swe-agent==2.4.6" not in requirements:
        raise SystemExit("mini-swe-agent is not pinned to v2.4.6")
    if "mini-swe-agent==2.4.6" not in requirements_lock:
        raise SystemExit("Dependency lock does not contain mini-swe-agent v2.4.6")
    if "Pillow==12.3.0" not in diagram_requirements:
        raise SystemExit("Diagram requirements do not pin Pillow 12.3.0")
    if "pillow==12.3.0" not in requirements_lock.lower():
        raise SystemExit("Dependency lock does not contain Pillow 12.3.0")
    if re.search(r"(?:^|\n)(?:-e\s+)?(?:git\+|.*swebench\s*@)", requirements_lock):
        raise SystemExit("Dependency lock must not install SWE-bench as a VCS wheel")
    if "f7bbbb2ccdf479001d6467c9e34af59e44a840f9" not in setup_script:
        raise SystemExit("SWE-bench source commit is not pinned")
    if "model.model_kwargs.api_key" in generation_script or re.search(
        r"^\s*api_key\s*:", model_config, re.M
    ):
        raise SystemExit("Model API key must not be passed through config or process argv")
    for mode in ("openai_compatible", "azure_foundry", "fireworks"):
        if mode not in generation_script or mode not in readme or mode not in readme_cn:
            raise SystemExit(f"Missing endpoint mode coverage: {mode}")
    for marker in (
        "compare_run_contracts.py",
        "MODEL_AND_METHOD_ALIGNED",
        "FINETUNING_METHOD_ALIGNED",
        "MODEL_SELECTION_METHOD_ALIGNED",
        "METHOD_ALIGNED",
        "ADAPTED_RUN",
        "NOT_COMPARABLE",
    ):
        if marker not in readme or marker not in readme_cn:
            raise SystemExit(f"Missing parity framework marker: {marker}")
    deployment_playbooks = (
        ("Four Deployment Paths and Test Contracts", "四条部署路径与测试合同"),
        ("How to Test Azure GPU VM", "如何测试 Azure GPU VM"),
        ("How to Test Foundry Serverless API", "如何测试 Foundry Serverless API"),
        ("How to Test Fireworks", "如何测试 Fireworks"),
        ("Pending: Managed Compute", "待验证：Managed Compute"),
    )
    for marker_en, marker_cn in deployment_playbooks:
        if marker_en not in readme or marker_cn not in readme_cn:
            raise SystemExit(
                f"Missing deployment test playbook: {marker_en} / {marker_cn}"
            )
    operational_markers = (
        ("P/D Disaggregation or Independent Endpoints", "P/D分离还是两个独立Endpoint"),
        ("Agent Version and Sampling", "Agent版本和Sampling"),
        ("shard_instance_manifest.py", "shard_instance_manifest.py"),
        ("Managed Compute API Contract (Specification Only)", "Managed Compute接口规范（仅定义，不执行）"),
    )
    for marker_en, marker_cn in operational_markers:
        if marker_en not in readme or marker_cn not in readme_cn:
            raise SystemExit(
                f"Missing operational best-practice marker: {marker_en} / {marker_cn}"
            )
    managed_compute_contract_markers = (
        "FOUNDRY_ACCOUNT_NAME",
        "FOUNDRY_DEPLOYMENT_NAME",
        "FOUNDRY_PROJECT_ENDPOINT",
        "FOUNDRY_TOKEN_SCOPE",
        "FOUNDRY_API_KEY",
        "create_entra_client",
        "create_api_key_client",
        "create_project_client",
        "create_tool_probe",
        "/managed-deployments/<deployment-name>/v1",
        "DeploymentNotFound",
        "Model service is unavailable",
    )
    for marker in managed_compute_contract_markers:
        if marker not in readme or marker not in readme_cn:
            raise SystemExit(f"Missing Managed Compute API contract marker: {marker}")
    if re.search(r"AMD|MI300|Xiaomi|小米", generation_script + model_config, re.I):
        raise SystemExit("Runtime code must not be coupled to the validation hardware or customer")

    print(
        "REPO_VALIDATION=PASS "
        f"h2={len(h2_en)} code_blocks={len(blocks_en)} image={width}x{height}"
    )


if __name__ == "__main__":
    main()
