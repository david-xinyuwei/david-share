// Studio Kit — the look-and-feel layer every generated scene imports (`import { kit } from 'studio-kit'`).
// Closes the gap between raw three.js primitives and a Blender-grade viewport: calibrated PBR materials
// (brushed metal via anisotropy, anodised, powder coat, polymer), filleted boxes, a Blender-style studio
// light rig with soft shadows and ACES tone mapping, a neutral grey workbench, and an outline helper.
// Pinned to the vendored three r160 — no CDN. Pure helpers: it never touches window.__scene or metrics.
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { createStudioEnvironment, viewportGradientTexture } from './studio-env.mjs';

// 1.1.0 (2026-11-08): dark softbox studio environment + AgX tone mapping + gradient backdrop (was RoomEnvironment + ACES:
// metals mirrored a white room and read as white sheets).
export const KIT_VERSION = '1.1.0';

// Calibrated against the reference workbench renders: albedo in sRGB, roughness/metalness tuned for RoomEnvironment.
export const MATERIAL_PRESETS = Object.freeze({
  aluminum:   { color: '#c9ced3', metalness: 1.0, roughness: 0.34, anisotropy: 0.55, anisotropyRotation: 0,        clearcoat: 0.0 },  // brushed 6061
  aluminumCast: { color: '#b9bec4', metalness: 0.9, roughness: 0.55, anisotropy: 0.0 },                                            // die-cast / sandblasted
  anodized:   { color: '#9aa1a8', metalness: 0.85, roughness: 0.40, anisotropy: 0.25, clearcoat: 0.25, clearcoatRoughness: 0.35 }, // anodised housing
  copper:     { color: '#c77b4a', metalness: 1.0, roughness: 0.30, anisotropy: 0.35 },
  brass:      { color: '#c9a23a', metalness: 1.0, roughness: 0.32, anisotropy: 0.30 },
  steel:      { color: '#a4aab0', metalness: 1.0, roughness: 0.28, anisotropy: 0.60 },                                             // stainless, brushed
  steelDark:  { color: '#4c5157', metalness: 0.95, roughness: 0.45 },                                                              // blackened fasteners
  powderCoat: { color: '#2f3237', metalness: 0.05, roughness: 0.62, clearcoat: 0.15, clearcoatRoughness: 0.5 },                    // dark powder-coated steel
  polymer:    { color: '#2b2b2e', metalness: 0.0, roughness: 0.58, clearcoat: 0.08 },                                              // PA66-GF30 housings
  polymerLight: { color: '#d8d6d0', metalness: 0.0, roughness: 0.65 },
  rubber:     { color: '#141416', metalness: 0.0, roughness: 0.92 },                                                               // O-rings / seals
  coolant:    { color: '#2f7fe0', metalness: 0.0, roughness: 0.12, transmission: 0.55, thickness: 2.0, ior: 1.33, opacity: 0.85, transparent: true, depthWrite: false }, // water-glycol
  refrigerant:{ color: '#38bdf8', metalness: 0.0, roughness: 0.10, transmission: 0.65, thickness: 1.5, ior: 1.2,  opacity: 0.8,  transparent: true, depthWrite: false },
  glass:      { color: '#ffffff', metalness: 0.0, roughness: 0.05, transmission: 0.95, thickness: 1.0, ior: 1.5,  transparent: true },
  copperWire: { color: '#b86a3a', metalness: 1.0, roughness: 0.45 },
  pcb:        { color: '#1f5f3a', metalness: 0.0, roughness: 0.55 },
  cardboard:  { color: '#c8a165', metalness: 0.0, roughness: 0.88 },                                                               // corrugated board
  wood:       { color: '#a8773f', metalness: 0.0, roughness: 0.78 },                                                               // pallet timber
  anodizedBlue:   { color: '#2f62c4', metalness: 0.55, roughness: 0.40, clearcoat: 0.3, clearcoatRoughness: 0.3 },               // dyed anodised aluminium
  anodizedGreen:  { color: '#24874a', metalness: 0.55, roughness: 0.40, clearcoat: 0.3, clearcoatRoughness: 0.3 },
  anodizedOrange: { color: '#de8a2a', metalness: 0.55, roughness: 0.40, clearcoat: 0.3, clearcoatRoughness: 0.3 },
  anodizedRed:    { color: '#cc3434', metalness: 0.55, roughness: 0.40, clearcoat: 0.3, clearcoatRoughness: 0.3 },
});

