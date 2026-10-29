"""Checks that need neither the GPU VM nor the laptop engine. Run from the project root:

    python -m unittest discover -s tests -v

Data: manifest hashes and counts, every label equals the vendor policy code, no message group crosses splits, the
B0-policy files describe the same records, every counterfactual record changes at least one label.
Scoring: parity.py on identical and on altered answers, temperature_whatif.py against kev's own Brier, and the paired
bootstrap of summarize_results.py. A test whose saved evidence is absent is skipped, never passed.
"""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "contoso"
FINAL = DATA / "final"
ENGINE = ROOT / "验证结果" / "端侧引擎_20261027-124700"
sys.path.insert(0, str(ROOT / "scripts"))
import summarize_engine as se
import summarize_results as sr  # noqa: E402
import systemone_client as client  # noqa: E402
import temperature_whatif as tw  # noqa: E402
import vendor_policy as vp  # noqa: E402


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def state_of(record):
    return record["state"] if isinstance(record["state"], dict) else json.loads(record["state"])


class DataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((FINAL / "manifest.json").read_text(encoding="utf-8"))
        cls.files = {name: read_jsonl(FINAL / name) for name in cls.manifest}
        cls.cases = {c["id"]: c for w in ("support", "assistant") for tag in ("g1", "ood")
                     for c in read_jsonl(DATA / f"{w}.{tag}.cases.jsonl")}

    def test_manifest_hashes_and_counts(self):
        for name, m in self.manifest.items():
            with self.subTest(file=name):
                self.assertEqual(hashlib.sha256((FINAL / name).read_bytes()).hexdigest(), m["sha256"])
                self.assertEqual(len(self.files[name]), m["records"])
                self.assertEqual(sum(len(r["questions"]) for r in self.files[name]), m["questions"])

    def test_labels_equal_vendor_policy(self):
        labels = {"support": vp.support_labels, "assistant": vp.assistant_labels}
        for name, rows in self.files.items():
            with self.subTest(file=name):
                for r in rows:
                    case = dict(self.cases[r["_meta"]["group"]])
                    field = "device" if case["workload"] == "support" else "context"
                    case[field] = state_of(r)[field]  # pair and counterfactual records change these fields
                    got = {q: v["label"] for q, v in r["questions"].items()}
                    self.assertEqual(got, labels[case["workload"]](case), r["_meta"]["case"])

    def test_no_message_group_crosses_splits(self):
        def groups(prefixes):
            return {r["_meta"]["group"] for n, rows in self.files.items() if n.startswith(prefixes) for r in rows}
        train, calib = groups(("train",)), groups(("calib",))
        dev, test, ood = groups(("dev",)), groups(("test", "policy_test")), groups(("ood", "policy_ood"))
        self.assertTrue(train and calib and dev and test and ood)
        for a, b in ((train, calib), (train, dev), (train, test), (train, ood), (calib, dev), (calib, test), (dev, test)):
            self.assertEqual(a & b, set())

    def test_policy_files_differ_only_in_instructions(self):
        for name in [n for n in self.files if n.startswith("policy_")]:
            base, pol = self.files[name[len("policy_"):]], self.files[name]
            with self.subTest(file=name):
                self.assertEqual([r["_meta"]["case"] for r in pol], [r["_meta"]["case"] for r in base])
                for a, b in zip(pol, base):
                    self.assertEqual(state_of(a), state_of(b))
                    for q, bq in b["questions"].items():
                        self.assertEqual(a["questions"][q]["label"], bq["label"])
                        self.assertTrue(a["questions"][q]["instructions"].startswith(bq["instructions"]))
                        self.assertGreater(len(a["questions"][q]["instructions"]), len(bq["instructions"]) + 200)

    def test_counterfactual_records_change_a_label(self):
        originals = {r["_meta"]["case"]: r for n, rows in self.files.items() if "_cf" not in n and not n.startswith("policy_")
                     for r in rows}
        for name in [n for n in self.files if "_cf" in n]:
            with self.subTest(file=name):
                variants = [r for r in self.files[name] if r["_meta"].get("aug") == "cf"]
                self.assertTrue(variants)
                for r in variants:
                    base = originals[r["_meta"]["group"]]
                    changed = [q for q, v in r["questions"].items() if v["label"] != base["questions"][q]["label"]]
                    self.assertTrue(changed, r["_meta"]["case"])


