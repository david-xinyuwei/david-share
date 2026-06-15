#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PPTX="$SCRIPT_DIR/Azure-Agent-Skills-In-Action.pptx"
OUT_DIR="$SCRIPT_DIR/preview"
PDF="$OUT_DIR/Azure-Agent-Skills-In-Action.pdf"

mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/slide-*.png "$PDF"

try_libreoffice() {
  command -v libreoffice >/dev/null 2>&1 || return 1
  command -v pdftoppm >/dev/null 2>&1 || return 1

  if ! libreoffice --headless --convert-to pdf --outdir "$OUT_DIR" "$PPTX"; then
    return 1
  fi
  [[ -f "$PDF" ]] || return 1

  pdftoppm -png -r 120 "$PDF" "$OUT_DIR/slide"

  for file in "$OUT_DIR"/slide-*.png; do
    [[ -e "$file" ]] || continue
    base="$(basename "$file")"
    num="${base#slide-}"
    num="${num%.png}"
    printf -v padded "%02d" "$num"
    mv "$file" "$OUT_DIR/slide-$padded.png"
  done
}

try_powerpoint_com() {
  command -v powershell.exe >/dev/null 2>&1 || return 1
  command -v wslpath >/dev/null 2>&1 || return 1

  local win_pptx win_out win_script
  win_pptx="$(wslpath -w "$PPTX")"
  win_out="$(wslpath -w "$OUT_DIR")"
  win_script="$(wslpath -w "$SCRIPT_DIR/export_slide_preview.ps1")"

  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$win_script" -Pptx "$win_pptx" -OutDir "$win_out"
}

if try_libreoffice || try_powerpoint_com; then
  echo "Wrote slide preview PNGs to $OUT_DIR"
else
  echo "Failed to export slide previews. Install LibreOffice + poppler-utils, or run on Windows with PowerPoint installed." >&2
  exit 1
fi