# Artifact Name Contract Audit: KPP1 and PSU275 Pipelines

- **Reviewed baseline commit**: `96755146c38614596455d3d0cb85a544d29b7fe2`
- **Audit scope**: Static source reading of job scripts, test doubles, and configs for `jobs/KPP1` and `jobs/PSU275`.
- **Operating disclaimer**: Purely static investigation. No pipelines, tests, or DCC tools (Blender, 3ds Max) were executed. No `data/` directories were read or written. Geometry topology and delivery acceptance remain unverified. No synthetic outputs were fabricated.

## Summary

- Traced static source artifact paths across `jobs/KPP1` and `jobs/PSU275` shell pipelines and Python scripts.
- Inspected default path strings agree conditional on stages succeeding; no runtime verified.
- KPP1 stage 6 artifact `KPP1_VPM_v006_ucx.blend` encodes the stage number (`v006`), correctly consumed by downstream QA and export steps from the newly reserved build directory.
- KPP1 `run_stage.sh` accepts directory tokens from `run_all.sh`; its internal default `build-v001` applies only when invoked standalone.
- PSU275 passes explicit `.blend` paths via Bash positional parameters [1], aligning stage 5 and stage 6 producers and consumers.
- Mainline PSU275 NPM textures match between atlas generator and exporter; environment variable `PSU275_NPM_ADDRESS` applies consistently to both scripts.
- Discrepancy occurs if `PSU275_NPM_ADDRESS` differs from `ADDR`: archive stem `0000_$ADDR.zip` and internal member `0000_${PSU275_NPM_ADDRESS}_01.fbx` exhibit identity divergence (checker response unverified).
- Shared VPM exporter saves an auxiliary triangulated blend `KPP1_VPM_export_tri.blend` under PSU275 packaging, which has no downstream runtime consumer.

## Findings: Stage Contract Tables

### Directory Token Aliases

To maintain compact contract matrices, output directories are referenced by their shell variable aliases defined in `run_all.sh`:
- **KPP1 aliases** (`jobs/KPP1/scripts/run_all.sh`): `B="$O/build-$V"` ([`jobs/KPP1/scripts/run_all.sh:13`](../../jobs/KPP1/scripts/run_all.sh)), `P="$O/package-vpm-$V"` ([`jobs/KPP1/scripts/run_all.sh:14`](../../jobs/KPP1/scripts/run_all.sh)), `N="$O/package-npm-$V"` ([`jobs/KPP1/scripts/run_all.sh:15`](../../jobs/KPP1/scripts/run_all.sh)), `A="$O/npm-textures-$V"` ([`jobs/KPP1/scripts/run_all.sh:16`](../../jobs/KPP1/scripts/run_all.sh)), `S="$O/sintez-$V"` ([`jobs/KPP1/scripts/run_all.sh:17`](../../jobs/KPP1/scripts/run_all.sh)), `X="$O/max-$V"` ([`jobs/KPP1/scripts/run_all.sh:18`](../../jobs/KPP1/scripts/run_all.sh)).
- **PSU aliases** (`jobs/PSU275/scripts/run_all.sh`): `D="$O/build-$V"` ([`jobs/PSU275/scripts/run_all.sh:14`](../../jobs/PSU275/scripts/run_all.sh)), `P="$O/package-vpm-$V"` ([`jobs/PSU275/scripts/run_all.sh:14`](../../jobs/PSU275/scripts/run_all.sh)), `A="$O/npm-textures-$V"` ([`jobs/PSU275/scripts/run_all.sh:14`](../../jobs/PSU275/scripts/run_all.sh)), `N="$O/package-npm-$V"` ([`jobs/PSU275/scripts/run_all.sh:14`](../../jobs/PSU275/scripts/run_all.sh)), `S="$O/sintez-$V"` ([`jobs/PSU275/scripts/run_all.sh:14`](../../jobs/PSU275/scripts/run_all.sh)).

### 1. KPP1 Artifact Contract Matrix

