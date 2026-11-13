# Historical KPP1 package-v003 / R1-v002 — superseded

Current latest-R1 package, checks and owners: [latest/REPORT.md](latest/REPORT.md).
The following is retained verbatim as historical evidence, not current package instructions.

Cells: `oks-npm`, `oks-vpm`. Base: `7c944e21` (current pilot main at start).
Decision [D267], Artem 2026-11-13, owning card t_b937f6cd: assemble without the unavailable
approved Ground FBX or KPP1-specific area sheet; no synthetic Ground/site-wide area substitution.
This authorizes an incomplete package report, NOT a waiver of delivery checks.

## Inputs and one-command reproduction

Use the hash-pinned #1271 `site-v004` artifacts derived from `rerun-1230` R1 v002.
The three exact source SHA-256 values are in `build_package.py` and the prior site manifest.
No source, live Max scene, geometry, topology, UV, material-slot assignment or UCX was changed.
The command works on copies and refuses an existing destination or a source-tree alias:

```bash
uv run python jobs/KPP1/package-1278/build_package.py "G:/Мой диск/AGR-evidence/1255-kpp1-msk77/site-v004" "G:/Мой диск/AGR-evidence/1278-kpp1-package/package-v004"
```

The output parent already exists. `package-v004` above is an unused reproduction destination;
**the measured delivery candidate is `package-v003`**, in the same parent directory.
It contains two ZIPs, standalone GeoJSON, `assembly.json`, `SHA256SUMS.txt`.
Reproduction `repro-v003` is **5/5 byte-identical** to the five assembly outputs.
Fresh validator receipts added later are not assembly outputs. Source hashes rechecked before publication.
The build exit 0 means assembled, not accepted: the assembly receipt explicitly has `passed=false`.

[D262] remains unchanged: **approximate, ±0.1 m, fitted to customer NPM
0607_77_05_0009005_117_02; entrance orientation not independently confirmed**.
No 180-degree alternative. Zero **171.050 m**; insertion point **[8056.144, -9581.270]**.
The fit median 0.099 m is not its maximum (0.721 m) or a survey certificate.

## Repairs that are ours

1. NPM glass `M_Kpp_1_MainGlass_1` / opacity ~0.3 became `M_Glass_01` / **0.5**,
   with TransparencyFactor **0.5**. Narrow binary FBX 7400 property rewrite, not a DCC re-export.
   Independent Blender 5.1.2 parser: **409 elements compared, exactly 3 material-property
   differences**; all other decoded properties/arrays, geometry, normals, UV, indices,
   connections and embedded pixels identical. Native importer confirms glass alpha 0.5.
   `material-parity.json` binds the source/output FBX; NPM v002 and v003 ZIPs are byte-identical.
2. GeoJSON coordinate token `-9581.27` became `-9581.270`; semantic JSON unchanged.
   SINTEZ's raw-text precision error is gone; missing areas/FNO stay empty.
3. Four single-colour VPM Diffuse tiles 1004–1007 reduced **2048x2048 -> 256x256**
   under the placeholder rule. Their ERM/Normal were already 256x256 and remain byte-identical.
   All **12/12** triplet images verified single-colour with exactly preserved RGB;
   no resampling of detail. Unsupported tile/role, nonflat, alpha, partial and wrong-size input rejected.

VPM accounting: **23/23 members retained, 0 drops**, 18 unchanged byte-for-byte,
4 Diffuse PNG changes plus one lexically corrected GeoJSON. The VPM FBX is unchanged.
Territorial code **0000 remains a placeholder** per [D262]/[D235]; SINTEZ recommends 0607,
which is recorded, not silently substituted for the upload-issued code.

## Validation and before/after

Fresh ZIP readback with `validate_package --scene --json`, Blender 5.1.2, both profiles:
**exit 1, passed=false** before and after. Full per-finding observed values, limits and
statuses for all V001–V017: [CHECKS.md](CHECKS.md); raw `npm/vpm-before/after.json` adjacent.
Before = immutable package-v001; after = final package-v003. Passing stages cover implemented
subsets only; none is evidence that the unimplemented/manual parts ran.