export const PALETTE = Object.freeze({
  workbench: '#3d4044',      // Blender default viewport grey
  workbenchDark: '#2b2d30',
  grid: '#55595e',
  gridMajor: '#6b7075',
  accent: '#e8a33d',
  hotspot: '#b11f4b',
});

const materialCache = new Map();

/** Material from a preset name or a preset-like object. Cached per preset+override so repeated parts share GPU state. */
export function material(preset, overrides = {}) {
  const base = typeof preset === 'string' ? MATERIAL_PRESETS[preset] : preset;
  if (!base) throw new Error(`studio-kit: unknown material preset "${preset}"`);
  const key = typeof preset === 'string' && !Object.keys(overrides).length ? preset : null;
  if (key && materialCache.has(key)) return materialCache.get(key);
  const spec = { ...base, ...overrides };
  const mat = new THREE.MeshPhysicalMaterial({
    color: new THREE.Color(spec.color),
    metalness: spec.metalness ?? 0.5,
    roughness: spec.roughness ?? 0.5,
    clearcoat: spec.clearcoat ?? 0,
    clearcoatRoughness: spec.clearcoatRoughness ?? 0.3,
    transmission: spec.transmission ?? 0,
    thickness: spec.thickness ?? 0,
    ior: spec.ior ?? 1.5,
    transparent: !!spec.transparent,
    opacity: spec.opacity ?? 1,
    depthWrite: spec.depthWrite ?? true,
    side: spec.side ?? THREE.FrontSide,
    envMapIntensity: spec.envMapIntensity ?? 1.0,
  });
  if (spec.anisotropy) { mat.anisotropy = spec.anisotropy; mat.anisotropyRotation = spec.anisotropyRotation ?? 0; }
  if (spec.emissive) { mat.emissive = new THREE.Color(spec.emissive); mat.emissiveIntensity = spec.emissiveIntensity ?? 1; }
  // Provenance tag: which preset produced this material (read by the outliner, the retrofit guard and the acceptance test).
  mat.userData.studioKit = typeof preset === 'string' ? preset : 'custom';
  if (key) materialCache.set(key, mat);
  return mat;
}

/**
 * Material for a specific geometry. Anisotropic (brushed) presets need a tangent frame, which three.js derives from
 * UV derivatives; geometry without a `uv` attribute (OCCT/STEP tessellations, raw STL) makes that frame NaN and the
 * surface renders white. Such geometry gets the same preset with anisotropy off (cached per preset).
 */
export function materialFor(preset, geometry, overrides = {}) {
  const base = typeof preset === 'string' ? MATERIAL_PRESETS[preset] : preset;
  if (!base) throw new Error(`studio-kit: unknown material preset "${preset}"`);
  const hasUv = !!(geometry && geometry.attributes && geometry.attributes.uv);
  if (hasUv || !base.anisotropy) return material(preset, overrides);
  const key = typeof preset === 'string' && !Object.keys(overrides).length ? `${preset}#nouv` : null;
  if (key && materialCache.has(key)) return materialCache.get(key);
  const mat = material({ ...base, anisotropy: 0 }, overrides);
  mat.userData.studioKit = typeof preset === 'string' ? preset : 'custom';
  mat.userData.anisotropyDisabled = 'no uv attribute';
  if (key) materialCache.set(key, mat);
  return mat;
}

