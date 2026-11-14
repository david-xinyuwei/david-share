(() => {
  'use strict';
  const renderId = document.currentScript.dataset.renderId;
  const origin = new URL(document.currentScript.src).origin;
  let failed = false;
  let ready = false;
  let timer;
  let workspace;
  let workspaceLoading;
  const notify = (type, data = {}, transfers = []) => parent.postMessage({ type, renderId, ...data }, '*', transfers);
  // System scenes call this when their stage auto-advances, so the host's stage strip can follow.
  window.__notifyStage = (index) => { if (Number.isInteger(index)) notify('stage', { index }); };
  function fail(message) {
    if (failed) return;
    failed = true;
    clearTimeout(timer);
    notify('render-error', { message: String(message).slice(0, 600) });
  }
  window.addEventListener('error', e => fail(e.message || `Resource failed: ${e.target.src || 'unknown'}`), true);
  window.addEventListener('unhandledrejection', e => fail(e.reason?.message || e.reason));
  // Budget of *visible* time: while the host keeps this frame hidden (display:none → 0×0 window, e.g. another
  // stage tab is active) nothing can be drawn, so that time is not counted against the deadline.
  const BUDGET_MS = 30000;
  // Give generated modules time to publish their integration objects before using canvas-only readiness.
  const FALLBACK_MS = 6000;
  let deadline = performance.now() + BUDGET_MS;
  let lastTick = performance.now();
  let lastNudge = 0;
  const hidden = () => window.innerWidth === 0 || window.innerHeight === 0 || document.visibilityState === 'hidden';
  // Observe drawing even when a generated module keeps its renderer private.
  const drawings = new Map();
  const WEBGL_TYPES = ['webgl2', 'webgl', 'experimental-webgl'];
  const DRAW_CALLS = ['drawArrays', 'drawElements', 'drawArraysInstanced', 'drawElementsInstanced'];
  const nativeGetContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (type, attributes) {
    if (!WEBGL_TYPES.includes(type)) return nativeGetContext.call(this, type, attributes);
    // preserveDrawingBuffer keeps the last frame readable, so a screenshot still works when the scene did not
    // expose its renderer and the bridge therefore cannot redraw on demand.
    const ctx = nativeGetContext.call(this, type, { ...(attributes || {}), preserveDrawingBuffer: true });
    if (!ctx || drawings.has(ctx)) return ctx;
    const canvas = this;
    const drawing = { canvas, width: 0, height: 0 };
    drawings.set(ctx, drawing);
    for (const name of DRAW_CALLS) {
      const native = ctx[name];
      if (typeof native !== 'function') continue;
      ctx[name] = function (...args) {
        const result = native.apply(this, args);
        const count = args[name.startsWith('drawArrays') ? 2 : 1];
        const instances = name.endsWith('Instanced') ? args[args.length - 1] : 1;
        // Shadow maps and environment-map passes do not prove the visible canvas was drawn.
        if (count > 0 && instances > 0 && !ctx.isContextLost() &&
            ctx.getParameter(ctx.DRAW_FRAMEBUFFER_BINDING ?? ctx.FRAMEBUFFER_BINDING) === null) {
          drawing.width = canvas.width; drawing.height = canvas.height;
        }
        return result;
      };
    }
    return ctx;
  };
  function drawnCanvas() {
    for (const [ctx, d] of drawings) {
      const c = d.canvas;
      if (!ctx.isContextLost() && c.isConnected && d.width > 0 && d.height > 0 &&
          d.width === c.width && d.height === c.height) return c;
    }
    return null;
  }
  const missingGlobals = () => ['__scene', '__camera', '__renderer'].filter(name => !window[name]);
  // Metrics computed by the scene script itself (window.__metrics) are authoritative for the metrics tab.
  function liveMetrics() {
    const list = window.__metrics;
    if (!Array.isArray(list)) return null;
    const clean = (v, n) => (v === undefined || v === null ? '' : String(v).slice(0, n));
    const out = list.filter(m => m && typeof m === 'object').slice(0, 10)
      .map(m => ({ label: clean(m.label, 60), value: clean(m.value, 60), unit: clean(m.unit, 30), note: clean(m.note, 120) }))
      .filter(m => m.label && m.value);
    return out.length ? out : null;
  }
  // System scenes (loops / modes / hotspots / stages) describe their components and operating stages so the
  // host can show a consistent index + stage strip and drive the scene through __focus / __setStage.
  function sceneHotspots() {
    const list = window.__hotspots;
    if (!Array.isArray(list) || typeof window.__focus !== 'function') return null;
    const clean = (v, n) => (v === undefined || v === null ? '' : String(v).slice(0, n));
    const out = list.filter(h => h && typeof h === 'object' && h.id && h.label).slice(0, 16)
      .map((h, i) => ({ id: clean(h.id, 40), n: Number.isInteger(h.n) ? h.n : i + 1, label: clean(h.label, 40), part: clean(h.part, 40), note: clean(h.note, 120) }));
    return out.length ? out : null;
  }
  function sceneStages() {
    const list = window.__stages;
    if (!Array.isArray(list) || typeof window.__setStage !== 'function') return null;
    const clean = (v, n) => (v === undefined || v === null ? '' : String(v).slice(0, n));
    const out = list.filter(s => s && typeof s === 'object' && s.title).slice(0, 8)
      .map(s => ({ title: clean(s.title, 40), text: clean(s.text, 160) }));
    return out.length ? out : null;
  }
  // A scene that initialised while hidden has a 0×0 canvas; once visible, let its own resize handler fix it
  // (synthetic resize), and if it has none, size the renderer ourselves.
  function nudgeSize(renderer, camera) {
    const now = performance.now();
    if (now - lastNudge < 400) return;
    lastNudge = now;
    window.dispatchEvent(new Event('resize'));
    if (renderer.domElement.width === 0 && window.innerWidth > 0) {
      renderer.setSize(window.innerWidth, window.innerHeight);
      if (camera && camera.isPerspectiveCamera) { camera.aspect = window.innerWidth / window.innerHeight; camera.updateProjectionMatrix(); }
    }
  }
  // Scenes written against the pre-kit prompt (saved examples, older live results) get the studio look applied here,
  // so the viewport matches what the new prompt produces: ACES/sRGB, light rig with soft shadows, calibrated materials,
  // neutral workbench. Scenes that already used studio-kit set window.__studioKit and are left untouched.
  async function applyStudioLookIfNeeded() {
    if (window.__studioKit || missingGlobals().length || !window.__model) return null;
    try {
      const { kit } = await import(`${origin}/static/studio-kit.js`);
      const result = kit.applyStudioLook(window.__scene, window.__renderer, window.__model);
      window.__studioKit = `${kit.KIT_VERSION}+retrofit`;
      // GridHelper from the old prompt doubles the kit's own grid: keep the kit's, hide the author's.
      window.__scene.children.forEach(o => { if (o.isGridHelper && o !== result.bench.grid) o.visible = false; });
      window.__renderer.render(window.__scene, window.__camera);
      return 'retrofit';
    } catch (error) { notify('scene-error', { message: `studio-kit retrofit skipped: ${String(error.message).slice(0, 200)}` }); return null; }
  }
  function succeed(info) {
    if (ready || failed) return;
    ready = true;
    clearTimeout(timer);
    const announce = (studioLook) => notify('render-ready', {
      ...info, canExportGlb: !!(window.__model || window.__scene),
      canInspect: missingGlobals().length === 0,
      studioLook,
      metrics: liveMetrics(), hotspots: sceneHotspots(), stages: sceneStages(),
    });
    // Synchronous for kit-native scenes and degraded (canvas-only) scenes; the retrofit path is the only async one.
    if (window.__studioKit) return announce('native');
    if (missingGlobals().length || !window.__model || typeof window.__renderer.render !== 'function' || !window.__renderer.capabilities) return announce(null);
    applyStudioLookIfNeeded().then(announce, () => announce(null));
  }
  function check() {
    if (failed) return;
    const now = performance.now();
    const isHidden = hidden();
    if (isHidden) deadline += now - lastTick;   // hidden time does not count
    lastTick = now;
    const renderer = window.__renderer;
    const scene = window.__scene;
    const camera = window.__camera;
    try {
      if (!isHidden && renderer && scene && camera && renderer.domElement.isConnected) {
        if (!isHidden && renderer.domElement.width === 0) nudgeSize(renderer, camera);
        let meshes = 0;
        // Points, lines and sprites are drawn content too: a scene built only from them is still a render.
        scene.traverse(obj => { if (obj.isMesh || obj.isPoints || obj.isLine || obj.isSprite) meshes++; });
        renderer.render(scene, camera);
        if (meshes > 0 && renderer.domElement.width > 0 && renderer.domElement.height > 0 && renderer.info.render.calls > 0) {
          succeed({ meshes });
          return;
        }
      }
      if (!isHidden && BUDGET_MS - (deadline - now) >= FALLBACK_MS && drawnCanvas()) {
        succeed({ meshes: 0, degraded: true, missing: missingGlobals().join(' / ') });
        return;
      }
      if (now >= deadline) { fail(`No rendered 3D scene within ${BUDGET_MS / 1000} seconds`); return; }
      timer = setTimeout(check, isHidden ? 400 : 150);
    } catch (err) { fail(err.message); }
  }
  timer = setTimeout(check, 150);
  window.addEventListener('message', async ev => {
    const d = ev.data || {};
    if (ev.source !== parent || d.renderId !== renderId) return;
    if (d.type === 'workspace') {
      try {
        if (!ready || failed || missingGlobals().length) throw new Error('Engineering views need the scene, camera and renderer');
        if (!workspaceLoading) workspaceLoading = Promise.all([
          import(`${origin}/static/viewer-workspace.mjs?rev=23`),
          import(`${origin}/static/vendor/three/three.module.js`),
          import(`${origin}/static/vendor/three/jsm/controls/OrbitControls.js`),
          import(`${origin}/static/vendor/three/jsm/environments/RoomEnvironment.js`),
          import(`${origin}/static/studio-env.mjs?rev=23`).catch(() => null),   // look-dev assets; the workspace still works without them
          import(`${origin}/static/vendor/three/jsm/postprocessing/GTAOPass.js`).catch(() => null),   // perspective-view AO (optional)
        ]).then(([module, THREE, { OrbitControls }, { RoomEnvironment }, studioEnv, gtao]) => {
          workspace = module.createWorkspace({ THREE, OrbitControls, RoomEnvironment, studioEnv, GTAOPass: gtao ? gtao.GTAOPass : null, scene: window.__scene,
            model: window.__model || window.__scene, renderer: window.__renderer,
            sourceCamera: window.__camera, sourceControls: window.__controls, notify, origin });
          return workspace;
        }).catch(error => { workspaceLoading = null; throw error; });
        (await workspaceLoading).apply(d.options || {});
      } catch (error) { notify('workspace-error', { message: String(error.message).slice(0, 600) }); }
      return;
    }
    if (d.type === 'focus') { try { if (typeof window.__focus === 'function') window.__focus(d.id ?? null); } catch (err) { notify('scene-error', { message: String(err.message) }); } return; }
    if (d.type === 'set-stage') { try { if (typeof window.__setStage === 'function') window.__setStage(d.index); } catch (err) { notify('scene-error', { message: String(err.message) }); } return; }
    if (!['export-png', 'export-glb'].includes(d.type)) return;
    try {
      if (!ready || failed) throw new Error('The 3D scene is not ready');
      if (d.type === 'export-png') {
        if (workspace?.active) { notify('png', { url: workspace.snapshot() }); return; }
        const renderer = window.__renderer;
        if (renderer && window.__scene && window.__camera) renderer.render(window.__scene, window.__camera);
        // No renderer contract → read the last preserved frame straight off the canvas that did the drawing.
        const canvas = renderer ? renderer.domElement : drawnCanvas();
        if (!canvas) throw new Error('No rendered canvas available for the snapshot');
        notify('png', { url: canvas.toDataURL('image/png') });
      } else {
        const source = window.__model || window.__scene;
        if (!source) throw new Error('GLB export needs window.__scene (or window.__model) from the scene script');
        const { GLTFExporter } = await import(`${origin}/static/vendor/three/jsm/exporters/GLTFExporter.js`);
        const buffer = await new GLTFExporter().parseAsync(source, { binary: true });
        if (!(buffer instanceof ArrayBuffer)) throw new Error('Expected binary GLB output');
        // The scene's up axis travels with the bytes: the overlay check converts a Z-up scene the way OCCT does.
        const up = window.__camera && window.__camera.up ? [window.__camera.up.x, window.__camera.up.y, window.__camera.up.z] : null;
        notify('glb', { buffer, up }, [buffer]);
      }
    } catch (err) { notify('export-error', { message: String(err.message) }); }
  });
})();
