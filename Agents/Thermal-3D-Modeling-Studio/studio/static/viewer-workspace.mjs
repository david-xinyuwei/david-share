export function viewportRects(width, height, layout) {
  if (layout !== 'quad') return [{ name: 'perspective', left: 0, top: 0, width, height }];
  const halfWidth = Math.floor(width / 2);
  const halfHeight = Math.floor(height / 2);
  return [
    { name: 'top', left: 0, top: 0, width: halfWidth, height: halfHeight },
    { name: 'perspective', left: halfWidth, top: 0, width: width - halfWidth, height: halfHeight },
    { name: 'front', left: 0, top: halfHeight, width: halfWidth, height: height - halfHeight },
    { name: 'right', left: halfWidth, top: halfHeight, width: width - halfWidth, height: height - halfHeight },
  ];
}

export function frameCamera(THREE, camera, bounds, width, height, direction, up) {
  if (bounds.isEmpty() || width <= 0 || height <= 0) return;
  const center = bounds.getCenter(new THREE.Vector3());
  const radius = Math.max(bounds.getSize(new THREE.Vector3()).length() / 2, 0.01);
  const aspect = width / height;
  camera.up.copy(up);
  camera.zoom = 1;
  if (camera.isPerspectiveCamera) {
    camera.aspect = aspect;
    const tangent = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    const horizontalAxis = new THREE.Vector3().crossVectors(up, direction).normalize();
    const verticalAxis = new THREE.Vector3().crossVectors(direction, horizontalAxis).normalize();
    let distance = radius;
    for (const horizontal of [bounds.min.x, bounds.max.x]) for (const vertical of [bounds.min.y, bounds.max.y]) for (const depth of [bounds.min.z, bounds.max.z]) {
      const point = new THREE.Vector3(horizontal, vertical, depth).sub(center);
      distance = Math.max(distance, point.dot(direction) + Math.max(Math.abs(point.dot(horizontalAxis)) / (tangent * aspect), Math.abs(point.dot(verticalAxis)) / tangent));
    }
    distance *= 1.18;
    camera.position.copy(center).addScaledVector(direction, distance);
    camera.near = Math.max(radius / 1000, 0.001);
    camera.far = distance + radius * 20;
  } else {
    camera.position.copy(center).addScaledVector(direction, radius * 4);
    camera.lookAt(center);
    camera.updateMatrixWorld(true);
    const projected = new THREE.Box3();
    for (const horizontal of [bounds.min.x, bounds.max.x]) {
      for (const vertical of [bounds.min.y, bounds.max.y]) {
        for (const depth of [bounds.min.z, bounds.max.z]) {
          projected.expandByPoint(new THREE.Vector3(horizontal, vertical, depth).applyMatrix4(camera.matrixWorldInverse));
        }
      }
    }
    const size = projected.getSize(new THREE.Vector3());
    const halfHeight = Math.max(size.y / 2, size.x / (2 * aspect), radius * 0.04) * 1.25;
    camera.left = -halfHeight * aspect;
    camera.right = halfHeight * aspect;
    camera.top = halfHeight;
    camera.bottom = -halfHeight;
    camera.near = radius / 1000;
    camera.far = radius * 20;
  }
  camera.lookAt(center);
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld(true);
}

export function modelViews(THREE, sourceUp) {
  const zUp = Math.abs(sourceUp.z) > Math.abs(sourceUp.y);
  return {
    zUp,
    directions: {
      perspective: new THREE.Vector3(...(zUp ? [1, -1.15, 0.72] : [1, 0.72, 1.15])).normalize(),
      top: new THREE.Vector3(...(zUp ? [0, 0, 1] : [0, 1, 0])),
      front: new THREE.Vector3(...(zUp ? [0, -1, 0] : [0, 0, 1])),
      right: new THREE.Vector3(1, 0, 0),
    },
    up: new THREE.Vector3(...(zUp ? [0, 0, 1] : [0, 1, 0])),
    topUp: new THREE.Vector3(...(zUp ? [0, 1, 0] : [0, 0, -1])),
  };
}

