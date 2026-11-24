#!/usr/bin/env bash
# Standing #47 render driver: A + 4 mesh-only variants on the #41/#45 rig, then compose. Usage: bash render47.sh
set -euo pipefail
E=C:/x/autoresearch-body-form-r47
ROOT=C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.worktrees/t_82c59435
B="C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"
cd "$E"
mkdir -p views comp
while read -r id variant param; do
  [ -z "$id" ] && continue
  if [ ! -f "comp/$id.png" ]; then
    "$B" --background --factory-startup --disable-autoexec --threads 1 --python-exit-code 1 \
      --python "$E/rig47.py" -- "$ROOT" "$E/inputs/A.fbx" "$variant" "$param" "$E/views/$id" 2>&1 | grep -E "RIG41_OK|Error|error" | tail -n 2
    python "$E/compose41.py" "$E/views/$id" "$E/comp/$id.png" | tail -n 1
  fi
done <<'EOF'
A A 0
N_tri N_tri 0
N_sub N_sub 0
N_jit_0.005 N_jit 0.005
N_jit_0.020 N_jit 0.020
EOF
echo RENDER47_DONE