| Stage | Produces Pattern & Producer `file:line` | Consumed By & Expected Pattern & `file:line` | Match |
|---|---|---|---|
| Run-Stage Handoff | `$B` dir token (`build-$V`) via positional parameter [1]<br>[`jobs/KPP1/scripts/run_all.sh:13`](../../jobs/KPP1/scripts/run_all.sh), [`jobs/KPP1/scripts/run_all.sh:20`](../../jobs/KPP1/scripts/run_all.sh) | `run_stage.sh` (`$BUILD`, standalone default `build-v001`); `build_kpp1.py` (`out`)<br>[`jobs/KPP1/scripts/run_stage.sh:8`](../../jobs/KPP1/scripts/run_stage.sh), [`jobs/KPP1/scripts/run_stage.sh:11-14`](../../jobs/KPP1/scripts/run_stage.sh), [`jobs/KPP1/scripts/build_kpp1.py:1096`](../../jobs/KPP1/scripts/build_kpp1.py) | Yes |
| Stage 6 (Master) | `$B/KPP1_VPM_v006_ucx.blend`<br>[`jobs/KPP1/scripts/build_kpp1.py:1144`](../../jobs/KPP1/scripts/build_kpp1.py) (`v006` is stage 6, not version) | QA & Exporters expect `$B/KPP1_VPM_v006_ucx.blend`<br>[`jobs/KPP1/scripts/run_all.sh:21-22`](../../jobs/KPP1/scripts/run_all.sh), [`jobs/KPP1/scripts/run_all.sh:24`](../../jobs/KPP1/scripts/run_all.sh), [`jobs/KPP1/scripts/run_all.sh:28`](../../jobs/KPP1/scripts/run_all.sh), [`jobs/KPP1/scripts/run_all.sh:35-36`](../../jobs/KPP1/scripts/run_all.sh) | Yes |
| Master Sidecar QA | `$B/KPP1_VPM_v006_ucx.qa.json`<br>[`jobs/KPP1/scripts/build_kpp1.py:1147`](../../jobs/KPP1/scripts/build_kpp1.py) | No subsequent automated consumer in this wrapper; terminal artifact | N/A (terminal) |
| QA Master Report | `$B/qa_master_v006.json`<br>[`jobs/KPP1/scripts/qa_master.py:238`](../../jobs/KPP1/scripts/qa_master.py) (run at [`jobs/KPP1/scripts/run_all.sh:21`](../../jobs/KPP1/scripts/run_all.sh)) | No subsequent automated consumer in this wrapper; terminal artifact | N/A (terminal) |
| QA Overlap Report | `$B/overlap_v006.json`<br>[`jobs/KPP1/scripts/qa_overlap.py:155`](../../jobs/KPP1/scripts/qa_overlap.py) (argv at [`jobs/KPP1/scripts/qa_overlap.py:120-121`](../../jobs/KPP1/scripts/qa_overlap.py), wrapper [`jobs/KPP1/scripts/run_all.sh:22`](../../jobs/KPP1/scripts/run_all.sh)) | No subsequent automated consumer in this wrapper; terminal artifact | N/A (terminal) |
| VPM Export | `$P/SM_Kpp_1/SM_Kpp_1.fbx`<br>[`jobs/KPP1/scripts/export_vpm.py:106`](../../jobs/KPP1/scripts/export_vpm.py) | VPM Packager expects `$P/SM_Kpp_1/SM_Kpp_1.fbx`<br>[`jobs/KPP1/scripts/package_vpm.py:20`](../../jobs/KPP1/scripts/package_vpm.py), [`jobs/KPP1/scripts/package_vpm.py:52-53`](../../jobs/KPP1/scripts/package_vpm.py) | Yes |
| VPM Metadata | `$P/export_meta.json`<br>[`jobs/KPP1/scripts/export_vpm.py:119`](../../jobs/KPP1/scripts/export_vpm.py) | VPM Packager expects `$(dirname $P/SM_Kpp_1)/export_meta.json`<br>[`jobs/KPP1/scripts/package_vpm.py:17`](../../jobs/KPP1/scripts/package_vpm.py) | Yes |
| VPM Thumbnail | `$P/thumbnail_256.jpg`<br>[`jobs/KPP1/scripts/export_vpm.py:63`](../../jobs/KPP1/scripts/export_vpm.py), [`jobs/KPP1/scripts/export_vpm.py:118`](../../jobs/KPP1/scripts/export_vpm.py) | VPM Packager expects metadata thumbnail path<br>[`jobs/KPP1/scripts/package_vpm.py:28`](../../jobs/KPP1/scripts/package_vpm.py) | Yes |
| VPM Aux Blend | `$P/KPP1_VPM_export_tri.blend`<br>[`jobs/KPP1/scripts/export_vpm.py:81-90`](../../jobs/KPP1/scripts/export_vpm.py), [`jobs/KPP1/scripts/export_vpm.py:120`](../../jobs/KPP1/scripts/export_vpm.py) | No subsequent automated consumer in this wrapper; terminal artifact | N/A (terminal) |
| VPM Package | `$P/SM_Kpp_1.zip`<br>[`jobs/KPP1/scripts/package_vpm.py:50`](../../jobs/KPP1/scripts/package_vpm.py) | Checker staging expects `$P/SM_Kpp_1.zip`<br>[`jobs/KPP1/scripts/run_all.sh:30`](../../jobs/KPP1/scripts/run_all.sh) | Yes |
| NPM Textures | `$A/T_Kpp_1_001_Main_{d,o}_1.png`, `npm_atlas.json`<br>[`jobs/KPP1/scripts/make_npm_atlas.py:57-62`](../../jobs/KPP1/scripts/make_npm_atlas.py) | NPM Exporter expects `$A/npm_atlas.json` and `$A/*.png`<br>[`jobs/KPP1/scripts/export_npm.py:28`](../../jobs/KPP1/scripts/export_npm.py), [`jobs/KPP1/scripts/export_npm.py:142-143`](../../jobs/KPP1/scripts/export_npm.py) | Yes |
| NPM Export | `$N/0000_Kpp_1/0000_Kpp_1_01.fbx`<br>[`jobs/KPP1/scripts/export_npm.py:172`](../../jobs/KPP1/scripts/export_npm.py) | Shell in-place zip expects `0000_Kpp_1_01.fbx`<br>[`jobs/KPP1/scripts/run_all.sh:29`](../../jobs/KPP1/scripts/run_all.sh) | Yes |
| NPM Package | `$N/0000_Kpp_1.zip`<br>[`jobs/KPP1/scripts/run_all.sh:29`](../../jobs/KPP1/scripts/run_all.sh) | Checker staging expects `$N/0000_Kpp_1.zip`<br>[`jobs/KPP1/scripts/run_all.sh:30`](../../jobs/KPP1/scripts/run_all.sh) | Yes |
| SINTEZ Ingestion | `$S/{SM_Kpp_1,0000_Kpp_1}.zip`<br>[`jobs/KPP1/scripts/run_all.sh:30`](../../jobs/KPP1/scripts/run_all.sh) | SINTEZ runner expects zip archives in directory `$S`<br>[`jobs/KPP1/scripts/run_agr_checker.py:32-34`](../../jobs/KPP1/scripts/run_agr_checker.py) | Yes |
| Quad Review Branch | `$X/vpm/SM_Kpp_1/SM_Kpp_1.fbx`, `$X/vpm/KPP1_VPM_export_tri.blend`<br>`$X/npm/0000_Kpp_1/0000_Kpp_1_01.fbx`, `$X/npm/KPP1_NPM_export_tri.blend`<br>[`jobs/KPP1/scripts/run_all.sh:34-36`](../../jobs/KPP1/scripts/run_all.sh), [`jobs/KPP1/scripts/export_vpm.py:106-120`](../../jobs/KPP1/scripts/export_vpm.py), [`jobs/KPP1/scripts/export_npm.py:172-181`](../../jobs/KPP1/scripts/export_npm.py) | No subsequent automated consumer in this wrapper; terminal artifact<br>(Retains `*_export_tri.blend` naming despite `KEEP_QUADS=1`) | N/A (terminal) |