/** Planar UVs from the two largest bounding-box axes — lets textures / brushed anisotropy work on UV-less meshes (GLB from OCCT, STL). */
export function planarUV(geometry) {
  geometry.computeBoundingBox();
  const size = geometry.boundingBox.getSize(new THREE.Vector3());
  const axes = ['x', 'y', 'z'].sort((a, b) => size[b] - size[a]).slice(0, 2);
  const pos = geometry.attributes.position;
  const uv = new Float32Array(pos.count * 2);
  const min = geometry.boundingBox.min;
  for (let i = 0; i < pos.count; i++) {
    const p = new THREE.Vector3().fromBufferAttribute(pos, i);
    uv[i * 2] = size[axes[0]] ? (p[axes[0]] - min[axes[0]]) / size[axes[0]] : 0;
    uv[i * 2 + 1] = size[axes[1]] ? (p[axes[1]] - min[axes[1]]) / size[axes[1]] : 0;
  }
  geometry.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  return geometry;
}

/** Box with real fillets (what makes machined parts read as machined). radius is clamped to half the smallest edge. */
export function filletBox(w, h, d, radius = Math.min(w, h, d) * 0.08, segments = 3) {
  const r = Math.max(0, Math.min(radius, Math.min(w, h, d) / 2 - 1e-4));
  return r > 0 ? new RoundedBoxGeometry(w, h, d, segments, r) : new THREE.BoxGeometry(w, h, d);
}

/** Cylinder with chamfered ends (ports, bosses, fasteners) — a lathe profile, so the chamfer is real geometry. */
export function chamferedCylinder(radius, height, chamfer = radius * 0.1, radialSegments = 48) {
  const c = Math.max(0, Math.min(chamfer, radius * 0.5, height * 0.5));
  const pts = [
    new THREE.Vector2(0, -height / 2), new THREE.Vector2(radius - c, -height / 2), new THREE.Vector2(radius, -height / 2 + c),
    new THREE.Vector2(radius, height / 2 - c), new THREE.Vector2(radius - c, height / 2), new THREE.Vector2(0, height / 2),
  ];
  const geo = new THREE.LatheGeometry(pts, radialSegments);
  geo.computeVertexNormals();
  return geo;
}

/** Tube/pipe along points with proper radial resolution for round highlights. */
export function pipe(points, radius, { tubularSegments = 128, radialSegments = 24, closed = false, tension = 0.5 } = {}) {
  const curve = new THREE.CatmullRomCurve3(points.map(p => Array.isArray(p) ? new THREE.Vector3(...p) : p), closed, 'catmullrom', tension);
  return new THREE.TubeGeometry(curve, tubularSegments, radius, radialSegments, closed);
}

/** Hex nut / bolt head profile (what makes fastener rows look manufactured instead of cylinders). */
export function hexPrism(acrossFlats, height, chamfer = 0) {
  const r = acrossFlats / Math.sqrt(3); // circumradius
  const geo = new THREE.CylinderGeometry(r, r, height, 6, 1);
  if (chamfer > 0) geo.scale(1, 1, 1);
  return geo;
}

/**
 * Renderer setup matching the reference: physically correct lights, AgX tone mapping (Blender 4.x default view transform:
 * highlights roll off instead of clipping to white), sRGB output, soft shadows. Idempotent on the same renderer.
 */
export function setupRenderer(renderer, { exposure = 1.0, shadows = true } = {}) {
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.AgXToneMapping ?? THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = exposure;
  renderer.shadowMap.enabled = shadows;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  return renderer;
}

/**
 * Blender-style studio: RoomEnvironment for reflections + a warm key light with soft shadows + cool fill + rim.
 * `size` is the model's bounding-sphere radius (mm) so shadow cameras and light distances fit the part.
 */
