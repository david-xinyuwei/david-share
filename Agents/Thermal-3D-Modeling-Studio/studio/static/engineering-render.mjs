// 工程渲染图: the STEP solid rendered directly (no image model) with a studio look, plus the STEP outline + edges drawn with the
// same camera, so the lines lie on the picture without any fit. One implementation for both callers: pregen_engineering.py
// (headless Edge, the preset scenarios) and the app (engineering-render.html in this browser, for live STEP results).
// The host page needs an import map for 'three' and 'three/addons/'.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { mergeGeometries, mergeVertices } from 'three/addons/utils/BufferGeometryUtils.js';
import { frameCamera, modelViews } from './viewer-workspace.mjs';
import { studioEnvironmentScene } from './studio-env.mjs';
import { kit } from './studio-kit.js';

export const ENGINEERING_VERSION = '2';
export const LOOK = Object.freeze({
  fill: 0.74,            // the silhouette's bounding box fills this share of the frame width or height
  exposure: 1.05, floor: '#d9d9d6', floorRoughness: 0.75, key: 3.0, cone: 0.72, soft: 0.35, sky: 1.8, hemi: 0.12, rim: 1.2,
  env: 1.0, dome: 0.04, envFloor: 0.12, back: 2.0, backElev: 0.75, backH: 5.0, vignette: 0.28,
});

const halton = (i, b) => { let f = 1, r = 0; while (i > 0) { f /= b; r += f * (i % b); i = Math.floor(i / b); } return r; };
const QUAD_VS = 'varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }';

async function loadModel(glb) {
  const loader = new GLTFLoader();
  const gltf = typeof glb === 'string' ? await loader.loadAsync(glb) : await new Promise((resolve, reject) => loader.parse(glb, '', resolve, reject));
  return gltf.scene;
}

// The workspace's perspective camera (frameCamera / modelViews, 38°), then zoomed and shifted so the projected solid fills
// `fill` of the frame: zoom scales NDC about the view centre, the view offset moves the silhouette's centre to the middle.
function frameTight(camera, root, W, H, fill) {
  const p = new THREE.Vector3();
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  root.traverse((m) => {
    if (!m.isMesh) return;
    const pos = m.geometry.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      p.fromBufferAttribute(pos, i).applyMatrix4(m.matrixWorld).project(camera);
      if (p.x < x0) x0 = p.x; if (p.x > x1) x1 = p.x; if (p.y < y0) y0 = p.y; if (p.y > y1) y1 = p.y;
    }
  });
  const zoom = fill / Math.max((x1 - x0) / 2, (y1 - y0) / 2, 1e-6);
  camera.zoom = zoom;
  camera.updateProjectionMatrix();
  return { zoom, offsetX: zoom * (x0 + x1) / 2 * W / 2, offsetY: -zoom * (y0 + y1) / 2 * H / 2 };
}

// STEP outline + edges with the given camera, the passes of window.cadViews in pregen_render_cad.py: white silhouette on black;
// per part the faces welded (OCCT writes one mesh per B-rep face) and 28° creases drawn over black, polygon-offset occluders.
// Outline = mask minus its cross-structure erosion; lines = (edges | outline) dilated by the cross structure.
function stepLines(renderer, root, camera, W, H) {
  const rt = new THREE.WebGLRenderTarget(W, H);
  const buf = new Uint8Array(W * H * 4);
  const read = () => {
    renderer.readRenderTargetPixels(rt, 0, 0, W, H, buf);
    const m = new Uint8Array(W * H);
    for (let y = 0; y < H; y++) { const s = (H - 1 - y) * W * 4, d = y * W; for (let x = 0; x < W; x++) m[d + x] = buf[s + x * 4] > 127 ? 1 : 0; }
    return m;
  };
  const scene = new THREE.Scene(); scene.background = new THREE.Color(0x000000); scene.add(root);
  const meshes = []; root.traverse((m) => { if (m.isMesh) meshes.push(m); });
  const saved = meshes.map((m) => m.material);
  const white = new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide });
  meshes.forEach((m) => { m.material = white; });
  renderer.setRenderTarget(rt); renderer.render(scene, camera);
  const mask = read();
  const byParent = new Map();
  for (const m of meshes) { const p = m.parent || root; if (!byParent.has(p)) byParent.set(p, []); byParent.get(p).push(m); }
  const group = new THREE.Group(), lineMat = new THREE.LineBasicMaterial({ color: 0xffffff });
  for (const list of byParent.values()) {
    const geoms = list.map((m) => {
      let g = new THREE.BufferGeometry(); g.setAttribute('position', m.geometry.attributes.position.clone());
      if (m.geometry.index) { g.setIndex(m.geometry.index.clone()); g = g.toNonIndexed(); }
      g.applyMatrix4(m.matrixWorld); return g;
    });
    group.add(new THREE.LineSegments(new THREE.EdgesGeometry(mergeVertices(mergeGeometries(geoms, false), 1e-3), 28), lineMat));
    geoms.forEach((g) => g.dispose());
  }
  const occluder = new THREE.MeshBasicMaterial({ color: 0x000000, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: 2, polygonOffsetUnits: 2 });
  meshes.forEach((m) => { m.material = occluder; });
  scene.add(group);
  renderer.render(scene, camera);
  const edges = read();
  renderer.setRenderTarget(null);
  meshes.forEach((m, i) => { m.material = saved[i]; });
  group.traverse((o) => { if (o.geometry) o.geometry.dispose(); });
  [white, lineMat, occluder].forEach((x) => x.dispose()); rt.dispose();

  const N = W * H, layer = new Uint8Array(N);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const i = y * W + x;
    const inner = mask[i] && x > 0 && x < W - 1 && y > 0 && y < H - 1 && mask[i - 1] && mask[i + 1] && mask[i - W] && mask[i + W];
    if (!(edges[i] || (mask[i] && !inner))) continue;
    layer[i] = 1; if (x > 0) layer[i - 1] = 1; if (x < W - 1) layer[i + 1] = 1; if (y > 0) layer[i - W] = 1; if (y < H - 1) layer[i + W] = 1;
  }
  return { mask, layer };
}

