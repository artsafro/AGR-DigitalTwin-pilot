# Skolkovo L4 — resume v005

Still **partial intake, passed=false, not buildable**. No PR is open. Current
main checked: `7b88d092185ff828766effda83bb2395b515c856` has no completed Skolkovo
job. Local and remote branch both started at orchestrator repair `13c9e8c`;
no reset/rebase/history rewrite was needed or executed by this run.

## Resolved decisions applied

- Interior remains exterior-only with opaque glazing; no common Shell and no
  interior retained by a transparent-glass exception.
- Artem's 2026-10-21 10:14 roof decision is now reflected in the proposed data:
  all five supplied FBX mast assemblies use **keep**, not contour rebuilding,
  rescaling or PDF-derived replacements. The PDF/FBX discrepancy remains a
  reported source discrepancy, not an open source-choice question.
- Actual source mast triangles: **55,230**, not the former 2,560 simplification
  allocation. Updating only this group changes the incomplete 20-group subset
  allocation from 81,496 to **134,166 triangles**. This is a design allocation,
  NOT a measured master, whole-building coverage or a budget pass. There is
  15,834 of unallocated target budget; missing parts cannot be assumed to fit.
- LFS/publication quota is no longer the blocker. All new binary evidence is
  stored on Drive. Five previously pushed gzip files are removed from the new
  git tree, after byte-for-byte copy/readback verification on Drive; their
  already-pushed history is not rewritten. Local copies remain ignored.

New proposed data (Drive `evidence-v005/`): `parts-subset-v005.json`, SHA-256
`c42701a34662a25afe1b1d84ba91d62dbf5f27dd23b8456dc81c1c84d13098c1`, and
`object-decisions-v005.csv.gz`. Both remain **unapproved**, `status=draft`,
`gate1=null`. This hash is NOT presented for Gate 1 approval.

## New exact data question

See [SOURCE-MATERIAL-QUESTION-v005.md](SOURCE-MATERIAL-QUESTION-v005.md): may
delivered VPM appearance become the explicit authority for exterior finishes
not mapped by the album/revision legend, while geometry stays source-derived?
Twelve roof-substrate wall rows (5402–5413) provide a specific witness: source
material mineral wool, above the roof, 924 positive source samples, but no
confirmed finish/legend association. Do not infer hidden/interior from a name,
assign Ф.1/Ф.10 arbitrarily, or silently turn the comparison model into an
independent material authority. The earlier mast question is answered.

## Durable evidence and real checks

Drive root: `G:/Мой диск/AGR-evidence/353-skolkovo-l4/`.

- `evidence-v005/SHA256SUMS.txt` indexes the five transferred v004 gzip files,
  v002/v004 archives and v005 proposal/question artifacts. Manifest SHA-256:
  `80f83b053e626a99423258aefb8344acacaf963d0cc18a13a5bedd2b5b6f4942`.
- `evidence-v005/source-diagnostics-v005.zip`: **36,228,895 bytes**, SHA-256
  `f062fc29494bae547f460329bed69163e284af0fdf1333b9364b31d074b9c5af`.
  Includes corrected raw mesh buffers, original v1 structure facts, native
  censuses, C5 JSON/text/page images, job drivers and v005 proposal; no supplied
  FBX/RVT or invented delivery outputs. ZIP CRC and **11,631/11,631 member
  hashes** were verified after reopening. Internal `SHA256SUMS.txt` lists each
  member. Old v002/v004 archives are separately preserved for their history.
- Independent second rehash: **12/12** indexed Drive artifacts match; all
  **104/104** original copied-package inventory hashes remain unchanged.
- Draft identity retained: **32,961/32,961** uniquely hash-pinned source rows.
  **1,695 facade review rows**, v1 supersession and final legend/joints remain
  unresolved; the changed mast group does not hide them.
- Job-only regression witness `drivers/l4_policy_probe_v005.py` (in the ZIP):
  old v004 draft **4/8 pass, 4/8 fail**, exit 1; v005 **8/8 pass**, exit 0.
  Failing checks were keep-policy, actual mast group/per-object budgets and
  answered source question. This tests data reconciliation, NOT kernel ops.
- Existing focused reader tests: **133 passed in 5.59 s**:
  `env -u MSYS_NO_PATHCONV -u MSYS2_ARG_CONV_EXCL uv run --extra pdf-review pytest -q -p no:cacheprovider tests/test_album_pdf_reader.py tests/test_album_below_line.py tests/parts/test_fbx_reader.py --basetemp=C:/x/t_b205c8e1-resume-v005`.
- No full suite run: reserved once for the first complete review head, through
  `suite_slot.py`. No approval/checker receipt or CI result is fabricated.
- No new production Python module or library; ad-hoc job drivers are archived.
  No DCC process was launched by this run; source diagnostics reuse the earlier
  corrected read-only Max extraction.

## L5 timing addition

The v005 policy reconciliation, sheet production, Drive copy, archive creation,
CRC and full member-hash readback took **15.8458887 seconds** measured wall time.
It is nested evidence-packaging work, not building-generation throughput. The
133 focused tests took **5.59 seconds**. Original-input rehash took **0.6467979
seconds**. In hours: packaging **0.004401636 h**, tests **0.001552778 h**,
original-input rehash **0.000179666 h**. Prior intake timings remain in RESUME-v004/timings.json; production,
export, visual review and final checker remain not measured, not zero.

## Resume order

1. Answer the exact material-authority question, without reopening the already
   settled interior/mast/storage decisions.
2. Reconcile exterior rows, v1 supersession, explicit source/legend mapping and
   all joints; produce the **final source-complete** budgeted PartsList.
3. Obtain user Gate 1 for its exact hash, then kernel operations/invariants.
4. Versioned FBX export, clean-process readback, comparison vs delivered final,
   board-tool visual review and user approval, then complete final SINTEZ.
5. One full suite via suite_slot.py, author receipts, push and open the one PR,
   then reviewer handoff. No incomplete intake PR has been opened.

Historical status in RESUME-v004 and SOURCE-QUESTION-v004 is superseded by this
report where it says mast choice/LFS are still open. Existing small text facts
are retained; binary names formerly relative to `evidence-v004/` resolve in
Drive under the same directory name. Current source-material sheet is a
**question**, not post-build visual acceptance.