### 2. PSU275 Artifact Contract Matrix

| Stage | Produces Pattern & Producer `file:line` | Consumed By & Expected Pattern & `file:line` | Match |
|---|---|---|---|
| Stage 5 (Shell+UV) | `$D/PSU275_VPM_stage5.blend`<br>[`jobs/PSU275/scripts/vpm_stage5.py:212`](../../jobs/PSU275/scripts/vpm_stage5.py) (argv at [`jobs/PSU275/scripts/run_all.sh:17`](../../jobs/PSU275/scripts/run_all.sh)) | Stage 6 (UCX) expects `$D/PSU275_VPM_stage5.blend`<br>[`jobs/PSU275/scripts/run_all.sh:18`](../../jobs/PSU275/scripts/run_all.sh) | Yes |
| Stage 5 Sidecar QA | `$D/PSU275_VPM_stage5.qa.json`<br>[`jobs/PSU275/scripts/vpm_stage5.py:213`](../../jobs/PSU275/scripts/vpm_stage5.py) | No subsequent automated consumer in this wrapper; terminal artifact | N/A (terminal) |
| Stage 6 (UCX) | `$D/PSU275_VPM_stage6_ucx.blend`<br>[`jobs/PSU275/scripts/vpm_ucx.py:53`](../../jobs/PSU275/scripts/vpm_ucx.py) (argv at [`jobs/PSU275/scripts/run_all.sh:18`](../../jobs/PSU275/scripts/run_all.sh)) | QA & Exporters expect `$D/PSU275_VPM_stage6_ucx.blend`<br>[`jobs/PSU275/scripts/run_all.sh:19-20`](../../jobs/PSU275/scripts/run_all.sh), [`jobs/PSU275/scripts/run_all.sh:22`](../../jobs/PSU275/scripts/run_all.sh), [`jobs/PSU275/scripts/run_all.sh:27`](../../jobs/PSU275/scripts/run_all.sh) | Yes |
| Stage 6 Sidecar UCX | `$D/PSU275_VPM_stage6_ucx.ucx.json`<br>[`jobs/PSU275/scripts/vpm_ucx.py:54`](../../jobs/PSU275/scripts/vpm_ucx.py) | No subsequent automated consumer in this wrapper; terminal artifact | N/A (terminal) |
| QA Master Blend | `$D/qa_master.json`<br>[`jobs/PSU275/scripts/qa_master_psu275.py:250`](../../jobs/PSU275/scripts/qa_master_psu275.py) (argv at [`jobs/PSU275/scripts/qa_master_psu275.py:37`](../../jobs/PSU275/scripts/qa_master_psu275.py), wrapper [`jobs/PSU275/scripts/run_all.sh:19`](../../jobs/PSU275/scripts/run_all.sh)) | No subsequent automated consumer in this wrapper; terminal artifact | N/A (terminal) |
| QA Overlap | `$D/overlap.json`<br>[`jobs/KPP1/scripts/qa_overlap.py:155`](../../jobs/KPP1/scripts/qa_overlap.py) (argv at [`jobs/KPP1/scripts/qa_overlap.py:120-121`](../../jobs/KPP1/scripts/qa_overlap.py), wrapper [`jobs/PSU275/scripts/run_all.sh:20`](../../jobs/PSU275/scripts/run_all.sh)) | No subsequent automated consumer in this wrapper; terminal artifact | N/A (terminal) |
| VPM Export | `$P/SM_$ADDR/SM_$ADDR.fbx`<br>[`jobs/KPP1/scripts/export_vpm.py:106`](../../jobs/KPP1/scripts/export_vpm.py) (default `ADDR=Psu_1` cited [`jobs/PSU275/vpm_textures.json:3`](../../jobs/PSU275/vpm_textures.json)) | Readback QA & Packager expect `$P/SM_$ADDR/SM_$ADDR.fbx`<br>[`jobs/PSU275/scripts/run_all.sh:23-24`](../../jobs/PSU275/scripts/run_all.sh), [`jobs/PSU275/scripts/package_vpm.py:20-55`](../../jobs/PSU275/scripts/package_vpm.py) | Yes |
| VPM Meta & Thumb | `$P/{export_meta.json,thumbnail_256.jpg}`<br>[`jobs/KPP1/scripts/export_vpm.py:63-119`](../../jobs/KPP1/scripts/export_vpm.py) | VPM Packager expects `$(dirname $P/SM_$ADDR)/export_meta.json` & thumb<br>[`jobs/PSU275/scripts/package_vpm.py:19-30`](../../jobs/PSU275/scripts/package_vpm.py) | Yes |
| VPM Readback QA | `$P/readback_qa.json`<br>[`jobs/KPP1/scripts/qa_master.py:238`](../../jobs/KPP1/scripts/qa_master.py) (invoked at [`jobs/PSU275/scripts/run_all.sh:23`](../../jobs/PSU275/scripts/run_all.sh)) | No subsequent automated consumer in this wrapper; terminal artifact | N/A (terminal) |
| VPM Aux Blend | `$P/KPP1_VPM_export_tri.blend`<br>[`jobs/KPP1/scripts/export_vpm.py:81-120`](../../jobs/KPP1/scripts/export_vpm.py) | No subsequent automated consumer in this wrapper; terminal artifact (local copy `export_vpm_psu275.py:128` not invoked by `run_all.sh:22`) | N/A (terminal divergence) |
| VPM Package | `$P/SM_$ADDR.zip`<br>[`jobs/PSU275/scripts/package_vpm.py:52`](../../jobs/PSU275/scripts/package_vpm.py) | Checker staging expects `$P/SM_$ADDR.zip`<br>[`jobs/PSU275/scripts/run_all.sh:29`](../../jobs/PSU275/scripts/run_all.sh) | Yes |
| NPM Textures | `$A/T_{a}_{nnn}_Main_{d,o}_1.png`, `npm_atlas.json`<br>[`jobs/PSU275/scripts/make_npm_atlas.py:55-62`](../../jobs/PSU275/scripts/make_npm_atlas.py) (default `Psu_1`) | NPM Exporter expects `$A/npm_atlas.json` and `$A/T_{A}_{NNN}_Main_{d,o}_1.png`<br>[`jobs/PSU275/scripts/export_npm.py:32-158`](../../jobs/PSU275/scripts/export_npm.py) | Yes (default; conditional spec-only override may break as section 3) |
| NPM Export | `$N/0000_$ADDR/{prefix}_{A}_{NN}.fbx`<br>[`jobs/PSU275/scripts/export_npm.py:188`](../../jobs/PSU275/scripts/export_npm.py) (default `0000_Psu_1_01.fbx`) | Shell in-place zip expects `*.fbx`<br>[`jobs/PSU275/scripts/run_all.sh:28`](../../jobs/PSU275/scripts/run_all.sh) | Yes |
| NPM Package | `$N/0000_$ADDR.zip`<br>[`jobs/PSU275/scripts/run_all.sh:28`](../../jobs/PSU275/scripts/run_all.sh) | Checker staging expects `$N/0000_$ADDR.zip`<br>[`jobs/PSU275/scripts/run_all.sh:29`](../../jobs/PSU275/scripts/run_all.sh) | Yes (conditional identity divergence) |
| SINTEZ Ingestion | `$S/{SM_$ADDR,0000_$ADDR}.zip`<br>[`jobs/PSU275/scripts/run_all.sh:29`](../../jobs/PSU275/scripts/run_all.sh) | SINTEZ runner expects zip archives in directory `$S`<br>[`jobs/KPP1/scripts/run_agr_checker.py:32-34`](../../jobs/KPP1/scripts/run_agr_checker.py) | Yes |

