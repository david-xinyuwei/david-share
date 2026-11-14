"""轨 B (CadQuery → STEP) tests. The model call and the OCCT child process are mocked: the real
kernel takes 2 s (VM) to 100 s (this laptop) just to import, and these tests are about the contract."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import app
import cad_runner


VALID_CODE = """import cadquery as cq
import math
P = {"L": 320, "W": 180, "T": 12}
DENSITY = 2.70
result = cq.Workplane("XY").box(P["L"], P["W"], P["T"])
METRICS = [{"label": "流道数", "value": "6", "unit": "", "note": "P.n"}]
"""

RAW_OK = f"""<<<SUMMARY>>>
铝合金冷板实体，320×180×12 mm。
<<<CAD>>>
{VALID_CODE}<<<END>>>"""

FAKE_METRICS = {
    "ok": True, "volume_mm3": 582219.0, "area_mm2": 148000.0, "bbox_mm": [320.0, 180.0, 12.0],
    "density_g_cm3": 2.7, "mass_kg": 1.572, "solids": 1, "faces": 32, "elapsed_s": 3.2,
    "step_bytes": 106639, "stl_bytes": 129284, "glb_bytes": 158792, "extra_metrics": [{"label": "流道数", "value": "6", "unit": "", "note": "P.n"}],
    "parts": [{"id": "part_1", "name": "流道基板", "volume_mm3": 500000.0, "mass_kg": 1.35, "density_g_cm3": 2.7, "faces": 30, "solids": 1, "material": "aluminum"},
              {"id": "part_2", "name": "进出口接头", "volume_mm3": 82219.0, "mass_kg": 0.222, "density_g_cm3": 2.7, "faces": 2, "solids": 1, "material": "aluminum"}],
}


def fake_run_script(code, out_dir, timeout, python=None, on_start=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "model.py").write_text(code, encoding="utf-8")
    (out_dir / "model.step").write_bytes(b"ISO-10303-21;\nEND-ISO-10303-21;\n")
    (out_dir / "model.stl").write_bytes(b"\0" * 84)
    (out_dir / "model.glb").write_bytes(b"glTF" + b"\0" * 16)
    (out_dir / "parts.json").write_text(json.dumps(FAKE_METRICS["parts"], ensure_ascii=False), encoding="utf-8")
    return dict(FAKE_METRICS)


class RunnerValidationTests(unittest.TestCase):
    def test_valid_script_accepted(self):
        self.assertIsNone(cad_runner.validate_code(VALID_CODE))

    def test_rejects_dangerous_constructs(self):
        cases = {
            "import os\n" + VALID_CODE: "os",
            VALID_CODE + "open('x.txt', 'w')\n": "open",
            VALID_CODE + "cq.exporters.export(result, 'a.step')\n": "export",
            VALID_CODE + "e = cq.exporters\n": "exporters",
            VALID_CODE + "x = result.__class__\n": "__class__",
            VALID_CODE + "exec('1')\n": "exec",
            "from subprocess import run\n" + VALID_CODE: "subprocess",
            VALID_CODE.replace("result =", "shape ="): "result",
            "P = {}\nresult = 1\n": "cadquery",
        }
        for code, needle in cases.items():
            problem = cad_runner.validate_code(code)
            self.assertIsNotNone(problem, code)
            self.assertIn(needle, problem)

    def test_syntax_error_and_size_limit(self):
        self.assertIn("语法错误", cad_runner.validate_code("import cadquery as cq\nresult = (\n") or "")
        big = VALID_CODE + "# " + "x" * cad_runner.MAX_SCRIPT_CHARS
        self.assertIsNotNone(cad_runner.validate_code(big))

    def test_child_metric_formatting(self):
        src = cad_runner._CHILD_TEMPLATE
        ns = {}
        exec(src[src.index("def _fmt"):src.index("extra = [")], ns)  # noqa: S102 — our own template
        fmt = ns["_fmt"]
        self.assertEqual(fmt(1866.349540849362), "1866.35")
        self.assertEqual(fmt(3.0), "3")
        self.assertEqual(fmt(6), "6")
        self.assertEqual(fmt(0), "0")
        self.assertEqual(fmt(True), "True")
        self.assertEqual(fmt("mm²"), "mm²")
        self.assertEqual(len(fmt("x" * 500)), 120)

    def test_extract_code_sentinels_and_fences(self):
        self.assertEqual(cad_runner.extract_code(RAW_OK).strip(), VALID_CODE.strip())
        fenced = "text\n```python\n" + VALID_CODE + "```\nmore"
        self.assertEqual(cad_runner.extract_code(fenced).strip(), VALID_CODE.strip())

    def test_parse_cad_output_without_contract(self):
        parsed = app.parse_cad_output("Sure, here is the script:\n" + VALID_CODE)
        self.assertEqual(parsed["summary"], "")
        self.assertTrue(parsed["code"].startswith("import cadquery as cq"))
        parsed = app.parse_cad_output(RAW_OK)
        self.assertEqual(parsed["summary"], "铝合金冷板实体，320×180×12 mm。")
        self.assertIsNone(cad_runner.validate_code(parsed["code"]))

    def test_extract_param_block(self):
        html = "<script>const P = { L: 320, W: 180, ch: { n: 6, w: 8 } };\nconst x = 1;</script>"
        self.assertEqual(app.extract_param_block(html), "const P = { L: 320, W: 180, ch: { n: 6, w: 8 } }")
        self.assertEqual(app.extract_param_block("<script>let q = 1;</script>"), "")

    def test_reference_example_passes_the_same_gate_as_model_output(self):
        """The few-shot shown to GPT-6 must itself satisfy the static gate and the parts/materials contract — otherwise the
        prompt teaches a script the server would reject. (Its OCCT execution is checked by the real-kernel smoke run, not here.)"""
        import ast
        example = app.CAD_EXAMPLE_PATH.read_text(encoding="utf-8")
        self.assertIsNone(cad_runner.validate_code(example))
        self.assertIn(example, app.CAD_PROMPT)                       # the prompt embeds the file verbatim
        self.assertLess(len(app.CAD_PROMPT), cad_runner.MAX_SCRIPT_CHARS + 12000, "prompt grew beyond the budget the model is told")
        names = {node.targets[0].id for node in ast.parse(example).body if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}
        self.assertTrue({"P", "DENSITY", "result", "PARTS", "MATERIALS", "DENSITIES", "NAME", "METRICS"} <= names, names)
        # Materials named in the example are presets the viewer actually has (static/studio-kit.js MATERIAL_PRESETS).
        kit = (Path(app.BASE) / "static" / "studio-kit.js").read_text(encoding="utf-8")
        for preset in ("aluminum", "anodized", "steel"):
            self.assertIn(f"{preset}:", kit)
        # The committed fixture is the OCCT output of this very script: 4 named parts, 3 material presets, ASCII node ids.
        parts = json.loads((Path(__file__).parent / "fixtures" / "cad_reference_coldplate" / "parts.json").read_text(encoding="utf-8"))
        self.assertEqual([p["name"] for p in parts], ["流道基板", "上盖板", "进口接头", "出口接头"])
        self.assertEqual([p["id"] for p in parts], ["part_1", "part_2", "part_3", "part_4"])
        self.assertEqual({p["material"] for p in parts}, {"aluminum", "anodized", "steel"})
        self.assertTrue(all(p["solids"] == 1 and p["faces"] > 0 and p["mass_kg"] > 0 for p in parts), parts)


class CadJobTests(unittest.IsolatedAsyncioTestCase):
    async def run_job(self, raws, runner=fake_run_script, body=None):
        body = body or app.CadBody(scenario_id="coldplate", prompt="320 mm 冷板", summary="s",
                                   html="<script>const P = { L: 320 };</script>", request_id="r" * 32)
        model = AsyncMock(side_effect=[(raw, {"usage": {"completion_tokens": 900}, "actual_model": "gpt-6-astra-test", "completion_id": "c1",
                                              "reasoning_effort": "low"}) for raw in raws])
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(app, "CAD_DIR", Path(tmp)), patch.object(app, "CAD_AVAILABLE", True), \
                patch.object(app, "cad_model_call", model), patch.object(app.cad_runner, "run_script", runner):
            blocks = [block async for block in app.run_cad(body)]
            events = [(b.split("\n")[0][7:], json.loads(b.split("\n")[1][6:])) for b in blocks]
            files = {p.name for p in Path(tmp).rglob("*") if p.is_file()}
        return events, model, files

    async def test_success_path_emits_metrics_and_files(self):
        body = app.CadBody(scenario_id="coldplate", prompt="320 mm 冷板", summary="s",
                           html="<script>const P = { L: 320 };</script>", request_id="r" * 32, reasoning_effort="low")
        events, model, files = await self.run_job([RAW_OK], body=body)
        names = [e for e, _ in events]
        self.assertEqual(names, ["start", "attempt", "attempt", "done"])
        start, done = events[0][1], events[-1][1]
        self.assertEqual(start["source"], "live")
        self.assertEqual(start["reasoning_effort"], "low")
        self.assertEqual(model.await_args.args[1], "low")  # the UI choice reaches the model call
        self.assertEqual(events[1][1]["phase"], "model")
        self.assertEqual(events[2][1]["phase"], "occt")
        self.assertTrue(done["ok"])
        self.assertEqual(done["attempts"], 1)
        self.assertEqual(done["job_id"], start["job_id"])
        self.assertEqual(done["summary"], "铝合金冷板实体，320×180×12 mm。")
        self.assertEqual(done["files"]["step"], f"/api/cad/file/{done['job_id']}/model.step")
        self.assertEqual(done["files"]["glb"], f"/api/cad/file/{done['job_id']}/model.glb")
        # Named parts (outliner rows + per-part material presets for the B-rep main view) travel with the result.
        self.assertEqual([p["name"] for p in done["parts"]], ["流道基板", "进出口接头"])
        self.assertEqual(done["parts"][0]["material"], "aluminum")
        labels = [m["label"] for m in done["metrics"]]
        self.assertEqual(labels[:5], ["STEP 实体体积", "STEP 实体质量", "外形包络", "表面积", "实体 / 面数"])
        self.assertIn("流道数", labels)
        self.assertEqual(done["metrics"][0]["value"], "582.22")
        self.assertEqual(done["metrics"][1]["value"], "1.572")
        self.assertEqual(done["raw"]["step_bytes"], 106639)
        self.assertTrue({"model.step", "model.stl", "model.py", "model.glb", "parts.json", "meta.json"} <= files)
        model.assert_awaited_once()
        self.assertEqual(done["reasoning_effort"], "low")  # effort actually used is echoed to the browser
        # The three.js parameter block is forwarded so both tracks share the same numbers.
        user_msg = model.await_args.args[0][1]["content"]
        self.assertIn("const P = { L: 320 }", user_msg)
        self.assertIn("冷板", user_msg)

    async def test_static_rejection_then_success_feeds_error_back(self):
        bad = RAW_OK.replace("import math\n", "import os\n")
        events, model, _ = await self.run_job([bad, RAW_OK])
        names = [e for e, _ in events]
        self.assertEqual(names, ["start", "attempt", "attempt_failed", "attempt", "attempt", "done"])
        self.assertIn("os", events[2][1]["error"])
        self.assertEqual(events[-1][1]["attempts"], 2)
        # second call carries the failed script and its error as conversation history
        second_msgs = model.await_args_list[1].args[0]
        self.assertEqual(second_msgs[-2]["role"], "assistant")
        self.assertIn("os", second_msgs[-1]["content"])

    async def test_runtime_failure_retries_and_gives_up(self):
        calls = []

        def failing(code, out_dir, timeout, python=None, on_start=None):
            calls.append(out_dir)
            return {"ok": False, "error": "Traceback...\nValueError: BRep_API: command not done", "elapsed_s": 1.0}

        with patch.object(app, "CAD_MAX_ATTEMPTS", 2):
            events, model, files = await self.run_job([RAW_OK, RAW_OK], runner=failing)
        self.assertEqual([e for e, _ in events][-1], "error")
        self.assertEqual(events[-1][1]["attempts"], 2)
        self.assertIn("BRep_API", events[-1][1]["message"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(model.await_count, 2)
        self.assertNotIn("model.step", files)

    async def test_unavailable_kernel_is_an_error_event(self):
        with patch.object(app, "CAD_AVAILABLE", False), patch.object(app, "cad_model_call", AsyncMock()) as model:
            events = [json.loads(b.split("\n")[1][6:]) | {"_e": b.split("\n")[0][7:]} for b in [x async for x in app.run_cad(app.CadBody(prompt="x"))]]
        self.assertEqual(events[-1]["_e"], "error")
        self.assertIn("CadQuery", events[-1]["message"])
        model.assert_not_awaited()

    async def test_file_endpoint_validates_ids_and_names(self):
        request = SimpleNamespace(cookies={app.COOKIE: app.make_session("test-user")})
        with tempfile.TemporaryDirectory() as tmp, patch.object(app, "CAD_DIR", Path(tmp)):
            job = Path(tmp) / "abcdef123456"
            job.mkdir()
            (job / "model.step").write_bytes(b"ISO-10303-21;")
            for job_id, name in [("../etc", "model.step"), ("abcdef123456", "meta.json"), ("abcdef123456", "../model.step"), ("000000000000", "model.step")]:
                with self.assertRaises(app.HTTPException) as ctx:
                    await app.cad_file(job_id, name, request)
                self.assertEqual(ctx.exception.status_code, 404)
            resp = await app.cad_file("abcdef123456", "model.step", request)
            self.assertEqual(resp.media_type, "application/step")
            self.assertIn("thermal3d-abcdef123456-model.step", resp.headers["content-disposition"])
        with self.assertRaises(app.HTTPException) as ctx:
            await app.cad_file("abcdef123456", "model.step", SimpleNamespace(cookies={}))
        self.assertEqual(ctx.exception.status_code, 401)

    async def test_pre_generated_cad_cache_is_served_like_a_live_result(self):
        """cad_cache/<id>/ (built offline by pregen_cad.py) is exposed with the shape of a live `done` event, provenance
        pinned to pre_generated, and its files served through /api/cad/file with a cache-<id> job id."""
        request = SimpleNamespace(cookies={app.COOKIE: app.make_session("test-user")})
        with tempfile.TemporaryDirectory() as tmp, patch.object(app, "CAD_CACHE_DIR", Path(tmp)):
            d = Path(tmp) / "coldplate"
            d.mkdir()
            for name, payload in (("model.step", b"ISO-10303-21;"), ("model.stl", b"\0" * 84), ("model.glb", b"glTF" + b"\0" * 16), ("model.py", b"import cadquery as cq\nresult = 1\n")):
                (d / name).write_bytes(payload)
            (d / "parts.json").write_text(json.dumps(FAKE_METRICS["parts"], ensure_ascii=False), encoding="utf-8")
            meta = {k: v for k, v in FAKE_METRICS.items() if k != "parts"} | {"summary": "参考水冷板", "model": "reference-script", "created_at": "2026-11-07T00:00:00+00:00", "source": "live"}
            (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
            half = Path(tmp) / "exv"; half.mkdir(); (half / "model.glb").write_bytes(b"glTF")   # incomplete → not advertised, not served
            self.assertEqual(app.cad_cached_ids(), ["coldplate"])
            resp = await app.cached_cad("coldplate", request)
            data = json.loads(resp.body)
            self.assertEqual(data["source"], "pre_generated")               # never the stored value
            self.assertEqual(data["job_id"], "cache-coldplate")
            self.assertEqual([p["name"] for p in data["parts"]], ["流道基板", "进出口接头"])
            self.assertEqual(data["files"]["glb"], "/api/cad/file/cache-coldplate/model.glb")
            self.assertEqual([m["label"] for m in data["metrics"]][:5], ["STEP 实体体积", "STEP 实体质量", "外形包络", "表面积", "实体 / 面数"])
            self.assertIn("流道数", [m["label"] for m in data["metrics"]])
            self.assertEqual(data["raw"]["step_bytes"], 106639)
            en = json.loads((await app.cached_cad("coldplate", request, lang="en")).body)
            self.assertEqual(en["metrics"][0]["label"], "STEP solid volume")
            served = await app.cad_file("cache-coldplate", "model.glb", request)
            self.assertEqual(served.media_type, "model/gltf-binary")
            for job_id, name in (("cache-exv", "model.glb"), ("cache-../coldplate", "model.glb"), ("cache-coldplate", "meta.json"), ("cache-coldplate", "../model.glb")):
                with self.assertRaises(app.HTTPException) as ctx:
                    await app.cad_file(job_id, name, request)
                self.assertEqual(ctx.exception.status_code, 404)
            with self.assertRaises(app.HTTPException) as ctx:
                await app.cached_cad("exv", request)
            self.assertEqual(ctx.exception.status_code, 404)
        with self.assertRaises(app.HTTPException) as ctx:
            await app.cached_cad("coldplate", SimpleNamespace(cookies={}))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_every_reference_script_passes_the_gate_and_has_a_fresh_cache(self):
        """cad_examples/<id>.py must be a scenario, pass the static gate, and cad_cache/<id>/ must be complete and newer than
        the script (pregen_cad.py rebuilds it). The OCCT run itself is the real-kernel smoke check, not this test."""
        import scenarios
        ids = {s["id"] for s in scenarios.SCENARIOS}
        scripts = sorted((Path(app.BASE) / "cad_examples").glob("*.py"))
        self.assertGreaterEqual(len(scripts), 7)
        for script in scripts:
            self.assertIn(script.stem, ids, script)
            self.assertIsNone(cad_runner.validate_code(script.read_text(encoding="utf-8")), script)
            cache = Path(app.BASE) / "cad_cache" / script.stem
            self.assertTrue(all((cache / n).is_file() for n in app.CAD_CACHE_FILES), f"run pregen_cad.py: {cache}")
            # Freshness by content, not mtime (OneDrive refreshes timestamps; Windows writes the copy with CRLF).
            built_from = (cache / "model.py").read_text(encoding="utf-8").replace("\r\n", "\n")
            self.assertEqual(built_from, script.read_text(encoding="utf-8").replace("\r\n", "\n"), f"stale cache: run pregen_cad.py {script.stem}")
            parts = json.loads((cache / "parts.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(parts), 2, script)
            self.assertTrue(all(p["id"] == f"part_{i}" for i, p in enumerate(parts, 1)), script)

    def test_prune_keeps_newest_jobs(self):
        import os, time
        with tempfile.TemporaryDirectory() as tmp, patch.object(app, "CAD_DIR", Path(tmp)):
            for i in range(5):
                d = Path(tmp) / f"job{i}"
                d.mkdir()
                ts = time.time() - (5 - i) * 100
                os.utime(d, (ts, ts))
            app.prune_cad_jobs(2)
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ["job3", "job4"])

    # ---- SOP six-pillar fix pass (2026-09-10): child result marker, kill-on-cancel, slot accounting

    def test_runner_only_trusts_marked_result_line(self):
        """A generated script printing its own {"ok": true} JSON must not be mistaken for the OCCT result."""
        fake_child = ("import sys, json\n"
                      "print(json.dumps({'ok': True, 'volume_mm3': 1, 'mass_kg': 1, 'bbox_mm': [1,1,1], 'area_mm2': 1, 'solids': 1, 'faces': 1, 'density_g_cm3': 1}))\n"
                      "sys.exit(1)\n")
        with tempfile.TemporaryDirectory() as tmp, patch.object(cad_runner, "_CHILD_TEMPLATE", fake_child):
            out = Path(tmp) / "a1"
            result = cad_runner.run_script(VALID_CODE, out, timeout=60)
            self.assertFalse(result["ok"])
        marked = ("import sys, json\n"
                  "open(sys.argv[1] + '/model.step', 'w').write('x'); open(sys.argv[1] + '/model.stl', 'w').write('y')\n"
                  "open(sys.argv[1] + '/model.glb', 'w').write('g'); open(sys.argv[1] + '/parts.json', 'w').write('[]')\n"
                  "print(json.dumps({'ok': True}))\n"  # unmarked decoy line from a 'script'
                  "print('__CADQUERY_RESULT__ ' + json.dumps({'ok': True, 'volume_mm3': 2.0}))\n")
        with tempfile.TemporaryDirectory() as tmp, patch.object(cad_runner, "_CHILD_TEMPLATE", marked):
            result = cad_runner.run_script(VALID_CODE, Path(tmp) / "a1", timeout=60)
            self.assertTrue(result["ok"])
            self.assertEqual(result["volume_mm3"], 2.0)
            self.assertEqual(result["step_bytes"], 1)

    def test_runner_kill_via_on_start_is_reported_as_cancelled(self):
        import threading, time
        sleeper = "import time\ntime.sleep(30)\n"
        handles = []
        with tempfile.TemporaryDirectory() as tmp, patch.object(cad_runner, "_CHILD_TEMPLATE", sleeper):
            def killer():
                while not handles:
                    time.sleep(0.02)
                cad_runner.kill(handles[0])
            threading.Thread(target=killer, daemon=True).start()
            result = cad_runner.run_script(VALID_CODE, Path(tmp) / "a1", timeout=60, on_start=handles.append)
        self.assertFalse(result["ok"])
        self.assertIn("取消", result["error"])
        self.assertLess(result["elapsed_s"], 20)


class CadSlotTests(unittest.IsolatedAsyncioTestCase):
    async def test_client_gone_mid_occt_kills_child_and_holds_slot_until_thread_returns(self):
        import asyncio, threading
        started = threading.Event(); released = threading.Event(); handles = []
        body = app.CadBody(scenario_id="coldplate", prompt="p", summary="s", html="", request_id=None)

        def slow_runner(code, out_dir, timeout, python=None, on_start=None):
            proc = SimpleNamespace(poll=lambda: None, kill=lambda: None)  # 'OCCT' keeps running until the test releases it
            on_start(proc); handles.append(proc)
            started.set()
            released.wait(5)
            return {"ok": False, "error": "killed"}

        model = AsyncMock(return_value=(RAW_OK, {"usage": {}, "actual_model": "m", "completion_id": "c"}))
        with tempfile.TemporaryDirectory() as tmp, patch.object(app, "CAD_DIR", Path(tmp)), patch.object(app, "CAD_AVAILABLE", True), \
                patch.object(app, "cad_model_call", model), patch.object(app.cad_runner, "run_script", slow_runner), \
                patch.object(app, "cad_slots", asyncio.Semaphore(1)), patch.object(app, "HEARTBEAT_S", 0.05):
            gen = app.run_cad(body)
            while True:  # advance until the server is heart-beating inside the OCCT phase (worker thread running)
                block = await gen.__anext__()
                if block.startswith("event: heartbeat") and '"phase": "occt"' in block:
                    break
            self.assertTrue(started.is_set())
            await gen.aclose()                       # client disconnected while OCCT runs
            self.assertTrue(getattr(handles[0], "_cad_killed", False))  # child was told to die
            self.assertTrue(app.cad_slots.locked())  # slot still held: the worker thread has not returned yet
            released.set()                           # the child exits → thread finishes
            for _ in range(200):                     # ...and only then is the slot returned
                if not app.cad_slots.locked():
                    break
                await asyncio.sleep(0.02)
            self.assertFalse(app.cad_slots.locked())


if __name__ == "__main__":
    unittest.main()
