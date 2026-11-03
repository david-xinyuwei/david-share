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
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "contoso"
FINAL = DATA / "final"
ENGINE = ROOT / "验证结果" / "端侧引擎_20261027-124700"
sys.path.insert(0, str(ROOT / "scripts"))
import calibration_boundary as cb  # noqa: E402
import summarize_engine as se
import summarize_results as sr  # noqa: E402
import systemone_client as client  # noqa: E402
import temperature_whatif as tw  # noqa: E402
import vendor_policy as vp  # noqa: E402


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def state_of(record):
    return record["state"] if isinstance(record["state"], dict) else json.loads(record["state"])


class PipelineCompletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        git_bash = Path("C:/Program Files/Git/bin/bash.exe")
        cls.bash = str(git_bash) if git_bash.is_file() else shutil.which("bash")
        if not cls.bash:
            raise unittest.SkipTest("Pipeline failure-path tests require Bash")

    def run_bash(self, program, directory):
        return subprocess.run([self.bash, "--noprofile", "--norc", "-s"],
                              input=program.encode("utf-8"), cwd=directory,
                              capture_output=True, timeout=15)

    def test_missing_evaluation_input_blocks_completion(self):
        for filename in ("remote_pipeline_v2.sh", "remote_cf_round.sh", "remote_round2.sh"):
            with self.subTest(script=filename), tempfile.TemporaryDirectory() as temporary:
                source = (ROOT / "scripts" / filename).read_text(encoding="utf-8")
                function = re.search(r"^ *bench\(\) \{.*?^ *\}", source, re.M | re.S).group()
                output = Path(temporary) / "runs/sample"
                output.mkdir(parents=True)
                (output / "report.json").write_text("{}", encoding="utf-8")
                arguments = 'sample "$PWD/missing.jsonl"' if filename == "remote_round2.sh" else 'sample unused "$PWD/missing.jsonl"'
                program = ('set -euo pipefail\nR="$PWD/runs"\nSTATUS="$PWD/status.log"\nTAG=r2-C\n'
                           + function + '\nbench ' + arguments + '\necho PIPELINE_DONE\n')
                result = self.run_bash(program, temporary)
                self.assertEqual(result.returncode, 3, result.stderr.decode())
                self.assertIn(b"MISSING_DATA", result.stdout)
                self.assertNotIn(b"PIPELINE_DONE", result.stdout)

    def test_comparison_failure_blocks_completion(self):
        source = (ROOT / "scripts/remote_pipeline_v2.sh").read_text(encoding="utf-8")
        comparison = source[source.index('stage "STAGE compare"'):]
        with tempfile.TemporaryDirectory() as temporary:
            for prefix in ("ft", "b0"):
                output = Path(temporary) / f"runs/{prefix}-test_support"
                output.mkdir(parents=True)
                (output / "report.json").write_text("{}", encoding="utf-8")
            program = ('set -euo pipefail\nR="$PWD/runs"\nPY=false\n'
                       'stage() { printf "%s\\n" "$1"; }\n' + comparison)
            result = self.run_bash(program, temporary)
        self.assertEqual(result.returncode, 4, result.stderr.decode())
        self.assertIn(b"COMPARE_FAILED", result.stdout)
        self.assertNotIn(b"PIPELINE_DONE", result.stdout)

    def test_quantization_failure_blocks_export_completion(self):
        for filename in ("remote_export_gguf.sh", "remote_export_gguf_cf.sh", "remote_export_round2.sh"):
            source = (ROOT / "scripts" / filename).read_text(encoding="utf-8")
            start = source.index('  [ -s "$OUT/$NAME-Q8_0.gguf" ]')
            end = source.index('  cat "$OUT/metadata.txt"')
            for failed_format in ("Q8_0", "Q4_K_M"):
                with self.subTest(script=filename, format=failed_format), tempfile.TemporaryDirectory() as temporary:
                    if failed_format == "Q4_K_M":
                        (Path(temporary) / "test-Q8_0.gguf").write_bytes(b"fixture")
                    program = ('set -euo pipefail\nOUT="$PWD"\nNAME=test\nSIZE=0.8b\nARM=C\nQ=false\nFLAGS_Q4_K_M=\n'
                               + source[start:end] + '\necho EXPORT_DONE\n')
                    result = self.run_bash(program, temporary)
                    self.assertEqual(result.returncode, 5, result.stderr.decode())
                    self.assertIn(b"QUANT_FAILED", result.stdout)
                    self.assertNotIn(b"EXPORT_DONE", result.stdout)
                    self.assertFalse((Path(temporary) / f"test-{failed_format}.gguf").exists())


class EngineRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pwsh = shutil.which("pwsh")
        if not cls.pwsh:
            raise unittest.SkipTest("Engine runner failure-path tests require PowerShell 7")

    def test_engine_modes_reject_existing_output_before_startup(self):
        for single_question in (False, True):
            with self.subTest(single_question=single_question), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / "existing"
                output.mkdir()
                evidence = output / "rows.jsonl"
                evidence.write_bytes(b"original evidence\n")
                arguments = [self.pwsh, "-NoProfile", "-NonInteractive", "-File",
                             str(ROOT / "scripts/run_engine_eval.ps1"), "-Model", "not-used.gguf",
                             "-Label", "existing", "-OutRoot", temporary]
                if single_question:
                    arguments.append("-SingleQuestion")
                else:
                    arguments.append("-SingleQuestion:$false")
                result = subprocess.run(arguments, capture_output=True, timeout=20)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"engine output already exists", result.stderr)
                self.assertNotIn(b"__ENGINE_EVAL_DONE__", result.stdout)
                self.assertEqual(evidence.read_bytes(), b"original evidence\n")
                self.assertFalse((output / "run.json").exists())

    def test_engine_defaults_to_single_question_and_preserves_legacy_mode(self):
        runner = (ROOT / "scripts/run_engine_eval.ps1").as_posix().replace("'", "''")
        program = (
            "$tokens=$null; $errors=$null; "
            f"$ast=[Management.Automation.Language.Parser]::ParseFile('{runner}',[ref]$tokens,[ref]$errors); "
            "$parameter=$ast.ParamBlock.Parameters | Where-Object {$_.Name.VariablePath.UserPath -eq 'SingleQuestion'}; "
            "$SingleQuestion=& ([scriptblock]::Create($parameter.DefaultValue.Extent.Text)); "
            "$branch=@($ast.FindAll({param($node) $node -is [Management.Automation.Language.IfStatementAst] "
            "-and $node.Extent.Text.StartsWith('if ($SingleQuestion) { $clientArgs')},$true)); "
            "if($errors.Count -or $branch.Count -ne 1) { throw 'runner mode parse failed' }; "
            "$clientArgs=@(); . ([scriptblock]::Create($branch[0].Extent.Text)); "
            "Write-Output ('default='+($clientArgs -join ',')); "
            "$SingleQuestion=$false; $clientArgs=@(); . ([scriptblock]::Create($branch[0].Extent.Text)); "
            "Write-Output ('legacy='+($clientArgs -join ','))"
        )
        result = subprocess.run([self.pwsh, "-NoProfile", "-NonInteractive", "-Command", program],
                                capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertIn(b"default=--single-question", result.stdout)
        self.assertIn(b"legacy=--record-questions", result.stdout)
        for name in ("laptop_round2c_eval.ps1", "laptop_round2c_concurrency.ps1"):
            self.assertIn("-SingleQuestion:$false", (ROOT / "scripts" / name).read_text(encoding="utf-8"))

    def test_engine_parity_failure_or_missing_input_blocks_completion(self):
        runner = (ROOT / "scripts/run_engine_eval.ps1").as_posix().replace("'", "''")
        python = Path(sys.executable).as_posix().replace("'", "''")
        for native_exit, has_reference in ((0, True), (23, True), (0, False)):
            with self.subTest(native_exit=native_exit, has_reference=has_reference):
                program = (
                    "$ErrorActionPreference='Stop'; $PSNativeCommandUseErrorActionPreference=$false; "
                    "$tokens=$null; $parseErrors=$null; "
                    f"$ast=[Management.Automation.Language.Parser]::ParseFile('{runner}',[ref]$tokens,[ref]$parseErrors); "
                    "$branch=@($ast.FindAll({param($node) $node -is [Management.Automation.Language.IfStatementAst] "
                    "-and $node.Extent.Text.StartsWith('if ($TorchPrefix -and -not $SingleQuestion)')},$true)); "
                    "if($branch.Count -ne 1) { throw 'comparison branch missing' }; "
                    f"function python {{ & '{python}' -B -c 'raise SystemExit({native_exit})'; $global:LASTEXITCODE=$LASTEXITCODE }}; "
                    f"function Test-Path {{ ${str(has_reference).lower()} }}; "
                    "$TorchPrefix='fixture/'; $SingleQuestion=$false; $w='support'; $out=[IO.Path]::GetTempPath(); "
                    "& ([scriptblock]::Create($branch[0].Extent.Text)); Write-Output '__ENGINE_EVAL_DONE__'"
                )
                result = subprocess.run([self.pwsh, "-NoProfile", "-NonInteractive", "-Command", program],
                                        capture_output=True, timeout=20)
                if native_exit == 0 and has_reference:
                    self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
                    self.assertIn(b"__ENGINE_EVAL_DONE__", result.stdout)
                else:
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn(b"__ENGINE_EVAL_DONE__", result.stdout)
                    expected = b"parity comparison failed" if has_reference else b"no PyTorch rows"
                    self.assertIn(expected, result.stderr)


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
            if name.startswith("long"):  # history clauses: LongInputTests
                continue
            with self.subTest(file=name):
                for r in rows:
                    case = dict(self.cases[r["_meta"]["group"]])
                    field = "device" if case["workload"] == "support" else "context"
                    case[field] = state_of(r)[field]  # pair and counterfactual records change these fields
                    got = {q: v["label"] for q, v in r["questions"].items()}
                    self.assertEqual(got, labels[case["workload"]](case), r["_meta"]["case"])

    def test_long_input_labels_follow_history_clauses(self):
        import gen_long_cases as glc
        long_rows = self.files["long_test_support.jsonl"]
        short_rows = self.files["longshort_test_support.jsonl"]
        self.assertEqual(len(long_rows), 160)
        self.assertEqual([r["_meta"]["case"] for r in long_rows], [r["_meta"]["case"] for r in short_rows])
        plain_rows = self.files["longplain_test_support.jsonl"]
        self.assertEqual([r["_meta"]["case"] for r in plain_rows], [r["_meta"]["case"] for r in short_rows])
        base_instr = {q: v["instructions"] for q, v in self.files["test_support.jsonl"][0]["questions"].items()}
        for s, p in zip(short_rows, plain_rows):
            self.assertEqual(state_of(s), state_of(p))
            for q in s["questions"]:
                self.assertEqual(s["questions"][q]["label"], p["questions"][q]["label"])
                self.assertEqual(p["questions"][q]["instructions"], base_instr[q])  # plain = training format
                self.assertTrue(s["questions"][q]["instructions"].startswith(base_instr[q]))
        kinds = {}
        for r, s in zip(long_rows, short_rows):
            meta = r["_meta"]
            kinds[meta["long_kind"]] = kinds.get(meta["long_kind"], 0) + 1
            self.assertGreaterEqual(len(r["state"]["case_history"]), 3000, meta["case"])
            self.assertNotIn("case_history", s["state"])
            self.assertTrue(all(glc.HISTORY_POLICY in q["instructions"] for q in r["questions"].values()))
            got = {q: v["label"] for q, v in r["questions"].items()}
            self.assertEqual({q: v["label"] for q, v in s["questions"].items()}, meta["short_policy_labels"], meta["case"])
            if not meta["decisive"]:  # control: the history is present but the decisive fact is absent -> short label
                self.assertEqual(got, meta["short_policy_labels"], meta["case"])
            else:  # decisive: the clause's question must come from the history clause, never from the short rule alone
                qid = {"H1": "queue", "H2": "queue", "H3": "urgency"}[meta["clause"]]
                if meta["clause"] == "H1":
                    self.assertEqual(got["queue"], "sales_ops")
                elif meta["clause"] == "H3":
                    self.assertEqual(got["urgency"], 3)
                else:
                    self.assertIn(got["queue"], ("onsite_repair", "depot_repair", "sales_ops"))
                self.assertIn(qid, got)
        self.assertEqual(set(kinds), set(glc.LONG_KINDS))

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
    def test_batch_modes_preserve_existing_evidence_before_sending(self):
        for single_question in (False, True):
            with self.subTest(single_question=single_question), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / "existing"
                output.mkdir()
                evidence = output / "rows.jsonl"
                original = b"prior evidence\n"
                evidence.write_bytes(original)
                argv = ["systemone_client.py", "--url", "http://127.0.0.1:1/v1/systemone",
                        "--data", str(FINAL / "test_support.jsonl"), "--out", str(output)]
                if single_question:
                    argv.append("--single-question")
                else:
                    argv.append("--record-questions")
                with mock.patch.object(client, "ask") as send, mock.patch("sys.argv", argv):
                    with self.assertRaises(FileExistsError):
                        client.main()
                send.assert_not_called()
                self.assertEqual(evidence.read_bytes(), original)
                self.assertFalse((output / "summary.json").exists())

    def test_single_question_batch_preserves_inputs_and_measures_each_request(self):
        record = {"state": {"message": "test", "region": "CN"}, "_meta": {"case": "case-1"},
                  "questions": {"queue": {"type": "choice", "choices": ["repair", "sales"], "label": "repair"},
                                "onsite": {"type": "noul", "label": True},
                                "urgency": {"type": "score", "label": 2}}}
        original = json.loads(json.dumps(record))
        answers = {"queue": {"choice": "repair", "probabilities": {"repair": 0.8, "sales": 0.2}},
                   "onsite": {"noul": 0.8}, "urgency": {"probabilities": {"1": 0.1, "2": 0.9}}}
        with tempfile.TemporaryDirectory() as temporary:
            data = Path(temporary) / "data.jsonl"
            data.write_text(json.dumps(record) + "\n", encoding="utf-8")
            output = Path(temporary) / "out"
            argv = ["systemone_client.py", "--url", "http://127.0.0.1:1/v1/systemone", "--data", str(data),
                    "--out", str(output), "--warmup", "0"]
            responses = [({"answers": {question_id: answer}}, latency)
                         for (question_id, answer), latency in zip(answers.items(), (10.0, 20.0, 30.0))]
            with mock.patch.object(client, "ask", side_effect=responses) as send, mock.patch("sys.argv", argv), mock.patch("builtins.print"):
                client.main()
            self.assertEqual(send.call_count, 3)
            for call, question_id in zip(send.call_args_list, record["questions"]):
                sent_record = call.args[1]
                self.assertEqual(sent_record["state"], record["state"])
                self.assertEqual(sent_record["questions"], {question_id: record["questions"][question_id]})
                self.assertNotIn("label", client.request_body(sent_record)["questions"][question_id])
            rows = read_jsonl(output / "rows.jsonl")
            self.assertEqual([row["latency_ms"] for row in rows], [10.0, 20.0, 30.0])
            self.assertEqual([row["record_index"] for row in rows], [0, 0, 0])
            self.assertEqual([list(row["questions"]) for row in rows], [[question_id] for question_id in record["questions"]])
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual((summary["records"], summary["requests"], summary["questions"]), (1, 3, 3))
            self.assertEqual(summary["request_mode"], "single_question")
            self.assertEqual(summary["latency_ms"]["p50"], 20.0)
            self.assertEqual(summary["accuracy"], 1.0)
            self.assertAlmostEqual(summary["calibration"]["ece"], 1 / 6)
            self.assertEqual(summary["calibration"]["coverage"], 1.0)
            self.assertEqual(rows[0]["response"], responses[0][0])
            self.assertEqual(rows[0]["request"], client.request_body(send.call_args_list[0].args[1]))
            with mock.patch.object(client, "ask") as repeated, mock.patch("sys.argv", argv), self.assertRaises(FileExistsError):
                client.main()
            repeated.assert_not_called()
        self.assertEqual(record, original)

    def test_single_question_failures_stay_in_denominator_and_raw_rows(self):
        record = {"state": "test", "questions": {
            "answered": {"type": "noul", "label": True},
            "timeout": {"type": "noul", "label": True},
            "invalid": {"type": "noul", "label": True}}}
        invalid_response = {"answers": {"invalid": {"noul": 1.2}}}
        responses = [({"answers": {"answered": {"noul": 0.8}}}, 12.0),
                     TimeoutError("timeout"), (invalid_response, 13.0)]
        with tempfile.TemporaryDirectory() as temporary:
            data = Path(temporary) / "data.jsonl"
            data.write_text(json.dumps(record) + "\n", encoding="utf-8")
            output = Path(temporary) / "out"
            argv = ["systemone_client.py", "--url", "http://127.0.0.1:1/v1/systemone", "--data", str(data),
                    "--out", str(output), "--warmup", "0", "--single-question"]
            with mock.patch.object(client, "ask", side_effect=responses), mock.patch("sys.argv", argv), mock.patch("builtins.print"):
                client.main()
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            rows = read_jsonl(output / "rows.jsonl")
            self.assertEqual((summary["questions"], summary["questions_answered"], summary["errors"]), (3, 1, 2))
            self.assertAlmostEqual(summary["accuracy"], 1 / 3)
            self.assertAlmostEqual(summary["calibration"]["coverage"], 1 / 3)
            self.assertAlmostEqual(summary["calibration"]["ece"], 0.2)
            self.assertEqual(summary["latency_ms"]["n"], 1)
            self.assertEqual(rows[1]["error"]["type"], "TimeoutError")
            self.assertEqual(rows[1]["labels"], {"timeout": True})
            self.assertGreaterEqual(rows[1]["error"]["elapsed_ms"], 0)
            self.assertEqual(rows[2]["response"], invalid_response)

    def test_probability_metrics_match_existing_calibration_method(self):
        import math
        distributions = [([0.8, 0.2], 0, "choice"), ([0.7, 0.3], 1, "noul"),
                         ([0.1, 0.2, 0.7], 2, "score")]
        scores = []
        for probabilities, label, question_type in distributions:
            question = {"type": question_type, "label": bool(label) if question_type == "noul" else label}
            answer = ({"noul": probabilities[1]} if question_type == "noul"
                      else {"choice": 0, "probabilities": {str(index): value for index, value in enumerate(probabilities)}})
            scores.append(client.score_answer(question, answer))
        actual = client.calibration_summary(scores)
        reference = cb.metrics([([math.log(value) for value in probabilities], label, question_type)
                                for probabilities, label, question_type in distributions], 1.0)
        self.assertAlmostEqual(actual["ece"], reference["ece"])
        self.assertAlmostEqual(actual["brier"], reference["brier"])
        self.assertEqual(actual["n"], reference["n"])
        self.assertIsNone(client.calibration_summary([])["ece"])

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

    def test_batch_concurrency_keeps_order_scoring_and_throughput_fields(self):
        """--concurrency N scores the same records with the same per-row shape as the sequential path; rows stay in
        record order, one failed request is counted not fatal, and only concurrent runs add wall/throughput fields."""
        records = [{"state": {"message": f"m{i}"}, "questions": {"q": {"type": "noul", "label": i % 2 == 0}}, "_meta": {"case": f"c{i}"}}
                   for i in range(6)]

        def fake_ask(url, record):
            index = int(record["state"]["message"][1:])
            if index == 3:
                raise ConnectionError("boom")
            time.sleep(0.01 * (6 - index))  # later records finish first when run concurrently
            return {"answers": {"q": {"type": "noul", "noul": 0.9}}, "usage": {"input_tokens": 10}}, 5.0 + index

        for concurrency in (1, 3):
            with self.subTest(concurrency=concurrency), tempfile.TemporaryDirectory() as temporary:
                data = Path(temporary) / "data.jsonl"
                data.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
                out = Path(temporary) / "out"
                argv = ["systemone_client.py", "--url", "http://127.0.0.1:1/v1/systemone", "--data", str(data), "--out", str(out),
                    "--warmup", "0", "--concurrency", str(concurrency), "--record-questions"]
                with mock.patch.object(client, "ask", side_effect=fake_ask), mock.patch("sys.argv", argv), mock.patch("builtins.print"):
                    client.main()
                rows = [json.loads(l) for l in (out / "rows.jsonl").read_text(encoding="utf-8").splitlines()]
                self.assertEqual([r["i"] for r in rows], list(range(6)))
                self.assertIn("error", rows[3])
                self.assertEqual([r["questions"]["q"]["pred"] for r in rows if "questions" in r], [True] * 5)
                summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
                self.assertEqual((summary["records"], summary["errors"], summary["questions"]), (6, 1, 5))
                self.assertEqual(summary["accuracy"], 0.6)  # correct for i in {0, 2, 4}, wrong for 1 and 5; record 3 failed
                self.assertEqual(summary["latency_ms"]["n"], 5)
                if concurrency == 1:
                    self.assertNotIn("requests_per_second", summary)
                else:
                    self.assertEqual(summary["concurrency"], 3)
                    self.assertGreater(summary["requests_per_second"], 0)
                    self.assertGreater(summary["wall_seconds"], 0)


class ReportLayoutTests(unittest.TestCase):
    def test_calibration_table_covers_all_measured_recipe_dataset_pairs(self):
        from render_diagrams import calibration_table

        text = calibration_table()
        rows = [line for line in text.splitlines() if line.startswith("| ")][1:]
        self.assertEqual(len(rows), 12)
        for recipe in ("0.8B FT-cf", "4B FT-cf", "0.8B 第二轮 C"):
            self.assertEqual(sum(recipe in row for row in rows), 4)
        self.assertIn("案例组95%区间", text)
        self.assertIn("（边界）", text)
        self.assertNotIn("修不掉", text)

    def test_overview_consumes_the_selected_summary(self):
        from render_diagrams import overview_blocks, report_sources

        sources = report_sources()
        summary = json.loads(sources["first_summary"].read_text(encoding="utf-8"))
        summary["sets"]["0.8b/test_support"]["b0"]["acc"] = 0.0
        with tempfile.TemporaryDirectory() as temporary:
            replacement = Path(temporary) / "summary.json"
            replacement.write_text(json.dumps(summary), encoding="utf-8")
            sources["first_summary"] = replacement
            with mock.patch("render_diagrams.report_sources", return_value=sources):
                table = overview_blocks()["ACCURACY"]
        self.assertIn("| 0.8B | 工单·同分布（510 题） | 0.0% |", table)

    def test_report_sources_reject_missing_or_external_paths(self):
        from render_diagrams import report_sources

        for invalid in ("missing-summary.json", "../outside-summary.json"):
            configuration = {name: invalid for name in
                             ("first_summary", "round2_summary", "device_results", "round2_device_results")}
            text = "<!-- REPORT:SOURCES\n" + json.dumps(configuration) + "\n-->"
            with self.subTest(path=invalid), mock.patch.object(Path, "read_text", return_value=text):
                with self.assertRaises(ValueError):
                    report_sources()

    def test_request_examples_match_captured_requests_and_responses(self):
        from render_diagrams import saved_request_examples

        for language in ("zh", "en"):
            text = saved_request_examples(language)
            blocks = re.findall(r"```json\n(.*?)\n```", text, re.S)
            self.assertEqual(len(blocks), 6)
            for index, dataset in enumerate(("test_support", "test_assistant", "ood_support")):
                raw = read_jsonl(ROOT / "验证结果/单题接口验收_20261102-161257" / dataset / "rows.jsonl")[0]
                self.assertEqual(json.loads(blocks[index * 2]), raw["request"])
                self.assertEqual(json.loads(blocks[index * 2 + 1]), raw["response"])
            self.assertIn("damage_claim", text)
            self.assertIn("答错" if language == "zh" else "incorrect", text)

    def test_record_request_tables_preserve_real_latency_and_recipe_coverage(self):
        import statistics
        from render_diagrams import record_request_tables

        text = record_request_tables()
        rows = [line for line in text.splitlines() if line.startswith("| ") and not line.startswith("| 模型")]
        self.assertEqual(len(rows), 14)
        self.assertNotIn("待测", text)
        self.assertEqual(text.count("处理完整请求中位时间（秒，每次3道判断）"), 2)
        for workload, dataset in (("support", "工单·同分布"), ("assistant", "助手·同分布")):
            raw = read_jsonl(ROOT / "验证结果/端侧引擎_骁龙第二轮C_20261101-203702/r2c-kev-0.8b-Q8_0-cpu" / workload / "rows.jsonl")
            row = next(line for line in rows if "第二轮 C" in line and dataset in line)
            self.assertIn(f"**{statistics.median(item['latency_ms'] for item in raw) / 1000:.3f}**", row)
            self.assertIn("100.0%", row)

    def test_single_question_matrix_omits_unexecuted_campaign(self):
        from render_diagrams import single_question_tables

        with tempfile.TemporaryDirectory() as temporary:
            text = single_question_tables(Path(temporary))
        self.assertEqual(text, "")

    def test_single_question_matrix_rejects_other_devices(self):
        from render_diagrams import single_question_tables

        with tempfile.TemporaryDirectory() as temporary:
            campaign = Path(temporary)
            output = campaign / "released-kev-0.8b-Q8_0-cpu" / "test_support"
            output.mkdir(parents=True)
            (output / "summary.json").write_text('{}', encoding="utf-8")
            (output.parent / "run.json").write_text(json.dumps({"request_mode": "single_question", "architecture": "AMD64"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "device/configuration mismatch"):
                single_question_tables(campaign)

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

    def test_accuracy_tables_pair_release_and_final_recipe(self):
        blocks = sr.report_blocks(self.accuracy_summary())
        block = blocks["README_ACC"]
        self.assertEqual(block.count("| 微调前准确率：发布版 | 微调后准确率：第一轮 FT-cf |"), 2)
        for size in ("0.8B", "4B"):
            for set_name, count in (("工单·同分布", "510"), ("助手·同分布", "477"),
                                    ("工单·分布外", "1,011"), ("助手·分布外", "951")):
                self.assertIn(f"| {size} | {set_name}（{count} 题） | 10.0% | 40.0% | +30.0 |", block)
        for count in ("510", "477", "1,011", "951"):
            self.assertIn(f"（{count} 题）", block)
        self.assertNotIn("20.0%", block)
        self.assertNotIn("30.0%", block)
        self.assertIn("| 10.0% | 20.0% | 30.0% | 40.0% |", blocks["ACC"])
        self.assertIn("| 10.0% | 20.0% | 30.0% | 40.0% |", blocks["CF"])
        self.assertTrue(all(len(line.strip("|").split("|")) == 5
                            for line in block.splitlines() if line.startswith("|")))

    def test_accuracy_tables_keep_unrun_cells_visible(self):
        summary = self.accuracy_summary()
        del summary["sets"]["4b/test_support"]["ftcf"]
        block = sr.report_blocks(summary)["README_ACC"]
        self.assertIn("| 4B | 工单·同分布（510 题） | 10.0% | 未跑 | 未跑 |", block)

    def test_accuracy_tables_reject_different_question_counts(self):
        summary = self.accuracy_summary()
        summary["sets"]["0.8b/test_support"]["ftcf"]["n"] = 509
        with self.assertRaisesRegex(ValueError, "question counts differ"):
            sr.report_blocks(summary)

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

    def performance_pair(self):
        common = {"backend": "cpu", "build": "b11935-cpu", "args": "-c 8192 -b 2048 -ub 2048 --cache-ram 0",
                  "support_records": 170, "assistant_records": 159,
                  "support_data": "test_support.jsonl", "assistant_data": "test_assistant.jsonl",
                  "support_cases_sha256": "same-support-cases", "assistant_cases_sha256": "same-assistant-cases",
                  "support_tokens_sha256": "same-support-tokens", "assistant_tokens_sha256": "same-assistant-tokens"}
        return [{**common, "label": "released-kev-0.8b-Q8_0-cpu", "support_p50": 666.5,
                 "assistant_p50": 843.3, "peak_ws_mib": 2323},
                {**common, "label": "ftcf-kev-0.8b-Q8_0-cpu", "support_p50": 646.0,
                 "assistant_p50": 983.8, "peak_ws_mib": 2314}]

    def test_performance_table_pairs_matching_runs(self):
        text = se.before_after_table(self.performance_pair())
        self.assertIn("| 0.8B / Q8_0 / CPU | 工单请求耗时中位数（毫秒） | 666 | 646 |", text)
        self.assertIn("| 0.8B / Q8_0 / CPU | 进程峰值工作集（MiB） | 2,323 | 2,314 |", text)
        self.assertIn("| 4B / Q4_K_M / CPU | 工单请求耗时中位数（毫秒） | 未跑 | 未跑 |", text)

    def test_performance_table_rejects_mismatched_cases_or_settings(self):
        for field, value in (("support_cases_sha256", "different-cases"),
                             ("args", "-c 2048 -b 2048 -ub 512 --cache-ram 0")):
            with self.subTest(field=field):
                rows = self.performance_pair()
                rows[1][field] = value
                with self.assertRaisesRegex(ValueError, "performance (conditions|settings) differ"):
                    se.before_after_table(rows)


class BilingualDocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from markdown_it import MarkdownIt
        except ImportError:
            raise unittest.SkipTest("Documentation tests require requirements-docs.txt")
        cls.parser = MarkdownIt("commonmark", {"html": True}).enable("table")
        from render_diagrams import DOCUMENT_PAIRS
        cls.pairs = DOCUMENT_PAIRS

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

    def test_delivered_results_contain_record_measurements_not_empty_plans(self):
        from render_diagrams import record_request_tables
        from fill_report_tables import localize_block

        expected = record_request_tables()
        for filename, rendered, boundary in (
                ("评测与端侧结果全集.md", expected, "不是独立盲测终验集"),
                ("Evaluation-Results.md", localize_block(expected), "not an independent blind acceptance set")):
            text = (ROOT / "文档" / filename).read_text(encoding="utf-8")
            measured = self.tables(self.parser.parse(text))[1:3]
            self.assertEqual(measured, self.tables(self.parser.parse(rendered)))
            self.assertEqual([len(table) - 1 for table in measured], [8, 6])
            self.assertIn(boundary, text)
            self.assertNotIn("SINGLE:INFERENCE", text)
            self.assertNotRegex(text, r"\|[^\n]*(?:待测|Not measured)")

    def test_report_alignment_keeps_measured_scope_and_removes_invalid_inferences(self):
        from render_diagrams import calibration_table
        from fill_report_tables import localize_block

        expected = calibration_table()
        for filename, translated in (("评测与端侧结果全集.md", expected),
                                     ("Evaluation-Results.md", localize_block(expected))):
            text = (ROOT / "文档" / filename).read_text(encoding="utf-8")
            tables = self.tables(self.parser.parse(text))
            self.assertEqual(tables[14], self.tables(self.parser.parse(translated))[0])
            self.assertEqual(len(tables[14]) - 1, 12)
            self.assertNotRegex(text, r"每秒约 190 token|about 190 tokens per second|812 对 646|812 vs\. 646")
            self.assertNotRegex(text, r"校准修不掉的部分|Not fixable by calibration|微调后准确率：最终方案|final-recipe accuracy")
            self.assertNotRegex(text, r"\|\s*(?:NPU（Hexagon）|NPU \(Hexagon\))\s*\|")
            self.assertNotRegex(text, r"从 45\.7% 提到 96\.3%|from 45\.7% to 96\.3%")
            self.assertIn("13,589 MiB", text)
            self.assertIn("10.08 GB", text)
        source = (ROOT / "scripts/render_diagrams.py").read_text(encoding="utf-8")
        training = source[source.index("def training("):source.index("def inference(")]
        self.assertNotIn("764 MiB", training)
        self.assertNotIn("517 MiB", training)
        self.assertNotIn("only pass/fail", training)
        self.assertIn('manifest[name]["records"]', training)

    def test_audited_prose_and_runner_contracts_stay_aligned(self):
        for filename in ("README_CN.md", "README.md", "文档/核心技术_微调与端侧运行.md", "文档/Core-Technology.md"):
            text = (ROOT / filename).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"四种微调|Four recipes are compared|All four fine-tuned recipes")
        for filename in ("操作步骤全本.md", "Operations-Guide.md"):
            text = (ROOT / "文档" / filename).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"笔记本上的并发（只在|concurrency on the laptop \(measured only")
            self.assertNotIn("其余内容与实验所用数据相同", text)
            self.assertNotIn("other content is unchanged, so SHA-256", text)
            self.assertIn("--sizes 0.8b --recipes r2-C", text)
            self.assertIn("__ENGINE_EVAL_DONE__", text)
            self.assertIn("<OutRoot>/<Label>", text)
        for filename in ("核心技术_微调与端侧运行.md", "Core-Technology.md"):
            text = (ROOT / "文档" / filename).read_text(encoding="utf-8")
            table = next(table for table in self.tables(self.parser.parse(text))
                         if any(row and row[0].startswith("`-c`") for row in table))
            context_row = next(row for row in table if row[0].startswith("`-c`"))
            self.assertIn("`-b`", context_row[-1])
            self.assertIn("`-ub`", context_row[-1])
            self.assertRegex(context_row[-1], r"不能仅归因|cannot be attributed")

    def test_single_question_default_is_distinct_from_historical_results(self):
        for filename, wording in (("README_CN.md", "新评测默认每次只发一道题"),
                                  ("README.md", "New evaluations send one question per request by default")):
            self.assertIn(wording, (ROOT / filename).read_text(encoding="utf-8"))
        for filename in ("操作步骤全本.md", "Operations-Guide.md"):
            text = (ROOT / "文档" / filename).read_text(encoding="utf-8")
            self.assertIn("-SingleQuestion:$false", text)
            self.assertIn("--record-questions", text)
            self.assertNotIn("不加此开关即走旧路径", text)
            self.assertNotIn("Ommiting the switch retains three-question mode", text)
            self.assertNotIn("Omitting the switch retains three-question mode", text)

    def test_readme_composition_identifies_frozen_and_updated_components(self):
        config_path = ROOT / "验证结果/第二轮微调评测_20261101-101948/runs/0.8b/r2-C/training_config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        self.assertEqual(config["args"]["base"], "Qwen/Qwen3.5-0.8B-Base")
        self.assertEqual(config["args"]["init_from"], "jaredpalmer/kev-0.8b@v1.0")
        self.assertEqual((config["args"]["lora"], config["args"]["full_ft"]), (16, 0))
        for filename, next_heading, required in (
                ("README_CN.md", "#### 核心代码示例", ("基座：冻结，不更新", "LoRA adapter：继续训练", "决策头：继续训练",
                                                     "不叠加第二套业务 adapter", "不是独立的全量基座权重包", "不需要再单独加载 Qwen 基座或 adapter")),
                ("README.md", "#### Core Code:", ("backbone: frozen, not updated", "LoRA adapter: continued training",
                                                 "decision head: continued training", "does not stack a second business adapter",
                                                 "not a standalone full-backbone weight package", "no separate Qwen base or adapter needs to be loaded"))):
            with self.subTest(document=filename):
                text = (ROOT / filename).read_text(encoding="utf-8")
                start = text.index('<a id="model-composition"></a>')
                section = text[start:text.index(next_heading, start)]
                for value in (*required, "--base", "--base_revision", "--init_from", "lora=16", "full_ft=0",
                              "training_config.json", "Checkpoint.warm_start()"):
                    self.assertIn(value, section)

    def test_readme_core_examples_match_the_delivered_c_recipe(self):
        text = (ROOT / "README_CN.md").read_text(encoding="utf-8")
        examples = [token.content for token in self.parser.parse(text)
                    if token.type == "fence" and token.info == "bash"]
        self.assertEqual(len(examples), 3)
        training, calibration, quantization = examples
        self.assertIn("--data /mnt/aipc/data/contoso/train_cf2.jsonl", training)
        for argument in ("--replay 1000", "--epochs 4", "--lr 2e-5", "--batch 4 --accum 2",
                         "--max_state 768", "--init_from jaredpalmer/kev-0.8b@v1.0"):
            self.assertIn(argument, training)
        self.assertIn("CK=/mnt/aipc/runs/0.8b/r2-C", training)
        self.assertIn("-m kev.benchmark", calibration)
        self.assertIn("--data /mnt/aipc/data/contoso/calib.jsonl", calibration)
        self.assertIn('scripts/calibrate_checkpoint.py --run "$CK"', calibration)
        self.assertIn('--rows "$ROWS/rows.json" --allow-in-distribution', calibration)
        self.assertIn('"$LLAMA/convert_hf_to_gguf.py" "$CK"', quantization)
        self.assertIn("--outtype bf16", quantization)
        self.assertIn('"$LLAMA/build/bin/llama-quantize"', quantization)
        self.assertIn('"$OUT/$NAME-Q8_0.gguf.part" Q8_0', quantization)
        self.assertIn("NAME=Contoso-Kev-0.8B-FTcf-R2C", quantization)
        self.assertLess(text.index('src="images/training.png"'), text.index("#### 核心代码示例"))
        self.assertLess(text.index("#### 核心代码示例"), text.index("### 日常推理"))
        git_bash = Path("C:/Program Files/Git/bin/bash.exe")
        bash = str(git_bash) if git_bash.is_file() else shutil.which("bash")
        if not bash:
            self.skipTest("README command syntax validation requires Bash")
        result = subprocess.run([bash, "--noprofile", "--norc", "-n"],
                                input="\n".join(examples).encode("utf-8"), capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))

    def test_current_model_reproduction_commands_are_present_in_both_languages(self):
        commands = ("bash scripts/remote_round2.sh 0.8b C",
                    "bash scripts/remote_export_round2.sh 0.8b C",
                    "-Size 0.8b-r2C -Only Q8_0")
        for filename in ("操作步骤全本.md", "Operations-Guide.md"):
            text = (ROOT / "文档" / filename).read_text(encoding="utf-8")
            for command in commands:
                self.assertIn(command, text, filename)
            self.assertIn('id="report-sources"', text)
            self.assertIn("REPORT:SOURCES", text)

    def test_long_input_token_table_matches_original_requests(self):
        import statistics

        text = (ROOT / "文档/评测与端侧结果全集.md").read_text(encoding="utf-8")
        table = next(table for table in self.tables(self.parser.parse(text))
                     if "输入 token 中位数（请求合计 / 每题平均）" in table[0])
        paths = (
            "验证结果/端侧引擎_x64_20261030-234858/ftcf-kev-0.8b-Q8_0-cpu-run1/support/rows.jsonl",
            "验证结果/端侧引擎_x64长输入_20261101-101318/ftcf-0.8b-q8-cpu-long8k/support/rows.jsonl",
        )
        for row, relative in zip(table[1:], paths):
            records = read_jsonl(ROOT / relative)[:40]
            total = statistics.median(record["input_tokens"] for record in records)
            mean = statistics.median(record["input_tokens"] / len(record["questions"]) for record in records)
            total_text = f"{total:,.1f}".removesuffix(".0")
            self.assertEqual(row[1], f"{total_text} / {mean:,.1f}")
        self.assertNotIn("时间按输入长度线性涨", text)
        self.assertNotIn("当前可行的是两条路", text)

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
                          if token.type == "heading_open" and token.tag == "h2"],
                         ["Purpose", "Results at a Glance", "Architecture", "Results", "Steps", "Repository Deliverables"])

    def test_overview_matches_saved_results_and_precedes_architecture(self):
        from render_diagrams import validate_overview

        chinese = (ROOT / "README_CN.md").read_text(encoding="utf-8")
        validate_overview(chinese)
        self.assertLess(chinese.index("## 成果一览"), chinese.index("## 架构"))
        self.assertLessEqual(len(chinese.splitlines()), 400)
        tables = self.tables(self.parser.parse(chinese))
        self.assertEqual(len(tables[0]) - 1, 8)
        self.assertEqual(sum("未做" in row for row in tables[0][1:]), 4)
        with self.assertRaises(ValueError):
            validate_overview(chinese.replace("44.7%", "44.8%"))

    def test_device_tables_exclude_gpu_only_reference_rows(self):
        chinese = (ROOT / "README_CN.md").read_text(encoding="utf-8")
        tables = self.tables(self.parser.parse(chinese))
        for table, expected_rows in zip(tables[1:3], (8, 6)):
            self.assertEqual(len(table) - 1, expected_rows)
            self.assertEqual(table[0][1], "测试集（题数）")
            self.assertEqual(table[0][2], "逐题准确率（%，含失败题）")
            self.assertEqual(table[0][3], "处理完整请求中位时间（秒，每次3道判断）")
            self.assertIn("校准误差 ECE（0–1，越低越好）", table[0])
            self.assertFalse(any("BF16 未量化" in row[0] for row in table[1:]))
            self.assertNotIn("模型加载阶段耗时（秒，日志）", table[0])
        details = (ROOT / "文档/评测与端侧结果全集.md").read_text(encoding="utf-8")
        self.assertIn('<a id="gpu-bf16-baseline"></a>', details)
        baseline = next(table for table in self.tables(self.parser.parse(details))
                        if "工单 / 助手准确率（GPU / PyTorch）" in table[0])
        self.assertEqual(baseline[1:], [
            ["0.8B FT-cf", "BF16", "16.0", "1,437", "86.9% / 97.5%"],
            ["4B FT-cf", "BF16", "16.0", "8,026", "95.9% / 99.8%"],
        ])
        self.assertTrue(all("GPU 准确率" in header for header in tables[0][0][2:5]))
        self.assertIn("3,832 条，训练 2 遍", tables[0][0][3])
        self.assertIn("4,038 条，训练 4 遍", tables[0][0][4])
        self.assertIn("从同一个发布版独立训练", chinese)
        self.assertIn("8.52 BPW", details)
        self.assertIn("5.76 BPW", details)

    def test_loading_times_use_the_same_server_log_interval(self):
        from render_diagrams import model_loading_seconds, overview_blocks

        prefix = "验证结果/端侧引擎_20261027-124700/"
        self.assertEqual(model_loading_seconds(prefix + "released-kev-0.8b-Q8_0-cpu/server.log"), "3.981")
        self.assertEqual(model_loading_seconds(prefix + "released-kev-4b-Q4_K_M-cpu/server.log"), "7.820")
        tables = self.tables(self.parser.parse(overview_blocks()["LEGACY_INFERENCE"]))
        expected = (("3.981", "1.483", "1.642", "2.236"), ("7.820", "8.552", "5.014"))
        for table, loading in zip(tables, expected):
            self.assertEqual(table[0][5], "单条任务处理耗时（工单 / 助手，毫秒，中位数）")
            self.assertEqual(table[0][7], "模型加载阶段耗时（秒，日志）")
            self.assertEqual(tuple(row[7] for row in table[1:]), loading)
            self.assertFalse(any(row[7] == "未记录" for row in table[1:]))
        details = (ROOT / "文档/评测与端侧结果全集.md").read_text(encoding="utf-8")
        self.assertIn("一次返回三道问题的答案", details)
        self.assertIn("不代表完整服务启动耗时", details)

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
                         {name + suffix + ".png" for name in ("training", "inference", "validation", "decision") for suffix in ("", "-en")})
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

    def test_calibration_boundary_accuracy_invariant_and_ece_arithmetic(self):
        """Temperature preserves argmax; a finite-grid ECE decrease remains an in-sample diagnostic."""
        rows = [r for r in json.loads(self.saved_rows("pytorch-b0-0.8b").read_text(encoding="utf-8")) if r.get("variant", "clean") == "clean"]
        prepared, served = cb.prepare(rows)
        accs = {round(cb.metrics(prepared, t)["acc"], 9) for t in (0.5, served, 1.0, 2.0, 4.0)}
        self.assertEqual(len(accs), 1)
        self.assertAlmostEqual(cb.metrics(prepared, served)["brier"], tw.score(rows, served)["brier"], places=4)  # tw rounds to 4 places
        result = cb.analyse(self.saved_rows("pytorch-b0-0.8b"), FINAL / "test_support.jsonl")
        self.assertLessEqual(abs(result["ece_decrease_on_grid"] - (result["at_served"]["ece"] - result["ece_at_best_T"])), 0.00011)
        self.assertFalse(result["temperature_search"]["global_bound"])
        self.assertNotIn("ece_removable_by_any_T", result)
        records = read_jsonl(FINAL / "test_support.jsonl")
        self.assertEqual(result["bootstrap_method"]["groups"], len({record["_meta"]["group"] for record in records}))
        self.assertEqual(result["input_hashes"]["data_sha256"], hashlib.sha256((FINAL / "test_support.jsonl").read_bytes()).hexdigest())
        cov = result["coverage_at_served"]
        self.assertTrue(all(cov[a]["coverage"] >= cov[b]["coverage"] for a, b in zip(("0.5", "0.6", "0.7", "0.8", "0.9"), ("0.6", "0.7", "0.8", "0.9", "0.95"))))
        # synthetic: confidently wrong on 30% of items at T=1 -> the ECE-optimal temperature must flatten (T > 1)
        synthetic = [([4.0, 0.0, 0.0], 0 if i % 10 < 7 else 1, "choice") for i in range(200)]
        best = min(cb.GRID, key=lambda t: cb.metrics(synthetic, t)["ece"])
        self.assertGreater(best, 1.0)
        self.assertEqual({round(cb.metrics(synthetic, t)["acc"], 9) for t in cb.GRID}, {0.7})

    def test_calibration_diagnostic_rejects_incomplete_or_duplicate_questions(self):
        rows = [row for row in json.loads(self.saved_rows("pytorch-b0-0.8b").read_text(encoding="utf-8"))
                if row.get("variant", "clean") == "clean"]
        invalid = {
            "missing": rows[:-1],
            "duplicate": rows + [rows[0]],
            "duplicate_replacing_missing": rows[:-1] + [rows[0]],
            "unexpected": rows + [{**rows[0], "question": "unexpected_question"}],
            "empty": [],
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "rows.json"
            for name, sample in invalid.items():
                with self.subTest(case=name):
                    path.write_text(json.dumps(sample), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "question coverage mismatch"):
                        cb.analyse(path, FINAL / "test_support.jsonl")

    def test_calibration_cli_rejects_empty_or_partial_campaigns(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            empty = directory / "empty"
            empty.mkdir()
            runs = directory / "runs"
            valid = runs / "0.8b/ftcf-test_support/rows.json"
            valid.parent.mkdir(parents=True)
            original = self.saved_rows("pytorch-ftcf-0.8b").read_bytes()
            valid.write_bytes(original)
            (runs / "4b").mkdir()
            command = [sys.executable, "-B", str(ROOT / "scripts/calibration_boundary.py"),
                       "--data", str(FINAL), "--recipes", "ftcf"]
            cases = {
                "empty": ["--runs", str(empty)],
                "missing_model": ["--runs", str(empty), "--sizes", "0.8b", "--sets", "test_support"],
                "missing_dataset": ["--runs", str(runs), "--sizes", "0.8b"],
                "missing_second_model": ["--runs", str(runs), "--sets", "test_support"],
                "missing_recipe": ["--runs", str(runs), "--sizes", "0.8b", "--sets", "test_support",
                                   "--recipes", "ftcf", "ft"],
            }
            for name, arguments in cases.items():
                with self.subTest(case=name):
                    output = directory / name / "diagnostic"
                    result = subprocess.run(command + arguments + ["--out", str(output)], capture_output=True, timeout=20)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(b"calibration", result.stderr.lower())
                    self.assertFalse(output.exists())
            output = directory / "complete"
            arguments = command + ["--runs", str(runs), "--sizes", "0.8b", "--sets", "test_support", "--out", str(output)]
            result = subprocess.run(arguments, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            evidence = output / "calibration_boundary.json"
            recorded = evidence.read_bytes()
            diagnostic = json.loads(recorded)
            self.assertEqual(list(diagnostic), ["0.8b/ftcf/test_support"])
            self.assertEqual(diagnostic["0.8b/ftcf/test_support"]["rows"], 510)
            self.assertEqual(diagnostic["0.8b/ftcf/test_support"]["input_hashes"]["rows_sha256"], hashlib.sha256(original).hexdigest())
            repeated = subprocess.run(arguments, capture_output=True, timeout=20)
            self.assertNotEqual(repeated.returncode, 0)
            self.assertEqual(evidence.read_bytes(), recorded)

    def test_calibration_bootstrap_keeps_case_groups_and_sources_together(self):
        prepared = [([3.0, 0.0], 0, "choice")] * 30 + [([3.0, 0.0], 1, "choice")] * 30
        groups = [("one-source", "correct-case")] * 30 + [("one-source", "wrong-case")] * 30
        self.assertEqual(cb.bootstrap(prepared, 1.0, groups, reps=200)["acc_95"], [0.0, 1.0])
        sources = [("first-source", "case")] * 30 + [("second-source", "case")] * 30
        self.assertEqual(cb.bootstrap(prepared, 1.0, sources, reps=200)["acc_95"], [0.5, 0.5])

    def test_paired_rejects_missing_and_duplicate_questions(self):
        rows = json.loads(self.saved_rows("pytorch-b0-0.8b").read_text(encoding="utf-8"))
        records = read_jsonl(FINAL / "test_support.jsonl")
        groups = {index: record["_meta"]["group"] for index, record in enumerate(records)}
        same = sr.paired(rows, rows, groups, n_boot=40)
        self.assertEqual((same["questions"], same["acc_delta"]), (510, 0.0))
        cases = {
            "missing_reference_record": (rows, rows[:-3]),
            "missing_reference_question": (rows, rows[:-1]),
            "missing_on_both_sides": (rows[:-3], rows[:-3]),
            "duplicate_candidate": (rows + [rows[0]], rows),
            "duplicate_reference": (rows, rows + [rows[0]]),
            "duplicate_replacing_missing": (rows[:-1] + [rows[0]], rows),
            "empty": ([], []),
        }
        for name, (candidate, reference) in cases.items():
            with self.subTest(case=name), self.assertRaisesRegex(ValueError, "[Cc]overage mismatch|Duplicate paired question"):
                sr.paired(candidate, reference, groups, n_boot=40)

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
