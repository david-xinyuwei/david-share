"""Download three.js r160 (the module build and the addons the studio uses) into studio/static/vendor/three/.

    python tools/vendor_three.py            # download what is missing, verify every file
    python tools/vendor_three.py --check    # verify only; exit 1 if a file is missing or differs

Works on Windows, macOS and Linux with the Python standard library. Every file is pinned by SHA-256, so a changed
CDN response fails instead of being served to the browser. deploy/vendor_three.sh does the same download on the VM.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

VERSION = "0.160.0"
MIRRORS = (f"https://cdn.jsdelivr.net/npm/three@{VERSION}", f"https://unpkg.com/three@{VERSION}")
DEST = Path(__file__).resolve().parents[1] / "studio" / "static" / "vendor" / "three"
FILES = {  # package path -> (path under static/vendor/three, SHA-256)
    "build/three.module.js": ("three.module.js", "76dea8151bc9352aef3528b4262e249b2604f62543828328db978d060d61a495"),
    "examples/jsm/controls/OrbitControls.js": ("jsm/controls/OrbitControls.js", "5a44a9e86a2a0fb11933eed69bc2cd33c76a496854c1aed6ed776efa87d7b064"),
    "examples/jsm/environments/RoomEnvironment.js": ("jsm/environments/RoomEnvironment.js", "e21f41b7ef2016f2984a5d27850b42dffa797a6a194a138e288b06576d765a7b"),
    "examples/jsm/exporters/GLTFExporter.js": ("jsm/exporters/GLTFExporter.js", "f8a6eb87719e68c925fdf445014b5ead49cf779ae14e69c6cc1cb1dd4eae514d"),
    "examples/jsm/geometries/RoundedBoxGeometry.js": ("jsm/geometries/RoundedBoxGeometry.js", "d20aeaf7077c459a8d952d215738d7b44fba028440bb862d84b622a34f0c80bb"),
    "examples/jsm/loaders/GLTFLoader.js": ("jsm/loaders/GLTFLoader.js", "d073b438e6a07e1359741dd5d6c76c953420cc0d4fd84eb1bdde94315540e6a3"),
    "examples/jsm/loaders/STLLoader.js": ("jsm/loaders/STLLoader.js", "896d006a48b8f125385a485ccae154dadee801a953f0b45ceffe7ddd8a29ca93"),
    "examples/jsm/math/SimplexNoise.js": ("jsm/math/SimplexNoise.js", "9b8d541b77b0ddc79afaa6a1de8941452c191b8b9006f04e7b8fc422e2b263f7"),
    "examples/jsm/postprocessing/GTAOPass.js": ("jsm/postprocessing/GTAOPass.js", "5140b7cc63800381ced45bef3a7a55c471f4be3cd9eb70b947e7ebfbe92658c2"),
    "examples/jsm/postprocessing/Pass.js": ("jsm/postprocessing/Pass.js", "b3c6128340eaa37e40a6a2f1b738e894c855239417d50959759b34a2b5e89f92"),
    "examples/jsm/shaders/CopyShader.js": ("jsm/shaders/CopyShader.js", "4e3346db194db56a596cd074e9bdb39fb5eb52040c333e0d29dc4eb1324d3b1d"),
    "examples/jsm/shaders/GTAOShader.js": ("jsm/shaders/GTAOShader.js", "94edb1040c7b5e859b17c2817782c8e895118a2d824ed162cab187aa32cc5a15"),
    "examples/jsm/shaders/PoissonDenoiseShader.js": ("jsm/shaders/PoissonDenoiseShader.js", "3dab419b23529f8fd59e2713458502f9f51d2dd3af3e1285dc671fcc451d49fb"),
    "examples/jsm/utils/BufferGeometryUtils.js": ("jsm/utils/BufferGeometryUtils.js", "9be041e96308775d00e2695cc607645b9a9b64fd7c0e759dd8f7c00a8d92becb"),
    "examples/jsm/utils/TextureUtils.js": ("jsm/utils/TextureUtils.js", "1b84a7fde8745dd614f62b6ca8108b592144278c07891a0cbe8cdf8e15796efa"),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(package_path: str) -> bytes:
    errors = []
    for base in MIRRORS:
        try:
            with urllib.request.urlopen(f"{base}/{package_path}", timeout=60) as response:
                return response.read()
        except OSError as e:
            errors.append(f"{base}: {e}")
    raise RuntimeError(f"{package_path}: every mirror failed: {errors}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="verify only, download nothing")
    ap.add_argument("--dest", type=Path, default=DEST)
    a = ap.parse_args()
    bad = 0
    for package_path, (rel, want) in FILES.items():
        target = a.dest / rel
        if target.is_file() and sha256(target.read_bytes()) == want:
            print(f"ok       {rel}")
            continue
        if a.check:
            print(f"{'MISMATCH' if target.is_file() else 'MISSING '} {rel}")
            bad += 1
            continue
        data = fetch(package_path)
        if sha256(data) != want:
            print(f"MISMATCH {rel}: downloaded SHA-256 {sha256(data)} is not the pinned {want}")
            bad += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        print(f"fetched  {rel} ({len(data):,} bytes)")
    print(f"three.js {VERSION}: {len(FILES) - bad}/{len(FILES)} files verified in {a.dest}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