export function studioLights(scene, renderer, size = 200, { background = 'gradient', envIntensity = 1.0, shadows = true } = {}) {
  // Dark studio with softboxes (studio-env.mjs): metals show streak highlights and a warm rim instead of mirroring a white room.
  const env = createStudioEnvironment(THREE, renderer).texture;
  scene.environment = env;
  // r160 has no Scene.environmentIntensity: apply the intensity per material instead (materials created by kit.material() default to 1.0).
  scene.traverse(o => { if (o.isMesh && o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach(m => { if ('envMapIntensity' in m) m.envMapIntensity = envIntensity; }); });
  if (background === 'gradient') scene.background = viewportGradientTexture(THREE);
  else if (background !== null) scene.background = new THREE.Color(background);

  const rig = new THREE.Group(); rig.name = 'studio-light-rig';
  const key = new THREE.DirectionalLight(0xfff1e0, 2.6);          // warm key, upper-right like the reference
  key.position.set(size * 1.6, size * 2.2, size * 1.4);
  key.castShadow = shadows;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.camera.near = size * 0.1; key.shadow.camera.far = size * 8;
  key.shadow.camera.left = key.shadow.camera.bottom = -size * 1.6; key.shadow.camera.right = key.shadow.camera.top = size * 1.6;
  key.shadow.bias = -0.0005; key.shadow.normalBias = size * 0.002;
  const fill = new THREE.DirectionalLight(0xdfe8ff, 0.9);         // cool fill, left
  fill.position.set(-size * 2.0, size * 0.9, size * 0.8);
  // Warm rim from behind and above: the orange contour on top edges and fillets of the reference's User Perspective.
  const rim = new THREE.DirectionalLight(0xffa25a, 2.2);
  rim.position.set(size * 0.4, size * 1.6, -size * 2.4);
  const hemi = new THREE.HemisphereLight(0xcfd6dd, 0x3a3d41, 0.35);
  rig.add(key, fill, rim, hemi);
  scene.add(rig);
  return { rig, key, fill, rim, hemi, env };
}

/** Neutral grey workbench floor that catches the key-light shadow (no texture, no download). Same colour as the
 * background by default, so only the shadow and the grid read — not a disc edge (Blender viewport look). */
export function workbench(scene, size = 200, y = 0, { color = PALETTE.workbench, grid = true, shadowOpacity = 0.38 } = {}) {
  // Shadow catcher: invisible except where the key light's shadow falls, so the background stays one flat tone (Blender viewport look).
  const floor = new THREE.Mesh(new THREE.CircleGeometry(size * 4, 96), new THREE.ShadowMaterial({ color: 0x000000, opacity: shadowOpacity, transparent: true, depthWrite: false }));
  floor.userData.studioColor = color;
  floor.rotation.x = -Math.PI / 2; floor.position.y = y - size * 0.002; floor.receiveShadow = true; floor.name = 'studio-workbench';
  scene.add(floor);
  let helper = null;
  if (grid) {
    helper = new THREE.GridHelper(size * 6, 60, PALETTE.gridMajor, PALETTE.grid);
    helper.position.y = y + size * 0.0005; helper.material.transparent = true; helper.material.opacity = 0.35; helper.name = 'studio-grid';
    scene.add(helper);
  }
  return { floor, grid: helper };
}

/** Enable shadows on everything under a root; InstancedMesh included. */
export function enableShadows(root) {
  root.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  return root;
}

/** Thin dark edge lines on hard-edged parts — Blender "cavity/outline" feel without post-processing. */
export function edgeLines(mesh, thresholdDeg = 30, color = 0x1a1c1f, opacity = 0.35) {
  const edges = new THREE.EdgesGeometry(mesh.geometry, thresholdDeg);
  const lines = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({ color, transparent: true, opacity }));
  lines.name = `${mesh.name || 'mesh'}-edges`;
  mesh.add(lines);
  return lines;
}

/**
 * Blender Workbench "cavity" on hard edges: convex (ridge) edges drawn light, concave (valley) edges dark, smooth
 * transitions not drawn. All meshes under `root` are welded by position first, so it works on OCCT tessellations where
 * every B-rep face is its own mesh (a per-mesh EdgesGeometry would outline every face, convex or not, in one colour).
 * Returns the Group of line sets added to `root` (or null when nothing qualifies).
 */
