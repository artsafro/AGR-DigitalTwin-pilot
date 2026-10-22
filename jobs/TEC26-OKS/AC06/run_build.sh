#!/usr/bin/env bash
# AC06 uses AC08 recipe with a separate source-glass adapter. New root only.
set -euo pipefail
O="${1:?new output root}"
B="jobs/TEC26-OKS/AC06"
S="jobs/TEC26-OKS/scripts"
BL='C:/Program Files/Blender Foundation/Blender 5.1/blender.exe'
blender() { "$BL" --background --factory-startup --disable-autoexec --threads 1 --python-exit-code 1 "$@"; }
[ ! -e "$O" ] || { printf 'refusing existing root %s\n' "$O" >&2; exit 1; }
uv run python "$B/make_maps.py" "$B/vpm_textures.json" "$O"
blender --python "$B/build_ac06.py" -- "$B/max-dump-006.json" "$B/vpm_textures.json" "$O/textures-vpm" "$O/build"
M="$O/build/Prg_1_VPM_master.blend"
blender "$M" --python "$S/qa_master.py" -- "$O/qa_master.json"
blender --python "$S/export_vpm.py" -- "$M" "$O/package-vpm/SM_Prg_1"
uv run python "$S/package_vpm.py" "$O/package-vpm/SM_Prg_1" "$O/textures-vpm" --no-geojson
blender --python "$S/export_npm.py" -- "$M" "$B/vpm_textures.json" "$O/textures-npm" "$O/package-npm/0000_Prg_1" 0000
uv run python -c "import zipfile,sys; r=sys.argv[1]; z=zipfile.ZipFile(r+'/package-npm/0000_Prg_1.zip','x',zipfile.ZIP_DEFLATED); z.write(r+'/package-npm/0000_Prg_1/0000_Prg_1_01.fbx','0000_Prg_1_01.fbx'); z.close()" "$O"
mkdir -p "$O/readback/vpm" "$O/readback/npm"
uv run python -c "import zipfile,sys; r=sys.argv[1]; zipfile.ZipFile(r+'/package-vpm/SM_Prg_1.zip').extractall(r+'/readback/vpm'); zipfile.ZipFile(r+'/package-npm/0000_Prg_1.zip').extractall(r+'/readback/npm')" "$O"
blender --python "$S/qa_readback.py" -- "$O/readback/vpm/SM_Prg_1.fbx" "$O/readback/vpm.json"
blender --python "$S/qa_readback.py" -- "$O/readback/npm/0000_Prg_1_01.fbx" "$O/readback/npm.json"
blender --python "$B/render_facades.py" -- "$B/vpm_textures.json" "$O/readback/vpm/SM_Prg_1.fbx" "$O/textures-vpm" "$O/readback/npm/0000_Prg_1_01.fbx" "$O/renders"
printf 'AC06-BUILD-OK %s\n' "$O"
