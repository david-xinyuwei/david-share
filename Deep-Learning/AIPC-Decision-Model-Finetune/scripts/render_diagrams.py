"""Render the three project-specific workflow diagrams with Pillow and a CJK font."""
import argparse
import hashlib
import html
import json
import math
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
INK = "#243746"
BLUE = "#0078D4"
GREY = "#D9E1E7"


class Diagram:
    def __init__(self, height, title, subtitle, font_path):
        self.image = Image.new("RGB", (800, height), "white")
        self.draw = ImageDraw.Draw(self.image)
        self.title_font = ImageFont.truetype(str(font_path), 38)
        self.node_font = ImageFont.truetype(str(font_path), 30)
        self.detail_font = ImageFont.truetype(str(font_path), 26)
        self.draw.rectangle((0, 0, 800, 105), fill="#F1F5F8")
        self.draw.rectangle((0, 0, 8, 105), fill=BLUE)
        self.text((30, 17), title, self.title_font, 740, BLUE)
        self.text((30, 66), subtitle, self.detail_font, 740, INK)

    def text(self, position, text, font, max_width, fill):
        if self.draw.textlength(text, font=font) > max_width:
            raise ValueError(f"Diagram label is too wide: {text}")
        self.draw.text(position, text, font=font, fill=fill)

    def box(self, bounds, title, detail, fill="white", stroke=BLUE):
        left, top, right, bottom = bounds
        self.draw.rounded_rectangle(bounds, radius=5, fill=fill, outline=stroke, width=2)
        lines = detail.split("\n")
        total_height = 40 + len(lines) * 34
        if total_height > bottom - top - 20:
            raise ValueError(f"Diagram node is too short: {title}")
        baseline = top + (bottom - top - total_height) // 2
        title_width = self.draw.textlength(title, font=self.node_font)
        self.text((left + (right - left - title_width) / 2, baseline), title,
                  self.node_font, right - left - 28, INK)
        for index, line in enumerate(lines):
            width = self.draw.textlength(line, font=self.detail_font)
            self.text((left + (right - left - width) / 2, baseline + 44 + 34 * index),
                      line, self.detail_font, right - left - 28, INK)

    def arrow(self, points):
        self.draw.line(points, fill=BLUE, width=3, joint="curve")
        previous, end = points[-2:]
        angle = math.atan2(end[1] - previous[1], end[0] - previous[0])
        triangle = [end]
        for offset in (-0.48, 0.48):
            triangle.append((end[0] - 14 * math.cos(angle + offset), end[1] - 14 * math.sin(angle + offset)))
        self.draw.polygon(triangle, fill=BLUE)

    def save(self, path):
        self.image.save(path)
        return {"file": path.name, "width": self.image.width, "height": self.image.height,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def training(font_path):
    diagram = Diagram(995, "1  训练与模型导出", "云端更新模型，导出文件交给笔记本", font_path)
    diagram.arrow([(197, 245), (197, 290), (400, 290), (400, 335)])
    diagram.arrow([(602, 245), (602, 290), (400, 290), (400, 335)])
    diagram.arrow([(400, 460), (400, 500)])
    diagram.arrow([(400, 610), (400, 655)])
    diagram.arrow([(250, 715), (320, 715)])
    diagram.arrow([(545, 780), (545, 820), (400, 820), (400, 865)])
    diagram.box((40, 135, 355, 245), "训练数据", "标注样本＋回放数据", fill="#F4F6F8", stroke=GREY)
    diagram.box((445, 135, 760, 245), "Kev 发布版", "0.8B 或 4B", fill="#EAF4FC")
    diagram.box((150, 335, 650, 460), "GPU 微调", "更新 LoRA 和指针头", fill="#F2F8E8", stroke="#618B16")
    diagram.box((150, 500, 650, 610), "业务检查点", "FT 与 FT-cf 分别训练、保存")
    diagram.box((25, 660, 250, 770), "校准集", "不做梯度训练", fill="#F4F6F8", stroke=GREY)
    diagram.box((320, 655, 775, 780), "校准概率温度", "固定权重，只拟合温度")
    diagram.box((150, 865, 650, 975), "CPU 导出 GGUF", "合并权重，写入校准温度", fill="#EAF4FC")
    return diagram


def inference(font_path):
    diagram = Diagram(790, "2  笔记本本地推理", "只做判断，不训练，不调用云端模型", font_path)
    diagram.arrow([(400, 265), (400, 345)])
    diagram.arrow([(400, 520), (400, 600)])
    diagram.box((100, 140, 700, 265), "业务输入", "用户原话＋设备信息，不带标签", fill="#F4F6F8", stroke=GREY)
    diagram.box((100, 345, 700, 520), "笔记本 CPU · llama.cpp", "加载微调后的 GGUF\nPOST /v1/systemone", fill="#EAF4FC")
    diagram.box((100, 600, 700, 775), "结构化决策", "返回选项、是非、等级和概率\n业务程序另行决定是否执行")
    return diagram


def validation(font_path):
    diagram = Diagram(950, "3  效果与引擎验证", "测试阶段：比较结果，不更新模型", font_path)
    diagram.arrow([(400, 245), (400, 285), (195, 285), (195, 330)])
    diagram.arrow([(400, 245), (400, 285), (605, 285), (605, 330)])
    diagram.arrow([(195, 505), (195, 550), (400, 550), (400, 605)])
    diagram.arrow([(605, 505), (605, 550), (400, 550), (400, 605)])
    diagram.arrow([(400, 780), (400, 830)])
    diagram.box((125, 135, 675, 245), "同一测试集", "输入给模型，标签留给评分程序", fill="#F4F6F8", stroke=GREY)
    diagram.box((25, 330, 365, 505), "云端 PyTorch", "GPU 推理\n保存逐题预测", fill="#F2F8E8", stroke="#618B16")
    diagram.box((435, 330, 775, 505), "笔记本 llama.cpp", "CPU / Adreno 推理\n记录耗时与内存", fill="#EAF4FC")
    diagram.box((75, 605, 725, 780), "核对两类结果", "对照标准答案：业务准确率\n对照两个引擎：答案一致率")
    diagram.box((100, 830, 700, 940), "验证结果", "准确率、一致率、时延和内存")
    return diagram


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids.add(attributes["id"])
        for name in (("src",) if tag == "img" else ("href",) if tag == "a" else ()):
            if attributes.get(name):
                self.paths.append(attributes[name])


def preview_documents():
    from markdown_it import MarkdownIt

    sources = [ROOT / "README.md", ROOT / "文档" / "微调与端侧验证报告_20261027-130700.md",
               ROOT / "文档" / "[NOTES]_实验协议_20261027-124000.md"]
    pages = {}
    style = """body{margin:0;color:#1f2328;background:#fff;font:16px/1.65 'Segoe UI','Microsoft YaHei',sans-serif;letter-spacing:0}
main{max-width:980px;margin:0 auto;padding:28px 24px 80px;overflow-wrap:anywhere}h1{font-size:30px;line-height:1.3}
h2{font-size:24px;border-bottom:1px solid #d1d9e0;padding-bottom:8px;margin-top:40px}h3{font-size:20px;margin-top:28px}
h4{font-size:17px}a{color:#0969da}img{max-width:100%;height:auto}blockquote{border-left:4px solid #d1d9e0;margin-left:0;padding-left:16px;color:#59636e}
pre{background:#f6f8fa;padding:16px;overflow-x:auto;border-radius:6px;font-size:13px;line-height:1.55}code{font-family:Consolas,monospace}
:not(pre)>code{background:#eff1f3;padding:2px 4px;border-radius:3px}.table-scroll{overflow-x:auto;margin:16px 0}
table{border-collapse:collapse;font-size:14px;width:max-content;min-width:100%}th,td{border:1px solid #d1d9e0;padding:7px 12px;max-width:400px}
th{background:#f6f8fa;text-align:left}tr:nth-child(even){background:#f6f8fa}li{margin:5px 0}
@media(max-width:500px){main{padding:16px 16px 48px}h1{font-size:26px}th,td{min-width:100px;max-width:250px}}
"""
    for source in sources:
        parser = MarkdownIt("commonmark", {"html": True}).enable("table")
        tokens = parser.parse(source.read_text(encoding="utf-8"))
        slugs = {}
        for index, token in enumerate(tokens):
            if token.type == "heading_open":
                heading = tokens[index + 1].content
                slug = re.sub(r"[^\w\s-]", "", heading.lower()).replace(" ", "-")
                occurrence = slugs.get(slug, 0)
                slugs[slug] = occurrence + 1
                token.attrSet("id", slug if not occurrence else f"{slug}-{occurrence}")
        parser.renderer.rules["table_open"] = lambda tokens, index, options, env: '<div class="table-scroll"><table>\n'
        parser.renderer.rules["table_close"] = lambda tokens, index, options, env: '</table></div>\n'
        body = parser.renderer.render(tokens, parser.options, {})
        references = References()
        references.feed(body)
        pages[source.resolve()] = (body, references, tokens, parser)
    checked = 0
    for source, (_, references, _, _) in pages.items():
        for reference in references.paths:
            parsed = urlsplit(reference)
            if parsed.scheme or parsed.netloc:
                continue
            target = (source.parent / unquote(parsed.path)).resolve() if parsed.path else source
            if not target.exists():
                raise ValueError(f"Broken local link in {source.name}: {reference}")
            if parsed.fragment and target in pages and unquote(parsed.fragment) not in pages[target][1].ids:
                raise ValueError(f"Broken anchor in {source.name}: {reference}")
            checked += 1
    for source, (_, _, tokens, parser) in pages.items():
        for token in tokens:
            for child in token.children or []:
                if child.type == "link_open":
                    parsed = urlsplit(child.attrGet("href") or "")
                    if not parsed.scheme and parsed.path:
                        target = (source.parent / unquote(parsed.path)).resolve()
                        if target in pages:
                            child.attrSet("href", urlunsplit(("", "", parsed.path[:-3] + ".preview.html", parsed.query, parsed.fragment)))
        body = parser.renderer.render(tokens, parser.options, {})
        destination = source.with_suffix(".preview.html")
        destination.write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
                               '<meta name="viewport" content="width=device-width,initial-scale=1">'
                               f'<title>{html.escape(source.stem)}</title><style>{style}</style><main>{body}</main></html>', encoding="utf-8")
    return {"pages": len(pages), "local_links_checked": checked}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, default=Path("C:/Windows/Fonts/msyh.ttc"))
    parser.add_argument("--out", type=Path, default=ROOT / "images")
    parser.add_argument("--preview", action="store_true", help="validate links and render ignored local HTML previews")
    arguments = parser.parse_args()
    if not arguments.font.is_file():
        parser.error("Provide --font with a locally installed CJK TrueType/OpenType font")
    arguments.out.mkdir(parents=True, exist_ok=True)
    assets = []
    for name, factory, sources in (
        ("training", training, ["scripts/remote_pipeline_v2.sh", "scripts/remote_cf_round.sh", "scripts/remote_export_gguf.sh"]),
        ("inference", inference, ["scripts/systemone_client.py", "scripts/run_engine_eval.ps1"]),
        ("validation", validation, ["scripts/remote_pipeline_v2.sh", "scripts/run_engine_eval.ps1", "scripts/parity.py"]),
    ):
        asset = factory(arguments.font).save(arguments.out / f"{name}.png")
        asset.update({"kind": "original explanatory diagram", "sources": sources,
                      "proves": "project workflow and stage ownership", "does_not_prove": "model accuracy or runtime success"})
        assets.append(asset)
    ledger = {"generator": "scripts/render_diagrams.py", "font": arguments.font.name,
              "reference": "https://github.com/jaredpalmer/kev/blob/2074cc44256200bb37540103fa4572901faa10f3/README.md",
              "selection": "Upstream model/accuracy and playground figures do not describe this project's training, export and laptop validation paths.",
              "visual_scope": "Generic workflow stages, not Azure service-resource icons or product screenshots.",
              "assets": assets}
    (arguments.out / "provenance.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    preview = preview_documents() if arguments.preview else None
    print(json.dumps({"status": "PASS", "assets": assets, "preview": preview}, ensure_ascii=False))


if __name__ == "__main__":
    main()