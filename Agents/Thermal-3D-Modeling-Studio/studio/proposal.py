from __future__ import annotations

import base64
import re
import unicodedata
import zipfile
from datetime import datetime
from io import BytesIO
from typing import Any

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Mm
from pydantic import BaseModel, Field, field_validator

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional fallback
    Image = None

_ALLOWED_IMAGE_KEYS = {"snapshot", "render", "concept", "drawing"}
_ALLOWED_IMAGE_MIMES = {"image/png", "image/jpeg"}
_ALLOWED_NARRATIVE_KEYS = {"executive_summary", "design_rationale", "risks", "next_steps"}
_MAX_IMAGE_BYTES = 6 * 1024 * 1024
_DATA_URL_RE = re.compile(r"^data:(image/(?:png|jpeg));base64,(.*)$", re.IGNORECASE | re.DOTALL)

LABELS = {
    "zh": {
        "subtitle": "GPT-6 生成的概念方案 · 需工程校核",
        "date": "生成时间",
        "requirement": "1 需求",
        "history": "迭代历史",
        "overview": "2 方案概述",
        "executive_summary": "方案要点",
        "renders": "3 三维模型与效果图",
        "snapshot": "三维模型截图（WebGL）",
        "render": "真实感渲染（图像模型生成，仅为示意）",
        "concept": "概念图",
        "drawing": "输入图纸 / 参考图",
        "image_error": "(图片无法解析 / image could not be decoded)",
        "estimates": "4 工程量估算",
        "metric": "指标",
        "value": "数值",
        "unit": "单位",
        "note": "说明",
        "vs_previous": "较上一版",
        "estimate_note": "注：上述数值来自参数化几何模型估算，未经 CAE/CAD 校核。",
        "step": "5 STEP 实体",
        "design_risks": "6 设计说明与风险",
        "design_rationale": "设计说明",
        "risks": "风险",
        "next_steps": "7 后续建议",
        "generation_info": "8 生成信息",
        "model": "文本模型",
        "image_model": "图像模型",
        "usage": "用量",
        "turns_elapsed": "轮次 / 耗时",
        "disclaimer": "本文件由生成式 AI 自动整理，几何、材料与工程量为概念级估算，未经 CAD/CAE 与工艺校核，不构成生产依据。",
    },
    "en": {
        "subtitle": "Concept proposal generated with GPT-6 · requires engineering review",
        "date": "Generated at",
        "requirement": "1 Requirement",
        "history": "Iteration history",
        "overview": "2 Overview",
        "executive_summary": "Executive summary",
        "renders": "3 3D model & renders",
        "snapshot": "3D model snapshot (WebGL)",
        "render": "Photoreal render (image model, illustrative only)",
        "concept": "Concept image",
        "drawing": "Input drawing / reference",
        "image_error": "(图片无法解析 / image could not be decoded)",
        "estimates": "4 Engineering estimates",
        "metric": "Metric",
        "value": "Value",
        "unit": "Unit",
        "note": "Note",
        "vs_previous": "vs previous",
        "estimate_note": "Note: values are model estimates from parametric geometry, not CAE/CAD-verified.",
        "step": "5 STEP solid",
        "design_risks": "6 Design notes & risks",
        "design_rationale": "Design rationale",
        "risks": "Risks",
        "next_steps": "7 Next steps",
        "generation_info": "8 Generation info",
        "model": "Model",
        "image_model": "Image model",
        "usage": "Usage",
        "turns_elapsed": "Turns / elapsed",
        "disclaimer": "This document was automatically assembled by generative AI. Geometry, materials, and engineering quantities are concept-level estimates, not validated by CAD/CAE or manufacturing review, and are not a production basis.",
    },
}


class ProposalMetric(BaseModel):
    label: str = Field(..., max_length=80)
    value: str = Field(..., max_length=40)
    unit: str = Field("", max_length=20)
    note: str = Field("", max_length=120)


class ProposalUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0
    turns: int = 0
    elapsed_s: float = 0