export function cavityLines(root, { thresholdDeg = 25, ridgeColor = 0xf2f4f7, ridgeOpacity = 0.6, valleyColor = 0x0a0c0f, valleyOpacity = 0.7, maxTriangles = 800000 } = {}) {
  root.updateMatrixWorld(true);
  const toRoot = new THREE.Matrix4().copy(root.matrixWorld).invert();
  const local = new THREE.Matrix4();
  const v = new THREE.Vector3();
  const tri = [];                                   // flat xyz triple per triangle corner, root space
  root.traverse(o => {
    if (!o.isMesh || o.isInstancedMesh || !o.geometry?.attributes?.position) return;
    local.multiplyMatrices(toRoot, o.matrixWorld);
    const pos = o.geometry.attributes.position, index = o.geometry.index;
    const n = index ? index.count : pos.count;
    for (let i = 0; i < n; i++) { v.fromBufferAttribute(pos, index ? index.getX(i) : i).applyMatrix4(local); tri.push(v.x, v.y, v.z); }
  });
  const triangles = tri.length / 9;
  if (!triangles || triangles > maxTriangles) return null;
  let min = Infinity, max = -Infinity;
  for (const c of tri) { if (c < min) min = c; if (c > max) max = c; }
  const q = Math.max((max - min) * 1e-5, 1e-6);    // weld tolerance: 0.003 mm on a 300 mm part
  const ids = new Map(); const pts = [];
  const corner = new Int32Array(triangles * 3);
  for (let i = 0; i < triangles * 3; i++) {
    const x = tri[i * 3], y = tri[i * 3 + 1], z = tri[i * 3 + 2];
    const key = `${Math.round(x / q)}_${Math.round(y / q)}_${Math.round(z / q)}`;
    let id = ids.get(key);
    if (id === undefined) { id = pts.length / 3; ids.set(key, id); pts.push(x, y, z); }
    corner[i] = id;
  }
  const normals = new Float32Array(triangles * 3);
  const a = new THREE.Vector3(), b = new THREE.Vector3(), c = new THREE.Vector3();
  for (let t = 0; t < triangles; t++) {
    a.fromArray(pts, corner[t * 3] * 3); b.fromArray(pts, corner[t * 3 + 1] * 3); c.fromArray(pts, corner[t * 3 + 2] * 3);
    c.sub(b); b.sub(a); b.cross(c).normalize();
    normals[t * 3] = b.x; normals[t * 3 + 1] = b.y; normals[t * 3 + 2] = b.z;
  }
  const edges = new Map();                           // key → [tri1, opposite corner1, tri2, opposite corner2]
  const span = pts.length / 3 + 1;
  for (let t = 0; t < triangles; t++) for (let e = 0; e < 3; e++) {
    const i0 = corner[t * 3 + e], i1 = corner[t * 3 + (e + 1) % 3], opp = corner[t * 3 + (e + 2) % 3];
    if (i0 === i1) continue;
    const key = i0 < i1 ? i0 * span + i1 : i1 * span + i0;
    const hit = edges.get(key);
    if (!hit) edges.set(key, [t, opp, -1, -1, i0, i1]);
    else if (hit[2] === -1) { hit[2] = t; hit[3] = opp; }
  }
  const cosLimit = Math.cos(THREE.MathUtils.degToRad(thresholdDeg));
  const ridge = [], valley = [];
  const n1 = new THREE.Vector3(), n2 = new THREE.Vector3(), p0 = new THREE.Vector3(), po = new THREE.Vector3();
  for (const [t1, , t2, opp2, i0, i1] of edges.values()) {
    if (t2 === -1) continue;                          // open boundary: not a crease
    n1.fromArray(normals, t1 * 3); n2.fromArray(normals, t2 * 3);
    if (n1.dot(n2) > cosLimit) continue;
    p0.fromArray(pts, i0 * 3); po.fromArray(pts, opp2 * 3).sub(p0);
    const target = n1.dot(po) < 0 ? ridge : valley;  // the other face falls away behind this one → convex
    target.push(pts[i0 * 3], pts[i0 * 3 + 1], pts[i0 * 3 + 2], pts[i1 * 3], pts[i1 * 3 + 1], pts[i1 * 3 + 2]);
  }
  if (!ridge.length && !valley.length) return null;
  const group = new THREE.Group();
  group.name = `${root.name || 'part'}-cavity`;
  group.userData.studioEdges = true;
  for (const [list, color, opacity, kind] of [[ridge, ridgeColor, ridgeOpacity, 'ridge'], [valley, valleyColor, valleyOpacity, 'valley']]) {
    if (!list.length) continue;
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(list, 3));
    const lines = new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color, transparent: true, opacity, depthWrite: false }));
    lines.name = `${group.name}-${kind}`;
    lines.renderOrder = 2;
    group.add(lines);
  }
  root.add(group);
  return group;
}