## Cross-Job Dependency Analysis

PSU275 reuses KPP1 modules through two active integration mechanisms:

```
PSU275 Pipeline (jobs/PSU275/scripts/run_all.sh)
├── Direct CLI Invocations (exact 4):
│   ├── jobs/KPP1/scripts/qa_overlap.py (line 20)
│   ├── jobs/KPP1/scripts/export_vpm.py (line 22)
│   ├── jobs/KPP1/scripts/qa_master.py (line 23)
│   └── jobs/KPP1/scripts/run_agr_checker.py (line 30)
│
├── Imported KPP1 Modules (exact 4):
│   ├── jobs/PSU275/scripts/vpm_stage5.py:21-23
│   │   ├── jobs/KPP1/scripts/seal.py (leaf imports: lines 19-21)
│   │   └── jobs/KPP1/scripts/vpm_uv.py (leaf imports: lines 15-17)
│   ├── jobs/PSU275/scripts/make_npm_atlas.py:23-24
│   │   └── jobs/KPP1/scripts/make_textures.py (leaf imports: lines 12-14)
│   └── jobs/PSU275/scripts/export_npm.py:26-27
│       └── jobs/KPP1/scripts/export_safety.py (leaf imports: lines 2-5)
│
└── Local Adaptations in jobs/PSU275/scripts/:
    ├── Called by run_all.sh: vpm_stage5.py (17), vpm_ucx.py (18), qa_master_psu275.py (19), package_vpm.py (24), make_npm_atlas.py (25), export_npm.py (27)
    └── Unused VPM Copy: export_vpm_psu275.py (not called by THIS wrapper; line 22 calls KPP1 export_vpm.py)
```