class ProposalPayload(BaseModel):
    lang: str = Field("zh", pattern=r"^(zh|en)$")
    title: str = Field(..., min_length=1, max_length=120)
    requirement: str = Field(..., min_length=1, max_length=4000)
    history: list[str] = Field(default_factory=list, max_length=10)
    summary: str = Field("", max_length=3000)
    metrics: list[ProposalMetric] = Field(default_factory=list, max_length=12)
    previous_metrics: list[ProposalMetric] | None = Field(default=None, max_length=12)
    suggestions: list[str] = Field(default_factory=list, max_length=6)
    images: dict[str, str] = Field(default_factory=dict)
    step: dict[str, str] = Field(default_factory=dict, max_length=12)
    usage: ProposalUsage | None = None
    model: str = Field("", max_length=80)
    image_model: str = Field("", max_length=80)
    narrative: dict[str, str] = Field(default_factory=dict)
    generated_at: str = ""

    @field_validator("history")
    @classmethod
    def _validate_history(cls, value: list[str]) -> list[str]:
        for item in value:
            if len(item) > 2000:
                raise ValueError("history items must be 2000 characters or fewer")
        return value

    @field_validator("suggestions")
    @classmethod
    def _validate_suggestions(cls, value: list[str]) -> list[str]:
        for item in value:
            if len(item) > 200:
                raise ValueError("suggestions must be 200 characters or fewer")
        return value

    @field_validator("images")
    @classmethod
    def _validate_images(cls, value: dict[str, str]) -> dict[str, str]:
        for key, data_url in value.items():
            if key not in _ALLOWED_IMAGE_KEYS:
                raise ValueError(f"unsupported image key: {key}")
            match = _DATA_URL_RE.match(data_url or "")
            if not match:
                mime = (data_url.split(";", 1)[0][5:] if data_url.startswith("data:") else "")
                if mime and mime not in _ALLOWED_IMAGE_MIMES:
                    raise ValueError(f"unsupported image mime type: {mime}")
                raise ValueError("image must be a PNG or JPEG data URL")
            b64 = re.sub(r"\s+", "", match.group(2))
            estimated = (len(b64) * 3) // 4 - min(b64[-2:].count("=") if b64 else 0, 2)
            if estimated > _MAX_IMAGE_BYTES:
                raise ValueError("image exceeds 6 MB decoded size limit")
        return value

    @field_validator("narrative")
    @classmethod
    def _validate_narrative(cls, value: dict[str, str]) -> dict[str, str]:
        for key, text in value.items():
            if key not in _ALLOWED_NARRATIVE_KEYS:
                raise ValueError(f"unsupported narrative key: {key}")
            if len(text) > 3000:
                raise ValueError("narrative sections must be 3000 characters or fewer")
        return value


