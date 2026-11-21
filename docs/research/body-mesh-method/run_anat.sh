#!/bin/bash
# #1742 loop-anatomy battery (read-only). Run from C:/x/body-mesh-research.
B="C:/Program Files/Blender Foundation/Blender 5.1/blender.exe"
S="$1"; O="${2:-anat}"
mkdir -p "$O"
run() { n=$1; shift; "$B" -b --factory-startup --python "$S" -- "$@" "$O/$n.json" 2>&1 | grep -E "^ANATOMY|^refused|Error" | sed "s/^/$n /"; }
run_ab() { n=$1; f=$2; shift 2; "$B" -b --factory-startup --python "$S" -- "$f" "$O/$n.json" "$@" 2>&1 | grep -E "^ANATOMY|^refused|rror" | sed "s/^/$n /"; }
run_ab g22_k1_etalon inputs/0707_Garibaldi_22_01.fbx --objects _001_Main --rejoin --zmin 217.64 --zmax 262.64 --step 3.0
run_ab g22_k2_etalon inputs/0707_Garibaldi_22_02.fbx --objects _002_Main --rejoin --zmin 217.64 --zmax 244.64 --step 3.0
run_ab g22_k3_etalon inputs/0707_Garibaldi_22_02.fbx --objects _003_Main --rejoin --zmin 217.64 --zmax 262.64 --step 3.0
run_ab g22_k2_v002r1 inputs/k2_v002r1_body_quad.fbx --step 3.0
run_ab 63A_v005 inputs/63A_Stage1_v005.fbx --step 3.15
run_ab 63C_v001 inputs/63C_stage1_QUAD.fbx --step 3.15
run_ab 63C_v002 inputs/63C_stage1_v002_QUAD.fbx --step 3.15
run_ab 63B_v004 inputs/63B_Stage1_v004.fbx --step 3.15
run_ab 63B_v005 inputs/63B_Stage1_v005.fbx --step 3.15
run_ab 63B_v006 inputs/63B_Stage1_v006.fbx --step 3.15
run_ab 63B_v007 inputs/63B_Stage1_v007.fbx --step 3.15
run_ab kpp1_delivered_full inputs/kpp1_delivered/SM_77_05_0009005_117_002.fbx --objects _002_Main --exclude Glass,UCX --rejoin --zmin 0 --step 3.9
run_ab kpp1_v004w7 inputs/kpp1_v004w7.fbx --objects SM_Kpp_1_Main --exclude Glass,UCX --zmin 0 --step 3.9