class RequestTests(unittest.TestCase):
    def test_request_excludes_labels_and_metadata(self):
        record = {"state": {"message": "test", "region": "CN"},
                  "questions": {"onsite": {"type": "noul", "label": True}}, "_meta": {"case": "test"}}
        body = client.request_body(record)
        self.assertEqual(body, {"state": record["state"], "questions": {"onsite": {"type": "noul"}}})
        self.assertTrue(record["questions"]["onsite"]["label"])
        with self.assertRaises(ValueError):
            client.request_body({"state": "test", "questions": {}})

    def test_single_request_saves_visible_input_and_raw_response(self):
        response = {"answers": {"onsite": {"type": "noul", "noul": 0.37}}, "usage": {"input_tokens": 15}}
        with tempfile.TemporaryDirectory() as temporary:
            request_path = Path(temporary) / "request.json"
            for region in ("CN", "SG"):
                record = {"state": {"message": "test", "region": region},
                          "questions": {"onsite": {"type": "noul", "label": True}}}
                request_path.write_text(json.dumps(record), encoding="utf-8-sig")
                output = Path(temporary) / region
                with mock.patch.object(client, "ask", return_value=(response, 12.3)) as send, mock.patch("builtins.print"):
                    result = client.single_request("http://127.0.0.1:8080/v1/systemone", request_path, output)
                send.assert_called_once_with("http://127.0.0.1:8080/v1/systemone", client.request_body(record))
                self.assertEqual(result["response"], response)
                self.assertEqual(result["request"]["state"]["region"], region)
                self.assertEqual(result["client_latency_ms"], 12.3)
                self.assertEqual(json.loads((output / "result.json").read_text(encoding="utf-8")), result)
                with mock.patch.object(client, "ask") as send, self.assertRaises(FileExistsError):
                    client.single_request("http://127.0.0.1:8080/v1/systemone", request_path, output)
                send.assert_not_called()

    def test_single_request_failure_never_writes_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            request_path = Path(temporary) / "request.json"
            request_path.write_text(json.dumps({"state": "test", "questions": {"onsite": {"type": "noul"}}}), encoding="utf-8")
            for name, effect, response in (("offline", ConnectionError("offline"), None),
                                           ("missing-answer", None, ({"answers": {}}, 1.0))):
                with self.subTest(name=name):
                    output = Path(temporary) / name
                    with mock.patch.object(client, "ask", side_effect=effect, return_value=response) as send:
                        with self.assertRaises((ConnectionError, ValueError)):
                            client.single_request("http://127.0.0.1:8080/v1/systemone", request_path, output)
                    send.assert_called_once()
                    self.assertFalse((output / "result.json").exists())


