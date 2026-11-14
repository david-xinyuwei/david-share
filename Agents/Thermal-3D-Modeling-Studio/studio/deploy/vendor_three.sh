#!/usr/bin/env bash
# Vendor three.js r160 (module build + the addons the generated scenes use) so the demo has no CDN dependency.
set -euo pipefail
VER="${THREE_VERSION:-0.160.0}"
DEST="${1:-$(dirname "$0")/../static/vendor/three}"
mkdir -p "$DEST/jsm/controls" "$DEST/jsm/exporters" "$DEST/jsm/utils" "$DEST/jsm/environments" "$DEST/jsm/loaders" "$DEST/jsm/geometries" \
         "$DEST/jsm/postprocessing" "$DEST/jsm/shaders" "$DEST/jsm/math"

fetch() { # $1 = path inside package, $2 = destination
  local rel="$1" out="$2" url
  for base in "https://cdn.jsdelivr.net/npm/three@${VER}" "https://unpkg.com/three@${VER}"; do
    url="$base/$rel"
    if curl -fsSL --retry 2 --max-time 60 "$url" -o "$out"; then echo "ok  $rel  ($(wc -c <"$out") bytes)"; return 0; fi
  done
  echo "FAILED $rel" >&2; return 1
}

fetch build/three.module.js                      "$DEST/three.module.js"
fetch examples/jsm/controls/OrbitControls.js     "$DEST/jsm/controls/OrbitControls.js"
fetch examples/jsm/environments/RoomEnvironment.js "$DEST/jsm/environments/RoomEnvironment.js"
fetch examples/jsm/exporters/GLTFExporter.js     "$DEST/jsm/exporters/GLTFExporter.js"
fetch examples/jsm/utils/BufferGeometryUtils.js  "$DEST/jsm/utils/BufferGeometryUtils.js"
fetch examples/jsm/utils/TextureUtils.js         "$DEST/jsm/utils/TextureUtils.js"
fetch examples/jsm/loaders/STLLoader.js          "$DEST/jsm/loaders/STLLoader.js"   # 轨 B STEP→STL preview
fetch examples/jsm/loaders/GLTFLoader.js         "$DEST/jsm/loaders/GLTFLoader.js"  # optional car-shell asset in system scenes + 轨 B B-rep glTF
fetch examples/jsm/geometries/RoundedBoxGeometry.js "$DEST/jsm/geometries/RoundedBoxGeometry.js"  # studio-kit.js filletBox()
# Engineering workspace: ambient occlusion in the perspective view (GTAOPass + its relative imports).
fetch examples/jsm/postprocessing/GTAOPass.js       "$DEST/jsm/postprocessing/GTAOPass.js"
fetch examples/jsm/postprocessing/Pass.js           "$DEST/jsm/postprocessing/Pass.js"
fetch examples/jsm/shaders/GTAOShader.js            "$DEST/jsm/shaders/GTAOShader.js"
fetch examples/jsm/shaders/PoissonDenoiseShader.js  "$DEST/jsm/shaders/PoissonDenoiseShader.js"
fetch examples/jsm/shaders/CopyShader.js            "$DEST/jsm/shaders/CopyShader.js"
fetch examples/jsm/math/SimplexNoise.js             "$DEST/jsm/math/SimplexNoise.js"
echo "three.js $VER vendored into $DEST"