export function createWorkspace({ THREE, OrbitControls, RoomEnvironment, studioEnv = null, GTAOPass = null, scene, model, renderer, sourceCamera, sourceControls, notify, origin }) {
  const bounds = new THREE.Box3().setFromObject(model, true);
  if (bounds.isEmpty()) throw new Error('No model geometry is available for engineering views');
  const extent = bounds.getSize(new THREE.Vector3());
  const center = bounds.getCenter(new THREE.Vector3());
  const span = Math.max(extent.x, extent.y, extent.z, 0.01);
  const canvas = renderer.domElement;
  const originalParent = canvas.parentNode;
  const originalNext = canvas.nextSibling;
  const originalStyle = canvas.style.cssText;
  const originalRender = renderer.render;
  const draw = originalRender.bind(renderer);
  const options = { layout: 'original', shading: 'material', grid: true, section: 'none', offset: 50, exposure: 1.1, lang: 'zh' };
  const visibilityOverrides = new Map();
  let selected = null;
  let isolated = null;
  let enabledBefore = true;
  let disposed = false;
  let frameId = 0;
  let lastSize = '';
  let active = false;
  let pointerStart = null;
  const root = document.createElement('div');
  root.id = 'studio-workspace';
  root.hidden = true;
  const sheet = document.createElement('link');
  sheet.rel = 'stylesheet';
  sheet.href = `${origin}/static/viewer-workspace.css?rev=20`;
  document.head.appendChild(sheet);
  document.body.appendChild(root);
  const palette = { background: 0x414549, grid: 0x65696d, axis: 0x92979b, solid: 0xbfc6cc, wire: 0xc6d5dd, selection: 0xecae63 };
  // Perspective view: the dark studio environment of studio-env.mjs (softboxes + warm rim) when the host provides it,
  // else RoomEnvironment. Pass the renderer to RoomEnvironment: without it the legacy light intensity leaves its floor black.
  let environment;
  if (studioEnv) environment = studioEnv.createStudioEnvironment(THREE, renderer);
  else {
    const environmentRoom = new RoomEnvironment(renderer);
    const pmrem = new THREE.PMREMGenerator(renderer);
    environment = pmrem.fromScene(environmentRoom, 0.04);
    environmentRoom.dispose();
    pmrem.dispose();
  }
  // Orthographic views and "solid" shading use a Blender-Workbench studio MatCap: lighting fixed to the camera, flat faces
  // one calm tone, every fillet / chamfer / bore a light-to-dark band. A PBR metal square to an orthographic camera
  // mirrors one patch of the environment and reads as a white sheet (or a black one) — the opposite of what an
  // engineering view is for. Fallback without studio-env: a matte standard material lit by a camera headlight.
  const matcapTexture = studioEnv ? studioEnv.studioMatcapTexture(THREE) : null;
  const solid = studioEnv ? studioEnv.studioMatcapMaterial(THREE, matcapTexture)
    : new THREE.MeshStandardMaterial({ color: palette.solid, metalness: 0.42, roughness: 0.32, side: THREE.DoubleSide });
  const orthoSolid = studioEnv ? solid
    : new THREE.MeshStandardMaterial({ color: 0x9da3a9, metalness: 0.08, roughness: 0.62, envMapIntensity: 0.35, side: THREE.DoubleSide });
  const wire = new THREE.MeshBasicMaterial({ color: palette.wire, wireframe: true });
  const background = new THREE.Color(palette.background);
  const perspectiveBackground = studioEnv ? studioEnv.viewportGradientTexture(THREE) : background;
  const toneMapping = THREE.AgXToneMapping ?? THREE.ACESFilmicToneMapping;   // AgX = Blender 4.x default view transform
  const helpers = new THREE.Scene();
  const grid = new THREE.GridHelper(span * 4, 40, palette.axis, palette.grid);
  grid.material.transparent = true;
  grid.material.opacity = 0.45;
  helpers.add(grid);
  const selectionBox = new THREE.Box3Helper(new THREE.Box3(), palette.selection);
  selectionBox.visible = false;
  helpers.add(selectionBox);
  // Blender Workbench studio lighting is fixed to the camera, not the world: an orthographic view has to read the same
  // whichever way the part is oriented. The scene's own key light sits above the part, so the face of a Z-up model
  // that the front view looks at (normal -Y) was pitch black. The headlight travels with each orthographic camera
  // (along the view direction, a little from the upper left) and is only in the scene while a frame is painted.
  const headlight = new THREE.DirectionalLight(0xffffff, 1.35);
  headlight.name = 'studio-workspace-headlight';
  headlight.castShadow = false;
  headlight.target.position.copy(center);
  headlight.target.updateMatrixWorld();
  const viewDirection = new THREE.Vector3();
  const viewRight = new THREE.Vector3();
  function aimHeadlight(camera) {
    camera.getWorldDirection(viewDirection);
    viewRight.crossVectors(viewDirection, camera.up).normalize();
    headlight.position.copy(center).addScaledVector(viewDirection, -span * 3).addScaledVector(camera.up, span * 0.9).addScaledVector(viewRight, -span * 0.6);
    headlight.updateMatrixWorld();
  }
  const clip = new THREE.Plane();
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  const parts = (model.isMesh ? [model] : model.children).filter(part => {
    let found = false;
    part.traverse(object => { if (object.isMesh || object.isLine || object.isPoints) found = true; });
    return found;
  });
  if (!parts.length) parts.push(model);
  // Edge lines (studio-kit edgeLines, author polylines) and the mesh materials, for the two-pass draw under an override
  // material: three.js applies scene.overrideMaterial to lines too, and a MatCap / PBR material on normal-less line
  // geometry renders undefined colours. Pass 1 draws the shaded solids, pass 2 only the lines with their own material.
  const edgeObjects = [];
  const meshMaterials = new Set();
  model.traverse(object => {
    if ((object.isLine || object.isLineSegments) && object.material && !Array.isArray(object.material)) edgeObjects.push(object);
    else if (object.isMesh && object.material) (Array.isArray(object.material) ? object.material : [object.material]).forEach(material => meshMaterials.add(material));
  });
  function drawWithOverride(camera) {
    if (!scene.overrideMaterial || !edgeObjects.length) { draw(scene, camera); return; }
    const lineVisible = edgeObjects.map(object => object.material.visible);
    const meshVisible = new Map([...meshMaterials].map(material => [material, material.visible]));
    const override = scene.overrideMaterial, backdrop = scene.background, autoClear = renderer.autoClear;
    try {
      edgeObjects.forEach(object => { object.material.visible = false; });
      draw(scene, camera);
      edgeObjects.forEach((object, index) => { object.material.visible = lineVisible[index]; });
      meshMaterials.forEach(material => { material.visible = false; });   // projectObject skips a mesh whose own material is invisible
      scene.overrideMaterial = null; scene.background = null; renderer.autoClear = false;
      draw(scene, camera);
    } finally {
      edgeObjects.forEach((object, index) => { object.material.visible = lineVisible[index]; });
      meshVisible.forEach((visible, material) => { material.visible = visible; });
      scene.overrideMaterial = override; scene.background = backdrop; renderer.autoClear = autoClear;
    }
  }
  // ---- Ambient occlusion for the perspective view (material shading, no section): darkens grooves, bores and part joints
  // the way Blender's Workbench cavity/AO does. GTAOPass renders its own normal/depth G-buffer of the scene, then the
  // denoised AO map is multiplied onto that viewport's pixels of the canvas. Any GL failure turns AO off for good — the
  // plain render is always drawn first, so AO can only add, never blank the view.
  // The AO map is recomputed only when what it depends on changes (camera, viewport size, visible meshes); a still view
  // costs one composite per frame. Recomputing every frame took ~0.45 s per frame under a software renderer (SwiftShader).
  // wait: a new workspace paints and reports itself active before the first AO pass, so shader compilation and the first
  // AO frame never delay opening the view.
  // Software WebGL (SwiftShader / llvmpipe: GPU-less VMs, blocklisted GPUs) also needs ~0.45 s per AO pass. There the map
  // is computed only while the view holds still (moving frames show the plain render), and the views drop orbit damping,
  // whose long tail of tiny moves would otherwise keep the view from ever holding still.
  const softwareRenderer = (() => {
    try {
      const gl = renderer.getContext();
      const info = gl.getExtension('WEBGL_debug_renderer_info');
      return /swiftshader|llvmpipe|softpipe|software|basic render/i.test(String(gl.getParameter(info ? info.UNMASKED_RENDERER_WEBGL : gl.RENDERER)));
    } catch { return false; }
  })();
  const viewRecord = () => ({ camera: null, matrix: new THREE.Matrix4(), projection: new THREE.Matrix4(), view: '', content: '' });
  const ao = { pass: null, quad: null, material: null, size: '', state: GTAOPass ? 'pending' : 'off:not loaded', wait: 2,
    mode: softwareRenderer ? 'when-still' : 'on-change', computed: viewRecord(), previous: viewRecord() };
  // Placement of every visible mesh folded into a string: part visibility toggles and animated scenes change it.
  function aoContentSignature() {
    let signature = 0, count = 0;
    scene.traverseVisible(object => {
      if (!object.isMesh) return;
      const e = object.matrixWorld.elements;
      count += 1;
      signature += (count % 97 + 1) * (e[0] + e[1] + e[2] + e[4] + e[5] + e[6] + e[8] + e[9] + e[10] + e[12] + e[13] + e[14]);
    });
    return `${count}:${signature}`;
  }
  // Same camera, viewport and visible meshes as a recorded frame, to a fraction of a pixel. The AO map is denoised over
  // 8 px, so a sub-pixel offset is invisible; exact comparison would recompute through every frame of a damping tail.
  // Comparing with the frame of the last computed map (not the previous frame) still catches a slow drift once it adds up.
  function sameView(record, camera, view, content) {
    if (record.camera !== camera || record.view !== view || record.content !== content || !record.projection.equals(camera.projectionMatrix)) return false;
    const current = camera.matrixWorld.elements, last = record.matrix.elements, shift = span * 1e-4;
    for (let i = 0; i < 16; i++) if (Math.abs(current[i] - last[i]) > (i >= 12 && i <= 14 ? shift : 1e-4)) return false;
    return true;
  }
  function remember(record, camera, view, content) {
    record.camera = camera; record.matrix.copy(camera.matrixWorld); record.projection.copy(camera.projectionMatrix);
    record.view = view; record.content = content;
  }
  function aoEnsure(camera, width, height) {
    if (!ao.pass) {
      // World-space radius (model units = mm): 5 % of the part span reaches into bores, slots and part joints. thickness is
      // the depth gap a sample may have and still occlude; at 3× the radius the walls of a bore or groove count (three.js'
      // own example uses 4×; below 1× the walls are rejected and the bottom of a groove stays white).
      const radius = Math.max(span * 0.05, 0.5);
      ao.pass = new GTAOPass(scene, camera, width, height, undefined,
        { radius, distanceExponent: 1.6, thickness: radius * 3, scale: 1.3, samples: 16, distanceFallOff: 1.0, screenSpaceRadius: false },
        { lumaPhi: 10, depthPhi: 2, normalPhi: 3, radius: 8, radiusExponent: 1, rings: 2, samples: 16 });
      ao.pass.setSceneClipBox(bounds.clone().expandByScalar(span * 0.02));   // background pixels get no occlusion
      ao.material = new THREE.ShaderMaterial({
        uniforms: { tAO: { value: null }, strength: { value: 1.0 } },
        vertexShader: 'varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }',
        fragmentShader: 'uniform sampler2D tAO; uniform float strength; varying vec2 vUv; void main() { float a = texture2D(tAO, vUv).r; gl_FragColor = vec4(vec3(mix(1.0, a, strength)), 1.0); }',
        depthTest: false, depthWrite: false, transparent: true, toneMapped: false,
        blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.DstColorFactor, blendDst: THREE.ZeroFactor,
      });
      const tri = new THREE.BufferGeometry();
      tri.setAttribute('position', new THREE.Float32BufferAttribute([-1, 3, 0, -1, -1, 0, 3, -1, 0], 3));
      tri.setAttribute('uv', new THREE.Float32BufferAttribute([0, 2, 0, 0, 2, 0], 2));
      ao.quad = new THREE.Mesh(tri, ao.material);
      ao.quad.frustumCulled = false;
      ao.scene = new THREE.Scene();
      ao.scene.add(ao.quad);
      ao.screen = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);   // the full-screen triangle ignores it; render() needs one
      // GTAOPass ends by copying its output into writeBuffer; a 1×1 scratch target keeps that copy off the AO texture
      // itself (sampling and writing the same texture is a WebGL feedback loop).
      ao.scratch = new THREE.WebGLRenderTarget(1, 1);
    }
    const key = `${width}x${height}`;
    if (ao.size !== key) { ao.pass.setSize(width, height); ao.size = key; }
    ao.pass.camera = camera;
  }
  // First computed AO frame, read back once per workspace: of the part's pixels (the G-buffer normal is not GTAOPass'
  // clear colour), the share darkened below 0.85 and the mean AO. Evidence that the pass really occludes: a skipped
  // G-buffer leaves no part pixels (null). Buffers start as half-float NaN, so a refused readback is null, not "100 %".
  function aoCoverage(width, height) {
    const size = width * height * 4, half = THREE.DataUtils.fromHalfFloat;
    const aoBuffer = new Uint16Array(size).fill(0x7e00), normalBuffer = new Uint16Array(size).fill(0x7e00);
    renderer.readRenderTargetPixels(ao.pass.pdRenderTarget, 0, 0, width, height, aoBuffer);
    renderer.readRenderTargetPixels(ao.pass.normalRenderTarget, 0, 0, width, height, normalBuffer);
    const clear = new THREE.Color(0x7777ff);   // GTAOPass clears its normal buffer to this (linear working space)
    let part = 0, occluded = 0, sum = 0;
    for (let i = 0; i < size; i += 4 * 5) {
      const value = half(aoBuffer[i]), r = half(normalBuffer[i]), g = half(normalBuffer[i + 1]), b = half(normalBuffer[i + 2]);
      if ([value, r, g, b].some(Number.isNaN)) continue;
      if (Math.abs(r - clear.r) < 0.01 && Math.abs(g - clear.g) < 0.01 && Math.abs(b - clear.b) < 0.01) continue;
      part++; sum += value; if (value < 0.85) occluded++;
    }
    return part ? { occluded: Number((occluded / part).toFixed(4)), mean: Number((sum / part).toFixed(4)) } : null;
  }
  function aoDraw(camera, rect, bottom) {
    if (!GTAOPass || ao.state.startsWith('off') || options.shading !== 'material' || options.section !== 'none') return;
    if (ao.state === 'pending' && ao.wait > 0) return;
    try {
      const ratio = renderer.getPixelRatio();
      const width = Math.max(1, Math.floor(rect.width * ratio)), height = Math.max(1, Math.floor(rect.height * ratio));
      aoEnsure(camera, width, height);
      const savedTarget = renderer.getRenderTarget(), savedTone = renderer.toneMapping, savedClip = renderer.clippingPlanes;
      const savedViewport = renderer.getViewport(new THREE.Vector4()), savedScissor = renderer.getScissor(new THREE.Vector4()), savedScissorTest = renderer.getScissorTest();
      const savedBackground = scene.background, savedOverride = scene.overrideMaterial;
      try {
        const view = `${width}x${height}`, content = aoContentSignature();
        const still = sameView(ao.previous, camera, view, content);
        remember(ao.previous, camera, view, content);
        if (!sameView(ao.computed, camera, view, content)) {
          if (softwareRenderer && !still) return;   // software WebGL: plain render while moving, AO once the view holds still
          renderer.setScissorTest(false);
          renderer.clippingPlanes = [];
          scene.background = null; scene.overrideMaterial = null;
          ao.pass.renderToScreen = false;
          ao.pass.output = GTAOPass.OUTPUT.Denoise;
          // While active, the workspace swallows renderer.render(scene) so the source scene's own loop cannot draw over the
          // views; GTAO's normal/depth G-buffer pass renders exactly that scene, so it needs the original render here.
          const patchedRender = renderer.render;
          renderer.render = originalRender;
          try { ao.pass.render(renderer, ao.scratch, ao.scratch); } finally { renderer.render = patchedRender; }
          remember(ao.computed, camera, view, content);
          if (ao.coverage === undefined) ao.coverage = aoCoverage(width, height);
        }
        renderer.setRenderTarget(savedTarget);
        renderer.toneMapping = THREE.NoToneMapping;
        renderer.setViewport(rect.left, bottom, rect.width, rect.height);
        renderer.setScissor(rect.left, bottom, rect.width, rect.height);
        renderer.setScissorTest(true);
        ao.material.uniforms.tAO.value = ao.pass.pdRenderTarget.texture;
        const clear = renderer.autoClear; renderer.autoClear = false;
        draw(ao.scene, ao.screen);
        renderer.autoClear = clear;
        if (ao.state === 'pending') { ao.state = 'on'; report(); }
      } finally {
        renderer.setRenderTarget(savedTarget);
        renderer.toneMapping = savedTone; renderer.clippingPlanes = savedClip;
        renderer.setViewport(savedViewport); renderer.setScissor(savedScissor); renderer.setScissorTest(savedScissorTest);
        scene.background = savedBackground; scene.overrideMaterial = savedOverride;
      }
    } catch (error) {
      ao.state = `off:${String(error && error.message || error).slice(0, 120)}`;
      report();
    }
  }
  const views = new Map();
  const axes = modelViews(THREE, sourceCamera.up);
  const directions = axes.directions;
  const labels = {
    zh: { perspective: '透视', top: `俯视 · ${axes.zUp ? 'XY' : 'XZ'}`, front: `前视 · ${axes.zUp ? 'XZ' : 'XY'}`, right: `右视 · ${axes.zUp ? 'YZ' : 'ZY'}` },
    en: { perspective: 'Perspective', top: `Top · ${axes.zUp ? 'XY' : 'XZ'}`, front: `Front · ${axes.zUp ? 'XZ' : 'XY'}`, right: `Right · ${axes.zUp ? 'YZ' : 'ZY'}` },
  };
  const viewKinds = {
    zh: { perspective: '用户透视', top: '顶视 正交', front: '前视 正交', right: '右视 正交' },
    en: { perspective: 'User Perspective', top: 'Top Orthographic', front: 'Front Orthographic', right: 'Right Orthographic' },
  };
  // Blender-style gizmo: X red, Y green, Z blue; positive ends are filled discs with the letter, negative ends hollow rings.
  const AXIS_COLORS = { x: '#ff5f5f', y: '#8ad44a', z: '#4f8ff5' };
  const SVG = 'http://www.w3.org/2000/svg';
  function buildGizmo() {
    const svg = document.createElementNS(SVG, 'svg');
    svg.setAttribute('viewBox', '-50 -50 100 100');
    svg.setAttribute('class', 'studio-gizmo');
    svg.setAttribute('aria-hidden', 'true');
    const items = [];
    for (const axis of ['x', 'y', 'z']) for (const sign of [1, -1]) {
      const group = document.createElementNS(SVG, 'g');
      const line = document.createElementNS(SVG, 'line');
      line.setAttribute('stroke', AXIS_COLORS[axis]); line.setAttribute('stroke-width', '2.4'); line.setAttribute('x1', '0'); line.setAttribute('y1', '0');
      const disc = document.createElementNS(SVG, 'circle');
      disc.setAttribute('r', sign > 0 ? '9' : '7.5');
      disc.setAttribute('fill', sign > 0 ? AXIS_COLORS[axis] : 'rgba(0,0,0,0.001)');
      disc.setAttribute('stroke', AXIS_COLORS[axis]); disc.setAttribute('stroke-width', sign > 0 ? '0' : '2');
      const text = document.createElementNS(SVG, 'text');
      text.setAttribute('text-anchor', 'middle'); text.setAttribute('dominant-baseline', 'central');
      text.setAttribute('font-size', '11'); text.setAttribute('font-weight', '700'); text.setAttribute('fill', '#1b1d1f');
      text.textContent = sign > 0 ? axis.toUpperCase() : '';
      if (sign > 0) group.appendChild(line);
      group.append(disc, text);
      svg.appendChild(group);
      items.push({ axis, sign, group, line, disc, text });
    }
    return { svg, items };
  }
  const unitVector = new THREE.Vector3();
  const inverseRotation = new THREE.Quaternion();
  function updateGizmo(view) {
    inverseRotation.copy(view.camera.quaternion).invert();
    const placed = view.gizmo.items.map(item => {
      unitVector.set(item.axis === 'x' ? item.sign : 0, item.axis === 'y' ? item.sign : 0, item.axis === 'z' ? item.sign : 0).applyQuaternion(inverseRotation);
      return { item, x: unitVector.x * 36, y: -unitVector.y * 36, depth: unitVector.z };
    });
    placed.sort((first, second) => first.depth - second.depth);   // far ends first so near ends paint on top
    for (const { item, x, y, depth } of placed) {
      view.gizmo.svg.appendChild(item.group);
      if (item.sign > 0) { item.line.setAttribute('x2', x.toFixed(2)); item.line.setAttribute('y2', y.toFixed(2)); }
      item.disc.setAttribute('cx', x.toFixed(2)); item.disc.setAttribute('cy', y.toFixed(2));
      item.text.setAttribute('x', x.toFixed(2)); item.text.setAttribute('y', y.toFixed(2));
      item.group.setAttribute('opacity', (0.55 + 0.45 * (depth + 1) / 2).toFixed(2));
    }
  }
  const stats = { triangles: 0, vertices: 0, objects: 0 };
  model.traverse(object => {
    if (!object.isMesh || !object.geometry) return;
    const geometry = object.geometry;
    const instances = object.isInstancedMesh ? object.count : 1;
    const positionCount = geometry.attributes.position ? geometry.attributes.position.count : 0;
    const indexCount = geometry.index ? geometry.index.count : positionCount;
    stats.objects += 1;
    stats.vertices += positionCount * instances;
    stats.triangles += Math.floor(indexCount / 3) * instances;
  });
  const partVisible = part => (visibilityOverrides.get(part.uuid) ?? part.visible) && (!isolated || isolated === part.uuid);
  for (const name of Object.keys(directions)) {
    const element = document.createElement('div');
    element.className = 'studio-viewport';
    element.dataset.view = name;
    const label = document.createElement('div');
    label.className = 'studio-view-label';
    const kind = document.createElement('strong');
    const collection = document.createElement('span');
    const scaleLine = document.createElement('span');
    label.append(kind, collection, scaleLine);
    element.appendChild(label);
    const gizmo = buildGizmo();
    element.appendChild(gizmo.svg);
    root.appendChild(element);
    const camera = name === 'perspective' ? new THREE.PerspectiveCamera(38, 1, 0.1, 20000) : new THREE.OrthographicCamera();
    const controls = new OrbitControls(camera, element);
    controls.enableDamping = !softwareRenderer;   // see the AO note: a damping tail never lets a software-rendered view hold still
    controls.enableRotate = name === 'perspective';
    controls.screenSpacePanning = true;
    controls.enabled = false;
    element.addEventListener('pointerdown', event => { pointerStart = { x: event.clientX, y: event.clientY }; });
    element.addEventListener('pointerup', event => {
      if (!pointerStart || Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) > 4) return;
      const rect = element.getBoundingClientRect();
      pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, 1 - (event.clientY - rect.top) / rect.height * 2);
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(parts.filter(partVisible), true);
      const hit = hits.find(entry => {
        let current = entry.object;
        while (current && current !== model) { if (!(visibilityOverrides.get(current.uuid) ?? current.visible)) return false; current = current.parent; }
        return options.section === 'none' || clip.distanceToPoint(entry.point) >= 0;
      });
      selected = hit ? parts.find(part => { let current = hit.object; while (current) { if (current === part) return true; current = current.parent; } return false; }) || null : null;
      report();
    });
    views.set(name, { element, label, kind, collection, scaleLine, gizmo, camera, controls });
  }

  function report() {
    notify('workspace-state', {
      ...options, active, selected: selected?.uuid || null, isolated, ao: ao.state, aoMode: ao.mode, aoCoverage: ao.coverage ?? null,
      bounds: { x: extent.x, y: extent.y, z: extent.z },
      stats,
      parts: parts.map((part, index) => ({ id: part.uuid, name: part.name || `${options.lang === 'en' ? 'Part' : '部件'} ${index + 1}`, visible: partVisible(part) })),
    });
  }

  function updateLabels() {
    const lang = options.lang;
    const unitText = span >= 1000 ? (lang === 'en' ? '1 Meter' : '1 米') : span >= 100 ? (lang === 'en' ? '10 Centimeters' : '10 厘米') : (lang === 'en' ? '1 Centimeter' : '1 厘米');
    for (const [name, view] of views) {
      view.kind.textContent = viewKinds[lang][name];
      view.collection.textContent = `(1) ${model.name || (lang === 'en' ? 'Model' : '模型')}`;
      view.scaleLine.textContent = unitText;
      view.label.title = labels[lang][name];
    }
  }

  function fit(targetBounds = bounds) {
    for (const rect of viewportRects(root.clientWidth, root.clientHeight, options.layout)) {
      const view = views.get(rect.name);
      frameCamera(THREE, view.camera, targetBounds, rect.width, rect.height, directions[rect.name], rect.name === 'top' ? axes.topUp : axes.up);
      view.controls.target.copy(targetBounds.getCenter(new THREE.Vector3()));
      view.controls.update();
      view.controls.saveState();
    }
  }

  function resize() {
    const width = root.clientWidth;
    const height = root.clientHeight;
    if (!width || !height) return [];
    const size = `${width}:${height}:${options.layout}`;
    const rects = viewportRects(width, height, options.layout);
    if (size !== lastSize) {
      renderer.setSize(width, height, false);
      for (const view of views.values()) { view.element.hidden = true; view.controls.enabled = false; }
      for (const rect of rects) {
        const view = views.get(rect.name);
        view.element.hidden = false;
        view.controls.enabled = true;
        Object.assign(view.element.style, { left: `${rect.left}px`, top: `${rect.top}px`, width: `${rect.width}px`, height: `${rect.height}px` });
      }
      fit();
      lastSize = size;
    }
    return rects;
  }

  function paint() {
    if (!active || disposed || document.visibilityState === 'hidden') return;
    const rects = resize();
    if (!rects.length) return;
    const previous = {
      background: scene.background, environment: scene.environment, override: scene.overrideMaterial, fog: scene.fog,
      toneMapping: renderer.toneMapping, exposure: renderer.toneMappingExposure, autoClear: renderer.autoClear,
      clipping: renderer.clippingPlanes, viewport: renderer.getViewport(new THREE.Vector4()),
      scissor: renderer.getScissor(new THREE.Vector4()), scissorTest: renderer.getScissorTest(),
    };
    const visibility = parts.map(part => part.visible);
    // The studio-kit workbench floor / grid and any author GridHelper belong to the free-look scene; the engineering
    // views draw their own per-viewport grid, and an opaque floor would hide the orthographic sides entirely.
    const sceneHelpers = scene.children.filter(o => o.isGridHelper || o.name === 'studio-workbench' || o.name === 'studio-grid');
    const helperVisibility = sceneHelpers.map(o => o.visible);
    try {
      parts.forEach(part => { part.visible = partVisible(part); });
      sceneHelpers.forEach(o => { o.visible = false; });
      scene.add(headlight);
      scene.environment = environment.texture;
      scene.background = background;
      scene.fog = null;
      const materialOverride = options.shading === 'solid' ? solid : options.shading === 'wireframe' ? wire : null;
      renderer.toneMapping = toneMapping;
      renderer.toneMappingExposure = options.exposure;
      renderer.autoClear = true;
      if (options.section !== 'none') {
        const coordinate = bounds.min[options.section] + extent[options.section] * options.offset / 100;
        clip.normal.set(0, 0, 0);
        clip.normal[options.section] = -1;
        clip.constant = coordinate;
        renderer.clippingPlanes = [clip];
      } else renderer.clippingPlanes = [];
      renderer.setScissorTest(true);
      selectionBox.visible = !!selected && selected.visible;
      if (selected) selectionBox.box.setFromObject(selected, true);
      for (const rect of rects) {
        const view = views.get(rect.name);
        view.controls.update();
        updateGizmo(view);
        const bottom = root.clientHeight - rect.top - rect.height;
        renderer.setViewport(rect.left, bottom, rect.width, rect.height);
        renderer.setScissor(rect.left, bottom, rect.width, rect.height);
        scene.overrideMaterial = materialOverride || (view.camera.isOrthographicCamera ? orthoSolid : null);
        scene.background = view.camera.isOrthographicCamera ? background : perspectiveBackground;
        // The headlight only matters for the PBR fallback; a MatCap carries its own camera-fixed lighting.
        headlight.visible = !studioEnv && view.camera.isOrthographicCamera && options.shading !== 'wireframe';
        if (headlight.visible) aimHeadlight(view.camera);
        drawWithOverride(view.camera);
        if (view.camera.isPerspectiveCamera) aoDraw(view.camera, rect, bottom);
        grid.visible = options.grid;
        grid.rotation.set(0, 0, 0);
        grid.position.copy(center);
        if (rect.name === 'front' && axes.zUp) grid.position.y = bounds.max.y + span * 0.02;
        else if (rect.name === 'front') { grid.rotation.x = Math.PI / 2; grid.position.z = bounds.min.z - span * 0.02; }
        else if (rect.name === 'right') { grid.rotation.z = Math.PI / 2; grid.position.x = bounds.min.x - span * 0.02; }
        else if (axes.zUp) { grid.rotation.x = Math.PI / 2; grid.position.z = bounds.min.z - span * 0.02; }
        else grid.position.y = bounds.min.y - span * 0.02;
        renderer.autoClear = false;
        renderer.clippingPlanes = [];
        draw(helpers, view.camera);
        renderer.autoClear = true;
        renderer.clippingPlanes = options.section === 'none' ? [] : [clip];
      }
    } finally {
      parts.forEach((part, index) => { part.visible = visibility[index]; });
      sceneHelpers.forEach((o, index) => { o.visible = helperVisibility[index]; });
      scene.remove(headlight);
      scene.background = previous.background;
      scene.environment = previous.environment;
      scene.overrideMaterial = previous.override;
      scene.fog = previous.fog;
      renderer.toneMapping = previous.toneMapping;
      renderer.toneMappingExposure = previous.exposure;
      renderer.autoClear = previous.autoClear;
      renderer.clippingPlanes = previous.clipping;
      renderer.setViewport(previous.viewport);
      renderer.setScissor(previous.scissor);
      renderer.setScissorTest(previous.scissorTest);
    }
  }

  function loop() {
    if (!active || disposed) return;
    if (ao.wait > 0) ao.wait -= 1;   // the first AO pass runs on the second animation frame of a new workspace
    try { paint(); } catch (error) { deactivate(); notify('workspace-error', { message: String(error.message) }); return; }
    frameId = requestAnimationFrame(loop);
  }

  function activate() {
    if (active) return;
    active = true;
    enabledBefore = sourceControls?.enabled ?? true;
    if (sourceControls) sourceControls.enabled = false;
    root.prepend(canvas);
    canvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:block;';
    document.body.dataset.studioWorkspace = 'active';
    root.hidden = false;
    renderer.render = function (targetScene, targetCamera) { if (targetScene !== scene) return originalRender.call(this, targetScene, targetCamera); };
    lastSize = '';
    loop();
  }

  function deactivate() {
    if (!active) return;
    active = false;
    cancelAnimationFrame(frameId);
    renderer.render = originalRender;
    if (sourceControls) sourceControls.enabled = enabledBefore;
    originalParent.insertBefore(canvas, originalNext?.parentNode === originalParent ? originalNext : null);
    canvas.style.cssText = originalStyle;
    delete document.body.dataset.studioWorkspace;
    root.hidden = true;
    for (const view of views.values()) view.controls.enabled = false;
    window.dispatchEvent(new Event('resize'));
  }

  function apply(change) {
    if (disposed) throw new Error('This model view has been disposed');
    if (change.layout !== undefined && !['original', 'single', 'quad'].includes(change.layout)) throw new Error('Unsupported viewport layout');
    if (change.shading !== undefined && !['material', 'solid', 'wireframe'].includes(change.shading)) throw new Error('Unsupported shading mode');
    if (change.section !== undefined && !['none', 'x', 'y', 'z'].includes(change.section)) throw new Error('Unsupported section axis');
    for (const [key, min, max] of [['offset', 0, 100], ['exposure', 0.4, 2]]) {
      if (change[key] !== undefined && (!Number.isFinite(change[key]) || change[key] < min || change[key] > max)) throw new Error(`Invalid ${key}`);
    }
    for (const key of ['layout', 'shading', 'section', 'offset', 'exposure']) if (change[key] !== undefined) options[key] = change[key];
    if (typeof change.grid === 'boolean') options.grid = change.grid;
    if (change.lang === 'zh' || change.lang === 'en') options.lang = change.lang;
    if (change.selected !== undefined) selected = parts.find(part => part.uuid === change.selected) || null;
    if (change.visibility) {
      const part = parts.find(entry => entry.uuid === change.visibility.id);
      if (!part) throw new Error('Part no longer belongs to this model');
      visibilityOverrides.set(part.uuid, !!change.visibility.visible);
    }
    if (change.action === 'isolate') isolated = selected?.uuid || null;
    if (change.action === 'show-all') { visibilityOverrides.clear(); isolated = null; selected = null; }
    updateLabels();
    if (options.layout === 'original') deactivate(); else activate();
    if (change.action === 'fit') { resize(); fit(selected ? new THREE.Box3().setFromObject(selected, true) : bounds); }
    paint();
    report();
  }

  function dispose() {
    deactivate();
    disposed = true;
    for (const view of views.values()) view.controls.dispose();
    environment.dispose();
    headlight.dispose();
    solid.dispose(); orthoSolid.dispose(); wire.dispose();
    if (matcapTexture) matcapTexture.dispose();
    if (perspectiveBackground !== background) perspectiveBackground.dispose();
    if (ao.pass) { ao.pass.dispose(); ao.material.dispose(); ao.quad.geometry.dispose(); ao.scratch.dispose(); }
    grid.geometry.dispose(); grid.material.dispose();
    selectionBox.geometry.dispose(); selectionBox.material.dispose();
    root.remove(); sheet.remove();
  }
  window.addEventListener('pagehide', dispose, { once: true });
  return { apply, dispose, get active() { return active; }, snapshot() { paint(); return canvas.toDataURL('image/png'); } };
}