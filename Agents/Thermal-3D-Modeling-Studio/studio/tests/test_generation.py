import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import app

HTTP_REQ = SimpleNamespace(url=SimpleNamespace(scheme="http"))     # login() reads the scheme to decide the Secure cookie flag
HTTPS_REQ = SimpleNamespace(url=SimpleNamespace(scheme="https"))


RAW = """<<<SUMMARY>>>
Concept only
<<<HTML>>>
<!DOCTYPE html><html><head></head><body>Model</body></html>
<<<METRICS>>>
[{"label":"width","value":"320","unit":"mm"}]
<<<SUGGESTIONS>>>
["Change width"]
<<<END>>>"""


class FakeStream:
    def __init__(self, raw=RAW, finish="stop", pieces=None):
        self.raw = raw
        self.finish = finish
        self.pieces = pieces if pieces is not None else [raw]
        self.closed = False

    async def __aiter__(self):
        for piece in self.pieces:
            yield SimpleNamespace(
                id="chatcmpl-test", model="gpt-6-astra-test-version", usage=None,
                choices=[SimpleNamespace(delta=SimpleNamespace(content=piece), finish_reason=None)],
            )
        yield SimpleNamespace(
            id="chatcmpl-test", model="gpt-6-astra-test-version", usage=None,
            choices=[SimpleNamespace(delta=SimpleNamespace(content=None), finish_reason=self.finish)],
        )

    async def close(self):
        self.closed = True


