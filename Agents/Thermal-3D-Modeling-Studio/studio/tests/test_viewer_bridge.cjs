const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');
const { pathToFileURL } = require('node:url');

const source = readFileSync(path.join(__dirname, '..', 'static', 'viewer-bridge.js'), 'utf8');
const RENDER_ID = '7';

// Minimal DOM/WebGL stand-in: the bridge only needs a canvas whose getContext it can wrap, a controllable
// clock, and a parent window to postMessage to. Time is driven manually so the 30 s budget costs no real time.
function harness({ visible = true } = {}) {
  const messages = [];
  const listeners = {};
  let now = 0;
  let timers = [];
  let nextTimerId = 1;

  class HTMLCanvasElement {}
  HTMLCanvasElement.prototype.getContext = function (type, attributes) {
    if (type !== 'webgl2' && type !== 'webgl' && type !== 'experimental-webgl') return null;
    this.contextAttributes = attributes;
    return this.gl ||= {
      FRAMEBUFFER_BINDING: 36006,
      framebuffer: null, lost: false,
      getParameter() { return this.framebuffer; },
      isContextLost() { return this.lost; },
      drawArrays() {},
      drawElements() {},
      drawArraysInstanced() {},
      drawElementsInstanced() {},
    };
  };

  const canvas = Object.assign(Object.create(HTMLCanvasElement.prototype), {
    width: 1280, height: 720, isConnected: true,
    toDataURL: () => 'data:image/png;base64,SNAPSHOT',
  });

  const context = vm.createContext({
    HTMLCanvasElement,
    performance: { now: () => now },
    setTimeout: (fn, ms) => { const id = nextTimerId++; timers.push({ id, fn, at: now + (ms || 0) }); return id; },
    clearTimeout: (id) => { timers = timers.filter((t) => t.id !== id); },
    document: {
      currentScript: { dataset: { renderId: RENDER_ID }, src: 'https://studio.example.com/static/viewer-bridge.js' },
      visibilityState: 'visible',
    },
    parent: { postMessage: (msg) => messages.push(msg) },
    URL,
    Event: class { constructor(type) { this.type = type; } },
  });
  context.window = context;
  context.window.innerWidth = visible ? 1280 : 0;
  context.window.innerHeight = visible ? 720 : 0;
  context.window.addEventListener = (name, fn) => { (listeners[name] = listeners[name] || []).push(fn); };
  context.window.dispatchEvent = (ev) => (listeners[ev.type] || []).forEach((fn) => fn(ev));

  vm.runInContext(source, context);

  // Advance the fake clock, running any timer the bridge scheduled along the way.
  function advance(ms) {
    const until = now + ms;
    for (let guard = 0; guard < 10000; guard++) {
      const due = timers.filter((t) => t.at <= until).sort((a, b) => a.at - b.at)[0];
      if (!due) break;
      timers = timers.filter((t) => t.id !== due.id);
      now = due.at;
      due.fn();
    }
    now = until;
  }

  return {
    context, canvas, messages, advance,
    of: (type) => messages.find((m) => m.type === type),
    // A scene that draws through its own (module-scoped) renderer.
    draw(target = canvas) {
      const gl = target.getContext('webgl2', { antialias: true });
      gl.drawElements(4, 3, 5123, 0);
      return gl;
    },
    // A scene that follows the contract and publishes its three.js objects.
    publish({ objects = [{ isMesh: true }], calls = 3, width = 1280 } = {}) {
      context.window.__scene = { traverse: (fn) => objects.forEach(fn) };
      context.window.__camera = { isPerspectiveCamera: true };
      context.window.__renderer = {
        domElement: Object.assign(Object.create(HTMLCanvasElement.prototype), { width, height: 720, isConnected: true, toDataURL: () => 'data:image/png;base64,RENDERER' }),
        info: { render: { calls } },
        render() { this.info.render.calls = calls; },
        setSize() {},
      };
    },
    async message(data) {
      const handlers = listeners.message || [];
      for (const fn of handlers) await fn({ source: context.parent, data: { renderId: RENDER_ID, ...data } });
    },
  };
}

test('a scene that draws without publishing the globals contract is a degraded success, not a failure', () => {
  const h = harness();
  h.draw();
  h.advance(30000);
  assert.equal(h.of('render-error'), undefined);
  const ready = h.of('render-ready');
  assert.ok(ready, 'expected render-ready');
  assert.equal(ready.degraded, true);
  assert.equal(ready.missing, '__scene / __camera / __renderer');
  assert.equal(ready.canExportGlb, false);
  assert.equal(ready.canInspect, false);
});

test('the degraded result arrives well before the 30 s budget expires', () => {
  const h = harness();
  h.draw();
  h.advance(3000);
  assert.equal(h.of('render-ready'), undefined, 'the globals contract must get priority first');
  h.advance(4000);
  assert.equal(h.of('render-ready').degraded, true);
});