class ReportLayoutTests(unittest.TestCase):
    def accuracy_summary(self):
        sets = {}
        for size in ("0.8b", "4b"):
            for set_name, count in (("test_support", 510), ("test_assistant", 477),
                                    ("ood_support", 1011), ("ood_assistant", 951),
                                    ("test_cf_support", 172), ("test_cf_assistant", 72)):
                scores = {model: {"n": count, "acc": 0.1 * (index + 1)}
                          for index, model in enumerate(sr.MODELS)}
                sets[f"{size}/{set_name}"] = (
                    {"changed_questions": count, "changed_acc": scores, "changed_paired": {}}
                    if "_cf_" in set_name else scores)
        return {"sets": sets, "public": {}, "training": {}}

    def test_accuracy_tables_keep_every_configuration_and_value(self):
        block = sr.report_blocks(self.accuracy_summary())["README_ACC"]
        self.assertEqual(block.count("| 参数规模 | 阶段与做法 |"), 3)
        labels = ("微调前：发布版", "微调前：仅在提示词中加入业务规则",
                  "微调后：业务数据微调", "微调后：业务数据＋字段变体增强")
        for size in ("0.8B", "4B"):
            for index, label in enumerate(labels):
                percentage = f"{10 * (index + 1):.1f}%"
                self.assertEqual(block.count(f"| {size} | {label} | {percentage} | {percentage} |"), 3)
        for count in ("510", "477", "1,011", "951", "172", "72"):
            self.assertIn(f"（{count} 题）", block)
        self.assertTrue(all(len(line.strip("|").split("|")) == 4
                            for line in block.splitlines() if line.startswith("|")))

    def test_accuracy_tables_keep_unrun_cells_visible(self):
        summary = self.accuracy_summary()
        del summary["sets"]["4b/test_support"]["ftcf"]
        block = sr.report_blocks(summary)["README_ACC"]
        self.assertIn("| 4B | 微调后：业务数据＋字段变体增强 | 未跑 | 40.0% |", block)

    def test_engine_tables_keep_values_and_incomplete_runs(self):
        rows = [{"label": "ftcf-kev-0.8b-Q8_0-cpu", "gguf_mib": 775.0,
                 "peak_ws_mib": 2314, "private_mib": 5014, "support_acc": 0.869,
                 "assistant_acc": 0.977, "support_torch_acc": 0.869, "assistant_torch_acc": 0.975,
                 "support_agree": 0.992, "assistant_agree": 0.998,
                 "support_p50": 646.0, "assistant_p50": 984.0},
                {"label": "released-kev-4b-Q4_K_M-cpu"}]
        text = se.brief_table(rows, ["unfinished（support 36 条，无汇总）"])
        self.assertEqual(text.count("| 模型、量化与运行参数 |"), 3)
        self.assertEqual(text.count("| 微调 FT-cf 0.8B<br>Q8_0 · CPU，默认参数 |"), 3)
        self.assertIn("| 86.9%（86.9%） | 97.7%（97.5%） | 99.2% | 99.8% |", text)
        self.assertIn("| 775 | 2,314 | 5,014 |", text)
        self.assertIn("| 646 | 984 |", text)
        self.assertIn("unfinished（support 36 条，无汇总）", text)
        self.assertIn("| — | — | — |", text)
        self.assertLess(text.index("发布版 4B"), text.index("微调 FT-cf 0.8B"))
        self.assertTrue(all(len(line.strip("|").split("|")) <= 5
                            for line in text.splitlines() if line.startswith("|")))

    def test_public_and_training_tables_keep_all_metrics(self):
        summary = self.accuracy_summary()
        summary["public"] = {"4b/ft": {"n": 656, "b0_acc": 0.817, "acc": 0.809,
                                       "acc_drop_pp": 0.8, "b0_brier": 0.243, "brier": 0.299}}
        summary["training"] = {"4b/ft": {"wall_s": 942, "batch": 4, "accum": 2,
                                         "peak_gpu_mib": 33359, "temperature": "1.66",
                                         "training_metrics": {"records_seen": 6294, "optimizer_steps": 788,
                                                              "peak_device_bytes": 22581 * 2**20}}}
        blocks = sr.report_blocks(summary)
        self.assertIn("| 4B FT | 656 | 81.7% | 80.9% | -0.8 |", blocks["PUBLIC"])
        self.assertIn("| 4B FT | 0.243 | 0.299 |", blocks["PUBLIC"])
        self.assertIn("| 4B FT | 4 × 2 | 6,294 | 788 |", blocks["TRAIN"])
        self.assertIn("| 4B FT | 15.7 分钟 | 33,359 MiB | 22,581 MiB | 1.66 |", blocks["TRAIN"])
        self.assertTrue(all(len(line.strip("|").split("|")) <= 5
                            for name in ("PUBLIC", "TRAIN") for line in blocks[name].splitlines()
                            if line.startswith("|")))


class BilingualDocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from markdown_it import MarkdownIt
        except ImportError:
            raise unittest.SkipTest("Documentation tests require requirements-docs.txt")
        cls.parser = MarkdownIt("commonmark", {"html": True}).enable("table")
        cls.pairs = (("README_CN.md", "README.md", 26, 20),
                     ("文档/微调与端侧验证报告_20261027-130700.md",
                      "文档/Finetuning-and-On-Device-Validation-Report.md", 20, 1))

    def tables(self, tokens):
        tables = []
        in_table = False
        for token in tokens:
            if token.type == "table_open":
                tables.append([])
                in_table = True
            elif token.type == "table_close":
                in_table = False
            elif token.type == "tr_open" and in_table:
                tables[-1].append([])
            elif token.type == "inline" and in_table:
                tables[-1][-1].append(token.content)
        return tables

    def test_bilingual_tables_preserve_numeric_cells(self):
        compared = 0
        for chinese, english, count, _ in self.pairs:
            source = self.tables(self.parser.parse((ROOT / chinese).read_text(encoding="utf-8")))
            target = self.tables(self.parser.parse((ROOT / english).read_text(encoding="utf-8")))
            self.assertEqual(len(source), count)
            self.assertEqual(len(target), count)
            for left_table, right_table in zip(source, target):
                self.assertEqual(len(left_table), len(right_table))
                for left_row, right_row in zip(left_table, right_table):
                    self.assertEqual(len(left_row), len(right_row))
                    for left, right in zip(left_row, right_row):
                        numeric = left.replace("MiB", "").replace("分钟", "").strip()
                        if numeric and re.fullmatch(r"[\d\s,./%+−\-–~()（）\[\]×]+", numeric):
                            numbers = lambda value: re.findall(r"[+−-]?\d+(?:\.\d+)?", value.replace(",", "").replace("−", "-"))
                            self.assertEqual(numbers(left), numbers(right), (left, right))
                            compared += 1
        self.assertGreater(compared, 0)

    def test_bilingual_code_and_source_anchors_are_complete(self):
        for chinese, english, _, count in self.pairs:
            source = self.parser.parse((ROOT / chinese).read_text(encoding="utf-8"))
            text = (ROOT / english).read_text(encoding="utf-8")
            target = self.parser.parse(text)
            source_code = [token.content for token in source if token.type == "fence"]
            target_code = [token.content for token in target if token.type == "fence"]
            self.assertEqual(len(source_code), count)
            self.assertEqual(source_code, target_code)
            self.assertNotRegex(text, r"<!-- SOURCE:(TABLE|FENCE):\d+ -->\s*<!-- /SOURCE:")
        english = self.parser.parse((ROOT / "README.md").read_text(encoding="utf-8"))
        self.assertEqual([english[index + 1].content for index, token in enumerate(english)
                          if token.type == "heading_open" and token.tag == "h2"], ["Purpose", "Results", "Steps"])

    def test_localization_preserves_nested_link_and_code(self):
        import fill_report_tables
        from urllib.parse import unquote

        source = "[文档/[NOTES]_实验协议_20261027-124000.md](文档/%5BNOTES%5D_实验协议_20261027-124000.md)，`manifest.json`"
        target = fill_report_tables.localize_block(source)
        source_tokens = self.parser.parseInline(source)[0].children
        target_tokens = self.parser.parseInline(target)[0].children
        self.assertEqual([unquote(token.attrGet("href")) for token in source_tokens if token.type == "link_open"],
                         [unquote(token.attrGet("href")) for token in target_tokens if token.type == "link_open"])
        self.assertEqual([token.content for token in target_tokens if token.type == "code_inline"], ["manifest.json"])
        self.assertIn("Experimental protocol", target)
        stages = fill_report_tables.localize_block(
            "| 阶段与做法 |\n| 微调前：发布版 |\n| 微调前：仅在提示词中加入业务规则 |\n"
            "| 微调后：业务数据微调 |\n| 微调后：业务数据＋字段变体增强 |")
        self.assertIn("Stage and method", stages)
        self.assertEqual(stages.count("Before fine-tuning:"), 2)
        self.assertEqual(stages.count("After fine-tuning:"), 2)
        self.assertIn("business rules in the prompt only", stages)
        self.assertIn("business data + field-variant augmentation", stages)

    def test_official_icons_and_both_diagram_languages(self):
        icons = json.loads((ROOT / "images/vendor/sources.json").read_text(encoding="utf-8"))["icons"]
        names = {icon["name"] for icon in icons}
        for icon in icons:
            for field in ("original", "raster"):
                self.assertEqual(hashlib.sha256((ROOT / "images/vendor" / icon[field]).read_bytes()).hexdigest(),
                                 icon[field + "_sha256"])
        assets = json.loads((ROOT / "images/provenance.json").read_text(encoding="utf-8"))["assets"]
        diagrams = [asset for asset in assets if asset["kind"] == "original explanatory diagram"]
        self.assertEqual({asset["file"] for asset in diagrams},
                         {name + suffix + ".png" for name in ("training", "inference", "validation") for suffix in ("", "-en")})
        for asset in diagrams:
            self.assertIn(asset["language"], ("zh", "en"))
            self.assertTrue(asset["vendor_icons"])
            self.assertTrue(set(asset["vendor_icons"]).issubset(names))
            self.assertEqual(hashlib.sha256((ROOT / "images" / asset["file"]).read_bytes()).hexdigest(), asset["sha256"])


