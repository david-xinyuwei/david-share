"""Validate bilingual README shape, local links, images, and critical claims."""

from __future__ import annotations

import re
import struct
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
README_PATHS = (ROOT / "README.md", ROOT / "README-CN.md")
CUSTOMER_PATHS = (ROOT / "CUSTOMER-START-HERE.md", ROOT / "CUSTOMER-START-HERE-CN.md")
WORKFLOW_PATH = ROOT.parents[1] / ".github" / "workflows" / "voice-live-aipc-ci.yml"
SCENARIO_IMAGES = (
    "images/scenario-medication-recognition.png",
    "images/scenario-email-delivery.png",
    "images/scenario-volume-control.png",
    "images/scenario-wallpaper-change.png",
)
UI_IMAGE = "images/voice-live-aipc-ui.png"
ARCHITECTURE_IMAGE = "images/voice-live-aipc-architecture.svg"
EXPECTED_IMAGES = SCENARIO_IMAGES + (UI_IMAGE, ARCHITECTURE_IMAGE)


def local_links(text: str) -> list[str]:
    links = []
    for target in re.findall(r"(?<!!)\[[^]]*]\(([^)]+)\)", text):
        target = target.split("#", 1)[0]
        if target and not target.startswith(("http://", "https://", "mailto:", "#")):
            links.append(target)
    return links


def local_images(text: str) -> list[str]:
    return [
        target
        for target in re.findall(r"!\[[^]]*]\(([^)]+)\)", text)
        if not target.startswith(("http://", "https://"))
    ]


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


def main() -> int:
    texts = [path.read_text(encoding="utf-8") for path in README_PATHS]
    headings = [re.findall(r"^(#{1,6}) ", text, flags=re.MULTILINE) for text in texts]
    fences = [re.findall(r"^```([^\r\n]*)", text, flags=re.MULTILINE) for text in texts]
    table_shapes = [
        [line.count("|") for line in text.splitlines() if re.fullmatch(r"\|[-:| ]+\|", line)]
        for text in texts
    ]
    images = [local_images(text) for text in texts]

    assert headings[0] == headings[1]
    assert fences[0] == fences[1]
    assert table_shapes[0] == table_shapes[1]
    assert tuple(images[0]) == EXPECTED_IMAGES
    assert images[0] == images[1]

    for text in texts:
        for link in local_links(text):
            assert (ROOT / link).exists(), link
        assert "Voice Live" in text
        assert "AIPC" in text
        assert "APIC" not in text
        assert text.count("24") >= 5
        assert "gpt-realtime" in text
        assert "gpt-4o-transcribe" in text
        assert "Microsoft Graph" in text
        assert "test-fixture" in text
        assert "https://learn.microsoft.com/azure/ai-services/speech-service/voice-live" in text
        assert ".mp4" not in text.casefold()
        for scenario_image in SCENARIO_IMAGES:
            assert scenario_image in text

    assert "No mock fallback" in texts[0]
    assert "No production certification" in texts[0]
    assert "## Technology stack and call paths" in texts[0]
    assert "## Scenario evidence" in texts[0]
    assert "No video is published" in texts[0]
    assert "Web search is implemented with **WebIQ**, not Bing" in texts[0]
    assert "不做 mock fallback" in texts[1]
    assert "不是生产认证" in texts[1]
    assert "## 技术栈与调用路径" in texts[1]
    assert "## 场景证据" in texts[1]
    assert "本仓库不发布视频" in texts[1]
    assert "Web Search 使用 **WebIQ**，不是 Bing" in texts[1]

    bilingual_claims = (
        (
            "The default validated path is **Voice Live**, not direct Realtime and not the Foundry Agent mode.",
            "默认且经过验证的路径是 **Voice Live**，不是 direct Realtime，也不是 Foundry Agent 模式。",
        ),
        (
            "the client cannot inject runtime instructions or tools",
            "客户端不能注入 runtime instructions 或 tools",
        ),
        (
            "Microsoft Graph is the default mail transport",
            "Microsoft Graph 是默认邮件传输方式",
        ),
        (
            "The current Tkinter chrome and deterministic tool-card labels remain Chinese-first",
            "当前 Tkinter 界面与确定性的 tool-card 标签仍以中文为主",
        ),
        (
            "They contain no human face or profile avatar, email or account identifier, desktop icon/folder/filename, or local path.",
            "截图中不包含真人、人像或账号头像，不包含邮箱或账号标识，不包含桌面图标、目录、文件名，也不包含本机路径。",
        ),
    )
    for english_claim, chinese_claim in bilingual_claims:
        assert english_claim in texts[0]
        assert chinese_claim in texts[1]

    customer_texts = [path.read_text(encoding="utf-8") for path in CUSTOMER_PATHS]
    customer_headings = [
        re.findall(r"^(#{1,6}) ", text, flags=re.MULTILINE) for text in customer_texts
    ]
    customer_fences = [
        re.findall(r"^```([^\r\n]*)", text, flags=re.MULTILINE) for text in customer_texts
    ]
    assert customer_headings[0] == customer_headings[1]
    assert customer_fences[0] == customer_fences[1]
    for text in customer_texts:
        for link in local_links(text):
            assert (ROOT / link).exists(), link
        assert "Voice Live" in text
        assert "AIPC" in text
        assert "gpt-realtime" in text
        assert "24" in text

    assert WORKFLOW_PATH.is_file(), WORKFLOW_PATH
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert '"Agents/Voice-Live-API-AIPC/**"' in workflow
    assert "SELF_CHECK=PASS" in workflow
    assert "pre_delivery_check.py" in workflow

    svg_root = ElementTree.parse(ROOT / ARCHITECTURE_IMAGE).getroot()
    assert svg_root.attrib["width"] == "1600"
    assert svg_root.attrib["height"] == "900"
    labels = " ".join("".join(node.itertext()) for node in svg_root.iter())
    for label in (
        "Windows AIPC",
        "Azure Voice Live WebSocket",
        "24 registered local tools",
        "Azure OpenAI Realtime",
        "Foundry Agent",
        "WebIQ Web Search",
        "Microsoft Graph API",
        "Azure OpenAI chat / image",
        "Open-Meteo",
    ):
        assert label in labels

    ui_path = ROOT / UI_IMAGE
    assert png_size(ui_path) == (1136, 739)
    assert ui_path.stat().st_size > 40_000

    print(
        f"PASS: bilingual READMEs share {len(headings[0])} headings, "
        f"{len(fences[0]) // 2} code blocks, {len(table_shapes[0])} tables, "
        f"and {len(images[0])} validated images; customer pages and monorepo CI are present."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
