from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_public_files_do_not_use_private_project_alias() -> None:
    private_alias = "yun" + "shang"
    for relative in (
        "README.md",
        "README-CN.md",
        "CUSTOMER-START-HERE.md",
        "CUSTOMER-START-HERE-CN.md",
        "agent.yaml",
        "azure.yaml",
        "evidence-managed-agent.json",
    ):
        assert private_alias not in (ROOT / relative).read_text(encoding="utf-8").casefold()
