"""Render bilingual architecture diagrams and document previews from local sources."""
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
        self.node_font = ImageFont.truetype(str(font_path), 25)
        self.detail_font = ImageFont.truetype(str(font_path), 20)
        self.small_font = ImageFont.truetype(str(font_path), 18)
        self.icons_used = set()
        self.draw.rectangle((24, 21, 29, 59), fill=BLUE)
        self.text((43, 16), title, self.title_font, 1133, INK)
        self.text((24, 65), subtitle, self.detail_font, 1152, "#536471")

    def text(self, position, text, font, max_width, fill):
        if self.draw.textlength(text, font=font) > max_width:
            raise ValueError(f"Diagram label is too wide: {text}")
        self.draw.text(position, text, font=font, fill=fill)

    def icon(self, name, position, size=48):
        folder = ROOT / "images" / "vendor"
        ledger = json.loads((folder / "sources.json").read_text(encoding="utf-8"))
        record = next(entry for entry in ledger["icons"] if entry["name"] == name)
        for field in ("original", "raster"):
            raw = (folder / record[field]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != record[field + "_sha256"]:
                raise ValueError(f"Vendor icon differs from its source ledger: {name}")
        with Image.open(folder / record["raster"]) as source:
            icon = source.convert("RGBA")
            icon.thumbnail((size, size), Image.Resampling.LANCZOS)
            self.image.paste(icon, position, icon)
        self.icons_used.add(name)

    def region(self, bounds, title, subtitle, icon, fill="#F3F8FC"):
        left, top, right, bottom = bounds
        self.draw.rounded_rectangle(bounds, radius=8, fill=fill, outline="#B8CEDF", width=2)
        self.icon(icon, (left + 20, top + 18), 48)
        self.text((left + 84, top + 15), title, self.node_font, right - left - 108, INK)
        self.text((left + 84, top + 51), subtitle, self.small_font, right - left - 108, "#536471")
        self.draw.line((left + 20, top + 91, right - 20, top + 91), fill="#D8E4ED", width=1)

    def lines(self, position, title, detail, width, accent=INK):
        left, top = position
        self.text((left, top), title, self.node_font, width, accent)
        for index, line in enumerate(detail.split("\n")):
            self.text((left, top + 39 + 29 * index), line, self.detail_font, width, "#536471")

    def artifact(self, position, title, detail, width):
        left, top = position
        self.icon("file", (left, top + 3), 34)
        self.lines((left + 48, top), title, detail, width - 48)

    def arrow(self, points, color=BLUE):
        self.draw.line(points, fill=color, width=2, joint="curve")
        previous, end = points[-2:]
        angle = math.atan2(end[1] - previous[1], end[0] - previous[0])
        triangle = [end]
        for offset in (-0.48, 0.48):
            triangle.append((end[0] - 11 * math.cos(angle + offset), end[1] - 11 * math.sin(angle + offset)))
        self.draw.polygon(triangle, fill=color)

    def save(self, path):
        self.image.save(path)
        return {"file": path.name, "width": self.image.width, "height": self.image.height,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "vendor_icons": sorted(self.icons_used)}


def training(font_path, language="zh"):
    label = lambda chinese, english: english if language == "en" else chinese
    diagram = Diagram(590, label("业务微调与模型导出", "Business fine-tuning and model export"),
                      label("数据进入训练主机，GGUF 文件交给端侧设备", "Business data enters the training host; the GGUF file goes to the device"), font_path)
    diagram.text((24, 124), label("输入", "INPUTS"), diagram.small_font, 250, "#536471")
    diagram.artifact((24, 179), label("业务训练集", "Training data"), label("标注样本\n+ 1,000 条回放", "Labeled samples\n+ 1,000 replay rows"), 264)
    diagram.artifact((24, 338), label("Kev 发布版", "Released Kev"), "0.8B / 4B", 264)
    diagram.region((324, 121, 1176, 415), label("Azure 训练主机", "Azure training host"), "NVIDIA H100 NVL · PyTorch", "azure-vm")
    diagram.lines((354, 239), label("01  监督微调", "01  Fine-tune"), label("LoRA + 指针头\nFT / FT-cf 独立训练", "LoRA + pointer head\nIndependent FT / FT-cf"), 244, "#527A08")
    diagram.lines((652, 239), label("02  温度校准", "02  Calibrate"), label("固定权重\n仅拟合温度参数", "Keep weights fixed\nFit temperature only"), 242)
    diagram.lines((938, 239), label("03  CPU 导出", "03  CPU export"), label("合并 LoRA\n保存 GGUF 与温度", "Merge LoRA\nGGUF + temperature"), 220)
    diagram.arrow([(274, 222), (300, 222), (300, 303), (338, 303)])
    diagram.draw.line([(274, 374), (300, 374), (300, 303)], fill=BLUE, width=2)
    diagram.arrow([(598, 302), (632, 302)])
    diagram.arrow([(897, 302), (922, 302)])
    diagram.artifact((592, 466), label("校准集", "Calibration set"), label("与训练样本分开", "Separate from training"), 284)
    diagram.arrow([(772, 449), (772, 383)])
    diagram.artifact((930, 466), "GGUF", label("交给笔记本", "Deliver to the laptop"), 248)
    diagram.arrow([(1053, 380), (1053, 448)])
    diagram.text((24, 552), label("微调、校准和 CPU 导出都在同一主机完成；端侧推理不会触发这些步骤。", "Fine-tuning, calibration and CPU export share one host; device inference does not run these stages."), diagram.small_font, 1152, "#536471")
    return diagram


def inference(font_path, language="zh"):
    label = lambda chinese, english: english if language == "en" else chinese
    diagram = Diagram(470, label("端侧业务判断", "On-device business decisions"),
                      label("模型只回答问题，业务应用决定下一步动作", "The model answers questions; the business application decides what happens next"), font_path)
    diagram.artifact((24, 229), label("业务输入", "Business input"), label("客户原话 + 设备字段\n待回答的问题\n不带标准答案", "Message + device fields\nQuestions to answer\nNo ground-truth labels"), 280)
    diagram.region((324, 121, 1176, 391), label("Windows on Arm 笔记本", "Windows on Arm laptop"), "Snapdragon X Elite · CPU · llama.cpp", "laptop")
    diagram.lines((360, 235), label("本机推理", "Local inference"), label("加载微调 GGUF\n读取内置温度\nPOST /v1/systemone", "Load fine-tuned GGUF\nUse saved temperature\nPOST /v1/systemone"), 294)
    diagram.arrow([(308, 286), (342, 286)])
    diagram.arrow([(678, 286), (758, 286)])
    diagram.lines((784, 235), label("结构化答案", "Structured answers"), label("选项 / 是非 / 等级\n应用温度后的概率", "Choice / yes-no / ordinal\nTemperature-scaled probabilities"), 363)
    diagram.text((24, 427), label("没有云端模型请求，不训练，也不替用户执行维修、联网或工具调用。", "No cloud-model request, training, repair action, network action or tool execution is performed here."), diagram.small_font, 1152, "#536471")
    return diagram


def validation(font_path, language="zh"):
    label = lambda chinese, english: english if language == "en" else chinese
    diagram = Diagram(660, label("测试拓扑与评分边界", "Test topology and scoring boundaries"),
                      label("两条独立推理路径；准确率与引擎一致率不是同一个指标", "Two independent inference paths; accuracy and engine agreement are different metrics"), font_path)
    diagram.artifact((24, 229), label("同一测试集", "Same test set"), label("无标签输入给模型\n逐题保留标准答案", "Unlabeled inputs\nKeep labels for scoring"), 280)
    diagram.region((334, 121, 766, 311), label("Azure GPU 主机", "Azure GPU host"), "H100 NVL · PyTorch", "azure-vm")
    diagram.lines((358, 230), label("保存逐题预测", "Per-question predictions"), label("答案与概率", "Answers and probabilities"), 383)
    diagram.region((334, 355, 766, 545), label("Windows on Arm", "Windows on Arm"), "llama.cpp · CPU / Adreno", "laptop")
    diagram.lines((358, 465), label("端侧计量", "Device measurements"), label("答案、请求耗时、进程内存", "Answers, request time, memory"), 383)
    diagram.draw.line((844, 144, 844, 537), fill="#B8CEDF", width=2)
    diagram.lines((870, 148), label("评分程序", "Scoring program"), label("不更新模型参数", "No model updates"), 300)
    diagram.lines((870, 263), label("业务准确率", "Task accuracy"), label("预测对照标准答案", "Predictions vs. ground truth"), 300)
    diagram.lines((870, 378), label("引擎一致率", "Engine agreement"), label("两条路径的答案互相比对", "Answers from the two paths"), 300)
    diagram.arrow([(274, 276), (303, 276), (303, 262), (320, 262)])
    diagram.arrow([(303, 276), (303, 496), (320, 496)])
    diagram.draw.line([(778, 262), (812, 262), (812, 496), (778, 496)], fill=BLUE, width=2)
    diagram.arrow([(812, 360), (855, 360)])
    diagram.draw.line([(155, 359), (155, 588), (418, 588)], fill="#687C8A", width=2)
    diagram.arrow([(800, 588), (1010, 588), (1010, 478)], color="#687C8A")
    diagram.text((435, 573), label("标准答案只供评分", "Ground truth: scoring only"), diagram.detail_font, 345, "#536471")
    diagram.text((24, 623), label("请求耗时在笔记本客户端计量，排除加载与预热；训练资源另外统计。", "Request timing is measured by the laptop client, excluding loading and warm-up; training resources are separate."), diagram.small_font, 1152, "#536471")
    return diagram


def sync_english_documents():
    from markdown_it import MarkdownIt
    from fill_report_tables import localize_block

    pairs = ((ROOT / "README_CN.md", ROOT / "README.md", 26, 20),
             (ROOT / "文档" / "微调与端侧验证报告_20261027-130700.md",
              ROOT / "文档" / "Finetuning-and-On-Device-Validation-Report.md", 20, 1))
    names = {"微调与端侧验证报告_20261027-130700.md": "Finetuning-and-On-Device-Validation-Report.md",
             "[NOTES]_实验协议_20261027-124000.md": "Experiment-Protocol.md", "README_CN.md": "README.md"}
    parser = MarkdownIt("commonmark", {"html": True}).enable("table")
    results = []
    for source, target, expected_tables, expected_fences in pairs:
        source_text = source.read_text(encoding="utf-8")
        source_lines = source_text.splitlines(keepends=True)
        fragments = {"TABLE": [], "FENCE": []}
        for token in parser.parse(source_text):
            if token.type in ("table_open", "fence"):
                kind = "TABLE" if token.type == "table_open" else "FENCE"
                fragments[kind].append("".join(source_lines[token.map[0]:token.map[1]]).rstrip())
        if (len(fragments["TABLE"]), len(fragments["FENCE"])) != (expected_tables, expected_fences):
            raise ValueError(f"Source structure changed; review the bilingual mapping: {source.name}")
        text = target.read_text(encoding="utf-8")
        for kind, blocks in fragments.items():
            for index, block in enumerate(blocks, 1):
                opening = f"<!-- SOURCE:{kind}:{index} -->"
                closing = f"<!-- /SOURCE:{kind}:{index} -->"
                expression = re.compile(re.escape(opening) + r".*?" + re.escape(closing), re.S)
                if len(expression.findall(text)) != 1:
                    raise ValueError(f"Missing or duplicated bilingual source anchor: {target.name} {kind} {index}")
                content = localize_block(block) if kind == "TABLE" else block
                if kind == "TABLE":
                    def target_link(match):
                        parsed = urlsplit(match.group(1))
                        if parsed.scheme or parsed.netloc:
                            return match.group()
                        path = unquote(parsed.path)
                        filename = path.rsplit("/", 1)[-1]
                        if filename in names:
                            path = path[:-len(filename)] + names[filename]
                        return "](" + urlunsplit(("", "", path, parsed.query, parsed.fragment)) + ")"
                    content = re.sub(r"\]\(([^)]+)\)", target_link, content)
                text = expression.sub(lambda _: opening + "\n" + content + "\n" + closing, text)
        target.write_text(text, encoding="utf-8")
        parsed_target = parser.parse(text)
        if sum(token.type == "table_open" for token in parsed_target) != expected_tables:
            raise ValueError(f"Bilingual table count mismatch: {target.name}")
        original_code = [token.content for token in parser.parse(source_text) if token.type == "fence"]
        translated_code = [token.content for token in parsed_target if token.type == "fence"]
        if original_code != translated_code:
            raise ValueError(f"Bilingual code-block drift: {target.name}")
        results.append({"source": str(source.relative_to(ROOT)), "target": str(target.relative_to(ROOT)),
                        "tables": expected_tables, "code_blocks": expected_fences})
    return results


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


def preview_documents(only=None):
    from markdown_it import MarkdownIt

    sources = [ROOT / "README.md", ROOT / "README_CN.md",
               ROOT / "文档" / "微调与端侧验证报告_20261027-130700.md",
               ROOT / "文档" / "Finetuning-and-On-Device-Validation-Report.md",
               ROOT / "文档" / "[NOTES]_实验协议_20261027-124000.md",
               ROOT / "文档" / "Experiment-Protocol.md"]
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
        opening = source.name in ("README.md", "README_CN.md")
        for index, token in enumerate(tokens):
            if opening and token.type == "heading_open" and token.tag == "h3":
                token.attrSet("class", "readme-first-section")
                opening = False
            elif opening and token.type in ("heading_open", "paragraph_open", "blockquote_open"):
                token.attrSet("class", "readme-opening")
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
    written = 0
    for source, (_, _, tokens, parser) in pages.items():
        if only is not None and source.name not in only:
            continue
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
        language = "zh-CN" if source.name == "README_CN.md" or re.search(r"[\u4e00-\u9fff]", source.stem) else "en"
        page_style = style
        if source.name in ("README.md", "README_CN.md"):
            page_style += "h1.readme-opening{margin-bottom:12px}p.readme-opening{margin:10px 0}blockquote.readme-opening{margin:12px 0}h2.readme-opening{margin-top:20px;margin-bottom:12px;padding-bottom:6px}h3.readme-first-section{margin-top:20px}\n"
        destination.write_text(f'<!doctype html><html lang="{language}"><meta charset="utf-8">'
                               '<meta name="viewport" content="width=device-width,initial-scale=1">'
                               f'<title>{html.escape(source.stem)}</title><style>{page_style}</style><main>{body}</main></html>', encoding="utf-8")
        written += 1
    return {"pages": written, "local_links_checked": checked}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", type=Path, default=Path("C:/Windows/Fonts/msyh.ttc"))
    parser.add_argument("--out", type=Path, default=ROOT / "images")
    parser.add_argument("--preview", action="store_true", help="validate links and render ignored local HTML previews")
    parser.add_argument("--sync-english", action="store_true", help="fill English source-backed tables and unchanged code blocks")
    arguments = parser.parse_args()
    if not arguments.font.is_file():
        parser.error("Provide --font with a locally installed CJK TrueType/OpenType font")
    arguments.out.mkdir(parents=True, exist_ok=True)
    assets = []
    for name, factory, sources in (
        ("training", training, ["scripts/remote_pipeline_v2.sh", "scripts/remote_cf_round.sh", "scripts/remote_export_gguf.sh",
                    "https://github.com/jaredpalmer/kev/blob/2074cc44256200bb37540103fa4572901faa10f3/scripts/calibrate_checkpoint.py"]),
        ("inference", inference, ["scripts/systemone_client.py", "scripts/run_engine_eval.ps1",
                      "https://github.com/ggml-org/llama.cpp/blob/b11935/tools/server/server-decision.cpp"]),
        ("validation", validation, ["scripts/remote_pipeline_v2.sh", "scripts/run_engine_eval.ps1", "scripts/parity.py"]),
    ):
        for language in ("zh", "en"):
            suffix = "" if language == "zh" else "-en"
            asset = factory(arguments.font, language).save(arguments.out / f"{name}{suffix}.png")
            asset.update({"kind": "original explanatory diagram", "language": language, "sources": sources,
                          "proves": "project workflow, execution placement and scoring boundaries",
                          "does_not_prove": "model accuracy or runtime success"})
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
              "visual_scope": "Azure host and Windows device boundaries; official Microsoft icons identify actual hosts and file artifacts, not custom services.",
              "icon_sources": "vendor/sources.json",
              "assets": assets}
    (arguments.out / "provenance.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    bilingual = sync_english_documents() if arguments.sync_english else None
    preview = preview_documents() if arguments.preview else None
    print(json.dumps({"status": "PASS", "assets": assets, "bilingual": bilingual, "preview": preview}, ensure_ascii=False))


if __name__ == "__main__":
    main()