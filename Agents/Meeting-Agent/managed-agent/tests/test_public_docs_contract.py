from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _squash_whitespace(text: str) -> str:
    return " ".join(text.split())


def test_public_docs_describe_one_repo_two_implementations() -> None:
    english = (ROOT / "docs" / "MANAGED-IMPLEMENTATION.md").read_text(
        encoding="utf-8"
    )
    chinese = (ROOT / "docs" / "MANAGED-IMPLEMENTATION-CN.md").read_text(
        encoding="utf-8"
    )

    assert "same repository, not a second repository" in english
    assert "不是第二个Repo" in chinese
    assert "prompt-style local orchestration" in english
    assert "本机prompt-style编排" in chinese
    assert "managed-agent/" in english
    assert "managed-agent/" in chinese


def test_public_docs_explain_ghcp_source_and_runtime_boundaries() -> None:
    english = (ROOT / "docs" / "IMPLEMENTATION-COMPARISON.md").read_text(
        encoding="utf-8"
    )
    chinese = (ROOT / "docs" / "IMPLEMENTATION-COMPARISON-CN.md").read_text(
        encoding="utf-8"
    )

    english_flat = _squash_whitespace(english)
    chinese_flat = _squash_whitespace(chinese)

    assert "What `GHCP Harness` Means" in english
    assert "`GHCP Harness` 到底是什么" in chinese
    assert "GitHub is an optional source-control" in english_flat
    assert "GitHub 可以承载源码和 CI/CD" in chinese_flat
    assert "no other harness value was validated" in english_flat
    assert "没有证据证明还可以设置其他值" in chinese_flat
    assert "Foundry Hosted Agent" in english
    assert "Foundry Hosted Agent" in chinese
    assert "Wrapper → deployed Agent" in english
    assert "Wrapper → 已部署 Agent" in chinese
    assert "A GPT-5.4 model API key cannot replace this identity" in english
    assert "GPT-5.4 模型 API Key 不能替代这条身份链" in chinese
    assert "langgraph" in english.casefold()
    assert "langgraph" in chinese.casefold()
    assert "not an invented harness value" in english.casefold()
    assert "不是自造 harness 值" in chinese.casefold()


def test_public_docs_ground_managed_agent_definition_in_microsoft_learn() -> None:
    english = (ROOT / "docs" / "MANAGED-IMPLEMENTATION.md").read_text(
        encoding="utf-8"
    )
    chinese = (ROOT / "docs" / "MANAGED-IMPLEMENTATION-CN.md").read_text(
        encoding="utf-8"
    )
    official_urls = (
        "https://learn.microsoft.com/azure/foundry/agents/overview",
        "https://learn.microsoft.com/azure/foundry/agents/quickstarts/prompt-agent",
        "https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents",
        "https://learn.microsoft.com/azure/foundry/agents/concepts/development-lifecycle",
        "https://learn.microsoft.com/azure/foundry/agents/concepts/agent-identity",
        "https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox",
        "https://github.com/microsoft/AgentSchema",
        "https://raw.githubusercontent.com/microsoft/AgentSchema/refs/heads/main/schemas/v1.0/PromptAgent.yaml",
    )
    english_flat = _squash_whitespace(english)
    chinese_flat = _squash_whitespace(chinese)

    assert "Microsoft Official Definition and This Implementation" in english
    assert "微软官方定义与本项目映射" in chinese
    assert "This is the deployed Managed Meeting Agent" in english
    assert "本项目部署的 Managed Meeting Agent 属于这一类" in chinese
    assert "not a Hosted Agent" in english_flat
    assert "不是 Hosted Agent" in chinese_flat
    assert "retrieved 2026-07-27" in english
    assert "访问日期：2026-07-27" in chinese
    for url in official_urls:
        assert url in english
        assert url in chinese


def test_agent_manifest_distinguishes_schema_type_from_managed_runtime() -> None:
    manifest = (ROOT / "agent.yaml").read_text(encoding="utf-8")
    english = (ROOT / "docs" / "MANAGED-IMPLEMENTATION.md").read_text(
        encoding="utf-8"
    )
    chinese = (ROOT / "docs" / "MANAGED-IMPLEMENTATION-CN.md").read_text(
        encoding="utf-8"
    )
    english_flat = _squash_whitespace(english)
    chinese_flat = _squash_whitespace(chinese)

    assert "yaml-language-server: $schema=" in manifest
    assert "microsoft/AgentSchema" in manifest
    assert "schemas/v1.0/PromptAgent.yaml" in manifest
    assert "Authoring schema only" in manifest
    assert "kind: prompt" in manifest
    assert "There is no `kind: managed` value" in manifest
    assert "`kind: prompt` identifies what is declared" in english_flat
    assert "`kind: prompt` 说明“定义了哪种 Agent”" in chinese_flat
    assert "There is no documented\n`kind: managed`" in english
    assert "没有文档化的 `kind: managed`" in chinese
    assert "There is no `kind: managed` value" in english
    assert "官方不存在 `kind: managed`" in chinese
    assert "does not select a runtime host" in english
    assert "不会选择 Runtime Host" in chinese
    assert "does not bind this Agent to a customer GitHub" in english_flat
    assert "不会把 Agent 绑定到客户 GitHub Repo" in chinese_flat


def test_docs_scope_skill_evidence_by_agent_version() -> None:
    english = (ROOT / "docs" / "MANAGED-IMPLEMENTATION.md").read_text(
        encoding="utf-8"
    )
    chinese = (ROOT / "docs" / "MANAGED-IMPLEMENTATION-CN.md").read_text(
        encoding="utf-8"
    )
    parity = (ROOT / "FEATURE-PARITY.md").read_text(encoding="utf-8")
    parity_cn = (ROOT / "FEATURE-PARITY-CN.md").read_text(encoding="utf-8")

    assert "current source adds an independently versionable `presentation-story`" in english
    assert "当前源码新增可独立版本化的 `presentation-story`" in chinese
    assert "dual-Skill live validation pending a new Agent version" in parity
    assert "双Skill Live验收等待新Agent Version" in parity_cn
    assert "does **not** prove that `presentation-story` is deployed" in english
    assert "**不证明** `presentation-story` 已部署" in chinese


def test_customer_runbook_and_package_use_current_runtime_boundaries() -> None:
    start_en = (ROOT / "CUSTOMER-START-HERE.md").read_text(encoding="utf-8")
    start_cn = (ROOT / "CUSTOMER-START-HERE-CN.md").read_text(encoding="utf-8")
    package = (ROOT / "scripts" / "build_customer_package.py").read_text(
        encoding="utf-8"
    )
    managed_doc = (ROOT / "docs" / "MANAGED-IMPLEMENTATION.md").read_text(
        encoding="utf-8"
    )

    assert '-ManagedAgentVersion "<active-version>"' in start_en
    assert '-ManagedAgentVersion "<active-version>"' in start_cn
    assert '-ManagedAgentVersion "2"' not in start_en + start_cn
    assert "large-input-recovery-validation.json" in package
    assert "source implementation now completes the presentation-domain separation" in (
        managed_doc
    )
    assert "dual-Skill Agent version" in managed_doc