class ScoringTests(unittest.TestCase):
    def saved_rows(self, run, workload="support"):
        path = ENGINE / run / workload / "rows.json"
        if not path.is_file():
            self.skipTest(f"saved PyTorch rows not present: {path}")
        return path

    def run_parity(self, torch_path, engine_rows):
        with tempfile.TemporaryDirectory() as tmp:
            eng, out = Path(tmp) / "rows.jsonl", Path(tmp) / "parity.json"
            eng.write_text("\n".join(json.dumps(r) for r in engine_rows), encoding="utf-8")
            subprocess.run([sys.executable, str(ROOT / "scripts" / "parity.py"), "--torch", str(torch_path), "--engine", str(eng),
                            "--out", str(out)], check=True, capture_output=True)
            return json.loads(out.read_text(encoding="utf-8"))

    def engine_rows_from(self, torch_rows):
        """The engine's /v1/systemone shape carrying exactly the PyTorch probabilities (noul as P(true))."""
        rows = {}
        for r in torch_rows:
            i = int(r["id"].rsplit("/", 1)[-1])
            p = dict(zip(r["keys"], r["p"]))
            rows.setdefault(i, {"i": i, "questions": {}})["questions"][r["question"]] = {"p": p["true"] if r["type"] == "noul" else p}
        return list(rows.values())

    def test_parity_of_identical_answers(self):
        path = self.saved_rows("pytorch-ft-0.8b")
        res = self.run_parity(path, self.engine_rows_from(json.loads(path.read_text(encoding="utf-8"))))
        self.assertEqual(res["missing"], 0)
        self.assertEqual(res["by_type"]["all"]["agreement"], 1.0)
        self.assertEqual(res["by_type"]["all"]["max_tvd"], 0.0)

    def test_parity_detects_a_changed_answer(self):
        path = self.saved_rows("pytorch-ft-0.8b")
        torch_rows = json.loads(path.read_text(encoding="utf-8"))
        engine = self.engine_rows_from(torch_rows)
        target = next(r for r in torch_rows if r["type"] == "choice")
        i = int(target["id"].rsplit("/", 1)[-1])
        best = max(range(len(target["p"])), key=lambda j: target["p"][j])
        other = target["keys"][(best + 1) % len(target["keys"])]
        q = next(e for e in engine if e["i"] == i)["questions"][target["question"]]
        q["p"] = {k: (1.0 if k == other else 0.0) for k in target["keys"]}
        res = self.run_parity(path, engine)
        self.assertEqual(res["by_type"]["all"]["agree_count"], res["by_type"]["all"]["n"] - 1)
        self.assertGreater(res["by_type"]["all"]["max_tvd"], 0.5)

    def test_temperature_whatif_reproduces_kev_brier(self):
        rows = [r for r in json.loads(self.saved_rows("pytorch-b0-0.8b").read_text(encoding="utf-8"))
                if r.get("variant", "clean") == "clean"]
        served = rows[0]["inference_temperature"]
        # kev.benchmark reported b0-test_support brier=0.6413 at the served temperature (pipeline-0.8b.status)
        self.assertAlmostEqual(tw.score(rows, served)["brier"], 0.6413, places=4)
        self.assertGreater(tw.score(rows, 1.0)["brier"], tw.score(rows, served)["brier"])

    def test_paired_bootstrap_bounds(self):
        def rows(correct):
            return [{"id": f"custom/{i}", "question": "q", "p": [0.9, 0.1] if correct else [0.1, 0.9], "label": 0} for i in range(20)]
        groups = {i: f"g{i}" for i in range(20)}
        same = sr.paired(rows(True), rows(True), groups, n_boot=200)
        self.assertEqual((same["acc_delta"], same["acc_ci95"]), (0.0, [0.0, 0.0]))
        better = sr.paired(rows(True), rows(False), groups, n_boot=200)
        self.assertEqual((better["acc_delta"], better["acc_ci95"]), (1.0, [1.0, 1.0]))
        mixed = sr.paired(rows(True)[:10] + rows(False)[10:], rows(False), groups, n_boot=2000)
        self.assertAlmostEqual(mixed["acc_delta"], 0.5)
        self.assertLess(mixed["acc_ci95"][0], 0.5)
        self.assertGreater(mixed["acc_ci95"][1], 0.5)


if __name__ == "__main__":
    unittest.main()