Each of the four imported KPP1 modules is a leaf module with respect to repository-job imports (they depend only on standard Python libraries or external/DCC packages, importing zero job scripts or `dt_ai` repository modules). Local adapted scripts are actively called by `jobs/PSU275/scripts/run_all.sh`, except `export_vpm_psu275.py` which is not called by this wrapper.

## Concrete Mismatches and Exact Evidence

### 1. Default Mainline Execution: Naming Agreement
- **KPP1 Run-Stage Directory Handoff and Output Reservations**: [`jobs/KPP1/scripts/run_all.sh:13`](../../jobs/KPP1/scripts/run_all.sh) defines `B="$O/build-$V"`. Prior to build execution, [`jobs/KPP1/scripts/run_all.sh:12`](../../jobs/KPP1/scripts/run_all.sh) executes reservation logic via `reserve_run` in [`jobs/KPP1/scripts/export_safety.py:21-46`](../../jobs/KPP1/scripts/export_safety.py), where fresh version-specific directories prevent old-version selection during full pipeline runs. In contrast, the standalone launcher ([`jobs/KPP1/scripts/run_stage.sh:8-14`](../../jobs/KPP1/scripts/run_stage.sh)) defaults to `build-v001` and does not enforce output freshness. In `run_all.sh` line 20, `BUILD` receives `"build-$V"` and passes `OUT="$J/outputs/$BUILD"` to [`jobs/KPP1/scripts/build_kpp1.py:1096-1144`](../../jobs/KPP1/scripts/build_kpp1.py). The builder evaluates `os.path.join(out, f"KPP1_VPM_v{stage:03d}_{STAGES[stage]}.blend")`. For stage 6, this formats as `KPP1_VPM_v006_ucx.blend`. The token `v006` designates stage 6, not the run version tag `$V`. Downstream consumers ([`jobs/KPP1/scripts/run_all.sh:21-22`](../../jobs/KPP1/scripts/run_all.sh), [`jobs/KPP1/scripts/run_all.sh:24`](../../jobs/KPP1/scripts/run_all.sh), [`jobs/KPP1/scripts/run_all.sh:28`](../../jobs/KPP1/scripts/run_all.sh), [`jobs/KPP1/scripts/run_all.sh:35-36`](../../jobs/KPP1/scripts/run_all.sh)) consume `$B/KPP1_VPM_v006_ucx.blend` directly from `$B`.
- **PSU275 Stage Handoff**: [`jobs/PSU275/scripts/run_all.sh:17-18`](../../jobs/PSU275/scripts/run_all.sh) passes explicit `.blend` paths via Bash positional parameters [1], identically consumed at lines 19-20, 22, and 27. Default address token `Psu_1` is cited in [`jobs/PSU275/vpm_textures.json:3`](../../jobs/PSU275/vpm_textures.json); KPP1 address token `Kpp_1` is cited in [`jobs/KPP1/scripts/build_kpp1.py:29-31`](../../jobs/KPP1/scripts/build_kpp1.py) and [`jobs/KPP1/scripts/vpm_textures.json:3`](../../jobs/KPP1/scripts/vpm_textures.json).