class GenerationTests(unittest.IsolatedAsyncioTestCase):
    async def generate(self, raw=RAW, finish="stop", pieces=None, messages=None, create=None):
        stream = FakeStream(raw, finish, pieces)
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create or AsyncMock(return_value=stream))),
            close=AsyncMock(),
        )
        body = app.GenerateBody(scenario_id="coldplate", messages=messages or [app.Message(role="user", content="320 mm")])
        with patch.object(app.tokens, "get", AsyncMock(return_value="not-a-real-token")), \
                patch.object(app, "AsyncOpenAI", return_value=client):
            blocks = [block async for block in app.run_generation(body)]
        events = [(block.split("\n")[0][7:], json.loads(block.split("\n")[1][6:])) for block in blocks]
        if create is None or create.return_value is stream:
            self.assertTrue(stream.closed)
        client.close.assert_awaited_once()
        return events, client

    async def test_live_provenance_and_model_version(self):
        events, client = await self.generate()
        start, result = events[0][1], events[-1][1]
        self.assertEqual(events[-1][0], "done")
        self.assertEqual(start["source"], "live")
        self.assertEqual(result["source"], "live")
        self.assertEqual(result["request_id"], start["request_id"])
        self.assertEqual(len(result["request_id"]), 32)
        self.assertEqual(result["actual_model"], "gpt-6-astra-test-version")
        self.assertEqual(result["completion_id"], "chatcmpl-test")
        self.assertTrue(result["created_at"].endswith("+00:00"))
        client.chat.completions.create.assert_awaited_once()
        other, _ = await self.generate()
        self.assertNotEqual(other[-1][1]["request_id"], result["request_id"])

    async def test_truncated_response_is_error_not_done(self):
        events, _ = await self.generate(finish="length")
        self.assertEqual(events[-1][0], "error")
        self.assertEqual(events[-1][1]["source"], "live")
        self.assertEqual(events[-1][1]["request_id"], events[0][1]["request_id"])
        self.assertFalse(any(event == "done" for event, _ in events))

    async def test_incomplete_html_is_not_success(self):
        events, _ = await self.generate(raw=RAW.replace("</html>", ""))
        self.assertEqual(events[-1][0], "error")
        self.assertFalse(app.parse_output(RAW.replace("<<<END>>>", ""))["ok"])

    async def test_cached_response_overrides_saved_live_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            saved = {"html": "<html></html>", "source": "live", "request_id": "old-live-request"}
            (path / "coldplate.json").write_text(json.dumps(saved), encoding="utf-8")
            request = SimpleNamespace(cookies={app.COOKIE: app.make_session("test-user")})
            with patch.object(app, "CACHE_DIR", path), patch.object(app.tokens, "get", AsyncMock()) as token:
                response = await app.cached_example("coldplate", request)
            result = json.loads(response.body)
            self.assertEqual(result["source"], "pre_generated")
            self.assertIsNone(result["request_id"])
            token.assert_not_awaited()

    async def test_early_html_event_when_sentinel_split_across_tokens(self):
        # Split the stream so "<<<METRICS>>>" straddles two deltas; the html event must still fire once,
        # before "done", and carry the same request id / normalised HTML as the final result.
        cut = RAW.index("<<<METRICS>>>") + 5
        pieces = [RAW[:cut], RAW[cut:cut + 3], RAW[cut + 3:]]
        events, _ = await self.generate(pieces=pieces)
        names = [event for event, _ in events]
        self.assertEqual(names.count("html"), 1)
        self.assertLess(names.index("html"), names.index("done"))
        html_ev = next(data for event, data in events if event == "html")
        done = events[-1][1]
        self.assertEqual(html_ev["request_id"], events[0][1]["request_id"])
        self.assertEqual(html_ev["source"], "live")
        self.assertEqual(html_ev["html"], done["html"])
        self.assertTrue(done["ok"])

    async def test_no_early_html_without_closing_tag(self):
        events, _ = await self.generate(raw=RAW.replace("</html>", ""))
        self.assertFalse(any(event == "html" for event, _ in events))

    async def test_prediction_not_sent_by_default_and_dropped_when_rejected(self):
        history = [
            app.Message(role="user", content="320 mm"),
            app.Message(role="assistant", content=RAW),
            app.Message(role="user", content="make it 400 mm"),
        ]
        events, client = await self.generate(messages=history)
        kwargs = client.chat.completions.create.await_args.kwargs
        self.assertNotIn("prediction", kwargs)
        self.assertFalse(events[-1][1]["predicted"])

        # With the flag on, an "unsupported_parameter" 400 must lead to one retry without `prediction`.
        stream = FakeStream()
        response = SimpleNamespace(status_code=400, headers={}, request=None)
        rejected = app.BadRequestError("Unsupported parameter: 'prediction' is not supported with this model.",
                                       response=response, body={"error": {"code": "unsupported_parameter"}})
        create = AsyncMock(side_effect=[rejected, stream])
        with patch.object(app, "AOAI_PREDICTED_OUTPUTS", True):
            events, client = await self.generate(messages=history, create=create)
        self.assertEqual(create.await_count, 2)
        self.assertIn("prediction", create.await_args_list[0].kwargs)
        self.assertNotIn("prediction", create.await_args_list[1].kwargs)
        self.assertEqual(events[-1][0], "done")
        self.assertFalse(events[-1][1]["predicted"])
        self.assertTrue(stream.closed)

    async def test_unexpected_exception_becomes_error_event(self):
        create = AsyncMock(side_effect=RuntimeError("upstream exploded"))
        events, _ = await self.generate(create=create)
        self.assertEqual(events[-1][0], "error")
        self.assertIn("RuntimeError", events[-1][1]["message"])
        self.assertEqual(events[-1][1]["request_id"], events[0][1]["request_id"])
        self.assertFalse(any(event == "done" for event, _ in events))

    def test_scenario_specific_system_prompt(self):
        import scenarios

        ids = [s["id"] for s in scenarios.SCENARIOS]
        self.assertEqual(len(ids), len(set(ids)))
        for required in ("thermal_sim", "aps"):
            self.assertIn(required, ids)
        for s in scenarios.SCENARIOS:
            self.assertEqual(len(s["chips"]), 3, s["id"])
            self.assertEqual(len(s["chips_en"]), 3, s["id"])
            for key in ("title", "title_en", "subtitle", "subtitle_en", "pain", "pain_en", "prompt", "prompt_en", "icon", "color"):
                self.assertTrue(s.get(key), f"{s['id']} missing {key}")
            # English strings really are English (no CJK), Chinese ones really are Chinese.
            for key in ("title_en", "subtitle_en", "pain_en", "prompt_en", *[f"chips_en[{i}]" for i in range(3)]):
                value = s["chips_en"][int(key[-2])] if key.startswith("chips_en") else s[key]
                self.assertFalse(any("\u4e00" <= ch <= "\u9fff" for ch in value), f"{s['id']}.{key} contains CJK")
            self.assertTrue(any("\u4e00" <= ch <= "\u9fff" for ch in s["prompt"]), s["id"])
            if s.get("metrics_labels_en"):
                self.assertEqual(len(s["metrics_labels_en"]), 6, s["id"])

        # Cards with an addendum get it appended to the system message; others get the plain prompt.
        base = scenarios.system_prompt_for(None)   # global prompt with the default (thermal) persona filled in
        plain = app.build_messages(app.GenerateBody(scenario_id="coldplate", messages=[app.Message(role="user", content="x")]))
        self.assertEqual(plain[0]["content"], base)
        none = app.build_messages(app.GenerateBody(messages=[app.Message(role="user", content="x")]))
        self.assertEqual(none[0]["content"], base)
        aps = app.build_messages(app.GenerateBody(scenario_id="aps", messages=[app.Message(role="user", content="x")]))
        self.assertTrue(aps[0]["content"].startswith(base))
        self.assertIn("【场景专项规范", aps[0]["content"])
        self.assertIn("EDD", aps[0]["content"])
        self.assertNotIn("EDD", plain[0]["content"])
        self.assertEqual(scenarios.system_prompt_for("does-not-exist"), base)

        # The browser never sees the system-side addenda.
        public = scenarios.public_scenarios()
        self.assertEqual([s["id"] for s in public], ids)
        self.assertFalse(any("system_extra" in s for s in public))
        self.assertFalse(any("metrics_labels_en" in s for s in public))
        self.assertTrue(all("prompt_en" in s and "chips_en" in s for s in public))
        self.assertTrue(any("system_extra" in s for s in scenarios.SCENARIOS))

        # Batch 3: system-level scenes get the generic system-scene rules (loops / modes / hotspots / stages) *and* their own addendum.
        for sid in ("vehicle_tms", "cdu"):
            self.assertIn(sid, ids)
            card = next(s for s in scenarios.SCENARIOS if s["id"] == sid)
            self.assertEqual(card.get("kind"), "system")
            prompt = scenarios.system_prompt_for(sid)
            self.assertIn("【系统级场景通用规范", prompt)
            for marker in ("window.__hotspots", "window.__stages", "window.__focus", "window.__setStage", "window.__notifyStage", "P.loops"):
                self.assertIn(marker, prompt, f"{sid} missing {marker}")
            self.assertIn("【场景专项规范 —— ", prompt)
            self.assertLess(prompt.index("【系统级场景通用规范"), prompt.index("【场景专项规范 —— "))
            en = scenarios.system_prompt_for(sid, "en")
            self.assertIn("7. System scenes", en)
            self.assertIn(card["metrics_labels_en"][0], en)
        self.assertIn("rvalve5", scenarios.system_prompt_for("cdu"))
        self.assertNotIn("【系统级场景通用规范", scenarios.system_prompt_for("coldplate"))
        self.assertNotIn("【系统级场景通用规范", scenarios.system_prompt_for("aps"))
        self.assertTrue(all(s.get("kind") == "system" for s in public if s["id"] in ("vehicle_tms", "cdu")))  # `kind` is public

    async def test_industry_groups_swap_persona_and_group_cards(self):
        import scenarios

        nb_ids = ["nb_thermal", "nb_chassis_mold", "nb_assembly_line", "nb_packing"]
        public = scenarios.public_scenarios()
        by_id = {s["id"]: s for s in public}
        for sid in nb_ids:
            self.assertEqual(by_id[sid]["industry"], "notebook", sid)
        self.assertTrue(all(by_id[s]["industry"] == "thermal" for s in ("coldplate", "vehicle_tms", "cdu", "aps")))
        groups = {g["id"]: g for g in scenarios.public_industries()}
        self.assertEqual([*groups], ["thermal", "notebook"])
        self.assertEqual((groups["thermal"]["count"], groups["notebook"]["count"]), (len(public) - 4, 4))
        self.assertFalse(any("persona" in g for g in groups.values()))            # persona is server-side only
        self.assertTrue(groups["notebook"]["label"] and groups["notebook"]["label_en"])
        self.assertFalse(any(k in groups["notebook"] for k in ("title", "hero", "hero_sub")))   # the studio keeps its own title / hero copy
        # Persona follows the card's group; the template token never leaks into a prompt.
        thermal = scenarios.system_prompt_for("coldplate")
        notebook = scenarios.system_prompt_for("nb_thermal")
        self.assertIn("制冷空调控制部件", thermal); self.assertNotIn("笔记本电脑", thermal)
        self.assertIn("笔记本电脑与消费电子制造商", notebook); self.assertNotIn("制冷空调控制部件", notebook)
        for sid in (None, "coldplate", "nb_packing", "nb_assembly_line", "does-not-exist"):
            self.assertNotIn(scenarios.PERSONA_TOKEN, scenarios.system_prompt_for(sid, "en"))
        # System-level notebook scenes reuse the loops / modes / hotspots / stages machinery; part-level ones don't.
        self.assertIn("【系统级场景通用规范", scenarios.system_prompt_for("nb_assembly_line"))
        self.assertIn("【系统级场景通用规范", scenarios.system_prompt_for("nb_thermal"))
        self.assertNotIn("【系统级场景通用规范", scenarios.system_prompt_for("nb_chassis_mold"))
        self.assertIn("锁模力", scenarios.system_prompt_for("nb_chassis_mold"))
        self.assertIn("Clamping-force estimate (t)", scenarios.system_prompt_for("nb_chassis_mold", "en"))
        self.assertNotIn("锁模力", scenarios.system_prompt_for("nb_packing"))
        # /api/industries is public (sign-in page needs the group title) and lists the default group.
        data = await app.industries()
        self.assertEqual(data["default"], "thermal")
        self.assertEqual([g["id"] for g in data["industries"]], ["thermal", "notebook"])
        self.assertEqual((await app.me(SimpleNamespace(cookies={app.COOKIE: app.make_session("u", "visitor")})))["mai_edits"], app.mai_enabled())

    def test_english_output_rules_follow_ui_language(self):
        import scenarios

        self.assertEqual(scenarios.normalize_lang(None), "zh")
        self.assertEqual(scenarios.normalize_lang("EN-us"), "en")
        self.assertEqual(scenarios.normalize_lang("fr"), "zh")

        # Default (zh) prompts are byte-identical to the pre-i18n prompts (persona filled in, nothing else changed).
        base = scenarios.SYSTEM_PROMPT.replace(scenarios.PERSONA_TOKEN, scenarios.INDUSTRIES["thermal"]["persona"])
        self.assertEqual(scenarios.system_prompt_for("coldplate"), base)
        self.assertEqual(scenarios.system_prompt_for("coldplate", "zh"), base)
        self.assertNotIn("English output required", scenarios.system_prompt_for("aps", "zh"))

        en = scenarios.system_prompt_for("coldplate", "en")
        self.assertTrue(en.startswith(base))
        self.assertTrue(en.endswith(scenarios.ENGLISH_OUTPUT_RULES))
        aps_en = scenarios.system_prompt_for("aps", "en")
        self.assertIn("【场景专项规范", aps_en)
        self.assertIn("Makespan AI/veteran (h)", aps_en)      # fixed-label scenarios get their English labels
        self.assertTrue(aps_en.endswith(scenarios.ENGLISH_OUTPUT_RULES))
        self.assertNotIn("Makespan", scenarios.system_prompt_for("coldplate", "en"))

        # /api/generate carries the UI language into the system message; default stays Chinese-only.
        body_en = app.GenerateBody(scenario_id="aps", lang="en", messages=[app.Message(role="user", content="x")])
        self.assertEqual(app.build_messages(body_en)[0]["content"], aps_en)
        body_zh = app.GenerateBody(scenario_id="aps", messages=[app.Message(role="user", content="x")])
        self.assertEqual(body_zh.lang, "zh")
        self.assertEqual(app.build_messages(body_zh)[0]["content"], scenarios.system_prompt_for("aps"))
        # Image-only turn: the fallback caption follows the language too.
        img_en = app.build_messages(app.GenerateBody(lang="en", messages=[app.Message(role="user", content="", image="data:image/png;base64,AA==")]))
        self.assertEqual(img_en[-1]["content"][0]["text"], "Model the part shown in this drawing/photo.")

        # Track B: English context, English repair instruction, English addendum; Chinese default unchanged.
        cad_en = app.cad_messages(app.CadBody(scenario_id="coldplate", prompt="plate", summary="s", lang="en"),
                                  [{"raw": "<<<SUMMARY>>>x<<<CAD>>>import cadquery as cq<<<END>>>", "error": "boom", "n": 1}])
        self.assertTrue(cad_en[0]["content"].startswith(app.CAD_PROMPT))
        self.assertIn("English output required", cad_en[0]["content"])
        self.assertIn("Part / scenario: EV Battery Cold Plate", cad_en[1]["content"])
        self.assertTrue(cad_en[-1]["content"].startswith("The server failed to run your script"))
        cad_zh = app.cad_messages(app.CadBody(scenario_id="coldplate", prompt="plate"), [])
        self.assertEqual(cad_zh[0]["content"], app.CAD_PROMPT)
        self.assertIn("零件/场景：电池水冷板", cad_zh[1]["content"])
        self.assertEqual(set(app.CAD_METRIC_LABELS["en"]), set(app.CAD_METRIC_LABELS["zh"]))

    async def test_english_cache_falls_back_to_chinese_and_is_flagged(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "coldplate.json").write_text(json.dumps({"html": "<html>zh</html>", "lang": "zh"}), encoding="utf-8")
            (path / "mchx.json").write_text(json.dumps({"html": "<html>zh</html>"}), encoding="utf-8")
            (path / "mchx.en.json").write_text(json.dumps({"html": "<html>en</html>", "source": "live", "request_id": "r"}), encoding="utf-8")
            request = SimpleNamespace(cookies={app.COOKIE: app.make_session("test-user")})
            with patch.object(app, "CACHE_DIR", path):
                self.assertEqual(app.cache_path("coldplate", "en").name, "coldplate.en.json")
                self.assertEqual(app.cache_path("Cold-Plate!", None).name, "cold-plate.json")
                fallback = json.loads((await app.cached_example("coldplate", request, lang="en")).body)
                self.assertEqual((fallback["lang"], fallback["lang_fallback"], fallback["source"]), ("zh", True, "pre_generated"))
                english = json.loads((await app.cached_example("mchx", request, lang="en")).body)
                self.assertEqual((english["lang"], english["lang_fallback"], english["html"]), ("en", False, "<html>en</html>"))
                self.assertEqual(english["source"], "pre_generated")
                self.assertIsNone(english["request_id"])
                chinese = json.loads((await app.cached_example("mchx", request)).body)
                self.assertEqual((chinese["lang"], chinese["lang_fallback"], chinese["html"]), ("zh", False, "<html>zh</html>"))
                with self.assertRaises(app.HTTPException):
                    await app.cached_example("nothing", request, lang="en")
                me = await app.me(request)
                self.assertEqual(me["cached"], ["coldplate", "mchx"])
                self.assertEqual(me["cached_en"], ["mchx"])

    async def test_token_error_is_reported_with_request_id(self):
        body = app.GenerateBody(messages=[app.Message(role="user", content="Model a plate")])
        with patch.object(app.tokens, "get", AsyncMock(side_effect=app.ClientAuthenticationError("test failure"))):
            blocks = [block async for block in app.run_generation(body)]
        self.assertTrue(blocks[0].startswith("event: start"))
        self.assertTrue(blocks[-1].startswith("event: error"))
        data = json.loads(blocks[-1].split("\n")[1][6:])
        self.assertEqual(data["source"], "live")
        self.assertIn("request_id", data)

    # ---- SOP six-pillar fix pass (2026-09-10): heartbeat, back-pressure, validation, atomic writes, credentials

    async def test_heartbeat_events_while_model_is_silent(self):
        class SlowStream(FakeStream):
            async def __aiter__(self):
                await asyncio.sleep(0.12)  # a decoding pause longer than the test heartbeat interval
                async for chunk in super().__aiter__():
                    yield chunk

        stream = SlowStream()

        async def slow_create(**_):
            await asyncio.sleep(0.12)  # Azure sends the headers with the first chunk: TTFT is spent inside create()
            return stream

        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(side_effect=slow_create))), close=AsyncMock())
        body = app.GenerateBody(messages=[app.Message(role="user", content="320 mm")])
        with patch.object(app, "HEARTBEAT_S", 0.03), patch.object(app.tokens, "get", AsyncMock(return_value="tok")), \
                patch.object(app, "AsyncOpenAI", return_value=client):
            blocks = [block async for block in app.run_generation(body)]
        names = [block.split("\n")[0][7:] for block in blocks]
        self.assertGreaterEqual(names.count("heartbeat"), 4)  # both silent phases (create() and first chunk) were covered
        self.assertEqual(names[-1], "done")
        self.assertLess(names.index("heartbeat"), names.index("delta"))  # heartbeats came during the silence, before tokens
        self.assertTrue(stream.closed)

    async def test_with_heartbeat_propagates_errors_and_stops_pump(self):
        async def failing():
            yield 1
            raise RuntimeError("upstream exploded")

        seen = []
        with self.assertRaises(RuntimeError):
            async for kind, item in app.with_heartbeat(failing(), interval=5):
                seen.append((kind, item))
        self.assertEqual(seen, [("item", 1)])

    async def test_back_pressure_rejects_when_all_slots_busy(self):
        body = app.GenerateBody(messages=[app.Message(role="user", content="320 mm")], lang="en")
        with patch.object(app, "gen_slots", asyncio.Semaphore(0)), patch.object(app, "MAX_CONCURRENT_GENERATIONS", 0):
            blocks = [block async for block in app.run_generation(body)]
        self.assertEqual(blocks[-1].split("\n")[0][7:], "error")
        self.assertIn("Server busy", json.loads(blocks[-1].split("\n")[1][6:])["message"])
        # and a free slot is released again after a normal run
        events, _ = await self.generate()
        self.assertEqual(events[-1][0], "done")
        self.assertFalse(app.gen_slots.locked())

    def test_backend_input_validation(self):
        app.Message(role="user", content="ok", image="data:image/png;base64,iVBORw0KGgo=")
        with self.assertRaises(ValueError):
            app.Message(role="user", content="ok", image="data:text/html;base64,PGh0bWw+")
        with self.assertRaises(ValueError):
            app.Message(role="user", content="ok", image="https://example.com/a.png")
        with self.assertRaises(ValueError):
            app.Message(role="user", content="x" * (app.MAX_PROMPT_CHARS + 1))
        app.Message(role="assistant", content="x" * (app.MAX_PROMPT_CHARS + 1))  # previous raw model output may be long
        with self.assertRaises(ValueError):
            app.GenerateBody(scenario_id="../etc", messages=[app.Message(role="user", content="ok")])
        with self.assertRaises(ValueError):  # the last turn is sent as the user prompt whatever role the client declares
            app.GenerateBody(messages=[app.Message(role="assistant", content="x" * (app.MAX_PROMPT_CHARS + 1))])
        with self.assertRaises(ValueError):
            app.CadBody(html="<html>" * 100_000)

    async def test_login_accepts_non_ascii_input_without_500(self):
        response = SimpleNamespace(set_cookie=lambda *a, **k: None)
        with patch.object(app, "PORTAL_PASSWORD", "pw-under-test"):
            with self.assertRaises(app.HTTPException) as ctx:  # a CJK username must be a clean 401, not a TypeError → 500
                await app.login(app.LoginBody(username="工坊用户", password="密码"), response, HTTP_REQ)
            self.assertEqual(ctx.exception.status_code, 401)
        with patch.object(app, "PORTAL_PASSWORD", "密码2026"), patch.object(app, "PORTAL_USERNAME", "工坊"):
            self.assertTrue((await app.login(app.LoginBody(username="工坊", password="密码2026"), response, HTTP_REQ))["ok"])

    def test_atomic_write_leaves_no_temp_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x.json"
            app.atomic_write_text(path, '{"a": 1}')
            app.atomic_write_text(path, '{"a": 2}')
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"a": 2})
            self.assertEqual([p.name for p in Path(directory).iterdir()], ["x.json"])

    async def test_login_disabled_without_configured_password(self):
        response = SimpleNamespace(set_cookie=lambda *a, **k: None)
        with patch.object(app, "PORTAL_PASSWORD", None):
            with self.assertRaises(app.HTTPException) as ctx:
                await app.login(app.LoginBody(username="studio", password="anything"), response, HTTP_REQ)
        self.assertEqual(ctx.exception.status_code, 503)
        with patch.object(app, "PORTAL_PASSWORD", "pw-under-test"):
            self.assertEqual((await app.login(app.LoginBody(username="studio", password="pw-under-test"), response, HTTP_REQ))["ok"], True)
            with self.assertRaises(app.HTTPException) as ctx:
                await app.login(app.LoginBody(username="studio", password="wrong"), response, HTTP_REQ)
        self.assertEqual(ctx.exception.status_code, 401)

    async def test_https_front_secure_cookie_and_redirect(self):
        cookies = {}
        response = SimpleNamespace(set_cookie=lambda name, value, **k: cookies.update({name: k}))
        with patch.object(app, "PORTAL_PASSWORD", "pw-under-test"):
            await app.login(app.LoginBody(username="studio", password="pw-under-test"), response, HTTPS_REQ)
            self.assertTrue(cookies[app.COOKIE]["secure"]); self.assertTrue(cookies[app.COOKIE]["httponly"])
            await app.login(app.LoginBody(username="studio", password="pw-under-test"), response, HTTP_REQ)
            self.assertFalse(cookies[app.COOKIE]["secure"])   # plain dev server keeps working

        def req(scheme, host, path="/", query=""):
            return SimpleNamespace(url=SimpleNamespace(scheme=scheme, path=path, query=query), headers={"host": host})
        with patch.object(app, "PUBLIC_BASE_URL", ""):
            self.assertIsNone(app.https_redirect_for(req("http", "vm.example.com:3005")))          # feature off
        with patch.object(app, "PUBLIC_BASE_URL", "https://studio.example.com"):
            r = app.https_redirect_for(req("http", "vm.example.com:3005", "/api/me", "lang=en"))
            self.assertEqual((r.status_code, r.headers["location"]), (308, "https://studio.example.com/api/me?lang=en"))
            self.assertIsNone(app.https_redirect_for(req("https", "studio.example.com")))         # already through the proxy
            self.assertIsNone(app.https_redirect_for(req("http", "127.0.0.1:3005")))              # loopback (deploy checks, pregen)
            self.assertIsNone(app.https_redirect_for(req("http", "localhost:8011")))
            self.assertIsNone(app.https_redirect_for(req("http", "vm.example.com:3005", "/healthz")))

    # ---- reasoning effort chosen in the UI (2026-09-10)

    async def test_reasoning_effort_from_ui_wins_over_server_default_and_is_recorded(self):
        stream = FakeStream()
        create = AsyncMock(return_value=stream)
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)), close=AsyncMock())
        body = app.GenerateBody(messages=[app.Message(role="user", content="320 mm")], reasoning_effort="high")
        with patch.object(app, "AOAI_REASONING_EFFORT", "none"), patch.object(app.tokens, "get", AsyncMock(return_value="tok")), \
                patch.object(app, "AsyncOpenAI", return_value=client):
            blocks = [block async for block in app.run_generation(body)]
        events = [(b.split("\n")[0][7:], json.loads(b.split("\n")[1][6:])) for b in blocks]
        self.assertEqual(create.await_args.kwargs["reasoning_effort"], "high")
        self.assertEqual(events[0][1]["reasoning_effort"], "high")       # start event announces what will be sent
        self.assertEqual(events[-1][1]["reasoning_effort"], "high")      # done event records what was sent
        self.assertIn("reasoning_tokens", events[-1][1])

    async def test_reasoning_effort_defaults_to_server_setting_and_off_sends_nothing(self):
        for server_default, expected in (("low", "low"), ("off", None), ("default", None), ("", None), ("MEDIUM", "medium")):
            stream = FakeStream()
            create = AsyncMock(return_value=stream)
            client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)), close=AsyncMock())
            body = app.GenerateBody(messages=[app.Message(role="user", content="320 mm")])  # no UI choice
            with patch.object(app, "AOAI_REASONING_EFFORT", server_default), patch.object(app.tokens, "get", AsyncMock(return_value="tok")), \
                    patch.object(app, "AsyncOpenAI", return_value=client):
                blocks = [block async for block in app.run_generation(body)]
            done = json.loads(blocks[-1].split("\n")[1][6:])
            self.assertEqual(create.await_args.kwargs.get("reasoning_effort"), expected, server_default)
            self.assertEqual(done["reasoning_effort"], expected, server_default)

    def test_reasoning_effort_values_are_validated(self):
        for bad in ("minimal", "ultra", "None ", "xhigh; drop"):
            with self.assertRaises(ValueError, msg=bad):
                app.GenerateBody(messages=[app.Message(role="user", content="x")], reasoning_effort=bad)
            with self.assertRaises(ValueError, msg=bad):
                app.CadBody(reasoning_effort=bad)
        for good in app.REASONING_EFFORTS:
            app.GenerateBody(messages=[app.Message(role="user", content="x")], reasoning_effort=good)
            app.CadBody(reasoning_effort=good)
        self.assertEqual(app.effective_effort("xhigh"), "xhigh")
        with patch.object(app, "AOAI_REASONING_EFFORT", "none"):          # gpt-6-astra does not support 'none': sent as 'low'
            self.assertEqual(app.effective_effort(None), "low")
            self.assertEqual(app.effective_effort(""), "low")

    async def test_default_efforts_are_the_ones_gpt6_astra_accepts(self):
        request = SimpleNamespace(cookies={app.COOKIE: app.make_session("test-user")})
        self.assertEqual(app.supported_efforts, ("low", "medium", "high", "xhigh"))
        me = await app.me(request)
        self.assertEqual(me["reasoning_efforts"], ["low", "medium", "high", "xhigh"])
        self.assertEqual(app.effective_effort("none"), "low")             # no 400 round trip first

    async def test_me_lists_the_selectable_efforts(self):
        request = SimpleNamespace(cookies={app.COOKIE: app.make_session("test-user")})
        with patch.object(app, "supported_efforts", app.REASONING_EFFORTS):
            me = await app.me(request)
        self.assertEqual(me["reasoning_efforts"], ["none", "low", "medium", "high", "xhigh"])
        self.assertIn("reasoning_effort", me)

    # ---- an effort the deployment refuses (2026-11-14: gpt-6-astra-2026-09-03 answers 'none' with this 400)

    REFUSED_NONE = ("Error code: 400 - {'error': {'message': \"Unsupported value: 'reasoning_effort' does not support 'none' with this "
                    "model. Supported values are: 'low', 'medium', 'high', and 'xhigh'.\", 'type': 'invalid_request_error', "
                    "'param': 'reasoning_effort', 'code': 'unsupported_value'}}")

    @staticmethod
    def refused(message=REFUSED_NONE):
        response = SimpleNamespace(status_code=400, headers={}, request=None)
        return app.BadRequestError(message, response=response, body={"error": {"code": "unsupported_value", "param": "reasoning_effort"}})

    def test_nearest_supported_effort(self):
        with patch.object(app, "supported_efforts", ("low", "medium", "high", "xhigh")):
            self.assertEqual([app.nearest_effort(e) for e in app.REASONING_EFFORTS], ["low", "low", "medium", "high", "xhigh"])
            with patch.object(app, "AOAI_REASONING_EFFORT", "none"):
                self.assertEqual(app.effective_effort(None), "low")
            with patch.object(app, "AOAI_REASONING_EFFORT", "off"):
                self.assertIsNone(app.effective_effort(None))
        with patch.object(app, "supported_efforts", ("none", "low")):
            self.assertEqual(app.nearest_effort("xhigh"), "low")

    async def test_refused_effort_moves_to_the_nearest_supported_one_and_is_remembered(self):
        request = SimpleNamespace(cookies={app.COOKIE: app.make_session("test-user")})
        with patch.object(app, "supported_efforts", app.REASONING_EFFORTS), patch.object(app, "AOAI_REASONING_EFFORT", "none"):
            create = AsyncMock(side_effect=[self.refused(), FakeStream()])
            events, _ = await self.generate(create=create)
            self.assertEqual([c.kwargs.get("reasoning_effort") for c in create.await_args_list], ["none", "low"])
            self.assertEqual(events[-1][0], "done")
            self.assertEqual(events[-1][1]["reasoning_effort"], "low")        # what was actually sent
            names = [event for event, _ in events]
            self.assertEqual(events[0][1]["reasoning_effort"], "none")        # announced before the deployment answered
            self.assertEqual(events[names.index("html")][1]["reasoning_effort"], "low")  # the early render shows the applied value
            self.assertEqual(app.supported_efforts, ("low", "medium", "high", "xhigh"))
            create = AsyncMock(return_value=FakeStream())                     # later requests: no second 400
            events, _ = await self.generate(create=create)
            self.assertEqual(create.await_count, 1)
            self.assertEqual(create.await_args.kwargs["reasoning_effort"], "low")
            self.assertEqual(events[0][1]["reasoning_effort"], "low")
            me = await app.me(request)
            self.assertEqual((me["reasoning_efforts"], me["reasoning_effort"]), (["low", "medium", "high", "xhigh"], "low"))

    async def test_refused_effort_without_a_list_is_dropped(self):
        with patch.object(app, "supported_efforts", app.REASONING_EFFORTS), patch.object(app, "AOAI_REASONING_EFFORT", "none"):
            create = AsyncMock(side_effect=[self.refused("Error code: 400 - 'reasoning_effort' is not supported with this model."),
                                            FakeStream()])
            events, _ = await self.generate(create=create)
            self.assertNotIn("reasoning_effort", create.await_args_list[1].kwargs)
            self.assertIsNone(events[-1][1]["reasoning_effort"])              # the deployment's own default
            self.assertEqual(app.supported_efforts, app.REASONING_EFFORTS)

    async def test_connection_test_step_and_narrative_follow_the_refusal(self):
        answer = SimpleNamespace(model="gpt-6-astra-2026-09-03", id="chatcmpl-x", usage=None,
                                 choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content='{"executive_summary": "ok"}'))])
        request = SimpleNamespace(cookies={app.COOKIE: app.make_session("u")}, headers={})
        for call in ("connection", "step", "narrative"):
            create = AsyncMock(side_effect=[self.refused(), answer])
            client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)), close=AsyncMock())
            with patch.object(app, "supported_efforts", app.REASONING_EFFORTS), patch.object(app, "AOAI_REASONING_EFFORT", "none"), \
                    patch.object(app.tokens, "get", AsyncMock(return_value="tok")), patch.object(app, "AsyncOpenAI", return_value=client):
                if call == "connection":
                    result = await app.connection_test(request)
                    self.assertTrue(result["ok"], result)
                elif call == "step":
                    _, meta = await app.cad_model_call([{"role": "user", "content": "x"}], app.effective_effort("none"))
                    self.assertEqual(meta["reasoning_effort"], "low")
                else:
                    body = app.ProposalBody(title="t", requirement="r", summary="s", reasoning_effort="none")
                    narrative, _ = await app.write_narrative(body, app.host_connection())
                    self.assertEqual(narrative, {"executive_summary": "ok"})
            self.assertEqual([c.kwargs.get("reasoning_effort") for c in create.await_args_list], ["none", "low"], call)

    def test_precompressed_vendor_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            static = Path(directory); vendor = static / "vendor" / "three"; vendor.mkdir(parents=True)
            (vendor / "three.module.js").write_text("export const x = 1;", encoding="utf-8")
            (vendor / "three.module.js.gz").write_bytes(b"\x1f\x8b fake")
            (vendor / "plain.js").write_text("// no gz twin", encoding="utf-8")
            req = lambda path, enc="gzip, deflate, br", method="GET": SimpleNamespace(method=method, url=SimpleNamespace(path=path), headers={"accept-encoding": enc})
            with patch.object(app, "STATIC", static), patch.object(app, "VENDOR_DIR", (static / "vendor").resolve()):
                self.assertEqual(app.precompressed_vendor(req("/static/vendor/three/three.module.js")), vendor / "three.module.js.gz")
                self.assertIsNone(app.precompressed_vendor(req("/static/vendor/three/three.module.js", enc="identity")))  # browser refuses gzip
                self.assertIsNone(app.precompressed_vendor(req("/static/vendor/three/plain.js")))                       # no .gz twin → StaticFiles
                self.assertIsNone(app.precompressed_vendor(req("/static/vendor/three/three.module.js", method="HEAD")))
                self.assertIsNone(app.precompressed_vendor(req("/static/app.js")))                                        # only vendor assets
                self.assertIsNone(app.precompressed_vendor(req("/static/vendor/../../app.py")))                           # traversal guard