```bash
uv run python tools/qa/validate_package.py "G:/Мой диск/AGR-evidence/1278-kpp1-package/package-v003/0000_Kpp_1.zip" --profile npm --scene --json
uv run python tools/qa/validate_package.py "G:/Мой диск/AGR-evidence/1278-kpp1-package/package-v003/SM_Kpp_1.zip" --profile vpm --scene --json
```

### Every remaining non-pass / missing input / owner

| Stage / profile | Value / status | Limit / missing input | Owner |
|---|---|---|---|
| V001 NPM | fail: 1 FBX, no `0000_Kpp_1_Ground.fbx` | 2..21, including approved Ground; unavailable per [D267] | Ground author; Artem coordinates |
| V011 VPM FNO | fail: `FNO_code=""`, `FNO_name=""` | mandatory classifier pair; upload-issued values, no invented code | SINTEZ after placement/upload [D220] |
| V011 VPM areas | fail: `s_obsh/s_naz/s_podz/spp_gns=""` | mandatory truthful KPP1-specific areas, not whole-site totals; unavailable per [D267] | Artem / architect |
| V003 both | not_run: quad work FBX not supplied | non-triangulated master, VPM faces <=4 m [D021]; R1 delivery FBX is triangulated | KPP1 master author / Artem |
| V004 NPM | review: 0 pairs <5 mm, 108 in 5–20 mm, 20266 >20 mm | co-directional clearance 5–20 mm; classify >20 mm; rotated lists not waived by [D256] | KPP1 geometry author; Artem review |
| V004 VPM | review: 0 pairs <5 mm, 166 in 5–20 mm, 107934 >20 mm | same; pair distances min/median/max 9.6005/7450/31170.3993 mm | KPP1 geometry author; Artem review |
| V010 VPM | not_run: UCX coverage/offset subset | independent coverage/offset evidence, reg p.34–37; no signed collision review | Artem / collision reviewer |
| V012 VPM | review: archive `SM_Kpp_1`, `_001` ambiguity | single OKS follows [D019]; naming-index checker cannot close this automatically | Validator maintainer; Artem review |
| V013 VPM | not_run: point vs survey subset | survey/DWG alignment and zero evidence; 0.5 m placement limit; approximate fit not certification | Artem / survey author; checker subset absent |
| V014 NPM | not_run: entire coordinate stage unimplemented | Moscow position/heights/plan angles, reg p.10; independent validation missing | Validator maintainer / Artem |
| V015 both | not_run: no signed architectural acceptance | silhouette/facades/materials/levels vs approved project; sign-off absent | Artem |
| V016 VPM | not_run: no signed collision acceptance | free passages and height-zone offsets, reg p.36–37 | Artem |
| V017 both | not_run: no signed placement acceptance | point/zero/orientation vs plan, <=0.5 m VPM; orientation not confirmed | Artem / survey author |
| xView VPM | fail: **99 faces / 0 vertices**, 154 face pairs | 0/0 at 5/2 mm; corrected geometry and native parity not supplied | KPP1 geometry author; Artem model review |
| Final AGR Tools | not_run | real Max final check, not substituted by offline evidence | Artem frees Max; AGR Tools operator |

NPM V004 distances min/median/max **13.695/6870.2359/31170.3557 mm**.
The issue's **112/12 faces** were measured on unplaced R1, not this final placed export.
Fresh placed-input xView before repairs: VPM 99/0 fail, NPM 0/0 pass. Corrected final NPM
xView is also 0/0 pass. No geometry was repaired, so neither difference is claimed as an
xView fix. This checker is orientation/float-storage-sensitive; a new native Max check remains needed.
VPM FBX is unchanged from measured placed input. Raw xView reports retained in durable evidence.

## SINTEZ diagnostic run (not final delivery gate)

Ran installed `bl_ext.user_default.sintez_agr_checker` via existing
`jobs/KPP1/scripts/run_agr_checker.py`, private Blender 5.1.2 `--background --factory-startup
--python-exit-code 1`, isolated versioned ZIP copies. No Max, preferences, install or upload changed.
This is a diagnostic requested by #1278, not a sign-off that bypasses visual-before-final-checker gates.
All three process exits **0**, checker `error=null`; failing/undefined checklist statuses are retained.