test('the published globals contract still wins and reports a full, non-degraded render', () => {
  const h = harness();
  h.publish();
  h.draw();
  h.advance(1000);
  const ready = h.of('render-ready');
  assert.equal(ready.meshes, 1);
  assert.equal(ready.degraded, undefined);
  assert.equal(ready.canExportGlb, true);
  assert.equal(ready.canInspect, true);
});

test('a scene drawn only from sprites, lines or points counts as rendered', () => {
  for (const object of [{ isSprite: true }, { isLine: true }, { isPoints: true }]) {
    const h = harness();
    h.publish({ objects: [object] });
    h.advance(1000);
    assert.equal(h.of('render-ready').meshes, 1, JSON.stringify(object));
    assert.equal(h.of('render-error'), undefined);
  }
});

test('a page that never draws anything still fails with the explicit timeout', () => {
  const h = harness();
  h.advance(30000);
  assert.equal(h.of('render-ready'), undefined);
  assert.match(h.of('render-error').message, /No rendered 3D scene within 30 seconds/);
});

test('a detached or zero-sized canvas is not accepted as a rendered scene', () => {
  for (const broken of [{ isConnected: false }, { width: 0 }]) {
    const h = harness();
    Object.assign(h.canvas, broken);
    h.draw();
    h.advance(30000);
    assert.equal(h.of('render-ready'), undefined, JSON.stringify(broken));
    assert.ok(h.of('render-error'));
  }
});

test('hidden time is not counted against the budget, so a background tab is never failed', () => {
  const h = harness({ visible: false });
  h.draw();
  h.advance(60000);
  assert.equal(h.of('render-error'), undefined);
  assert.equal(h.of('render-ready'), undefined);
});

test('WebGL contexts keep the last frame readable so degraded snapshots are not blank', async () => {
  const h = harness();
  const gl = h.draw();
  assert.equal(typeof gl.drawElements, 'function', 'the instrumented context stays usable by the scene');
  assert.equal(h.canvas.contextAttributes.preserveDrawingBuffer, true);
  assert.equal(h.canvas.contextAttributes.antialias, true, 'the scene\'s own attributes must survive');
  h.advance(30000);
  await h.message({ type: 'export-png' });
  assert.equal(h.of('png').url, 'data:image/png;base64,SNAPSHOT');
});

test('snapshots prefer a freshly rendered frame when the renderer is published', async () => {
  const h = harness();
  h.publish();
  h.advance(1000);
  await h.message({ type: 'export-png' });
  assert.equal(h.of('png').url, 'data:image/png;base64,RENDERER');
});

test('GLB export explains the missing contract instead of throwing an opaque type error', async () => {
  const h = harness();
  h.draw();
  h.advance(30000);
  await h.message({ type: 'export-glb' });
  assert.match(h.of('export-error').message, /window\.__scene/);
});

test('non-WebGL canvas contexts are passed through untouched', () => {
  const h = harness();
  assert.equal(h.canvas.getContext('2d'), null);         // the stub only serves WebGL
  assert.equal(h.canvas.contextAttributes, undefined);   // and 2d requests are never rewritten
});

test('repeated getContext calls do not wrap the same draw method twice', () => {
  const h = harness();
  const gl = h.draw(), draw = gl.drawElements;
  assert.equal(h.canvas.getContext('webgl2').drawElements, draw);
});

test('empty, offscreen and lost-context draws cannot turn a blank canvas into a success', () => {
  for (const kind of ['empty', 'zero-instances', 'offscreen', 'lost', 'resized']) {
    const h = harness();
    const gl = h.canvas.getContext('webgl2');
    if (kind === 'offscreen') gl.framebuffer = {};
    if (kind === 'lost') gl.lost = true;
    if (kind === 'zero-instances') gl.drawElementsInstanced(4, 3, 5123, 0, 0);
    else gl.drawElements(4, kind === 'empty' ? 0 : 3, 5123, 0);
    if (kind === 'resized') h.canvas.width = 640;
    h.advance(30000);
    assert.equal(h.of('render-ready'), undefined, kind);
    assert.ok(h.of('render-error'), kind);
  }
});

test('each WebGL draw entry point can prove canvas rendering', () => {
  for (const [name, args] of [
    ['drawArrays', [4, 0, 3]], ['drawElements', [4, 3, 5123, 0]],
    ['drawArraysInstanced', [4, 0, 3, 2]], ['drawElementsInstanced', [4, 3, 5123, 0, 2]],
  ]) {
    const h = harness();
    h.canvas.getContext('webgl2')[name](...args);
    h.advance(7000);
    assert.ok(h.of('render-ready'), name);
  }
});

