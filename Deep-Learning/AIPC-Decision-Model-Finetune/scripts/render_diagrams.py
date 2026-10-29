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
        self.image = Image.new("RGB", (1200, height), "white")
        self.draw = ImageDraw.Draw(self.image)
        self.title_font = ImageFont.truetype(str(font_path), 32)
        self.node_font = ImageFont.truetype(str(font_path), 28)
        self.detail_font = ImageFont.truetype(str(font_path), 22)
        self.draw.rectangle((24, 21, 29, 59), fill=BLUE)
        self.text((43, 16), title, self.title_font, 1133, INK)
        self.text((24, 65), subtitle, self.detail_font, 1152, "#536471")

    def text(self, position, text, font, max_width, fill):
        if self.draw.textlength(text, font=font) > max_width:
            raise ValueError(f"Diagram label is too wide: {text}")
        self.draw.text(position, text, font=font, fill=fill)

    def box(self, bounds, title, detail, fill="white", stroke=BLUE):
        left, top, right, bottom = bounds
        self.draw.rounded_rectangle(bounds, radius=5, fill=fill, outline=stroke, width=2)
        lines = detail.split("\n")
        total_height = 36 + len(lines) * 30
        if total_height > bottom - top - 20:
            raise ValueError(f"Diagram node is too short: {title}")
        baseline = top + (bottom - top - total_height) // 2
        title_width = self.draw.textlength(title, font=self.node_font)
        self.text((left + (right - left - title_width) / 2, baseline), title,
                  self.node_font, right - left - 28, INK)
        for index, line in enumerate(lines):
            width = self.draw.textlength(line, font=self.detail_font)
            self.text((left + (right - left - width) / 2, baseline + 38 + 30 * index),
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
    diagram = Diagram(510, "训练与模型导出", "训练主机更新权重，笔记本接收模型文件", font_path)
    diagram.arrow([(260, 183), (290, 183), (290, 250), (322, 250)])
    diagram.arrow([(260, 340), (290, 340), (290, 250), (322, 250)])
    diagram.arrow([(590, 250), (630, 250)])
    diagram.arrow([(850, 250), (890, 250)])
    diagram.arrow([(740, 369), (740, 326)])
    diagram.box((24, 123, 260, 243), "业务训练集", "带标签样本\n+ 1,000 条回放", fill="#F4F6F8", stroke=GREY)
    diagram.box((24, 288, 260, 392), "Kev 发布版", "0.8B / 4B", fill="#EAF4FC")
    diagram.box((322, 183, 590, 326), "GPU 微调", "LoRA + 指针头\nFT / FT-cf 独立训练", fill="#F2F8E8", stroke="#76B900")
    diagram.box((630, 183, 850, 326), "温度校准", "固定模型权重\n只拟合温度")
    diagram.box((630, 369, 850, 457), "独立校准集", "不做梯度训练", fill="#F4F6F8", stroke=GREY)
    diagram.box((890, 183, 1176, 326), "CPU 导出", "合并 LoRA\nGGUF + 校准温度", fill="#EAF4FC")
    diagram.text((24, 474), "训练与校准在 GPU 主机完成；导出只用该主机的 CPU。", diagram.detail_font, 1152, "#536471")
    return diagram


def inference(font_path):
    diagram = Diagram(330, "端侧推理", "每条业务输入变成一次结构化判断", font_path)
    diagram.arrow([(335, 190), (416, 190)])
    diagram.arrow([(780, 190), (860, 190)])
    diagram.box((24, 119, 335, 262), "业务输入", "原话 + 设备字段\n问题，不带标签", fill="#F4F6F8", stroke=GREY)
    diagram.box((416, 119, 780, 262), "笔记本 CPU", "llama.cpp + 微调 GGUF\nPOST /v1/systemone", fill="#EAF4FC")
    diagram.box((860, 119, 1176, 262), "结构化判断", "选项 / 是非 / 等级\n答案 + 概率")
    diagram.text((24, 291), "不训练，不调用云端模型；维修、联网和工具执行由业务应用另行决定。", diagram.detail_font, 1152, "#536471")
    return diagram


def validation(font_path):
    diagram = Diagram(550, "效果与引擎验证", "相同输入，分别运行；准确率与答案一致率分开统计", font_path)
    diagram.arrow([(300, 204), (340, 204), (340, 170), (380, 170)])
    diagram.arrow([(300, 204), (340, 204), (340, 355), (380, 355)])
    diagram.arrow([(740, 170), (780, 170), (780, 260), (820, 260)])
    diagram.arrow([(740, 355), (780, 355), (780, 260), (820, 260)])
    diagram.draw.line([(162, 275), (162, 465), (375, 465)], fill=BLUE, width=3)
    diagram.arrow([(765, 465), (998, 465), (998, 360)])
    diagram.box((24, 130, 300, 275), "同一测试集", "无标签输入给模型\n标准答案留给评分", fill="#F4F6F8", stroke=GREY)
    diagram.box((380, 105, 740, 235), "云端 PyTorch", "H100 上运行 Kev\n逐题答案与概率", fill="#F2F8E8", stroke="#76B900")
    diagram.box((380, 290, 740, 420), "端侧 llama.cpp", "CPU / Adreno\n答案、耗时与内存", fill="#EAF4FC")
    diagram.box((820, 160, 1176, 360), "两种核对", "对标准答案：业务准确率\n对另一引擎：答案一致率")
    diagram.text((393, 448), "标准答案只进入评分程序", diagram.detail_font, 354, INK)
    diagram.text((24, 510), "训练资源单独统计；端侧计时是一条请求的完整往返，不含加载与预热。", diagram.detail_font, 1152, "#536471")
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
    style = """*{box-sizing:border-box}body{margin:0;color:#1f2328;background:#fff;font:16px/1.7 'Segoe UI','Microsoft YaHei',sans-serif;letter-spacing:0}
main{max-width:980px;margin:0 auto;padding:32px 32px 80px;overflow-wrap:break-word}h1{font-size:30px;line-height:1.35;margin:0 0 20px}
h2{font-size:25px;border-bottom:2px solid #0078d4;padding-bottom:9px;margin-top:44px}h3{font-size:21px;margin-top:32px}
h4{font-size:17px;margin-top:24px}a{color:#0969da;text-underline-offset:3px}img{max-width:100%;height:auto}blockquote{border-left:3px solid #d1d9e0;margin:20px 0;padding-left:16px;color:#59636e}
pre{background:#f6f8fa;padding:16px;overflow-x:auto;border-radius:5px;font-size:13px;line-height:1.55}code{font-family:Consolas,monospace}
:not(pre)>code{background:#eff1f3;padding:2px 4px;border-radius:3px;overflow-wrap:anywhere}.table-scroll{overflow-x:auto;margin:18px 0;max-width:100%}
table{border-collapse:collapse;font-size:14px;width:100%;line-height:1.6}th,td{border:1px solid #d1d9e0;padding:10px 12px;min-width:76px;vertical-align:top;overflow-wrap:break-word}
th{background:#edf3f8;text-align:left;font-weight:600}tr:nth-child(even){background:#f8fafc}li{margin:7px 0}.figure-scroll{max-width:100%;overflow-x:auto;margin:18px 0}.figure-scroll img{display:block;margin:auto}p:has(>em:only-child){font-size:14px;color:#536471}
@media(max-width:600px){main{padding:20px 16px 48px}h1{font-size:26px}h2{font-size:23px}table{min-width:600px}th,td{padding:8px 10px}.figure-scroll img{max-width:none;min-width:760px;width:760px}}
"""
    for source in sources:
        parser = MarkdownIt("commonmark", {"html": True}).enable("table")
        tokens = parser.parse(source.read_text(encoding="utf-8"))
        slugs = {}
        for index, token in enumerate(tokens):
            if token.type == "html_block" and token.content.lstrip().startswith("<img "):
                token.content = '<div class="figure-scroll">' + token.content + '</div>\n'
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
    leaderboard = arguments.out / "kev-leaderboard.png"
    if leaderboard.is_file():
        with Image.open(leaderboard) as official:
            official.verify()
            dimensions = official.size
        assets.append({"file": leaderboard.name, "width": dimensions[0], "height": dimensions[1],
                       "sha256": hashlib.sha256(leaderboard.read_bytes()).hexdigest(),
                       "kind": "unchanged producer-published figure", "owner": "Jared Palmer / Kev",
                       "source": "https://raw.githubusercontent.com/jaredpalmer/kev/2074cc44256200bb37540103fa4572901faa10f3/docs/kev-family.png",
                       "license": "Apache-2.0", "crop": "none",
                       "proves": "producer-reported transfer-v4 development comparison at commit 2074cc44",
                       "does_not_prove": "this project's vendor-task accuracy, laptop latency, or universal model ranking"})
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