function png(W, H, fill) {
  const canvas = document.createElement('canvas'); canvas.width = W; canvas.height = H;
  const ctx = canvas.getContext('2d'), img = ctx.createImageData(W, H);
  fill(img.data);
  ctx.putImageData(img, 0, 0);
  return canvas.toDataURL('image/png');
}

/**
 * Render a STEP glTF (URL or ArrayBuffer of model.glb) with the materials named in parts.json and return PNG data URLs:
 * `image` (the render) and `lines` (cyan STEP outline + edges on transparent, same camera, same pixels). `debug` adds `mask`.
 * Accumulates up to `spp` jittered frames, stopping early after `maxMs` (at least 16 frames).
 */
export async function renderEngineering({ glb, parts = [], width = 2048, height = 1152, spp = 256, maxMs = Infinity, look = {}, debug = false, onProgress = null }) {
  const o = { ...LOOK, ...look }, W = width, H = height, t0 = performance.now();
  const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1); renderer.setSize(W, H, false);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.AgXToneMapping; renderer.toneMappingExposure = o.exposure;
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const gl = renderer.getContext(), dbg = gl.getExtension('WEBGL_debug_renderer_info');
  const gpu = dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
  const floatOk = renderer.extensions.has('EXT_color_buffer_float');
  const disposables = [];
  try {
    // Same part → material mapping as brep-viewer.html (the main-viewport B-rep).
    const root = await loadModel(glb); root.updateMatrixWorld(true);
    const byId = new Map(parts.map((p) => [p.id, p])), used = {};
    root.traverse((node) => {
      const info = byId.get(node.name); if (!info) return;
      used[info.name] = info.material || 'aluminum';
      node.traverse((m) => { if (!m.isMesh) return; m.userData.part = info.id; m.material = kit.materialFor(used[info.name], m.geometry); m.castShadow = m.receiveShadow = true; });
    });
    let meshes = 0, unmatched = 0;
    root.traverse((m) => { if (m.isMesh) { meshes++; if (!m.userData.part) unmatched++; else m.material.envMapIntensity = o.env; } });

    const bounds = new THREE.Box3().setFromObject(root, true);
    const center = bounds.getCenter(new THREE.Vector3()), R = bounds.getSize(new THREE.Vector3()).length() / 2;
    const camera = new THREE.PerspectiveCamera(38, W / H, 0.1, 20000);
    const v = modelViews(THREE, new THREE.Vector3(0, 1, 0));
    frameCamera(THREE, camera, bounds, W, H, v.directions.perspective, v.up);
    const framing = frameTight(camera, root, W, H, o.fill);
    const view = (jx, jy) => camera.setViewOffset(W, H, framing.offsetX + jx, framing.offsetY + jy, W, H);

    const up = new THREE.Vector3(0, 1, 0), dir = v.directions.perspective.clone();
    const dirH = new THREE.Vector3(dir.x, 0, dir.z).normalize(), right = new THREE.Vector3().crossVectors(dir.clone().negate(), up).normalize();
    // Reflections: the studio softbox scene of studio-env.mjs with a light-grey surround plus a softbox behind the part.
    const envScene = studioEnvironmentScene(THREE);
    envScene.children[0].material.color.setRGB(o.dome, o.dome, o.dome * 1.02);
    envScene.children[1].material.color.setRGB(o.envFloor, o.envFloor, o.envFloor);
    const backMat = new THREE.MeshBasicMaterial({ side: THREE.DoubleSide, toneMapped: false });
    backMat.color.setRGB(o.back, o.back * 0.97, o.back * 0.93);
    const back = new THREE.Mesh(new THREE.PlaneGeometry(18, o.backH), backMat);
    back.position.copy(dirH).multiplyScalar(-10).addScaledVector(up, 10 * o.backElev); back.lookAt(0, 0, 0); envScene.add(back);
    const pmrem = new THREE.PMREMGenerator(renderer), env = pmrem.fromScene(envScene, 0.035);
    envScene.userData.dispose(); back.geometry.dispose(); backMat.dispose(); pmrem.dispose();
    disposables.push(env);

    const scene = new THREE.Scene(); scene.add(root);
    scene.environment = env.texture;
    scene.background = new THREE.Color(o.floor);
    const floorMat = new THREE.MeshStandardMaterial({ color: new THREE.Color(o.floor), roughness: o.floorRoughness, metalness: 0, envMapIntensity: 0.3 });
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(R * 80, R * 80), floorMat);
    floor.rotation.x = -Math.PI / 2; floor.position.y = bounds.min.y - R * 1e-4; floor.receiveShadow = true; scene.add(floor);
    disposables.push(floor.geometry, floorMat);
    const keyDir = new THREE.Vector3().addScaledVector(right, -0.9).addScaledVector(dirH, 0.55).addScaledVector(up, 1.35).normalize();
    const keyDist = 4 * R;
    // Spot key with inverse-square falloff: illuminance o.key at the part centre, a soft pool of light on the floor.
    const key = new THREE.SpotLight(0xfff3e6, o.key * keyDist * keyDist, 0, o.cone, 1.0, 2);
    key.castShadow = true; key.shadow.mapSize.set(2048, 2048);
    key.shadow.camera.near = R * 1.5; key.shadow.camera.far = R * 8; key.shadow.bias = -0.0002; key.shadow.normalBias = R * 0.0015;
    key.target.position.copy(center);
    // Sky: one shadowed directional light per frame from a cosine-weighted direction; averaged it is occluded sky light.
    const sky = new THREE.DirectionalLight(0xffffff, o.sky);
    sky.castShadow = true; sky.shadow.mapSize.set(2048, 2048);
    Object.assign(sky.shadow.camera, { left: -1.6 * R, right: 1.6 * R, top: 1.6 * R, bottom: -1.6 * R, near: R, far: 8 * R });
    sky.shadow.camera.updateProjectionMatrix(); sky.shadow.bias = -0.0002; sky.shadow.normalBias = R * 0.0015;
    sky.target.position.copy(center);
    // Cool rim from behind and above: separates top edges and silhouettes from the light backdrop.
    const rim = new THREE.DirectionalLight(0xdfe8ff, o.rim);
    rim.position.copy(center).addScaledVector(dirH, -3 * R).addScaledVector(up, 2.5 * R); rim.target.position.copy(center);
    scene.add(key, key.target, sky, sky.target, rim, rim.target, new THREE.HemisphereLight(0xffffff, 0x8c8c8c, o.hemi));

    const type = floatOk ? THREE.FloatType : THREE.HalfFloatType;
    const frameRT = new THREE.WebGLRenderTarget(W, H, { type });
    let prev = new THREE.WebGLRenderTarget(W, H, { type, depthBuffer: false }), next = new THREE.WebGLRenderTarget(W, H, { type, depthBuffer: false });
    disposables.push(frameRT, prev, next);
    const quad = new THREE.PlaneGeometry(2, 2), quadCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1); quadCam.position.z = 0.5;
    const accMat = new THREE.ShaderMaterial({
      uniforms: { tPrev: { value: null }, tCur: { value: null }, w: { value: 1 } }, vertexShader: QUAD_VS,
      fragmentShader: 'uniform sampler2D tPrev; uniform sampler2D tCur; uniform float w; varying vec2 vUv;\n' +
                      'void main() { gl_FragColor = mix(texture2D(tPrev, vUv), texture2D(tCur, vUv), w); }',
      depthTest: false, depthWrite: false });
    const passScene = new THREE.Scene(), passQuad = new THREE.Mesh(quad, accMat); passQuad.frustumCulled = false; passScene.add(passQuad);
    disposables.push(quad, accMat);
    const a = new THREE.Vector3().crossVectors(keyDir, up).normalize(), b = new THREE.Vector3().crossVectors(keyDir, a).normalize();
    let frames = 0;
    for (let i = 0; i < spp; i++) {
      const n = i + 1;
      view(halton(n, 2) - 0.5, halton(n, 3) - 0.5);   // sub-pixel jitter = box-filtered anti-aliasing
      const rr = Math.sqrt(halton(n, 5)) * o.soft * R, th = 2 * Math.PI * halton(n, 7);
      key.position.copy(center).addScaledVector(keyDir, keyDist).addScaledVector(a, rr * Math.cos(th)).addScaledVector(b, rr * Math.sin(th));
      const u1 = halton(n, 11), ph = 2 * Math.PI * halton(n, 13), s = Math.sqrt(u1);
      sky.position.set(center.x + 4 * R * s * Math.cos(ph), center.y + 4 * R * Math.sqrt(1 - u1), center.z + 4 * R * s * Math.sin(ph));
      renderer.setRenderTarget(frameRT); renderer.render(scene, camera);
      accMat.uniforms.tPrev.value = prev.texture; accMat.uniforms.tCur.value = frameRT.texture; accMat.uniforms.w.value = 1 / n;
      renderer.setRenderTarget(next); renderer.render(passScene, quadCam);
      [prev, next] = [next, prev];
      frames = n;
      if (n % 4 === 0) {
        if (onProgress) onProgress(n, spp);
        await new Promise((r) => setTimeout(r, 0));
        if (n >= 16 && performance.now() - t0 > maxMs) break;
      }
    }
    // Studio vignette on the averaged linear image, then tone mapping + sRGB once on the way to the canvas.
    const vigMat = new THREE.ShaderMaterial({
      uniforms: { tSrc: { value: prev.texture }, k: { value: o.vignette }, aspect: { value: W / H } }, vertexShader: QUAD_VS,
      fragmentShader: 'uniform sampler2D tSrc; uniform float k; uniform float aspect; varying vec2 vUv;\n' +
                      'void main() { vec2 q = (vUv - 0.5) * vec2(2.0, 2.0 / aspect); gl_FragColor = texture2D(tSrc, vUv) * (1.0 - 0.5 * k * dot(q, q)); }',
      depthTest: false, depthWrite: false });
    passQuad.material = vigMat; renderer.setRenderTarget(next); renderer.render(passScene, quadCam);
    const outMat = new THREE.MeshBasicMaterial({ map: next.texture });
    passQuad.material = outMat; renderer.setRenderTarget(null); renderer.render(passScene, quadCam);
    disposables.push(vigMat, outMat);
    const image = renderer.domElement.toDataURL('image/png');
    const renderMs = Math.round(performance.now() - t0);

    view(0, 0);   // the lines use the render camera without jitter, i.e. the centre of the averaged frames
    const { mask, layer } = stepLines(renderer, root, camera, W, H);
    const lines = png(W, H, (d) => { for (let i = 0; i < layer.length; i++) if (layer[i]) { d[i * 4 + 1] = 229; d[i * 4 + 2] = 255; d[i * 4 + 3] = 255; } });
    const result = {
      version: ENGINEERING_VERSION, image, lines, size: [W, H], spp: frames, look: o, gpu, float_accumulation: floatOk, render_ms: renderMs,
      lines_ms: Math.round(performance.now() - t0) - renderMs, meshes, unmatched_meshes: unmatched, materials: used,
      camera: { fov: camera.fov, aspect: camera.aspect, zoom: framing.zoom, view_offset_px: [framing.offsetX, framing.offsetY],
                position: camera.position.toArray(), up: camera.up.toArray() },
    };
    if (debug) result.mask = png(W, H, (d) => { for (let i = 0; i < mask.length; i++) { const c = mask[i] ? 255 : 0; d[i * 4] = d[i * 4 + 1] = d[i * 4 + 2] = c; d[i * 4 + 3] = 255; } });
    root.traverse((m) => { if (m.isMesh) m.geometry.dispose(); });
    return result;
  } finally {
    disposables.forEach((x) => x.dispose());
    renderer.dispose(); renderer.forceContextLoss();
  }
}