test('degraded readiness preserves independently published metrics, stages and GLB source', () => {
  const h = harness();
  h.context.__model = {};
  h.context.__metrics = [{ label: 'rate', value: '10', unit: 'units/h' }];
  h.context.__hotspots = [{ id: 'station', label: 'Station' }];
  h.context.__focus = () => {};
  h.context.__stages = [{ title: 'Assembly', text: 'Running' }];
  h.context.__setStage = () => {};
  h.draw(); h.advance(7000);
  const ready = h.of('render-ready');
  assert.equal(ready.canExportGlb, true);
  assert.equal(ready.metrics[0].value, '10');
  assert.equal(ready.hotspots[0].id, 'station');
  assert.equal(ready.stages[0].title, 'Assembly');
});

test('runtime exceptions remain errors even after a canvas has drawn', () => {
  const h = harness();
  h.draw();
  h.context.dispatchEvent({ type: 'error', message: 'Scene crashed' });
  h.advance(30000);
  assert.equal(h.of('render-ready'), undefined);
  assert.equal(h.of('render-error').message, 'Scene crashed');
});

test('messages from unrelated frames cannot trigger exports', async () => {
  const h = harness();
  h.draw(); h.advance(7000);
  h.context.dispatchEvent({ type: 'message', source: {}, data: { type: 'export-png', renderId: RENDER_ID } });
  await h.message({ type: 'export-png', renderId: 'stale-render' });
  assert.equal(h.of('png'), undefined);
});

test('engineering view requests fail explicitly when only a canvas was published', async () => {
  const harnessInstance = harness();
  harnessInstance.draw(); harnessInstance.advance(7000);
  await harnessInstance.message({ type: 'workspace', options: { layout: 'quad' } });
  assert.match(harnessInstance.of('workspace-error').message, /scene, camera and renderer/);
  assert.equal(harnessInstance.of('render-error'), undefined);
});

test('quad view covers every pixel once even at odd viewport dimensions', async () => {
  const { viewportRects } = await import(pathToFileURL(path.join(__dirname, '..', 'static', 'viewer-workspace.mjs')));
  const rects = viewportRects(801, 603, 'quad');
  assert.equal(rects.length, 4);
  assert.equal(rects.reduce((area, rect) => area + rect.width * rect.height, 0), 801 * 603);
  assert.deepEqual(rects.map(rect => rect.name), ['top', 'perspective', 'front', 'right']);
  assert.equal(rects[0].left + rects[0].width, rects[1].left);
  assert.equal(rects[0].top + rects[0].height, rects[2].top);
  assert.equal(viewportRects(390, 520, 'single').length, 1);
});

test('perspective and orthographic cameras frame thin, tall and wide real geometry without clipping', async () => {
  const { frameCamera } = await import(pathToFileURL(path.join(__dirname, '..', 'static', 'viewer-workspace.mjs')));
  const THREE = await import(pathToFileURL(path.join(__dirname, '..', 'static', 'vendor', 'three', 'three.module.js')));
  for (const dimensions of [[320, 12, 180], [32, 120, 40], [10, 10, 1800]]) {
    const bounds = new THREE.Box3(new THREE.Vector3(-20, 5, 30), new THREE.Vector3(dimensions[0] - 20, dimensions[1] + 5, dimensions[2] + 30));
    for (const [width, height] of [[640, 300], [190, 380]]) {
      for (const name of ['perspective', 'top', 'front', 'right']) {
        const camera = name === 'perspective' ? new THREE.PerspectiveCamera(38) : new THREE.OrthographicCamera();
        const direction = new THREE.Vector3(...({ perspective: [1, 0.72, 1.15], top: [0, 1, 0], front: [0, 0, 1], right: [1, 0, 0] }[name])).normalize();
        const up = name === 'top' ? new THREE.Vector3(0, 0, -1) : new THREE.Vector3(0, 1, 0);
        frameCamera(THREE, camera, bounds, width, height, direction, up);
        for (const horizontal of [bounds.min.x, bounds.max.x]) for (const vertical of [bounds.min.y, bounds.max.y]) for (const depth of [bounds.min.z, bounds.max.z]) {
          const projected = new THREE.Vector3(horizontal, vertical, depth).project(camera);
          assert.ok(Math.abs(projected.x) <= 1 && Math.abs(projected.y) <= 1 && Math.abs(projected.z) <= 1, `${name}: ${dimensions} in ${width}x${height}`);
        }
      }
    }
  }
});

test('engineering view orientation follows both Z-up cold plates and Y-up assemblies', async () => {
  const { modelViews } = await import(pathToFileURL(path.join(__dirname, '..', 'static', 'viewer-workspace.mjs')));
  const THREE = await import(pathToFileURL(path.join(__dirname, '..', 'static', 'vendor', 'three', 'three.module.js')));
  for (const sourceUp of [new THREE.Vector3(0, 0, 1), new THREE.Vector3(0, 1, 0)]) {
    const axes = modelViews(THREE, sourceUp);
    assert.ok(axes.directions.top.equals(sourceUp));
    assert.equal(axes.topUp.dot(axes.directions.top), 0);
    assert.equal(axes.up.dot(axes.directions.front), 0);
    assert.equal(axes.up.dot(axes.directions.right), 0);
  }
});