class BringYourOwnKeyTests(unittest.IsolatedAsyncioTestCase):
    """Visitors may supply their own Azure OpenAI connection in headers; it is used per request and never persisted."""

    @staticmethod
    def request(**headers):
        return SimpleNamespace(headers={k.lower(): v for k, v in headers.items()}, cookies={})

    def test_header_parsing_and_validation(self):
        host = app.connection_from_request(self.request())
        self.assertEqual((host.source, host.key), ("host", None))
        # Host-managed mode deliberately ignores any browser credential, including stale localStorage headers.
        ignored = app.connection_from_request(self.request(**{"X-AOAI-Endpoint": "https://acme-res.openai.azure.com/", "X-AOAI-Key": "k" * 32}))
        self.assertEqual((ignored.source, ignored.key, ignored.endpoint), ("host", None, app.AOAI_ENDPOINT))
        with patch.object(app, "HOST_CONNECTION_FOR_ALL", False):
            own = app.connection_from_request(self.request(**{"X-AOAI-Endpoint": "https://acme-res.openai.azure.com/", "X-AOAI-Key": "k" * 32, "X-AOAI-Deployment": "gpt-6-astra"}))
            self.assertEqual((own.source, own.endpoint, own.deployment, own.host), ("visitor", "https://acme-res.openai.azure.com", "gpt-6-astra", "acme-res.openai.azure.com"))
            self.assertEqual(own.key, "k" * 32)
            # deployment defaults to the host's when omitted
            self.assertEqual(app.connection_from_request(self.request(**{"X-AOAI-Endpoint": "https://a.services.ai.azure.com", "X-AOAI-Key": "k" * 32})).deployment, app.AOAI_DEPLOYMENT)
            bad = [
                {"X-AOAI-Endpoint": "http://acme.openai.azure.com", "X-AOAI-Key": "k" * 32},             # not https
                {"X-AOAI-Endpoint": "https://evil.example.com", "X-AOAI-Key": "k" * 32},                 # not an Azure OpenAI host (SSRF guard)
                {"X-AOAI-Endpoint": "https://acme.openai.azure.com/openai/v1", "X-AOAI-Key": "k" * 32},  # path not allowed
                {"X-AOAI-Endpoint": "https://acme.openai.azure.com", "X-AOAI-Key": "short"},
                {"X-AOAI-Endpoint": "https://acme.openai.azure.com", "X-AOAI-Key": "k" * 32, "X-AOAI-Deployment": "bad name!"},
                {"X-AOAI-Key": "k" * 32},                                                                 # key without endpoint
            ]
            for headers in bad:
                with self.assertRaises(app.HTTPException, msg=str(headers)) as ctx:
                    app.connection_from_request(self.request(**headers))
                self.assertEqual(ctx.exception.status_code, 400, str(headers))
            with patch.object(app, "REQUIRE_BYOK", True):
                with self.assertRaises(app.HTTPException) as ctx:
                    app.connection_from_request(self.request())
                self.assertEqual(ctx.exception.status_code, 403)
                self.assertEqual(app.connection_from_request(self.request(**{"X-AOAI-Endpoint": "https://acme.openai.azure.com", "X-AOAI-Key": "k" * 32})).source, "visitor")

    async def test_visitor_key_is_used_for_the_call_and_reported_but_never_cached(self):
        stream = FakeStream()
        created = {}
        def fake_client(**kw): created.update(kw); return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=stream))), close=AsyncMock())
        conn = app.ModelConnection("https://acme.openai.azure.com", "my-gpt6", "visitor-secret-key-0123456789", "visitor")
        body = app.GenerateBody(scenario_id="coldplate", save_as_cache=True, messages=[app.Message(role="user", content="320 mm")])
        token_get = AsyncMock(return_value="host-token")
        with tempfile.TemporaryDirectory() as directory, patch.object(app, "CACHE_DIR", Path(directory)), \
                patch.object(app.tokens, "get", token_get), patch.object(app, "AsyncOpenAI", side_effect=fake_client):
            blocks = [b async for b in app.run_generation(body, conn)]
            saved = list(Path(directory).iterdir())
        events = [(b.split("\n")[0][7:], json.loads(b.split("\n")[1][6:])) for b in blocks]
        self.assertEqual(created["api_key"], "visitor-secret-key-0123456789")
        self.assertEqual(created["base_url"], "https://acme.openai.azure.com/openai/v1")
        token_get.assert_not_awaited()                                   # host Entra token is not touched
        self.assertEqual(events[0][1]["key_source"], "visitor")
        self.assertEqual(events[0][1]["endpoint_host"], "acme.openai.azure.com")
        self.assertEqual(events[0][1]["model"], "my-gpt6")
        done = events[-1][1]
        self.assertEqual((done["key_source"], done["model"], done["endpoint_host"]), ("visitor", "my-gpt6", "acme.openai.azure.com"))
        self.assertNotIn("visitor-secret-key", json.dumps(done))          # key never echoed
        self.assertEqual(saved, [])                                       # visitor output never becomes a saved example

    async def test_host_connection_uses_entra_token(self):
        stream = FakeStream()
        created = {}
        def fake_client(**kw): created.update(kw); return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=stream))), close=AsyncMock())
        body = app.GenerateBody(messages=[app.Message(role="user", content="320 mm")])
        with patch.object(app.tokens, "get", AsyncMock(return_value="host-token")), patch.object(app, "AsyncOpenAI", side_effect=fake_client), \
                patch.object(app, "AOAI_ENDPOINT", "https://host-res.openai.azure.com"):
            blocks = [b async for b in app.run_generation(body)]
        self.assertEqual(created["api_key"], "host-token")
        self.assertEqual(created["base_url"], "https://host-res.openai.azure.com/openai/v1")
        done = json.loads(blocks[-1].split("\n")[1][6:])
        self.assertEqual((done["key_source"], done["endpoint_host"]), ("host", "host-res.openai.azure.com"))

    async def test_connection_test_endpoint_reports_without_leaking_the_key(self):
        request = SimpleNamespace(cookies={app.COOKIE: app.make_session("u")}, headers={"x-aoai-endpoint": "https://acme.openai.azure.com", "x-aoai-key": "visitor-secret-key-0123456789"})
        ok_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=SimpleNamespace(model="gpt-6-astra-2026-09-03")))), close=AsyncMock())
        with patch.object(app, "HOST_CONNECTION_FOR_ALL", False), patch.object(app, "AsyncOpenAI", return_value=ok_client):
            r = await app.connection_test(request)
        self.assertTrue(r["ok"]); self.assertEqual(r["actual_model"], "gpt-6-astra-2026-09-03"); self.assertEqual(r["endpoint_host"], "acme.openai.azure.com")
        bad_client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(side_effect=RuntimeError("401 Unauthorized: Access denied due to invalid subscription key")))), close=AsyncMock())
        with patch.object(app, "HOST_CONNECTION_FOR_ALL", False), patch.object(app, "AsyncOpenAI", return_value=bad_client):
            r = await app.connection_test(request)
        self.assertFalse(r["ok"]); self.assertIn("401", r["error"]); self.assertNotIn("visitor-secret-key", json.dumps(r))
        with patch.object(app.tokens, "get", AsyncMock(return_value="host-token")), patch.object(app, "AsyncOpenAI", return_value=ok_client):
            r = await app.connection_test(SimpleNamespace(cookies={app.COOKIE: app.make_session("u")}, headers={}))
        self.assertTrue(r["ok"])
        self.assertEqual(r["endpoint_host"], app.AOAI_ENDPOINT.split("//", 1)[-1])

    async def test_owner_account_is_exempt_from_require_byok_and_uses_host_connection(self):
        response = SimpleNamespace(cookies={}, set_cookie=lambda name, value, **k: response.cookies.__setitem__(name, value))
        with patch.object(app, "PORTAL_OWNER_USERNAME", "owner"), patch.object(app, "PORTAL_OWNER_PASSWORD", "owner-pw"), \
                patch.object(app, "PORTAL_USERNAME", "guest"), patch.object(app, "PORTAL_PASSWORD", "guest-pw"), \
                patch.object(app, "HOST_CONNECTION_FOR_ALL", False), patch.object(app, "REQUIRE_BYOK", True):
            self.assertEqual((await app.login(app.LoginBody(username="owner", password="owner-pw"), response, HTTP_REQ))["role"], "owner")
            owner_cookie = response.cookies[app.COOKIE]
            self.assertEqual((await app.login(app.LoginBody(username="guest", password="guest-pw"), response, HTTP_REQ))["role"], "visitor")
            guest_cookie = response.cookies[app.COOKIE]
            with self.assertRaises(app.HTTPException):
                await app.login(app.LoginBody(username="owner", password="guest-pw"), response, HTTP_REQ)   # no cross-matching
            self.assertEqual(app.read_session(owner_cookie), ("owner", "owner"))
            self.assertEqual(app.read_session(guest_cookie), ("guest", "visitor"))
            self.assertIsNone(app.read_session("u|admin|9999999999|deadbeef"))                # unknown role / bad signature
            owner_req = SimpleNamespace(cookies={app.COOKIE: owner_cookie}, headers={})
            guest_req = SimpleNamespace(cookies={app.COOKIE: guest_cookie}, headers={})
            self.assertEqual(app.connection_from_request(owner_req).source, "host")          # owner: host connection, no key needed
            with self.assertRaises(app.HTTPException) as ctx:
                app.connection_from_request(guest_req)                                         # visitor: must bring a key
            self.assertEqual(ctx.exception.status_code, 403)
            self.assertFalse((await app.me(owner_req))["byok_required"])
            self.assertTrue((await app.me(guest_req))["byok_required"])
            self.assertEqual((await app.me(owner_req))["role"], "owner")
            # Owner sessions live 30 days (presenter signs in once per browser); visitors keep the 12 h cookie.
            owner_exp, guest_exp = int(owner_cookie.split("|")[2]), int(guest_cookie.split("|")[2])
            self.assertGreater(owner_exp - guest_exp, 29 * 86400)
            self.assertEqual((app.session_ttl_for("owner"), app.session_ttl_for("visitor")), (app.OWNER_SESSION_TTL, app.SESSION_TTL))

    async def test_host_connection_for_all_gives_visitors_zero_input_access(self):
        request = SimpleNamespace(
            cookies={app.COOKIE: app.make_session("guest", app.ROLE_VISITOR)},
            headers={"x-aoai-endpoint": "https://stale.openai.azure.com", "x-aoai-key": "stale-browser-key-0123456789"},
        )
        with patch.object(app, "HOST_CONNECTION_FOR_ALL", True), patch.object(app, "REQUIRE_BYOK", True), \
                patch.object(app, "AOAI_ENDPOINT", "https://host-res.openai.azure.com"), \
                patch.object(app, "AOAI_DEPLOYMENT", "gpt-6-astra"), patch.object(app, "AOAI_API_KEY", "server-secret-key"):
            conn = app.connection_from_request(request)
            info = await app.me(request)
        self.assertEqual((conn.source, conn.endpoint, conn.deployment, conn.key), ("host", "https://host-res.openai.azure.com", "gpt-6-astra", None))
        self.assertFalse(info["byok_required"])
        self.assertTrue(info["host_connection_for_all"])
        self.assertEqual((info["endpoint"], info["host_auth"]), ("https://host-res.openai.azure.com", "api_key"))
        self.assertNotIn("server-secret-key", json.dumps(info))
        self.assertNotIn("stale-browser-key", json.dumps(info))

    async def test_host_connection_prefers_env_api_key_when_configured(self):
        created = {}
        def fake_client(**kw): created.update(kw); return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=FakeStream()))), close=AsyncMock())
        token_get = AsyncMock(return_value="host-token")
        body = app.GenerateBody(messages=[app.Message(role="user", content="320 mm")])
        with patch.object(app, "AOAI_API_KEY", "env-key-0123456789abcdef"), patch.object(app.tokens, "get", token_get), patch.object(app, "AsyncOpenAI", side_effect=fake_client):
            blocks = [b async for b in app.run_generation(body)]
        self.assertEqual(created["api_key"], "env-key-0123456789abcdef")
        token_get.assert_not_awaited()
        self.assertEqual(json.loads(blocks[-1].split("\n")[1][6:])["key_source"], "host")