/** Frame a perspective camera + OrbitControls on a model (quality framing: ~70% of the view, slight top-down). */
export function frame(camera, controls, model, { direction = [1, 0.7, 1.2], fill = 0.7 } = {}) {
  const box = new THREE.Box3().setFromObject(model, true);
  const sphere = box.getBoundingSphere(new THREE.Sphere());
  const dir = new THREE.Vector3(...direction).normalize();
  const fov = THREE.MathUtils.degToRad(camera.fov);
  const dist = sphere.radius / Math.sin(fov / 2) / fill;
  camera.position.copy(sphere.center).addScaledVector(dir, dist);
  camera.near = Math.max(dist / 500, 0.1); camera.far = dist * 20; camera.updateProjectionMatrix();
  if (controls) { controls.target.copy(sphere.center); controls.update(); }
  return sphere;
}

/** One call that applies the whole look to an existing scene (used by the compatibility shim for old examples). */
export function applyStudioLook(scene, renderer, model, opts = {}) {
  setupRenderer(renderer, opts);
  const sphere = new THREE.Box3().setFromObject(model, true).getBoundingSphere(new THREE.Sphere());
  const size = Math.max(sphere.radius, 10);
  // remove the generic lights the old prompt asked for, keep anything named by the scene author
  [...scene.children].forEach(o => { if ((o.isHemisphereLight || o.isDirectionalLight || o.isAmbientLight) && !o.name) scene.remove(o); });
  const lights = studioLights(scene, renderer, size, opts);
  const minY = new THREE.Box3().setFromObject(model, true).min.y;
  const bench = workbench(scene, size, minY, opts);
  enableShadows(model);
  // Upgrade stock MeshStandardMaterials to physical ones with the closest preset by colour family.
  model.traverse(o => {
    if (!o.isMesh || !o.material || o.material.userData.studioKit) return;
    const mats = Array.isArray(o.material) ? o.material : [o.material];
    const upgraded = mats.map(m => upgradeMaterial(m, o.geometry));
    o.material = Array.isArray(o.material) ? upgraded : upgraded[0];
  });
  return { lights, bench, size };
}

/** Map a stock MeshStandardMaterial onto the nearest preset while keeping the author's colour + transparency. */
export function upgradeMaterial(m, geometry = null) {
  if (!m || !m.isMeshStandardMaterial || m.userData.studioKit) return m;
  const hsl = m.color.getHSL({ h: 0, s: 0, l: 0 });
  let preset;
  if (m.transparent && m.opacity < 0.95) preset = hsl.h > 0.45 && hsl.h < 0.72 ? 'coolant' : 'glass';
  else if (m.metalness >= 0.6) preset = hsl.s > 0.25 && hsl.h < 0.12 ? 'copper' : hsl.s > 0.25 && hsl.h < 0.2 ? 'brass' : hsl.l < 0.35 ? 'steelDark' : 'aluminum';
  else preset = hsl.l < 0.3 ? 'polymer' : 'polymerLight';
  const out = materialFor(preset, geometry, { color: `#${m.color.getHexString()}`, transparent: m.transparent, opacity: m.opacity, depthWrite: m.depthWrite, side: m.side });
  out.userData.studioKit = preset;
  if (m.emissive && m.emissive.getHex() !== 0) { out.emissive = m.emissive.clone(); out.emissiveIntensity = m.emissiveIntensity; }
  return out;
}

export const kit = { KIT_VERSION, MATERIAL_PRESETS, PALETTE, material, materialFor, planarUV, filletBox, chamferedCylinder, pipe, hexPrism, setupRenderer, studioLights, workbench, enableShadows, edgeLines, cavityLines, frame, applyStudioLook, upgradeMaterial };
export default kit;
