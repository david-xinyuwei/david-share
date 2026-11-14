import base64
import re
import unittest
import zipfile
from io import BytesIO

from pydantic import ValidationError

from proposal import ProposalMetric, ProposalPayload, ProposalUsage, build_proposal_docx, proposal_filename

PNG_1X1 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
PNG_URL = f"data:image/png;base64,{PNG_1X1}"


def document_xml(docx_bytes):
    with zipfile.ZipFile(BytesIO(docx_bytes)) as archive:
        return archive.read("word/document.xml").decode("utf-8"), archive.namelist()


class ProposalTests(unittest.TestCase):
    def test_full_zh_payload_contains_expected_content(self):
        payload = ProposalPayload(
            title="thermal3d",
            requirement="需要一个换热器概念模型",
            history=["第一版需求"],
            summary="概念方案摘要",
            metrics=[
                ProposalMetric(label="散热面积", value="112", unit="cm2", note="估算"),
                ProposalMetric(label="压降", value="96", unit="kPa", note="估算"),
            ],
            previous_metrics=[
                ProposalMetric(label="散热面积", value="100", unit="cm2"),
                ProposalMetric(label="压降", value="100", unit="kPa"),
            ],
            suggestions=["继续校核流道"],
            step={"文件": "thermal3d-demo.step", "体积": "123.4 cm³"},
            usage=ProposalUsage(input_tokens=10, output_tokens=20, total_tokens=30, cached_tokens=3, reasoning_tokens=4, turns=2, elapsed_s=1.2),
            model="gpt-6-astra",
            image_model="gpt-image-2.5-sunburst",
            narrative={"executive_summary": "方案要点文本", "design_rationale": "设计说明文本", "risks": "风险文本", "next_steps": "下一步文本"},
            generated_at="2026-09-11T19:51:00+08:00",
        )
        data = build_proposal_docx(payload)
        xml, names = document_xml(data)
        self.assertIn("word/document.xml", names)
        self.assertIn("需要一个换热器概念模型", xml)
        self.assertIn("散热面积", xml)
        self.assertIn("▲", xml)
        self.assertIn("▼", xml)
        self.assertIn("thermal3d-demo.step", xml)
        self.assertIn("gpt-6-astra", xml)

    def test_en_payload_uses_english_labels(self):
        payload = ProposalPayload(
            lang="en",
            title="thermal3d",
            requirement="Create a heat exchanger concept.",
            metrics=[ProposalMetric(label="Area", value="10", unit="cm2")],
        )
        xml, _ = document_xml(build_proposal_docx(payload))
        self.assertIn("Engineering estimates", xml)
        self.assertNotIn("工程量估算", xml)

    def test_valid_png_data_url_is_embedded(self):
        payload = ProposalPayload(title="image", requirement="show image", images={"snapshot": PNG_URL})
        _, names = document_xml(build_proposal_docx(payload))
        self.assertTrue(any(name.startswith("word/media/") for name in names))

    def test_invalid_base64_image_is_skipped_with_note(self):
        payload = ProposalPayload(title="bad image", requirement="show image", images={"snapshot": "data:image/png;base64,not-valid-base64"})
        xml, _ = document_xml(build_proposal_docx(payload))
        self.assertIn("image could not be decoded", xml)

    def test_gif_image_raises(self):
        with self.assertRaises((ValueError, ValidationError)):
            ProposalPayload(title="gif", requirement="bad", images={"snapshot": "data:image/gif;base64,AAAA"})

    def test_oversize_image_raises_without_real_png(self):
        encoded_len = ((6 * 1024 * 1024 + 1 + 2) // 3) * 4
        with self.assertRaises((ValueError, ValidationError)):
            ProposalPayload(title="large", requirement="bad", images={"snapshot": "data:image/png;base64," + ("A" * encoded_len)})

    def test_validation_limits(self):
        with self.assertRaises(ValidationError):
            ProposalPayload(title="h", requirement="r", history=["x"] * 11)
        with self.assertRaises((ValueError, ValidationError)):
            ProposalPayload(title="i", requirement="r", images={"unknown": PNG_URL})
        with self.assertRaises(ValidationError):
            ProposalPayload(title="m", requirement="r", metrics=[ProposalMetric(label=str(i), value="1") for i in range(13)])

    def test_proposal_filename_is_ascii_docx(self):
        payload = ProposalPayload(title="散热 Thermal 方案", requirement="r", generated_at="2026-09-11T19:51:00+08:00")
        name = proposal_filename(payload)
        self.assertTrue(name.endswith(".docx"))
        self.assertRegex(name, r"^[\x00-\x7F]+$")
        self.assertIsNotNone(re.match(r"thermal-proposal-20260911-1951\.docx", name))


if __name__ == "__main__":
    unittest.main()