class RenderTests(unittest.IsolatedAsyncioTestCase):
    PNG = "data:image/png;base64," + __import__("base64").b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 200).decode()

    def test_body_validation_and_prompt(self):
        body = app.RenderBody(image=self.PNG, summary="Aluminium cold plate, 6 serpentine channels", style="exhibition", instruction="white background", lang="en")
        p = app.render_prompt(body)
        for needle in ("Keep the object's geometry", "Trade-show display", "aluminium: brushed", "Aluminium cold plate", "highest priority): white background", "no text anywhere"):
            self.assertIn(needle, p)
        self.assertLessEqual(len(p), 3900)
        self.assertIn("材质按摘要中的材料还原", app.render_prompt(app.RenderBody(image=self.PNG)))
        for bad in ({"image": "data:image/jpeg;base64,AAAA"}, {"image": self.PNG, "style": "anime"}, {"image": self.PNG, "size": "2048x2048"}, {"image": self.PNG, "quality": "ultra"}, {"image": self.PNG, "base": "url"}):
            with self.assertRaises(ValueError, msg=str(bad)):
                app.RenderBody(**bad)
        # Whitelist follows the Foundry image how-to for GPT-Image-2.5 (edges ×16, ≤3:1) and was live-verified on the deployment
        for size in app.RENDER_SIZES:
            w, h = (int(v) for v in size.split("x"))
            self.assertEqual((w % 16, h % 16), (0, 0), size); self.assertLessEqual(max(w, h) / min(w, h), 3, size)
            self.assertEqual(app.RenderBody(image=self.PNG, size=size).size, size)
            self.assertEqual(app.ConceptBody(prompt="a valve", size=size).size, size)
        for q in app.RENDER_QUALITIES:
            self.assertEqual((app.RenderBody(image=self.PNG, quality=q).quality, app.ConceptBody(prompt="a valve", quality=q).quality), (q, q))
        self.assertIn("xhigh", app.RENDER_QUALITIES); self.assertIn("max", app.RENDER_QUALITIES); self.assertIn("2048x1152", app.RENDER_SIZES)

    async def test_render_stream_uses_image_edit_with_snapshot_and_reports_provenance(self):
        edit = AsyncMock(return_value=SimpleNamespace(data=[SimpleNamespace(b64_json="QUJD", revised_prompt=None)], usage=SimpleNamespace(model_dump=lambda: {"total_tokens": 739, "input_tokens": 300, "output_tokens": 439})))
        client = SimpleNamespace(images=SimpleNamespace(edit=edit), close=AsyncMock())
        conn = app.ModelConnection("https://acme.openai.azure.com", "gpt-6-astra", "visitor-secret-key-0123456789", "visitor")
        body = app.RenderBody(image=self.PNG, style="studio", instruction="brushed finish", size="1536x1024", quality="high", base="previous")
        with patch.object(app, "AOAI_IMAGE_DEPLOYMENT", "gpt-image-2.5-sunburst"), patch.object(app, "AsyncOpenAI", return_value=client):
            blocks = [b async for b in app.run_render(body, conn)]
        events = [(b.split("\n")[0][7:], json.loads(b.split("\n")[1][6:])) for b in blocks]
        self.assertEqual(events[0][0], "start"); self.assertEqual(events[0][1]["model"], "gpt-image-2.5-sunburst"); self.assertEqual(events[0][1]["key_source"], "visitor")
        done = events[-1][1]; self.assertEqual(events[-1][0], "done")
        self.assertEqual(done["image"], "data:image/png;base64,QUJD")
        self.assertEqual((done["style"], done["base"], done["size"], done["quality"], done["usage"]["total_tokens"]), ("studio", "previous", "1536x1024", "high", 739))
        kw = edit.await_args.kwargs
        self.assertEqual(kw["model"], "gpt-image-2.5-sunburst"); self.assertEqual(kw["image"][0], "snapshot.png"); self.assertTrue(kw["image"][1].startswith(b"\x89PNG"))
        self.assertEqual((kw["size"], kw["quality"], kw["n"], kw["output_format"]), ("1536x1024", "high", 1, "png"))
        self.assertNotIn("input_fidelity", kw)   # rejected by gpt-image-2.5 (probed 2026-09-11)
        self.assertIn("brushed finish", kw["prompt"])
        self.assertNotIn("visitor-secret-key", json.dumps(done))
        client.close.assert_awaited_once()

    async def test_pre_generated_render_is_served_like_a_live_result(self):
        """render_cache/<id>/ (made by pregen_render.py) comes back in the shape of the live `done` event, provenance pinned."""
        request = SimpleNamespace(cookies={app.COOKIE: app.make_session("test-user")})
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
        meta = {"render_id": "abc123def456", "style": "studio", "base": "snapshot", "instruction": "", "size": "1536x1024", "quality": "high",
                "model": "gpt-image-2.5-sunburst", "latency_s": 61.2, "created_at": "2026-11-09T10:00:00+00:00", "source": "live",
                "usage": {"total_tokens": 2130}, "endpoint_host": "internal.example"}
        with tempfile.TemporaryDirectory() as tmp, patch.object(app, "RENDER_CACHE_DIR", Path(tmp)):
            d = Path(tmp) / "coldplate"; d.mkdir()
            (d / "render.png").write_bytes(png); (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
            half = Path(tmp) / "exv"; half.mkdir(); (half / "render.png").write_bytes(png)   # no meta.json → not advertised, not served
            self.assertEqual(app.render_cached_ids(), ["coldplate"])
            data = json.loads((await app.cached_render("coldplate", request)).body)
            self.assertEqual(data["source"], "pre_generated")               # never the stored value
            self.assertEqual(data["image"], "data:image/png;base64," + __import__("base64").b64encode(png).decode())
            self.assertEqual((data["style"], data["base"], data["size"], data["quality"], data["usage"]["total_tokens"]), ("studio", "snapshot", "1536x1024", "high", 2130))
            self.assertNotIn("endpoint_host", data)
            self.assertIsNone(data["cad_overlay"])                           # no fitted STEP lines yet
            (d / "cad_lines.png").write_bytes(png)
            (d / "cad_overlay.json").write_text(json.dumps({"fit": "uniform", "scale": 3.155, "iou_pct": 89.8}), encoding="utf-8")
            ov = json.loads((await app.cached_render("coldplate", request)).body)["cad_overlay"]
            self.assertEqual((ov["fit"], ov["iou_pct"]), ("uniform", 89.8))
            self.assertEqual(ov["lines"], "data:image/png;base64," + __import__("base64").b64encode(png).decode())
            self.assertIsNone(json.loads((await app.cached_render("coldplate", request)).body)["engineering"])   # no STEP-direct render yet
            (d / "engineering.png").write_bytes(png); (d / "engineering_lines.png").write_bytes(png)
            (d / "engineering.json").write_text(json.dumps({"size": [2048, 1152], "image_model": None}), encoding="utf-8")
            eng = json.loads((await app.cached_render("coldplate", request)).body)["engineering"]
            self.assertEqual((eng["size"], eng["image_model"]), ([2048, 1152], None))
            self.assertEqual(eng["image"], "data:image/png;base64," + __import__("base64").b64encode(png).decode())
            self.assertEqual(eng["lines"], eng["image"])
            with self.assertRaises(app.HTTPException) as ctx:
                await app.cached_render("exv", request)
            self.assertEqual(ctx.exception.status_code, 404)
        with self.assertRaises(app.HTTPException) as ctx:
            await app.cached_render("coldplate", SimpleNamespace(cookies={}))
        self.assertEqual(ctx.exception.status_code, 401)

    async def test_render_without_deployment_or_with_bad_png_is_an_error_event(self):
        with patch.object(app, "AOAI_IMAGE_DEPLOYMENT", ""):
            blocks = [b async for b in app.run_render(app.RenderBody(image=self.PNG))]
        self.assertTrue(blocks[-1].startswith("event: error")); self.assertIn("AOAI_IMAGE_DEPLOYMENT", blocks[-1])
        not_png = "data:image/png;base64," + __import__("base64").b64encode(b"GIF89a" + b"\x00" * 200).decode()
        with patch.object(app, "AOAI_IMAGE_DEPLOYMENT", "img"), patch.object(app.tokens, "get", AsyncMock(return_value="tok")):
            blocks = [b async for b in app.run_render(app.RenderBody(image=not_png))]
        self.assertTrue(blocks[-1].startswith("event: error")); self.assertIn("PNG", blocks[-1])


class ConceptTests(unittest.IsolatedAsyncioTestCase):
    PNG = "data:image/png;base64," + __import__("base64").b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 200).decode()

    def test_body_and_prompt(self):
        gen = app.ConceptBody(prompt="800 V integrated thermal module", provider="mai", web_grounding=True)
        self.assertIn("Subject: 800 V integrated thermal module", app.concept_prompt(gen)); self.assertIn("no text", app.concept_prompt(gen))
        edit = app.ConceptBody(prompt="ports facing left", image=self.PNG)
        self.assertIn("Instruction: ports facing left", app.concept_prompt(edit)); self.assertIn("keep everything else", app.concept_prompt(edit))
        for bad in ({"prompt": "x"}, {"prompt": "ok", "provider": "dalle"}, {"prompt": "ok", "image": "data:image/jpeg;base64,AAAA"}):
            with self.assertRaises(ValueError, msg=str(bad)):
                app.ConceptBody(**bad)

    async def test_gpt_image_generate_then_edit(self):
        gen = AsyncMock(return_value=SimpleNamespace(data=[SimpleNamespace(b64_json="R0VO", revised_prompt="rp")], usage=SimpleNamespace(model_dump=lambda: {"total_tokens": 500})))
        edit = AsyncMock(return_value=SimpleNamespace(data=[SimpleNamespace(b64_json="RURJVA==", revised_prompt=None)], usage=None))
        client = SimpleNamespace(images=SimpleNamespace(generate=gen, edit=edit), close=AsyncMock())
        with patch.object(app, "AOAI_IMAGE_DEPLOYMENT", "gpt-image-2.5-sunburst"), patch.object(app, "AsyncOpenAI", return_value=client), patch.object(app.tokens, "get", AsyncMock(return_value="tok")):
            b1 = [b async for b in app.run_concept(app.ConceptBody(prompt="a cold plate concept", size="1536x1024"))]
            b2 = [b async for b in app.run_concept(app.ConceptBody(prompt="make it copper", image=self.PNG))]
        d1 = json.loads(b1[-1].split("\n")[1][6:]); d2 = json.loads(b2[-1].split("\n")[1][6:])
        self.assertEqual((d1["image"], d1["edit"], d1["provider"], d1["model"], d1["usage"]["total_tokens"]), ("data:image/png;base64,R0VO", False, "gpt-image", "gpt-image-2.5-sunburst", 500))
        self.assertEqual(gen.await_args.kwargs["size"], "1536x1024"); self.assertNotIn("image", gen.await_args.kwargs)
        self.assertEqual((d2["image"], d2["edit"]), ("data:image/png;base64,RURJVA==", True)); self.assertTrue(edit.await_args.kwargs["image"][1].startswith(b"\x89PNG"))
        self.assertIn("make it copper", edit.await_args.kwargs["prompt"])

    async def test_mai_provider_posts_web_grounding_and_is_hidden_when_unconfigured(self):
        with patch.object(app, "MAI_ENDPOINT", ""), patch.object(app, "MAI_API_KEY", None):
            blocks = [b async for b in app.run_concept(app.ConceptBody(prompt="x y", provider="mai", web_grounding=True))]
            self.assertFalse(app.mai_enabled())
        self.assertTrue(blocks[-1].startswith("event: error")); self.assertIn("MAI_ENDPOINT", blocks[-1])
        captured = {}
        async def fake_mai(prompt, size, web_grounding, image_png=None):
            captured.update(prompt=prompt, size=size, web_grounding=web_grounding, image_png=image_png); return "TUFJ", {"num_output_tokens": 1000}, None
        with patch.object(app, "MAI_ENDPOINT", "https://mai.services.ai.azure.com"), patch.object(app, "MAI_API_KEY", "k"), patch.object(app, "mai_generate", fake_mai):
            blocks = [b async for b in app.run_concept(app.ConceptBody(prompt="integrated module", provider="mai", web_grounding=True))]
            me = await app.me(SimpleNamespace(cookies={app.COOKIE: app.make_session("u")}))
        d = json.loads(blocks[-1].split("\n")[1][6:])
        self.assertEqual((d["provider"], d["web_grounding"], d["image"], d["model"]), ("mai", True, "data:image/png;base64,TUFJ", app.MAI_MODEL))
        self.assertTrue(captured["web_grounding"]); self.assertIn("integrated module", captured["prompt"]); self.assertIsNone(captured["image_png"])
        self.assertIn("mai", me["concept_providers"]); self.assertTrue(me["mai_edits"])
        # MAI-Image-2.6 also edits (multipart): the previous concept is passed through as PNG bytes.
        with patch.object(app, "MAI_ENDPOINT", "https://mai.services.ai.azure.com"), patch.object(app, "MAI_API_KEY", None), patch.object(app, "mai_generate", fake_mai):
            self.assertTrue(app.mai_enabled())   # endpoint alone is enough: auth falls back to the host Entra token
            blocks = [b async for b in app.run_concept(app.ConceptBody(prompt="tweak", provider="mai", image=self.PNG))]
        d = json.loads(blocks[-1].split("\n")[1][6:])
        self.assertTrue(d["edit"]); self.assertTrue(captured["image_png"].startswith(b"\x89PNG"))

    async def test_mai_dims_headers_and_usage_normalisation(self):
        # Documented MAI limits: edges ≥ 768, width × height ≤ 1,048,576 — every UI size maps inside them with 16-px alignment.
        for size in app.RENDER_SIZES:
            w, h = app.mai_dims(size)
            self.assertLessEqual(w * h, app.MAI_MAX_PIXELS, size); self.assertGreaterEqual(min(w, h), app.MAI_MIN_EDGE, size)
            self.assertEqual((w % 16, h % 16), (0, 0), size)
            sw, sh = (int(v) for v in size.split("x"))
            self.assertAlmostEqual(w / h, sw / sh, delta=0.12, msg=size)
        self.assertEqual(app.mai_dims("1024x1024"), (1024, 1024))
        with patch.object(app, "MAI_API_KEY", "secret-key"):
            self.assertEqual(await app.mai_headers(), {"api-key": "secret-key"})
        with patch.object(app, "MAI_API_KEY", None), patch.object(app.tokens, "get", AsyncMock(return_value="tok")):
            self.assertEqual(await app.mai_headers(), {"Authorization": "Bearer tok"})

        class FakeResp:
            def __init__(self, payload): self.status, self._payload = 200, payload
            async def text(self): return json.dumps(self._payload)
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False

        class FakeSession:
            calls = []
            def __init__(self, *a, **k): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return False
            def post(self, url, **kw):
                FakeSession.calls.append((url, kw))
                return FakeResp({"data": [{"b64_json": "QUJD"}], "usage": {"num_output_tokens": 1024, "num_input_text_tokens": 34, "num_input_image_tokens": 0}})
        with patch.object(app, "MAI_ENDPOINT", "https://mai.services.ai.azure.com"), patch.object(app, "MAI_API_KEY", "k"), patch.object(app.aiohttp, "ClientSession", FakeSession):
            b64, usage, _ = await app.mai_generate("draw", "1792x1024", True)
            _, usage_edit, _ = await app.mai_generate("edit", "1024x1024", False, b"\x89PNGfake")
        self.assertEqual(b64, "QUJD")
        self.assertEqual((usage["input_tokens"], usage["output_tokens"], usage["total_tokens"]), (34, 1024, 1058))
        gen_url, gen_kw = FakeSession.calls[0]; edit_url, edit_kw = FakeSession.calls[1]
        self.assertTrue(gen_url.endswith("/mai/v1/images/generations")); self.assertEqual(gen_kw["json"]["web_grounding"], True)
        self.assertEqual((gen_kw["json"]["width"], gen_kw["json"]["height"]), app.mai_dims("1792x1024"))
        self.assertTrue(edit_url.endswith("/mai/v1/images/edits")); self.assertIn("data", edit_kw); self.assertNotIn("json", edit_kw)
        self.assertEqual(usage_edit["total_tokens"], 1058)


if __name__ == "__main__":
    unittest.main()
