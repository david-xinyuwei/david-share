import py_compile
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
TEXT_SUFFIXES = {".md", ".py", ".yaml", ".yml", ".txt", ".example", ".json", ".dockerignore", ".gitignore"}
REQUIRED_FILES = [
    "README.md",
    "README-CN.md",
    ".env.example",
    ".gitignore",
    ".dockerignore",
    "Dockerfile",
    "requirements.txt",
    "main.py",
    "agent.yaml",
    "agent.manifest.yaml",
    "scripts/create_toolbox.py",
    "scripts/verify_toolbox.py",
    "scripts/smoke_test.py",
    "scripts/http_smoke_test.py",
    "scripts/repo_check.py",
    "docs/architecture.md",
    "docs/demo-script.md",
    "docs/scenario-mapping.md",
    "docs/troubleshooting.md",
    "docs/validation.md",
    "docs/why-this-architecture.md",
    "docs/architecture-tradeoffs.md",
    "docs/comparison.md",
    "docs/mcp-protocol-deep-dive.md",
    "docs/request-flow-with-budget.md",
    "docs/failure-modes.md",
    "docs/production-scale.md",
    "docs/hybrid-edge-cloud.md",
    "docs/voice-and-multimodal.md",
    "docs/why-this-architecture-CN.md",
    "docs/architecture-tradeoffs-CN.md",
    "docs/comparison-CN.md",
    "docs/mcp-protocol-deep-dive-CN.md",
    "docs/request-flow-with-budget-CN.md",
    "docs/failure-modes-CN.md",
    "docs/production-scale-CN.md",
    "docs/hybrid-edge-cloud-CN.md",
    "docs/voice-and-multimodal-CN.md",
    "examples/hybrid-edge-cloud/contract.py",
    "examples/hybrid-edge-cloud/edge_agent.py",
    "examples/hybrid-edge-cloud/cloud_handoff.py",
    "examples/hybrid-edge-cloud/README.md",
    "examples/hybrid-edge-cloud/README-CN.md",
    "infra/setup_foundry.py",
    "scripts/measure_latency.py",
    "examples/custom-mcp-server/custom_mcp_server.py",
    "examples/custom-mcp-server/custom_mcp_client.py",
    "examples/custom-mcp-server/README.md",
    "examples/custom-mcp-server/README-CN.md",
    "examples/requests/code_interpreter.json",
    "examples/requests/direct_web_search.json",
]
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"hf_[A-Za-z0-9]{30,}"),
    re.compile(r"api[_-]?key\s*[=:]\s*['\"][^'\"]{16,}['\"]", re.IGNORECASE),
    re.compile(r'"api-key"[\s\S]{0,300}"default"\s*:\s*"[A-Za-z0-9]{16,}"', re.IGNORECASE),
    re.compile(r"apim-(?!<)[A-Za-z0-9-]+\.azure-api\.net", re.IGNORECASE),
    re.compile(r"https://(?!<account>)[A-Za-z0-9-]+\.services\.ai\.azure\.com/api/projects/(?!<project>)[A-Za-z0-9_-]+", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9-]+\.eastasia\.cloudapp\.azure\.com(?::\d+)?\b", re.IGNORECASE),
]
FORBIDDEN_PUBLIC_TERMS = [
    "总" + "司令",
    "虎" + "豹骑",
    "柯" + "南",
    "星" + "链",
    "雷" + "神",
    "哨" + "兵",
    "Qi" + "ra",
    "太" + "极石",
    "Leno" + "vo",
]


def pass_msg(message: str) -> None:
    print(f"PASS {message}")


def fail_msg(message: str) -> None:
    print(f"FAIL {message}")


def iter_text_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name == ".env" or not path.is_file():
            continue
        if path.suffix in TEXT_SUFFIXES or path.name in {"Dockerfile", ".dockerignore", ".gitignore"}:
            files.append(path)
    return files


def check_required_files() -> bool:
    ok = True
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).exists():
            fail_msg(f"missing {relative}")
            ok = False
    if ok:
        pass_msg("required files present")
    return ok


def check_python_compile() -> bool:
    ok = True
    for path in sorted(ROOT.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as error:
            fail_msg(f"python syntax {path.relative_to(ROOT)}: {error.msg}")
            ok = False
    if ok:
        pass_msg("python files compile")
    return ok


def check_manifest_text() -> bool:
    ok = True
    checks = {
        "agent.yaml": ["protocol: responses", "FOUNDRY_PROJECT_ENDPOINT", "ENABLE_DIRECT_WEB_SEARCH"],
        "agent.manifest.yaml": ["kind: hosted", "kind: toolbox", "code_interpreter"],
        ".env.example": ["FOUNDRY_PROJECT_ENDPOINT", "TOOLBOX_NAME", "ENABLE_DIRECT_WEB_SEARCH"],
    }
    for relative, needles in checks.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                fail_msg(f"{relative} missing {needle}")
                ok = False
    if ok:
        pass_msg("manifest and env text checks")
    return ok


def check_public_safety() -> bool:
    ok = True
    for path in iter_text_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        relative = path.relative_to(ROOT)
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                fail_msg(f"possible secret in {relative}")
                ok = False
        for term in FORBIDDEN_PUBLIC_TERMS:
            if term in text:
                fail_msg(f"customer/internal term '{term}' in {relative}")
                ok = False
    if ok:
        pass_msg("no obvious secrets or customer/internal terms in public files")
    return ok


def main() -> None:
    checks = [
        check_required_files(),
        check_python_compile(),
        check_manifest_text(),
        check_public_safety(),
    ]
    if not all(checks):
        sys.exit(1)
    print("PASS repo check complete")


if __name__ == "__main__":
    main()