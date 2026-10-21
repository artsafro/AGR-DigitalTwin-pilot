# Skolkovo — roof-mast source decision before the final PartsList

**Needs user input; not Gate 1 and not a delivered-model review.**
The interior question is already answered in [the job decision](DECISION-2026-10-21.md):
exterior only, whole interior excluded with provenance, opaque glazing.
Do not ask that question again or treat this sheet as an approval of the incomplete subset.

## Exact question

The September revision PDF, physical page 3, labels **M4 h=8 m** and **M5 h=12 m**.
The supplied roof/lightning FBX has two assemblies near these positions both named
**10.4 m**, including one `variant 2`. Should production **preserve the supplied
FBX mast geometry**, or **reconstruct mast heights and positions from the revision
PDF**? Please name the source to use if neither is intended.

No rescaling, replacement, inferred platform elevation or mast reconstruction has
been performed. A family name is not a measurement of the pole length; the assembly
span below includes supports. The question is about source authority, not a claim
that the source assembly is a failed or unsafe lightning-protection design.

![Source question, drawing crop plus measured facts](evidence-v004/source-question-v004.png)

## Evidence and limits

- PDF authority: `01_source/02_pravki_2026-09-15/Изменение фасадов.pdf`, physical
  page 3. Read its rendered image at full resolution; the printed plan also places
  M4 10,400 mm from the left axis and M5 11,000 mm from the right axis. Page 4
  contains a section with M1/M2/M3; it does not establish a measured M4 mounting datum.
- FBX: `01_source/02_pravki_2026-09-15/fbx/` file ending in `молниеотводы.fbx`;
  SHA-256 `f2167c8f48537cfaeaeab3bdad6a81ca1822b86029a1da4c473ec643312ac23e`.
- Read-only 3ds Max 2026.3 extraction on a worktree-staged copy. Five assemblies
  were extracted, not all 3,741 objects in that file. Vertex bboxes independently
  equal the Max node bboxes, **5/5 within 0.1 mm**.
- Coordinate comparison uses the measured dominant revision-facade minus v1
  translation `[42.266, -35.629, 0] m` from the earlier shared-ID probe. It is a
  diagnostic frame correspondence, not a human approval of every source object's
  registration or an MSK-77 placement receipt. M4/M5 spatial associations remain
  provisional; do not assign PDF identity from nearest bbox alone.

| FBX element ID | Source name cue | Assembly Z min / max (m) | Tip XY in facade frame (m) |
|---|---|---:|---:|
| 6641475 | 10.4 m, variant 2 | 15.260 / 26.965 | 10.400 / 28.295 |
| 6631253 | 10.4 m | 11.935 / 23.640 | 34.795 / 28.795 |
| 6640426 | 12.45 m | 12.075 / 25.830 | 42.395 / 9.505 |
| 6640949 | 12.45 m | 12.075 / 25.830 | 3.705 / 9.505 |
| 6677027 | 10 m | 13.810 / 25.115 | 25.125 / 9.005 |

Numbers are rounded only in this table; full float coordinates, original names,
vertex arrays and hashes are in `evidence-v004/mast-geometry.json.gz` and
`diagnostic-probes-v004.json`. No expected tip Z has been invented from the PDF's h.

After the answer: reconcile the mast source, finish exterior/revision/material/joint
classification, then request Gate 1 on the exact final PartsList hash. Approval of
this source choice alone is not Gate 1 and does not waive the output visual gate.