### 2. Auxiliary Artifact Name Divergence in Shared Exporter
- **Location**: [`jobs/KPP1/scripts/export_vpm.py:81-120`](../../jobs/KPP1/scripts/export_vpm.py).
- **Behavior**: When invoked by [`jobs/PSU275/scripts/run_all.sh:22`](../../jobs/PSU275/scripts/run_all.sh), the exporter triangulates meshes (lines 81-90) and writes an auxiliary triangulated blend to `os.path.join(pkg, "..", "KPP1_VPM_export_tri.blend")` (line 120). It is not an untriangulated backup.
- **Quad review branch**: In KPP1 review runs with `KEEP_QUADS=1` ([`jobs/KPP1/scripts/run_all.sh:35`](../../jobs/KPP1/scripts/run_all.sh)), triangulation is skipped, but line 120 still saves under the literal name `KPP1_VPM_export_tri.blend` inside `$X/vpm` (and `export_npm.py:181` saves `KPP1_NPM_export_tri.blend` inside `$X/npm`).
- **Packaging behavior**: Downstream [`jobs/PSU275/scripts/package_vpm.py:19-55`](../../jobs/PSU275/scripts/package_vpm.py) reads `export_meta.json` (line 19) and `thumbnail_256.jpg` (line 30) from the parent directory, but archives the package child directory only (`pkg`). When `--no-geojson` is passed, generated JSON files stay in the parent; the ZIP holds FBX and PNGs only.
- **Classification**: Auxiliary naming divergence without runtime consumers; N/A not a broken contract. Local adapted copy [`jobs/PSU275/scripts/export_vpm_psu275.py:128`](../../jobs/PSU275/scripts/export_vpm_psu275.py) writes `PSU275_VPM_export_tri.blend` but is not called by this wrapper.

