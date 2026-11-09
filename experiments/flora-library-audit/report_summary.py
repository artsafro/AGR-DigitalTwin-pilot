"""Generate the measurement summary from catalogue and independently checked receipt."""
import argparse
import ast
import json
from pathlib import Path
from catalogue import species_keys

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--partial', action='store_true')
    args = ap.parse_args()
    catalog = json.loads((HERE / 'catalogue.json').read_text(encoding='utf-8'))
    receipt_name = 'partial-verification.json' if args.partial else 'verification.json'
    verified = json.loads((HERE / receipt_name).read_text(encoding='utf-8'))
    comp = catalog['project_vs_library']
    out = ['# Flora library audit: catalogue and triangle budgets (#189)', '',
        '## Question and scope', '',
        'Audit the supplied Max library and FLORIO set without inventing species identity: enumerate every label, compare XY nearest pairing against bounded display-row pairing, export every plant variant, and read the outputs back.',
        'This is a source audit, not a passed AGR delivery. No new species/textures, original-scene edits, standards changes or production checker changes.', '',
        '## Setup and commands', '',
        '- Headless 3ds Max 2026.3 (28.3.0.30732), embedded Python 3.11.12, via `dcc_batch.py max` only, one locked batch at a time. No live bridge/safe-mode changes.',
        '- Both originals were hashed before copying to `C:/x/t_366e8d9d/`; Max loads only those copies. Both scenes report meters, SystemScale 1 and one scene unit per metre.',
        '- Native entry points: `tools/max_flora_inventory.py`, `tools/max_flora_archive.py`. Pure analysis and reproduction commands: [README](../../experiments/flora-library-audit/README.md).',
        '- Actual FBX outputs: `C:/x/t_366e8d9d/out/assets-v003/`; corrected SVG previews and coordinate-verified receipts: `out/verified-v004/`. FBX 2014 / 7.4 binary. No binaries in Git.',
        '- Machine [catalogue](../../experiments/flora-library-audit/catalogue.json); schema/fields in README; complete [findings](flora-library-audit-findings.md).',
        '- Source method context: [Max scripting research](../research/3dsmax-scripting.md), `tools/max_profile_roundtrip.py`, user Flora grilling notes (2026-10-15 [D099, D100, D101, D102]).',
        '- Startup warning: `polyunwrapper_autoload.mse` CLR error returns native -130; the wrapper classifies it as a warning. Current job markers/receipts and independent hash/readback checks determine completion, not native exit alone. Legacy mental-ray attributes are unavailable.', '',
        '## Counts and interpretation', '',
        '| Source | All nodes | Text / TextPlus | All meshes / plant | Paired labels | Ambiguous | Orphan incl headings | Normalized captions | NPM / VPM candidates |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---|']
    for scene, counted in zip(catalog['scenes'], verified['label_accounting']):
        entries = scene['entries']
        textplus = sum(l['class'] == 'TextPlus' for l in scene['labels'])
        names = set().union(*(species_keys(e) for e in entries))
        vals = [Path(scene['source']['scene']).name, sum(scene['counts'].values()),
                f"{len(scene['labels'])-textplus} / {textplus}", f"{len(entries)+sum(bool(n['triangles']) for n in scene['excluded_nodes'])} / {len(entries)}", counted.get('paired',0), counted.get('ambiguous',0),
                counted.get('unpaired',0)+counted.get('category_heading',0), len(names),
                f"{sum('NPM' in e['profile_candidates'] for e in entries)} / {sum('VPM' in e['profile_candidates'] for e in entries)}"]
        out.append('| ' + ' | '.join(map(str, vals)) + ' |')
    out += ['', 'The 80 display slots are not 90 proven unique species. Normalized caption counts include cultivar-only strings and project multiline alternatives; see the complete names in findings. LP -> HP entries overlap both descriptive profiles. NPM/VPM candidates are not conformity assertions.',
        'Library nonplants: 80 Box envelopes, five planters, four size cylinders, one helper; all retained under `excluded_nodes`. Every Box has 20 triangles, Multi_Ground and a bbox top at/below placement Z within 1mm; its display-plinth role remains unverified.',
        'Library species/profile labels contain no height/crown dimensions. Project Hnnn tokens assume cm explicitly (unverified); all alternatives and >10% mismatches are retained. Hidden TextPlus uses the static GetPlaintextString by-reference adapter. No raw caption is repaired.', '',
        '## Baseline versus prototype', '',
        'Same extracted nodes and exclusions; median of three pairing runs, excluding Max startup, I/O and scene loading. Concordance means agreement with a literal triangle-count label, not independently established botanical correctness.', '',
        '| Source | Method | Median s | Unique / ambiguous | Triangle-label concordance |', '|---|---|---:|---|---|']
    for row in catalog['pairing_comparison']:
        out.append(f"| {row['scene']} | {row['plane']} | {row['median_seconds']:.7f} | {row['unique_labels']} / {row['ambiguous_labels']} | {row['unique_triangle_concordance']} / {row['triangle_labels']} |")
    tree = ast.parse((HERE / 'catalogue.py').read_text(encoding='utf-8'))
    loc = {n.name:(n.end_lineno or n.lineno)-n.lineno+1 for n in tree.body if isinstance(n, ast.FunctionDef)}
    out += ['', f"Pairing function size: XY baseline `pair` {loc['pair']} lines; bounded row prototype `row_pair` {loc['row_pair']} lines. It adds row/right selection, bounded nearest fallback and <=20% distance ties. In this library labels sit below mesh pivots in XZ, so fallback is intentional; FLORIO is a left-hand XY schedule with two high/low columns, retained together by Y row. Conflicting same-role captions are ambiguous; identical Text/TextPlus duplicates corroborate rather than compete.",
        'All ambiguous pairs, headings, orphan notes and unlabelled plant names are enumerated in the generated findings; no silent nearest-first resolution. Three ordinary source count discrepancies remain: SM_klen_tatarsky001 (1901 label / 1091 measured), Object002 (10 / 8), co-located SM_boyaryshnyck_obyknovennyi001 (488 / 574).', '',
        '## Triangle statistics and proposed budgets', '',
        '| Type | Profile | n | Min | Median | p90 nearest-rank | Max | Review above |', '|---|---|---:|---:|---:|---:|---:|---:|']
    for b in catalog['proposed_budgets']:
        if b['profile'] != 'unknown' and b['type'] in ('tree','bush','hedge'):
            out.append('| ' + ' | '.join(str(b[k]) for k in ['type','profile','n','min','median','p90','max','proposed_review_above']) + ' |')
    out += ['', 'Review thresholds round the observed maximum up to 100, rather than failing the upper 10% of the current library. p90 is descriptive. No hedge samples means no hedge budget. Bush includes ornamental perennials. These are not regulation limits or a checker change: NPM Ground+GroundEl+Flora still share 180k triangles; VPM Ground limits depend on area and unresolved regulation conflicts.', '',
        '### Project comparison statistics (not new budgets)', '',
        '| Type | Profile | n | Min | Median | p90 | Max |', '|---|---|---:|---:|---:|---:|---:|',
        *['| ' + ' | '.join(str(b[k]) for k in ['type','profile','n','min','median','p90','max']) + ' |' for b in catalog['project_statistics'] if b['profile'] in ('NPM','VPM') and b['type'] in ('tree','bush','hedge','climber')], '',
        '## Library versus FLORIO', '',
        f"Exact normalized captions: {len(comp['shared_species_names'])} shared, {len(comp['library_only_species_names'])} library-only, {len(comp['project_only_species_names'])} project-only. Project variants with name candidates: {sum(bool(r['library_name_candidates']) for r in comp['entries'])}/46; with exact-triangle and bbox-within-20% candidates: {sum(bool(r['dimension_and_triangle_candidates']) for r in comp['entries'])}/46. Exact mesh-name matches: {len(comp['exact_mesh_name_matches'])}.",
        'Full name lists and per-entry candidates are in findings/JSON. No synonym, typo or cultivar normalization beyond case/yo-e is invented. Candidates are not approved replacements.', '',
        '## Native archive and independent verification', '',
        f"**Acceptance complete: {verified['acceptance_complete']}.** Exports/previews: {verified['export_count']}/136; native readbacks: {verified['readback_count']}/136; exact-with-tolerance readback checks equal: {verified['readbacks_equal']}; failed IDs: {verified['failed_readback_ids']}.", '',
        '| Native variant | Observed result |', '|---|---|',
        '| MAX v001 baseline | 9 saves, median 47.043s between saves; cancelled, no readback; retained outside Git |',
        '| FBX v002 early attempt | 1 file + SVG before cancellation, no readback; retained unverified |',
        '| FBX v003 | 136 exports + 136 initial readbacks; six apparent mismatches exposed a double-transform bug in the measurement, not promoted as a pass |',
        f"| Final selected versions (see artifact_basis in JSON) | Median selected export+preview {verified['median_export_and_preview_seconds']}s; corrected signature+preview {verified['median_corrected_signature_preview_seconds']}s; native readback {verified['median_readback_seconds']}s; maximum matched-corner deviation {verified['max_matched_corner_deviation_mm']}mm |", '',
        f"Corrected native source snapshot bboxes agree with independent nodeGetBoundingBox (maximum {verified['source_snapshot_bbox_max_error_mm']}mm); maximum matched UV deviation {verified['max_uv_deviation']}. `tools/max_flora_verify.py` first checks a translated/rotated SYNTHETIC mesh, then every real source and imported object. `snapshotAsMesh` vertices are already world coordinates here: multiplying node.transform again created placement-dependent errors. The correction removes that multiplication, preserves the FBX bytes, regenerates previews to a new version and repeats every readback without relaxing the matcher tolerance.",
        f"Selected artifact routes: {verified.get('artifact_basis_counts',{})}. The v004 coordinate correction alone left five genuine polygon-corner/winding or affine-transform conversion failures. Tree_LP changed from 2075/3065 matching triangles to 3065/3065 after an isolated Editable Mesh snapshot (v006, 0mm max). Full-scene snapshot export v005 stalled without an output and was cancelled; its exact blocked API phase was not instrumented. Four flowers retain shear in snapshot NODE transforms; their FBX bboxes change even though source/snapshot match. The separate v007 variant creates `mesh(mesh=world_TriMesh_value)` at identity, checks equality before export and reads each file back. No old file is overwritten; any failed/pending rows keep acceptance_complete=false. Maximum deviation above covers equal rows only when the audit is incomplete.",
        'Autodesk reference for snapshot/node versus TriMesh-value construction: https://help.autodesk.com/cloudhelp/2017/ENU/MAXScript-Help/files/GUID-0532C071-4401-4846-8450-3DA5510A3883.htm (native behavior tested in Max 2026). World geometry, not original pivot/matrix identity, is preserved in derived exports.',
        'Readback is native Max FBX import into a reset headless scene, one geometry object per file, binary header/version independently checked. The bijective matcher checks every triangle/cyclic corner (preserving winding), world positions, per-corner UV and finish material names, plus bitmap-reference equality and metre units. It does not certify shading/smoothing, topology quality of the originals, texture pixels or botanical appearance.',
        'All stored bitmap references were unresolved in the source inventory. Atlas use is reference sharing only; no atlas pixel/UV-island validation is claimed. Previews are actual untextured native-mesh XZ wireframes, not rendered/opacity appearance approval. Materials are not repathed and no textures are generated.',
        f"Native wrapper wall times including startup/shutdown: original v003 archive+first readbacks {verified.get('native_export_runner',{}).get('seconds')}s; v004 source-probe/signature/corrected-readback job {verified.get('native_runner',{}).get('seconds')}s. Per-asset medians above are a heterogeneous workload distribution, not a controlled cold/warm or MAX/FBX speedup claim.",
        'The v003 first two exports measured 156.85s and 97.56s; later calls were materially faster. The initial abort-based extrapolation from a cold first file was not representative. Per-row checkpoints preserve progress and source/artifact hashes; repeating the same command skips only verified receipts. Cause of the cold delays is not proven.', '',
        f"Independent receipt: [{receipt_name}](../../experiments/flora-library-audit/{receipt_name}). Both original hashes were re-read after the archive audit; copied scenes are equal too.", '',
        '| Source | Bytes | SHA-256 before | SHA-256 after |', '|---|---:|---|---|']
    for source in verified['source_integrity']:
        out.append(f"| {Path(source['copy']).name} | {source.get('bytes',source.get('size'))} | `{source['sha256']}` | `{source['sha256_after_audit']}` |")
    out += ['', '## Invariants', '',
        '- Original untouched: two original/copy hash equalities; generated synthetic hash probe mutates a copy 30 times and proves the reference unchanged; hostile-path probe rejects 100 traversals.',
        '- Every Text accounted: library 326 = 319 paired + 4 ambiguous + 3 explicit orphan/non-asset records; project 23 = 0 + 23 + 0. Synthetic competing-caption/accounting probe covers 21 translated layouts; every candidate resolves to a plant handle.',
        '- No binaries committed: actual diff/untracked-path scan rejects native/image extensions and NUL bytes, plus generated probes for seven binary/image suffixes and disguised NUL text. Final Git diff check is also recorded in the PR.',
        '- Resume safety: synthetic checkpoint probe rejects changed source hashes and 30 modified outputs; real archive verifies each receipt before skipping. Existing unreceipted files are never overwritten.',
        '- RED on prior catalogue implementation (20420b4 plus new acceptance tests): 3 assertion failures / 1 pass for missing structured parser, row matcher and p90. GREEN: 20 standalone audit tests, including the additional double-transform regression (RED: actual X=20 vs expected X=10; GREEN after removing extra node transform). The earlier collection ImportError is not valid RED evidence.',
        '- Full unchanged project suite final rerun: 3279 passed, 9 skipped, 13 deselected, 359.69s (concurrent native verification). Earlier run this attempt: same counts, 327.76s; prior baseline 326.45s. No claimed suite speed improvement. Profiles: 3 OK; schemas: 11 OK; `git diff --check` clean.',
        '- Regression evals: `tmp/evals/flora-library-audit-resume/report.json`, exit 2, 0 passed / 0 failed / 10 NOT MEASURED (Hermes has no expected Claude-format transcript/PR evidence); not an eval pass.',
        '- Pattern / new case: module docstrings mark #189 as a standalone source-audit case, not production modelling or a reusable general-layout rule.',
        '- CI: not run (billing lock). No fabricated subagent or trace claims.', '',
        '## Author receipts', '',
        '- Pattern / new-case: new case #189 in catalogue/checkpoint/native-entry module docstrings; explicit non-delivery scope and empirical layout rule.',
        '- Regression evals: local `tmp/evals/flora-library-audit-resume/report.json`, 10 not measured, exit 2; missing Claude-format transcript is recorded, not treated as green.',
        '- Probe: generated source-integrity, label-accounting, binary-diff and resume-tampering probes plus every-file native readback receipt; see Invariants above.', '',
        '## Verdicts and follow-up', '',
        '**ADOPT, limited to this display layout:** bounded row/display-plane association with raw labels, ambiguity and orphan lists. It improves the triangle-label proxy without inventing species identity. Proposed follow-up: **Flora catalogue intake: explicit layout schema and reviewed species/profile IDs**; scope: review co-located/unlabelled/cultivar-only entries, reject unknown layouts and add hedge fixtures before checker thresholds.',
        '**ADOPT, bounded to these intake cases:** evaluated Mesh exports with source-corner guards; use identity-transform world TriMesh VALUES where source nodes carry shear. Tree_LP snapshot fixed its polygon conversion; four sheared flower variants required identity baking, not snapshot nodes alone. Proposed follow-up: **Flora FBX intake: world-state Mesh values and affine guards**; scope: generalize behind a flag with translated/rotated/sheared fixtures, immutable UV/finish/winding readback, source hashes and per-file resume receipts. Do not normalize original masters or claim appearance approval.',
        '**MAYBE:** observed type/profile ceilings as review-only budgets; no regulation or checker update without planting-quantity/site context. **REJECT:** automatic authoritative species substitution, appearance approval or a delivery pass from this audit.', '',
        '## Out of scope / seen, not mine', '',
        '- Missing maps, curated species deduplication and stable Flora material IDs belong to [#216](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/216); texture generation belongs to #190. No new species or texture is added here.',
        '- Shared runner stale-lock ownership risk: [#223](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/223), filed after two duplicate searches. The waiter timeout can expire a healthy longer holder; no external wrapper was edited or lock manually removed, and this card never submitted overlapping native calls.',
        '- No PROJECT_STATE edit on this task branch; merge/acceptance/publication remain separate gates.', '']
    target = HERE.parents[1] / 'docs/experiments/flora-library-audit.md'
    target.write_text('\n'.join(out), encoding='utf-8')
    print('Generated', target, len(out), 'lines')


if __name__ == '__main__':
    main()
