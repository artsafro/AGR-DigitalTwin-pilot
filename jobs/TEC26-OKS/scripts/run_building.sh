#!/usr/bin/env bash
# TEC26 one-building run (KPP1 recipe): Max dump -> master (source geometry, new UV) -> QA -> VPM package -> NPM atlas + package.
# Scope (Artem 2026-10-22): colour only; geometry/topology/UCX/IDs exactly as in the source, findings reported.
# Usage: run_building.sh <building dir, e.g. jobs/TEC26-OKS/AC08> <new output root> [npm prefix]
# Inputs: <building>/max-dump-*.json (dump_max_poly.py on a staged Max COPY) and <building>/vpm_textures.json.
# Every output directory is new (no overwrite, no rm); a failing step stops the run.
set -euo pipefail
S="$(cd "$(dirname "$0")" && (pwd -W 2>/dev/null || pwd))"
B="${1:?building dir}"
O="${2:?new output root}"
PFX="${3:-0000}"
BL="${BLENDER:-/c/Program Files/Blender Foundation/Blender 5.1/blender.exe}"
PY="${PY:-uv run python}"
SPEC="$B/vpm_textures.json"
DUMP="$(ls "$B"/max-dump-*.json)"
A="$($PY -c "import json,sys; print(json.load(open(sys.argv[1], encoding='utf-8'))['address'])" "$SPEC")"
[ ! -e "$O" ] || { echo "output root exists: $O" >&2; exit 1; }
mkdir -p "$O"
blender() { "$BL" --background --factory-startup --disable-autoexec --python-exit-code 1 "$@"; }
$PY "$S/make_textures.py" "$SPEC" "$O/textures-vpm"
$PY "$S/make_npm_atlas.py" "$SPEC" "$O/textures-npm"
mkdir "$O/build"
blender --python "$S/build_master.py" -- "$DUMP" "$SPEC" "$O/textures-vpm" "$O/build/${A}_VPM_master.blend" 2>&1 | grep -E "^BUILD"
blender "$O/build/${A}_VPM_master.blend" --python "$S/qa_master.py" -- "$O/build/qa_master.json" 2>&1 | grep -E "^QA-"
mkdir -p "$O/package-vpm/SM_${A}"
blender --python "$S/export_vpm.py" -- "$O/build/${A}_VPM_master.blend" "$O/package-vpm/SM_${A}" 2>&1 | grep -E "^EXPORT"
PYTHONIOENCODING=utf-8 $PY "$S/package_vpm.py" "$O/package-vpm/SM_${A}" "$O/textures-vpm" --no-geojson > /dev/null
mkdir -p "$O/package-npm/${PFX}_${A}"
blender --python "$S/export_npm.py" -- "$O/build/${A}_VPM_master.blend" "$SPEC" "$O/textures-npm" "$O/package-npm/${PFX}_${A}" "$PFX" 2>&1 | grep -E "^EXPORT"
$PY -c "import zipfile,sys,os; d=sys.argv[1]; z=zipfile.ZipFile(os.path.join(d,'..',sys.argv[2]+'.zip'),'x',zipfile.ZIP_DEFLATED); z.write(os.path.join(d,sys.argv[2]+'_01.fbx'),sys.argv[2]+'_01.fbx'); z.close()" "$O/package-npm/${PFX}_${A}" "${PFX}_${A}"
# quad review copies for 3ds Max (not a delivery)
mkdir -p "$O/max-review/vpm/SM_${A}" "$O/max-review/npm/${PFX}_${A}"
KEEP_QUADS=1 blender --python "$S/export_vpm.py" -- "$O/build/${A}_VPM_master.blend" "$O/max-review/vpm/SM_${A}" 2>&1 | grep -c "^EXPORT"
KEEP_QUADS=1 blender --python "$S/export_npm.py" -- "$O/build/${A}_VPM_master.blend" "$SPEC" "$O/textures-npm" "$O/max-review/npm/${PFX}_${A}" "$PFX" 2>&1 | grep -c "^EXPORT"
echo "RUN-OK $O"
# readback of both delivered ZIPs (copies; embedded images unpack inside readback/) and package QA
R="$O/readback"; mkdir "$R" "$R/vpm" "$R/npm"
$PY -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$O/package-vpm/SM_${A}.zip" "$R/vpm"
$PY -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$O/package-npm/${PFX}_${A}.zip" "$R/npm"
blender --python "$S/qa_readback.py" -- "$R/vpm/SM_${A}.fbx" "$R/vpm.readback.json" 2>&1 | grep -E "^READBACK"
blender --python "$S/qa_readback.py" -- "$R/npm/${PFX}_${A}_01.fbx" "$R/npm.readback.json" 2>&1 | grep -E "^READBACK"
$PY "$S/qa_packages.py" "$SPEC" "$O/package-vpm/SM_${A}.zip" "$R/vpm.readback.json" "$O/package-npm/${PFX}_${A}.zip" \
    "$R/npm.readback.json" "$O/textures-npm/npm_atlas.json" "$O/textures-vpm" "$O/textures-npm" "$DUMP" "$O/qa_packages.json"
echo "QA-OK $O"