### 3. Conditional Environment Override Risk
- **Locations**: [`jobs/PSU275/scripts/make_npm_atlas.py:32-34`](../../jobs/PSU275/scripts/make_npm_atlas.py) and [`jobs/PSU275/scripts/export_npm.py:49`](../../jobs/PSU275/scripts/export_npm.py).
- **Behavior**: On mainline execution, both scripts default to address `Psu_1` and match. If `PSU275_NPM_ADDRESS` is supplied, both scripts use it consistently, preserving texture filename alignment.
- **Identity divergence**: Shell wrapper [`jobs/PSU275/scripts/run_all.sh:16-29`](../../jobs/PSU275/scripts/run_all.sh) extracts `ADDR` exclusively from `vpm_textures.json:3`. If `PSU275_NPM_ADDRESS` differs from `ADDR`:
  - `export_npm.py` creates `0000_${PSU275_NPM_ADDRESS}_01.fbx` inside `$N/0000_$ADDR`.
  - Shell line 28 runs `glob.glob('*.fbx')` followed by selection of its first result, which successfully matches the FBX file (no missing file), packaging it into `../0000_$ADDR.zip`.
  - Archive name (`0000_$ADDR.zip`) and contained member stem (`0000_${PSU275_NPM_ADDRESS}_01.fbx`) exhibit identity divergence. Only static divergence is demonstrated; SINTEZ checker response remains unverified.
- **Atlas spec risk**: If `PSU275_SPEC` changes the texture spec address while the master blend retains its original address and no explicit `PSU275_NPM_ADDRESS` is provided, atlas and exporter image stems may diverge. This risk is conditional only.

## How It Applies to This Repository

- **KPP1 Open Acceptance Gates ([`docs/PROJECT_STATE.md:15-22`](../PROJECT_STATE.md))**: KPP1 delivery gates require a real `run_all.sh` run on a new version (e.g. v007). Static reading shows that the output directory reservation mechanism ([`jobs/KPP1/scripts/export_safety.py:21-46`](../../jobs/KPP1/scripts/export_safety.py) + [`jobs/KPP1/scripts/run_all.sh:12`](../../jobs/KPP1/scripts/run_all.sh)) refuses already occupied run directories before building; stage 6 naming (`KPP1_VPM_v006_ucx.blend`) connects to downstream QA and packaging. This is not evidence of a successful live run.
- **PSU275 Open Real-Run Gates ([`docs/PROJECT_STATE.md:15-22`](../PROJECT_STATE.md))**: PSU275 (delivery-v003) retains open gates for address resolution and SINTEZ acceptance. On default runs, artifact paths align; however, if `PSU275_NPM_ADDRESS` diverges from `ADDR`, archive and member stems diverge before SINTEZ ingestion. This gate must be addressed before unblocking official delivery passes.
- **Job Scripts Coupling vs Shared Library**: The scripts under `jobs/KPP1` and `jobs/PSU275` operate as tightly coupled, per-job procedural runners rather than a unified shared library (demonstrated by 4 direct cross-job CLI calls, 4 leaf imports, and unused local adaptations like `export_vpm_psu275.py`). No production code fixes or refactoring are introduced in this research audit; all findings document current static contracts for upcoming tracked tasks.

## Existing Test Coverage and Secondary Observations

1. **Existing Shell Test Coverage**: [`tests/test_kpp1_export_safety.py:97-163`](../../tests/test_kpp1_export_safety.py) provides fixture `shell_run`, verifying that shell scripts execute real entry points against synthetic process doubles. However, at line 135, the mock Blender script synthesizes the master blend by writing a literal string `"KPP1_VPM_v006_ucx.blend"` to the output directory argument (the third positional CLI parameter after the separator in the mock double), rather than evaluating the dynamic filename expression in `build_kpp1.py`.
2. **Secondary DCC Observation (Seen-Not-Mine)**: In [`jobs/PSU275/scripts/run_all.sh:11`](../../jobs/PSU275/scripts/run_all.sh), `BL` points to Blender 4.4 (`/c/Program Files/Blender Foundation/Blender 4.4/blender.exe`). Current execution policy (`COORDINATION_RULES.md` rule 17) sets Blender 5.1.2; shell paths referencing `Blender 5.1` (such as `BL51` at line 12 and in KPP1) do not themselves prove the patch version. Recorded per seen-not-mine policy; no correction applied.

## Proposed Contract Test Tasks

