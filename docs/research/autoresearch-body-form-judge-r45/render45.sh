#!/usr/bin/env bash
# Standing #45 render driver: 11 variants on the #41 rig, then compose. Usage: bash render45.sh
set -euo pipefail
E=C:/x/autoresearch-body-form-r45
ROOT=C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.worktrees/t_cda3b2af
B="C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"
cd "$E"
mkdir -p views comp
while read -r id variant param; do
  [ -z "$id" ] && continue
  if [ ! -f "comp/$id.png" ]; then
    "$B" --background --factory-startup --disable-autoexec --threads 1 --python-exit-code 1 \
      --python "$E/rig45.py" -- "$ROOT" "$E/inputs/A.fbx" "$variant" "$param" "$E/views/$id" 2>&1 | grep -E "RIG41_OK|Error|error" | tail -n 2
    python "$E/compose41.py" "$E/views/$id" "$E/comp/$id.png" | tail -n 1
  fi
done <<'EOF'
A A 0
W_recess P_recess 0.13
W_corner P_corner 0.80
P_recess_0.20 P_recess 0.20
P_recess_0.11 P_recess 0.11
P_recess_0.06 P_recess 0.06
P_recess_0.03 P_recess 0.03
P_corner_0.40 P_corner 0.40
P_corner_0.20 P_corner 0.20
P_corner_0.10 P_corner 0.10
P_corner_0.05 P_corner 0.05
EOF
echo RENDER45_DONE
