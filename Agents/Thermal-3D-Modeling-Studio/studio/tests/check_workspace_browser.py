import argparse
import hashlib
import json
import os
import struct
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


# Software WebGL (SwiftShader) gets slower the longer one page runs: opening a scenario's engineering view measured
# 15-59 s late in the run (diag_ao_ab2.py, AO on and off alike) versus about 1 s on a GPU. The waits for the
# engineering view check that it opens, not how fast the software renderer is.
WORKSPACE_TIMEOUT_MS = 180000


def verify(base_url, cdp_url, output, headless=False):
    if urlparse(base_url).hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("This check is restricted to the isolated localhost preview")
    output.mkdir(parents=True, exist_ok=True)
    result = {"timestamp": datetime.now(timezone.utc).isoformat(), "url": base_url, "browser": "edge-headless-swiftshader" if headless else f"edge-cdp {cdp_url}",
              "executionPlane": "LOCAL_WINDOWS", "checks": [], "pageErrors": [], "modelCalls": [], "files": {}}
    project = Path(__file__).resolve().parents[1]
    with sync_playwright() as playwright:
        if headless:
            browser = playwright.chromium.launch(channel="msedge", headless=True, args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            context = browser.new_context()
        else:
            browser = playwright.chromium.connect_over_cdp(cdp_url, timeout=20000)
            context = browser.contexts[0]
        page = context.new_page()
        # Collect the workspace's reported ambient-occlusion state (workspace-state messages from the viewer iframe).
        page.add_init_script("window.__aoReports = []; addEventListener('message', e => { const d = e.data || {}; "
                             "if (d.type === 'workspace-state' && d.ao) window.__aoReports.push({ ao: d.ao, mode: d.aoMode, coverage: d.aoCoverage || null, "
                             "parts: (d.parts || []).map(p => p.name) }); });")
        page.set_viewport_size({"width": 1600, "height": 1000})
        page.on("pageerror", lambda error: result["pageErrors"].append(str(error)))
        page.on("request", lambda request: result["modelCalls"].append(request.url)
                if request.method == "POST" and urlparse(request.url).path in
                {"/api/generate", "/api/cad", "/api/render", "/api/concept", "/api/proposal"} else None)

        def record(name, details=True):
            result["checks"].append({"name": name, "result": "PASS", "details": details})
            print(f"PASS {name}", flush=True)

        def wait_frame():
            page.frame_locator("#viewer").locator("body").evaluate(
                "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")

        def snapshot_hash():
            wait_frame()
            encoded = page.frame_locator("#viewer").locator("body").evaluate(
                "() => window.__renderer.domElement.toDataURL('image/png')")
            return hashlib.sha256(encoded.encode()).hexdigest()

        def source_state():
            return page.frame_locator("#viewer").locator("body").evaluate("""() => {
              const objects = [];
              window.__model.traverse(object => objects.push({ id: object.uuid, visible: object.visible,
                geometry: object.geometry?.uuid, material: Array.isArray(object.material) ? object.material.map(material => material.uuid) : object.material?.uuid,
                position: object.position.toArray(), scale: object.scale.toArray() }));
              return objects;
            }""")

        try:
            for relative in ["static/index.html", "static/app.js", "static/styles.css", "static/viewer-bridge.js",
                             "static/viewer-workspace.mjs", "static/viewer-workspace.css", "static/icons/lucide.min.js",
                             "static/studio-kit.js", "static/studio-env.mjs", "static/brep-viewer.html",
                             "static/vendor/three/jsm/geometries/RoundedBoxGeometry.js", "static/vendor/three/jsm/loaders/GLTFLoader.js",
                             "static/vendor/three/jsm/postprocessing/GTAOPass.js"]:
                response = context.request.get(f"{base_url}/{relative}" if relative != "static/index.html" else base_url)
                assert response.ok, (relative, response.status)
                expected = hashlib.sha256((project / relative).read_bytes()).hexdigest()
                assert hashlib.sha256(response.body()).hexdigest() == expected, relative
                result["files"][relative] = expected
            record("served_bytes_match_source")
            response = context.request.post(f"{base_url}/api/login", data={
                "username": os.getenv("STUDIO_TEST_USER", "preview"),
                "password": os.getenv("STUDIO_TEST_PASSWORD", "local-ui-test-only"),
            })
            assert response.ok, response.status
            page.goto(f"{base_url}/?lang=zh", wait_until="domcontentloaded")
            page.locator("#viewportBody.engineering").wait_for(timeout=WORKSPACE_TIMEOUT_MS)
            assert "本次未调用" in page.locator("#sourceLabel").inner_text()
            # The first scenario (coldplate) ships a pre-generated STEP solid: it arrives after the concept scene and takes
            # over the main viewport, labelled as pre-generated everywhere (badge, CAD tab, outliner names from parts.json).
            page.wait_for_function('document.querySelector("#viewStatus").textContent.includes("B-rep")', timeout=WORKSPACE_TIMEOUT_MS)
            cached_cad = page.evaluate("""() => ({ badge: document.querySelector('#stageBadge').textContent, cadBadge: document.querySelector('#cadBadge').textContent,
              parts: [...document.querySelectorAll('#partList button')].map(b => b.textContent), cadRows: document.querySelectorAll('#cadMetrics tbody tr').length,
              runInfo: document.querySelector('#cadRunInfo').textContent, glbHref: document.querySelector('#cadDlStep').getAttribute('href'),
              brepPressed: document.querySelector('[data-geometry=brep]').getAttribute('aria-pressed') })""")
            assert "预生成" in cached_cad["badge"] and "预生成" in cached_cad["cadBadge"] and "未调用 GPT-6" in cached_cad["runInfo"], cached_cad
            assert cached_cad["parts"] == ["流道基板", "上盖板", "进口接头", "出口接头"] and cached_cad["cadRows"] >= 5, cached_cad
            assert cached_cad["glbHref"] == "/api/cad/file/cache-coldplate/model.step" and cached_cad["brepPressed"] == "true", cached_cad
            assert page.locator(".msg.assistant.error").count() == 0, page.locator(".msg.assistant.error").all_inner_texts()
            record("pre_generated_cad_opens_with_the_scenario", cached_cad)
            # The B-rep opens in the workspace's perspective view with ambient occlusion. "on" alone is not enough (a skipped
            # G-buffer once left AO "on" but white): the first AO frame must darken a real share of the part's pixels.
            # Only the B-rep workspace's reports count (its outliner holds 流道基板); the concept scene before it reports too.
            page.wait_for_function("() => window.__aoReports.some(r => r.ao !== 'pending' && r.parts.includes('流道基板'))", timeout=60000)
            ao_report = page.evaluate("() => window.__aoReports.filter(r => r.ao !== 'pending' && r.parts.includes('流道基板')).pop()")
            assert ao_report["ao"] == "on" and ao_report["coverage"] and ao_report["coverage"]["occluded"] > 0.01, ao_report
            record("brep_perspective_ambient_occlusion_darkens_the_part", ao_report)
            # The remaining legacy checks exercise the concept mesh (GPT-6's three.js scene + studio-kit retrofit): switch back.
            page.evaluate("() => document.querySelector('[data-geometry=\"concept\"]').click()")
            page.wait_for_function('document.querySelector("[data-geometry=concept]").getAttribute("aria-pressed") === "true" && !document.querySelector("#viewStatus").textContent.includes("B-rep") && document.querySelector("#viewportBody").classList.contains("engineering")', timeout=WORKSPACE_TIMEOUT_MS)
            original_state = source_state()
            record("authenticated_cached_model")
            look = page.frame_locator("#viewer").locator("body").evaluate("""() => ({
              studioKit: window.__studioKit, toneMapping: window.__renderer.toneMapping, shadows: window.__renderer.shadowMap.enabled,
              background: window.__scene.background && (window.__scene.background.isColor ? '#' + window.__scene.background.getHexString() : window.__scene.background.isTexture ? 'gradient-texture' : String(window.__scene.background)),
              rig: !!window.__scene.getObjectByName('studio-light-rig'), bench: !!window.__scene.getObjectByName('studio-workbench'),
              presets: [...new Set((() => { const a = []; window.__model.traverse(o => { if (o.isMesh) (Array.isArray(o.material) ? o.material : [o.material]).forEach(m => a.push(m.userData.studioKit || m.type)); }); return a; })())],
            })""")
            assert look["studioKit"] and look["studioKit"].endswith("+retrofit"), look
            assert look["toneMapping"] == 6 and look["shadows"] and look["rig"] and look["bench"], look   # 6 = AgXToneMapping (Blender 4.x view transform)
            assert look["background"] == "gradient-texture", look
            assert all(p in ("aluminum", "aluminumCast", "anodized", "copper", "brass", "steel", "steelDark", "powderCoat", "polymer", "polymerLight", "rubber", "coolant", "refrigerant", "glass") for p in look["presets"]), look
            record("legacy_example_retrofitted_with_studio_kit", look)
            page.locator('[data-workspace-layout="quad"]').click(force=True)
            page.locator("#viewGrid").uncheck(force=True)
            wait_frame()
            def pixel_regions():
                return page.frame_locator("#viewer").locator("body").evaluate("""() => {
              const source = window.__renderer.domElement;
              const canvas = document.createElement('canvas'); canvas.width = 240; canvas.height = 160;
              const context = canvas.getContext('2d'); context.drawImage(source, 0, 0, 240, 160);
              const pixels = context.getImageData(0, 0, 240, 160).data;
              return [...document.querySelectorAll('.studio-viewport:not([hidden])')].sort((first, second) => first.offsetTop - second.offsetTop || first.offsetLeft - second.offsetLeft).map((element, index) => {
                const left = index % 2 * 120, top = Math.floor(index / 2) * 80;
                let content = 0, samples = 0;
                for (let vertical = top + 3; vertical < top + 77; vertical++) for (let horizontal = left + 3; horizontal < left + 117; horizontal++) {
                  const offset = (vertical * 240 + horizontal) * 4;
                  if (Math.max(Math.abs(pixels[offset] - 65), Math.abs(pixels[offset + 1] - 69), Math.abs(pixels[offset + 2] - 73)) > 24) content++;
                  samples++;
                }
                return { view: element.dataset.view, contentPixels: content, sampledPixels: samples };
              });
                }""")
            regions = pixel_regions()
            assert len(regions) == 4 and all(region["contentPixels"] > 10 for region in regions), regions
            record("four_nonblank_model_views_without_grid", regions)
            material_hash = snapshot_hash()
            page.get_by_role("checkbox", name="显示: 上盖板", exact=True).check(force=True)
            assert snapshot_hash() != material_hash
            assert source_state() == original_state
            page.get_by_role("checkbox", name="显示: 上盖板", exact=True).uncheck(force=True)
            record("hidden_lid_can_be_shown_without_mutating_source")
            page.locator('[data-workspace-shading="solid"]').click(force=True)
            solid_hash = snapshot_hash()
            page.locator('[data-workspace-shading="wireframe"]').click(force=True)
            wire_hash = snapshot_hash()
            assert len({material_hash, solid_hash, wire_hash}) == 3
            page.locator('[data-workspace-shading="material"]').click(force=True)
            record("shading_changes_rendered_pixels")
            before_section = snapshot_hash()
            page.locator("#viewSection").select_option("x", force=True)
            assert snapshot_hash() != before_section
            page.locator("#viewSection").select_option("none", force=True)
            record("section_changes_rendered_geometry")
            page.locator("#partList button").filter(has_text="入口快插套筒").click(force=True)
            # selection round-trips through the iframe (workspace-state) before the isolate action becomes enabled
            page.wait_for_function('!document.getElementById("viewIsolate").disabled')
            page.locator("#viewIsolate").click(force=True)
            page.wait_for_function('document.querySelectorAll("#partList input:checked").length === 1')
            page.locator("#viewShowAll").click(force=True)
            assert source_state() == original_state
            record("part_isolation_and_restore")
            perspective = page.frame_locator("#viewer").locator('[data-view="perspective"]')
            area = perspective.bounding_box()
            before_drag = snapshot_hash()
            page.mouse.move(area["x"] + area["width"] * .5, area["y"] + area["height"] * .5)
            page.mouse.down()
            page.mouse.move(area["x"] + area["width"] * .65, area["y"] + area["height"] * .6, steps=10)
            page.mouse.up()
            assert snapshot_hash() != before_drag
            page.locator("#viewFit").click(force=True)
            record("perspective_drag_changes_view")
            page.locator("#viewGrid").check(force=True)
            with page.expect_download() as download:
                page.locator("#btnPng").click(force=True)
            png_path = output / "workspace-export.png"
            download.value.save_as(png_path)
            image = png_path.read_bytes()
            assert image.startswith(b"\x89PNG\r\n\x1a\n")
            dimensions = struct.unpack(">II", image[16:24])
            assert dimensions[0] > 500 and dimensions[1] > 300, dimensions
            record("png_export_from_active_workspace", {"width": dimensions[0], "height": dimensions[1]})
            with page.expect_download(timeout=60000) as download:
                page.locator("#btnGlb").click(force=True)
            glb_path = output / "model-export.glb"
            download.value.save_as(glb_path)
            model_bytes = glb_path.read_bytes()
            assert model_bytes[:4] == b"glTF" and struct.unpack("<I", model_bytes[8:12])[0] == len(model_bytes)
            record("original_model_glb_export", {"bytes": len(model_bytes)})
            page.screenshot(path=str(output / "desktop-quad.png"), scale="css")
            page.locator('[data-workspace-layout="original"]').click(force=True)
            page.frame_locator("#viewer").locator("#studio-workspace").wait_for(state="hidden")
            assert source_state() == original_state
            assert page.frame_locator("#viewer").locator("body").evaluate("() => window.__controls.enabled")
            record("original_scene_and_controls_restored")
            page.locator(".scenario").filter(has_text="电子膨胀阀").click(force=True)
            page.locator("#viewportBody.engineering").wait_for(timeout=WORKSPACE_TIMEOUT_MS)
            page.locator('[data-workspace-layout="quad"]').click(force=True)
            wait_frame()
            page.screenshot(path=str(output / "valve-quad.png"), scale="css")
            record("second_real_model")
            page.locator('.topbar [data-lang="en"]').click(force=True)
            page.wait_for_function('document.querySelector("[data-workspace-layout=quad]").textContent.includes("Quad view")')
            # exv ships a pre-generated solid too: after the English example reloads, the English B-rep status must show.
            page.wait_for_function('document.querySelector("#viewStatus").textContent === "OCCT B-rep solid · Engineering view"', timeout=WORKSPACE_TIMEOUT_MS)
            assert "Pre-generated" in page.locator("#stageBadge").inner_text() and "pre-generated" in page.locator("#cadBadge").inner_text()
            record("english_workspace_controls")
            page.set_viewport_size({"width": 390, "height": 844})
            page.reload(wait_until="domcontentloaded")
            page.locator("#viewportBody.engineering").wait_for(timeout=WORKSPACE_TIMEOUT_MS)
            # (coldplate reloads in English and brings its pre-generated solid; wait for that so the quad view is measured on a settled stage)
            page.wait_for_function('document.querySelector("#viewStatus").textContent.includes("B-rep")', timeout=WORKSPACE_TIMEOUT_MS)
            page.locator('[data-workspace-layout="quad"]').click(force=True)
            page.locator("#viewGrid").uncheck(force=True)
            wait_frame()
            mobile_regions = pixel_regions()
            assert len(mobile_regions) == 4 and all(region["contentPixels"] > 10 for region in mobile_regions), mobile_regions
            page.locator("#viewGrid").check(force=True)
            assert page.locator("#partInspector").is_hidden()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
            page.evaluate("window.scrollTo({ top: 0, behavior: 'instant' })")
            page.screenshot(path=str(output / "mobile-quad.png"), scale="css")
            record("mobile_quad_without_horizontal_overflow", {"width": 390, "height": 844, "pixelRegions": mobile_regions})
            page.locator("#newChat").click(force=True)
            assert page.locator('[data-workspace-layout="quad"]').is_disabled()
            assert page.locator("#partInspector").is_hidden()
            assert page.locator("#viewStatus").inner_text() == ""
            record("new_conversation_clears_workspace")
            # A scene written the way the updated system prompt instructs (imports studio-kit itself) must render through
            # the same srcdoc + bridge path a live GPT-6 result takes, report studioLook=native and expose kit presets.
            page.set_viewport_size({"width": 1600, "height": 1000})
            fixture = (project / "tests" / "fixtures" / "kit_native_scene.html").read_text(encoding="utf-8")
            native = page.evaluate("""(html) => new Promise((resolve, reject) => {
              const frame = document.getElementById('viewer');
              const renderId = String(Date.now());
              const bridge = `<script src="${location.origin}/static/viewer-bridge.js?rev=24" data-render-id="${renderId}"></script>`;
              const timer = setTimeout(() => reject(new Error('fixture render timeout')), 60000);
              addEventListener('message', function onMessage(ev) {
                if (ev.source !== frame.contentWindow || ev.data?.renderId !== renderId) return;
                if (ev.data.type === 'render-ready' || ev.data.type === 'render-error') { clearTimeout(timer); removeEventListener('message', onMessage); resolve(ev.data); }
              });
              frame.srcdoc = html.replace(/(\"|')\\/static\\//g, `$1${location.origin}/static/`).replace(/<head([^>]*)>/i, `<head$1><base href="${location.origin}/">${bridge}`);
            })""", fixture)
            assert native["type"] == "render-ready" and native.get("studioLook") == "native" and native.get("canInspect"), native
            presets = page.frame_locator("#viewer").locator("body").evaluate("() => { const a = new Set(); window.__model.traverse(o => { if (o.isMesh) a.add(o.material.userData.studioKit || o.material.type); }); return [...a]; }")
            assert set(presets) >= {"copper", "powderCoat", "steel", "copperWire"}, presets
            wait_frame()
            page.frame_locator("#viewer").locator("canvas").screenshot(path=str(output / "kit-native-fixture.png"))
            record("kit_native_scene_renders_through_bridge", {"meshes": native.get("meshes"), "presets": presets})
            assert not result["modelCalls"], result["modelCalls"]
            assert not result["pageErrors"], result["pageErrors"]
            page.set_viewport_size({"width": 1600, "height": 1000})
            page.locator('.topbar [data-lang="zh"]').click(force=True)
            page.locator(".scenario").filter(has_text="电池水冷板").first.click(force=True)
            # Software WebGL, 20+ minutes into the run: re-opening the cold plate (concept scene, then its filleted B-rep,
            # 34 k triangles) measured 15–59 s to the engineering view in diag_ao_ab2.py, AO on or blocked alike; a real
            # GPU takes about 1 s. 120 s keeps the check about correctness, not about the speed of the software renderer.
            page.locator("#viewportBody.engineering").wait_for(timeout=WORKSPACE_TIMEOUT_MS)
            # coldplate auto-loads its pre-generated solid; the live-job path below must start from the concept mesh and
            # then *replace* that cached result (badge flips from pre-generated to live).
            page.wait_for_function('document.querySelector("#viewStatus").textContent.includes("B-rep")', timeout=WORKSPACE_TIMEOUT_MS)
            page.evaluate("() => document.querySelector('[data-geometry=\"concept\"]').click()")
            page.wait_for_function('document.querySelector("[data-geometry=concept]").getAttribute("aria-pressed") === "true" && !document.querySelector("#viewStatus").textContent.includes("B-rep")', timeout=WORKSPACE_TIMEOUT_MS)

            # ---- 轨 B result as the main viewport. /api/cad is replayed from the committed OCCT output of
            # cad_examples/coldplate.py (no model call, no kernel run); the glb/parts.json bytes come from the
            # real authenticated file endpoint through a job directory created for this run.
            fixture_dir = project / "tests" / "fixtures" / "cad_reference_coldplate"
            job_id = "c0ffee0b4e9f"
            job_dir = project / "cad_out" / job_id
            job_dir.mkdir(parents=True, exist_ok=True)
            for name in ("model.glb", "model.stl", "parts.json"):
                (job_dir / name).write_bytes((fixture_dir / name).read_bytes())
            parts_json = json.loads((fixture_dir / "parts.json").read_text(encoding="utf-8"))
            done = {"ok": True, "job_id": job_id, "attempts": 1, "summary": "replayed reference cold plate", "code": "# replay",
                    "metrics": [], "raw": {}, "latency_s": 12.0, "model": "replay", "source": "replay", "parts": parts_json,
                    "created_at": "2026-11-07T00:00:00+00:00",
                    "files": {k: f"/api/cad/file/{job_id}/model.{k}" for k in ("step", "stl", "py", "glb")}}
            sse = ('event: start\ndata: {"job_id": "' + job_id + '"}\n\nevent: done\ndata: ' + json.dumps(done, ensure_ascii=False) + "\n\n").encode("utf-8")
            page.route("**/api/cad", lambda route: route.fulfill(status=200, headers={"content-type": "text/event-stream"}, body=sse))
            glb_fetches = []
            page.on("request", lambda request: glb_fetches.append(request.url) if request.url.endswith(f"/{job_id}/model.glb") else None)

            def js_click(selector):   # the software-rendered quad view keeps the main thread busy; a real click can wait >30 s for stability
                page.evaluate("selector => document.querySelector(selector).click()", selector)

            def quad_regions():
                js_click('[data-workspace-layout="quad"]')
                page.wait_for_function('document.querySelector("[data-workspace-layout=quad]").getAttribute("aria-pressed") === "true"', timeout=60000)
                if page.locator("#viewGrid").is_checked():
                    js_click("#viewGrid")
                page.wait_for_timeout(1500)
                return page.frame_locator("#viewer").locator("body").evaluate("""() => {
              const source = window.__renderer.domElement;
              const canvas = document.createElement('canvas'); canvas.width = 240; canvas.height = 160;
              const context = canvas.getContext('2d'); context.drawImage(source, 0, 0, 240, 160);
              const pixels = context.getImageData(0, 0, 240, 160).data;
              return [...document.querySelectorAll('.studio-viewport:not([hidden])')].sort((first, second) => first.offsetTop - second.offsetTop || first.offsetLeft - second.offsetLeft).map((element, index) => {
                const left = index % 2 * 120, top = Math.floor(index / 2) * 80;
                let content = 0, bright = 0, dark = 0;
                for (let vertical = top + 3; vertical < top + 77; vertical++) for (let horizontal = left + 3; horizontal < left + 117; horizontal++) {
                  const offset = (vertical * 240 + horizontal) * 4;
                  if (Math.max(Math.abs(pixels[offset] - 65), Math.abs(pixels[offset + 1] - 69), Math.abs(pixels[offset + 2] - 73)) > 24) {
                    content++; const luma = (pixels[offset] + pixels[offset + 1] + pixels[offset + 2]) / 3; if (luma > 225) bright++; if (luma < 20) dark++;
                  }
                }
                return { view: element.dataset.view, contentPixels: content, brightShare: content ? bright / content : null, darkShare: content ? dark / content : null };
              });
                }""", timeout=60000)

            js_click("#btnStep")
            page.wait_for_function('document.querySelector("#viewStatus").textContent.includes("B-rep") && !document.querySelector("#stageBadge").textContent.includes("预生成")', timeout=WORKSPACE_TIMEOUT_MS)
            assert "预生成" not in page.locator("#cadBadge").inner_text() and page.locator("#cadDlStep").get_attribute("href") == f"/api/cad/file/{job_id}/model.step"
            brep = page.frame_locator("#viewer").locator("body").evaluate("""() => ({
              kit: window.__studioKit, parts: window.__model.children.map(child => child.name),
              presets: [...new Set((() => { const a = []; window.__model.traverse(o => { if (o.isMesh) a.push(o.material.userData.studioKit); }); return a; })())],
              anisotropyDisabled: (() => { let n = 0; window.__model.traverse(o => { if (o.isMesh && o.material.userData.anisotropyDisabled) n++; }); return n; })(),
            })""", timeout=60000)
            assert brep["kit"] == "1.1.0" and brep["parts"] == ["流道基板", "上盖板", "进口接头", "出口接头"], brep
            assert set(brep["presets"]) == {"aluminum", "anodized", "steel"} and brep["anisotropyDisabled"] > 0, brep
            assert page.locator("#partList button").all_inner_texts() == brep["parts"]
            assert "B-rep" in page.locator("#stageBadge").inner_text()
            assert page.locator('[data-geometry="brep"]').get_attribute("aria-pressed") == "true"
            # The STL preview on the CAD tab loaded from the same job (a 404 there would surface as an error bubble).
            assert page.locator(".msg.assistant.error").count() == 0, page.locator(".msg.assistant.error").all_inner_texts()
            record("brep_solid_becomes_main_viewport", brep)
            brep_regions = quad_regions()
            assert len(brep_regions) == 4 and all(region["contentPixels"] > 10 for region in brep_regions), brep_regions
            # Orthographic views must read as matte solid shading: no view is a white sheet (mirror metal square-on) or
            # a black silhouette (the face the view looks at pointing away from every scene light).
            assert all(region["brightShare"] < 0.5 and region["darkShare"] < 0.2 for region in brep_regions), brep_regions
            page.screenshot(path=str(output / "brep-quad.png"), scale="css")
            record("brep_quad_views_are_shaded_not_blank", brep_regions)
            js_click('[data-workspace-layout="original"]')
            page.wait_for_timeout(500)
            # A real click: Chromium silently drops a page's further automatic downloads when no user gesture is involved,
            # so a scripted element.click() here would make the export look broken although the iframe answered.
            with page.expect_download(timeout=90000) as download:
                page.locator("#btnGlb").click(force=True, timeout=90000)
            brep_glb = output / "brep-export.glb"
            download.value.save_as(brep_glb)
            exported = brep_glb.read_bytes()
            assert exported[:4] == b"glTF" and struct.unpack("<I", exported[8:12])[0] == len(exported), len(exported)
            record("brep_glb_export", {"bytes": len(exported)})
            js_click('[data-geometry="concept"]')
            page.wait_for_function('document.querySelector("[data-geometry=concept]").getAttribute("aria-pressed") === "true" && !document.querySelector("#viewStatus").textContent.includes("B-rep") && document.querySelector("#viewportBody").classList.contains("engineering")', timeout=WORKSPACE_TIMEOUT_MS)
            concept_names = page.frame_locator("#viewer").locator("body").evaluate("() => window.__model.children.map(child => child.name)", timeout=60000)
            assert concept_names != brep["parts"] and len(concept_names) >= 2, concept_names
            assert "B-rep" not in page.locator("#stageBadge").inner_text()
            js_click('[data-geometry="brep"]')
            page.wait_for_function('document.querySelector("#viewStatus").textContent.includes("B-rep")', timeout=WORKSPACE_TIMEOUT_MS)
            assert page.frame_locator("#viewer").locator("body").evaluate("() => window.__model.children.map(child => child.name)", timeout=60000) == brep["parts"]
            assert len(glb_fetches) == 1, glb_fetches   # the second switch reuses the buffer already downloaded
            record("geometry_source_round_trip_reuses_glb", {"conceptParts": concept_names, "glbFetches": len(glb_fetches)})
            page.unroute("**/api/cad")
            # The two /api/cad POSTs above never left the browser (route.fulfill replayed them); anything else would be a real call.
            replayed = [url for url in result["modelCalls"] if urlparse(url).path == "/api/cad"]
            assert 1 <= len(replayed) <= 2 and len(replayed) == len(result["modelCalls"]), result["modelCalls"]
            result["modelCalls"] = []
            result["replayedCadRequests"] = len(replayed)
            assert not result["pageErrors"], result["pageErrors"]
            page.locator(".scenario").filter(has_text="电子膨胀阀").click(force=True)
            page.locator("#viewportBody.engineering").wait_for(timeout=WORKSPACE_TIMEOUT_MS)
            js_click('[data-workspace-layout="quad"]')
            result["status"] = "PASS"
        except Exception as error:
            result["status"] = "FAIL"
            result["failure"] = {"type": type(error).__name__, "message": str(error)}
            page.screenshot(path=str(output / "failure.png"), scale="css")
            raise
        finally:
            (output / "browser-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            replay_job = project / "cad_out" / "c0ffee0b4e9f"
            if replay_job.exists():
                for leftover in replay_job.iterdir():
                    leftover.unlink()
                replay_job.rmdir()
            page.close()
            if headless:
                browser.close()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8015")
    parser.add_argument("--cdp", default="http://127.0.0.1:9334")
    parser.add_argument("--headless", action="store_true", help="launch a private headless Edge (software WebGL) instead of attaching over CDP")
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    verification = verify(arguments.url.rstrip("/"), arguments.cdp, arguments.output, headless=arguments.headless)
    print(json.dumps({"status": verification["status"], "checks": len(verification["checks"]), "evidence": str(arguments.output)}, ensure_ascii=False))