### Task 1: AST-Only Contract Test for Stage Blend Filename Mapping
- **Effort**: Small (S) | **Value**: Medium (M).
- **Value Rationale**: Prevents silent stage filename drift that breaks downstream packaging without requiring DCC/bpy execution.
- **Scope**: Future tests must evaluate REAL source expressions via restricted AST or extracted pure helper, not duplicate expected logic. Parse [`jobs/KPP1/scripts/build_kpp1.py`](../../jobs/KPP1/scripts/build_kpp1.py) using the Python `ast` module without importing `bpy` or executing `main()`. Extract the `STAGES` dictionary (line 1092) and filename format expression `f"KPP1_VPM_v{stage:03d}_{STAGES[stage]}.blend"` (line 1144). Assert full stages 1..6 mapping (`v001_body.blend` through `v006_ucx.blend`), and evaluate stage 6 path for versions `v002` and `v007`, confirming consistent mapping to `KPP1_VPM_v006_ucx.blend`.
- **Future Criteria**:
  - RED: Fails if AST fails to locate `STAGES` or formatting logic in real source expressions, or if stage 6 resolves to anything other than `KPP1_VPM_v006_ucx.blend` in `$B`.
  - GREEN: Passes when all stages 1..6 map to exact expected blend filenames and stage 6 matches `run_all.sh` expectations regardless of version tag parameter.
- **Constraints**: No data, no DCC, no runtime execution. Future criteria defined; no tests implemented now.

### Task 2: Static Matrix Contract Test for Address Parity and Glob Ambiguity
- **Effort**: Medium (M) | **Value**: Medium (M).
- **Value Rationale**: Catches archive-internal file identity parity divergence and ambiguous glob patterns before submitting packages to the SINTEZ AGR checker.
- **Scope**: Evaluate address and artifact path agreement across default and environment override permutations (`PSU275_NPM_ADDRESS`, `PSU275_SPEC`) against synthetic dictionary inputs and paths. Emphasize that an architectural decision is required on whether to officially support environment overrides or reject them before implementing any code fix; no executable model is invented here. Future tests must evaluate REAL source expressions / pure helpers rather than duplicate expected logic, verifying fail-closed handling for the shell one-FBX glob (`glob.glob('*.fbx')` in [`jobs/PSU275/scripts/run_all.sh:28`](../../jobs/PSU275/scripts/run_all.sh)) when zero or multiple `.fbx` files are present.
- **Future Criteria**:
  - RED: Fails if archive stem and contained member FBX name diverge under environment overrides, or if zero or multiple FBX files fail to trigger a fail-closed error.
  - GREEN: Passes when the static matrix confirms stem parity across all outputs once policy is decided, and zero/multiple FBX scenarios trigger explicit fail-closed exceptions.
- **Constraints**: No data, no DCC, no runtime execution. Future criteria defined; no tests implemented now.

### Task 3: AST and Shell Source Dependency Inventory Contract Test
- **Effort**: Small (S) | **Value**: Small (S).
- **Value Rationale**: Prevents accidental drift and unvetted additions to cross-job imports between KPP1 and PSU275.
- **Scope**: Static inspection of [`jobs/PSU275/scripts/run_all.sh`](../../jobs/PSU275/scripts/run_all.sh) CLI invocations and AST parsing of PSU script imports. Future tests must evaluate REAL source expressions and imports rather than hardcoding duplicate expectations. Verifies the exact inventory of four direct CLI calls and four imported KPP1 modules. Detects accidental changes to invocation targets (e.g. switching between shared KPP1 exporter and local PSU exporter) and asserts the auxiliary `.blend` naming policy.
- **Future Criteria**:
  - RED: Fails if any of the four direct CLI calls or four module imports change target, are removed, or if unverified cross-job imports are added.
  - GREEN: Passes when the dependency graph matches the exact 4 direct + 4 imported inventory without unapproved drift.
- **Constraints**: No data, no DCC, no runtime execution. Future criteria defined; no tests implemented now.

## Open Questions for the User

1. **Advisory (NPM Archive Multi-OKS Naming)**: In multi-OKS production setups where secondary structures use distinct NPM addresses, should shell packaging in [`jobs/PSU275/scripts/run_all.sh:28`](../../jobs/PSU275/scripts/run_all.sh) accept an explicit NPM address parameter for the archive name, noting that VPM `ADDR` and NPM address may intentionally differ in multi-OKS scenarios?
2. **Advisory (PSU275 Exporter Routing)**: Should [`jobs/PSU275/scripts/run_all.sh:22`](../../jobs/PSU275/scripts/run_all.sh) be updated to invoke the local adapted copy [`jobs/PSU275/scripts/export_vpm_psu275.py`](../../jobs/PSU275/scripts/export_vpm_psu275.py) (which outputs `PSU275_VPM_export_tri.blend` and supports `PSU275_VPM_PIVOT`), or should `export_vpm.py` in KPP1 remain the shared exporter?

## Sources

[1] https://www.gnu.org/software/bash/manual/html_node/Positional-Parameters.html — Bash positional parameters