| Run | HP verified / failed / undefined | LP verified / failed / undefined | Boundary |
|---|---|---|---|
| sintez-v001, unmodified copies | 58 / 3 / 59 | 37 / 6 / 29 | Image subgroup remained undefined; not a complete clean baseline |
| sintez-v002, material/coordinate repair | 63 / 4 / 53 | 39 / 4 / 29 | Exposed four oversized flat Diffuse placeholders |
| sintez-v003, final | **64 / 3 / 53** | **39 / 4 / 29** | Placeholder error gone; not passed |

Every remaining SINTEZ fail:

| Stage | Value | Limit / missing input | Owner |
|---|---|---|---|
| HP/LP 2.1.1 (V001/signature) | `.sig` absent, checker labels failed with 0 errors and 1 recommendation | matching genuine UKEP file; no cryptographic validity asserted | Artem / applicant [D163] |
| HP 2.2.1 (V011) | empty FNO code | 3/6/9-digit classifier code; upload result absent | SINTEZ |
| HP 2.2.6 (V011) | FNO_code/name empty | truthful mandatory values | SINTEZ |
| LP 2.1.2 (V001) | 1 FBX | 2..21; approved Ground absent | Ground author |
| LP 2.1.6 (V001) | Ground absent | mandatory Ground | Ground author |
| LP 2.10.3.1 (V012) | code 0000; diagnostic suggests 0607 | upload-confirmed code; keep placeholder by [D262]/[D235] | SINTEZ / Artem |

53 HP and 29 LP undefined requirement IDs are listed in `sintez-v003-summary.json`;
these are manual/unmeasured, not passed. Recommendations for glass metallicity 0.84 and
h_abs literal 179.70 (current 179.7) remain advisory, not invented material/height changes.
FNO cannot be issued by this installed offline checker; no upload service credentials/approval used.

## RED/GREEN, probes and evidence

- `927caada` tests-first: **17 failed**, package command absent.
- `1dc13a1d` tests-first: **7 failed** (material/coordinate functions absent).
  Integration probe before wiring repairs: **1 failed / 23 passed**.
- `d17d6c52` tests-first: **17 failed** (placeholder repair absent).
- Repairs were exercised on real copied ZIPs; no checker thresholds or synthetic area values changed.
- Generated geometry-payload probe: seed **1278**, **64/64** opaque payloads unchanged.
- Native independent comparison: **409/409 elements** accounted, only 3 permitted property differences.
- Real deterministic reproduction: **5/5 assembly files identical**.
- Hostile classes: relative/source-tree/hardlink aliases rejected without writes; existing output and
  `.partial` sentinel preserved; changed input between snapshot reads rejected before output;
  fresh-process alias exits nonzero; failed delivery states never turned into pass; pinned source hashes
  reject stale/empty/partial/unsupported/NaN/Infinity/zero-byte input. Duplicate/missing package member
  validation exists in the immutable-source route; no externally configurable fallback material/slot.
- Initial Drive parent missing: WinError 3, self-repaired by creating the task's evidence parent;
  no source or pre-existing output overwritten. A scratch parity script initially assumed 12 changed
  PNGs; actual byte comparison showed only 4 changed (ERM/Normal already 256px), recorded correctly above.
- `check_ready_gate --issue 1278`: missing legacy intake headings (Inputs and versions; Evidence the PR
  must bring). Issue unchanged; optional CI ready gate omitted rather than fabricating a pass.
- Full suite, eval receipt and exact head evidence belong to the PR Author receipts.

Durable evidence: **`G:/Мой диск/AGR-evidence/1278-kpp1-package/`** and its root
`SHA256SUMS.txt`; local committed manifest `evidence-SHA256SUMS.txt` binds the files.
No binaries or LFS committed. Packaging readiness, machine diagnostics, manual acceptance and
publication remain separate; **NPM/VPM delivery passed=false**.
