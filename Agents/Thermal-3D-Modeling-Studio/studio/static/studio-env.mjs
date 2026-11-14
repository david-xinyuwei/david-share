// Shared look-development assets for studio-kit (scene lighting) and the engineering workspace (viewport shading).
// THREE is passed in so this module works both where it is resolved through the import map (generated scenes,
// studio-kit) and where the host injects it (viewer-workspace.mjs). Everything is procedural: no HDR file, no download.

/**
 * Studio environment for PMREM: dark surroundings with a warm key softbox, an overhead strip, a cool fill and a warm rim.
 * Metals then read as polished parts with streak highlights (the Blender studio look) instead of mirroring a white room —
 * RoomEnvironment's bright walls are what turned every aluminium part into a white sheet.
 */
export function studioEnvironmentScene(THREE) {
  const scene = new THREE.Scene();
  const own = [];
  const basic = (r, g, b, side = THREE.DoubleSide) => {
    const m = new THREE.MeshBasicMaterial({ side, toneMapped: false });
    m.color.setRGB(r, g, b);            // linear values; > 1 makes the panel an emitter in the PMREM bake
    own.push(m);
    return m;
  };
  const dome = new THREE.Mesh(new THREE.SphereGeometry(30, 48, 24), basic(0.030, 0.032, 0.037, THREE.BackSide));
  const floor = new THREE.Mesh(new THREE.CircleGeometry(30, 48), basic(0.085, 0.082, 0.080));
  floor.rotation.x = -Math.PI / 2; floor.position.y = -4;
  scene.add(dome, floor);
  const panel = (w, h, pos, rgb, k) => {
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(w, h), basic(rgb[0] * k, rgb[1] * k, rgb[2] * k));
    mesh.position.set(...pos);
    mesh.lookAt(0, 0, 0);
    scene.add(mesh);
    return mesh;
  };
  panel(11, 7, [-9, 8, 7], [1.0, 0.88, 0.74], 7.0);     // warm key softbox, upper left front
  panel(16, 3, [0, 12, 0], [1.0, 0.98, 0.95], 3.2);     // overhead strip: long highlight along top fillets
  panel(6, 9, [11, 3, 5], [0.72, 0.83, 1.0], 1.8);      // cool fill, right
  panel(16, 5, [3, 6, -12], [1.0, 0.56, 0.26], 7.0);    // warm rim from behind: the orange edge glow of the reference
  panel(10, 2, [0, -1.5, 11], [0.95, 0.95, 0.95], 0.7); // low front bounce: lower edges do not go black
  scene.userData.dispose = () => {
    scene.traverse(o => { if (o.geometry) o.geometry.dispose(); });
    own.forEach(m => m.dispose());
  };
  return scene;
}

/** PMREM-filtered texture of the studio environment (caller disposes it). */
export function createStudioEnvironment(THREE, renderer) {
  const pmrem = new THREE.PMREMGenerator(renderer);
  const scene = studioEnvironmentScene(THREE);
  const target = pmrem.fromScene(scene, 0.035);
  scene.userData.dispose();
  pmrem.dispose();
  return target;
}

function canvasTexture(THREE, size, draw) {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  draw(canvas.getContext('2d'), size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

/**
 * Blender Workbench-style studio MatCap: calm mid tone for faces looking at the camera, a bright key toward the
 * upper-left rim, a dark lower-right rim and a faint rim light. Flat faces stay one tone; every fillet, chamfer and
 * bore shows a light-to-dark band — which is what makes the reference's orthographic views read as machined parts.
 */
export function studioMatcapTexture(THREE) {
  return canvasTexture(THREE, 256, (g, s) => {
    const c = s / 2;
    const tilt = g.createLinearGradient(s * 0.16, s * 0.14, s * 0.86, s * 0.88);
    tilt.addColorStop(0.0, '#e4e8ec');
    tilt.addColorStop(0.42, '#8b929b');
    tilt.addColorStop(0.72, '#5b6169');
    tilt.addColorStop(1.0, '#24282d');
    g.fillStyle = tilt; g.fillRect(0, 0, s, s);
    // Faces square to the camera: a slightly darker blue-grey, so that the bright fillet / silhouette band reads against it.
    const plateau = g.createRadialGradient(c, c, 0, c, c, c);
    plateau.addColorStop(0.0, 'rgba(114,124,138,1)');
    plateau.addColorStop(0.5, 'rgba(114,124,138,0.9)');
    plateau.addColorStop(0.82, 'rgba(114,124,138,0)');
    g.fillStyle = plateau; g.fillRect(0, 0, s, s);
    const key = g.createRadialGradient(s * 0.27, s * 0.24, 0, s * 0.27, s * 0.24, s * 0.3);
    key.addColorStop(0, 'rgba(255,247,236,0.95)');
    key.addColorStop(1, 'rgba(255,247,236,0)');
    g.fillStyle = key; g.fillRect(0, 0, s, s);
    const rim = g.createRadialGradient(c, c, s * 0.39, c, c, s * 0.5);
    rim.addColorStop(0, 'rgba(226,232,240,0)');
    rim.addColorStop(1, 'rgba(226,232,240,0.62)');
    g.fillStyle = rim; g.fillRect(0, 0, s, s);
    const warm = g.createRadialGradient(c, s * 0.02, 0, c, s * 0.02, s * 0.42);   // warm tint on up-facing bevels
    warm.addColorStop(0, 'rgba(255,214,170,0.35)');
    warm.addColorStop(1, 'rgba(255,214,170,0)');
    g.fillStyle = warm; g.fillRect(0, 0, s, s);
  });
}

/**
 * MatCap material for the engineering views. three.js derives the MatCap lookup from the direction to the camera at
 * each fragment, which is only right for perspective cameras: under an orthographic camera that direction changes across
 * the viewport, so one flat face would shade unevenly. The patch uses the constant view axis for orthographic cameras.
 */
export function studioMatcapMaterial(THREE, texture, extra = {}) {
  const material = new THREE.MeshMatcapMaterial({ matcap: texture, side: THREE.DoubleSide, toneMapped: false, ...extra });
  material.onBeforeCompile = (shader) => {
    shader.fragmentShader = shader.fragmentShader.replace(
      'vec3 viewDir = normalize( vViewPosition );',
      'vec3 viewDir = isOrthographic ? vec3( 0.0, 0.0, 1.0 ) : normalize( vViewPosition );');
  };
  material.customProgramCacheKey = () => 'studio-matcap-ortho-v1';
  material.userData.studioMatcap = true;
  return material;
}

/**
 * Perspective viewport background: a quiet warm centre falling off to a darker vignette, kept within ±20 of the
 * workspace grey (#414549) so the subject — not the backdrop — carries the contrast.
 */
export function viewportGradientTexture(THREE) {
  // Warm glow behind the subject (the reference's User Perspective), cooling to a dark vignette at the corners.
  return canvasTexture(THREE, 512, (g, s) => {
    const glow = g.createRadialGradient(s * 0.52, s * 0.56, 0, s * 0.5, s * 0.52, s * 0.74);
    glow.addColorStop(0.0, '#6b5646');
    glow.addColorStop(0.38, '#4f4a47');
    glow.addColorStop(0.75, '#3a3c40');
    glow.addColorStop(1.0, '#2c2e32');
    g.fillStyle = glow; g.fillRect(0, 0, s, s);
  });
}