def build_proposal_docx(payload: ProposalPayload) -> bytes:
    labels = LABELS[payload.lang]
    generated_at = payload.generated_at or datetime.now().astimezone().isoformat(timespec="minutes")

    doc = _new_document()
    section = doc.sections[0]
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    for attr in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
        setattr(section, attr, Cm(2))

    title = doc.add_heading(payload.title, 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle = doc.add_paragraph(labels["subtitle"])
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_line = doc.add_paragraph(f"{labels['date']}: {generated_at}")
    date_line.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_heading(labels["requirement"], level=1)
    _add_multiline(doc, payload.requirement)
    if payload.history:
        doc.add_heading(labels["history"], level=2)
        for item in payload.history:
            doc.add_paragraph(item, style="List Number")

    doc.add_heading(labels["overview"], level=1)
    _add_multiline(doc, payload.summary or "—")
    if payload.narrative.get("executive_summary"):
        doc.add_heading(labels["executive_summary"], level=2)
        _add_multiline(doc, payload.narrative["executive_summary"])

    doc.add_heading(labels["renders"], level=1)
    _add_images(doc, payload, labels)

    doc.add_heading(labels["estimates"], level=1)
    _add_metrics_table(doc, payload, labels)
    note = doc.add_paragraph(labels["estimate_note"])
    note.runs[0].italic = True

    if payload.step:
        doc.add_heading(labels["step"], level=1)
        _add_key_value_table(doc, payload.step)

    if payload.narrative.get("design_rationale") or payload.narrative.get("risks"):
        doc.add_heading(labels["design_risks"], level=1)
        if payload.narrative.get("design_rationale"):
            doc.add_heading(labels["design_rationale"], level=2)
            _add_multiline(doc, payload.narrative["design_rationale"])
        if payload.narrative.get("risks"):
            doc.add_heading(labels["risks"], level=2)
            _add_multiline(doc, payload.narrative["risks"])

    doc.add_heading(labels["next_steps"], level=1)
    for suggestion in payload.suggestions:
        doc.add_paragraph(suggestion, style="List Bullet")
    if payload.narrative.get("next_steps"):
        _add_multiline(doc, payload.narrative["next_steps"])
    if not payload.suggestions and not payload.narrative.get("next_steps"):
        doc.add_paragraph("—")

    doc.add_heading(labels["generation_info"], level=1)
    _add_generation_info(doc, payload, labels, generated_at)
    doc.add_paragraph(labels["disclaimer"])

    out = BytesIO()
    doc.save(out)
    return out.getvalue()


def proposal_filename(payload: ProposalPayload) -> str:
    generated_at = _parse_datetime(payload.generated_at) or datetime.now().astimezone()
    stamp = generated_at.strftime("%Y%m%d-%H%M")
    slug = unicodedata.normalize("NFKD", payload.title).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", slug).strip("-").lower() or "thermal3d"   # CJK-only titles fall back to the studio's file stem
    return f"{slug[:48]}-proposal-{stamp}.docx"


def _new_document() -> Any:
    try:
        return Document()
    except Exception:
        return Document(BytesIO(_minimal_docx_template()))


def _minimal_docx_template() -> bytes:
    files = {
        "[Content_Types].xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
</Types>""",
        "_rels/.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""",
        "word/_rels/document.xml.rels": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
</Relationships>""",
        "word/document.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body><w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr></w:body>
</w:document>""",
        "word/settings.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>""",
        "word/styles.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:rPr><w:b/><w:sz w:val="52"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:uiPriority w:val="9"/><w:qFormat/><w:pPr><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:uiPriority w:val="9"/><w:qFormat/><w:pPr><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="ListNumber"><w:name w:val="List Number"/><w:basedOn w:val="Normal"/><w:pPr><w:numPr><w:numId w:val="1"/></w:numPr></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="ListBullet"><w:name w:val="List Bullet"/><w:basedOn w:val="Normal"/><w:pPr><w:numPr><w:numId w:val="2"/></w:numPr></w:pPr></w:style>
</w:styles>""",
        "word/numbering.xml": """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum>
<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum>
<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num><w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>
</w:numbering>""",
    }
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return out.getvalue()


def _add_multiline(doc: Document, text: str) -> None:
    for line in (text or "").splitlines() or [""]:
        doc.add_paragraph(line)


def _set_table_style(table: Any) -> None:
    for style in ("Light Grid Accent 1", "Table Grid"):
        try:
            table.style = style
            return
        except Exception:
            continue


def _add_metrics_table(doc: Document, payload: ProposalPayload, labels: dict[str, str]) -> None:
    has_previous = payload.previous_metrics is not None
    headers = [labels["metric"], labels["value"], labels["unit"], labels["note"]]
    if has_previous:
        headers.append(labels["vs_previous"])
    table = doc.add_table(rows=1, cols=len(headers))
    _set_table_style(table)
    for idx, header in enumerate(headers):
        table.rows[0].cells[idx].text = header

    previous = {metric.label: metric for metric in payload.previous_metrics or []}
    for metric in payload.metrics:
        cells = table.add_row().cells
        values = [metric.label, metric.value, metric.unit, metric.note]
        if has_previous:
            values.append(_delta_text(metric.value, previous.get(metric.label).value if metric.label in previous else None))
        for idx, value in enumerate(values):
            cells[idx].text = value
    if not payload.metrics:
        cells = table.add_row().cells
        cells[0].text = "—"


def _add_key_value_table(doc: Document, values: dict[str, str]) -> None:
    table = doc.add_table(rows=0, cols=2)
    _set_table_style(table)
    for key, value in values.items():
        row = table.add_row().cells
        row[0].text = str(key)
        row[1].text = str(value)


def _add_generation_info(doc: Document, payload: ProposalPayload, labels: dict[str, str], generated_at: str) -> None:
    rows = {
        labels["model"]: payload.model or "—",
        labels["image_model"]: payload.image_model or "—",
        labels["date"]: generated_at,
    }
    if payload.usage:
        usage = payload.usage
        rows[labels["usage"]] = (
            f"input {usage.input_tokens}, output {usage.output_tokens}, total {usage.total_tokens}, "
            f"cached {usage.cached_tokens}, reasoning {usage.reasoning_tokens}"
        )
        rows[labels["turns_elapsed"]] = f"{usage.turns} / {usage.elapsed_s:.1f}s"
    _add_key_value_table(doc, rows)


def _add_images(doc: Document, payload: ProposalPayload, labels: dict[str, str]) -> None:
    added = False
    for key in ("snapshot", "render", "concept", "drawing"):
        data_url = payload.images.get(key)
        if not data_url:
            continue
        added = True
        doc.add_paragraph(labels[key])
        image_bytes = _decode_image(data_url)
        if image_bytes is None or not _add_picture(doc, image_bytes):
            paragraph = doc.add_paragraph()
            run = paragraph.add_run(labels["image_error"])
            run.italic = True
    if not added:
        doc.add_paragraph("—")


def _decode_image(data_url: str) -> bytes | None:
    match = _DATA_URL_RE.match(data_url or "")
    if not match:
        return None
    try:
        return base64.b64decode(re.sub(r"\s+", "", match.group(2)), validate=True)
    except Exception:
        return None


def _add_picture(doc: Document, image_bytes: bytes) -> bool:
    try:
        stream = BytesIO(image_bytes)
        if Image is not None:
            with Image.open(BytesIO(image_bytes)) as img:
                img.verify()
        doc.add_picture(stream, width=Cm(16))
        return True
    except Exception:
        return False


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", value.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _delta_text(current_value: str, previous_value: str | None) -> str:
    current = _parse_float(current_value)
    previous = _parse_float(previous_value)
    if current is None or previous is None or previous == 0:
        return "—"
    percent = (current - previous) / abs(previous) * 100
    if current == previous:
        return "—"
    if percent > 0:
        return f"▲ +{percent:.1f}%"
    return f"▼ −{abs(percent):.1f}%"


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

