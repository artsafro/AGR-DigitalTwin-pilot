# Per-part finish crop evidence — issue #1366

## Provenance and ownership

Read-only source: PR [#1443](https://github.com/artsafro/AGR-DigitalTwin-pilot/pull/1443),
`job/4bk-k3-vpm`, frozen commit `50d671b3bd01bcd4a83b5b2149f3fd25f101c359`.
Read `jobs/4bk-k3/SOURCE_ANALYSIS.md` and `jobs/4bk-k3/parts/k3_parts_v001.json`
with `git show`; no merge and no edits to that job's files.
Original manifest SHA-256: `d681151ccbe77cc76095a00a802535188f064ba0bc43f893871bc2805fd58b20`.

The operator supplied the original architect sheet at
`C:/Users/artsafro/Desktop/!3D viz/!А101/63_4BK_vlad/inbox/ТЗ_Архитекторы/1 эт_2.jpg`.
Only its copy `C:/x/4bk-k3-1366/sheet_1et_2.jpg` was inspected/cropped.
Image dimensions: 10000 × 6293 pixels. No source was modified.

## Crop readback

External fallback evidence directory: `C:/x/4bk-k3-1366/` (no binaries in git, no LFS).
Coordinates are original-image pixels `[left, top, right, bottom]`, top-left origin,
right/bottom exclusive. These are finish-detail regions, not full-building extents.

| Manifest part | bbox | Crop path relative to evidence directory | Observation / finish authority |
|---|---|---|---|
| `TypFloor` (tower) | `[3400, 0, 8550, 2400]` | `TypFloor_finish_v002.png` | Tower brick hatch and coloured strips; existing tower legend retained. No material text labels in crop: RAL/product identity comes from the original manifest, not sampled colour. |
| `Stylobate` | `[8680, 2650, 10000, 4070]` | `Stylobate_finish_v002.png` | Right-hand brick-hatched block, not the left dark annex; brick identity follows the user's correction quoted in #1366. No RAL/product inference from colour. |

Both crops were opened for visual inspection and independently decoded against
`sheet.crop(bbox)`: 2/2 exact pixel matches, 2/2 bboxes inside image dimensions.
The first tower crop included a corner of the left annex: retained as v001 evidence,
then replaced by this narrower **v002** reference, not silently overwritten.

## Real-manifest re-validation

Original 19-part manifest: `PartsList.model_validate` succeeds.
External evidence overlay `k3_parts_finish_evidence_draft_v002.json`: the same 19 parts,
all original geometry/operations/budgets/joints preserved, two `finish_refs` added,
`finish_sheets` registers the copied image with `multi_building: true`.
The Stylobate legend in this **external draft only** records the user's brick correction.
`status: draft`, `gate1: null`: historic approval is not transferred to changed content.
Overlay validates; removing bbox separately from tower and stylobate is rejected with
the part id and `bbox`: 2/2. A fresh Python process exercised the actual model.

Not done: migration/correction of #1443's tracked job manifest and its historical
source-analysis prose; these remain owned by that open job PR. This is validator
and evidence verification, not Gate 1 approval, texture production or delivery acceptance.
The validator checks metadata only, not filesystem existence, pixel identity, image
bounds or semantic building identity; those manual/readback checks above are separate.
The generated JSON Schema is structural; registry-dependent checks run in `PartsList`.

## SHA-256 seal

Manifest: `C:/x/4bk-k3-1366/SHA256SUMS_v002.txt`.

```text
6d46eb572f10bfa044bd8869e7485ed025c4da4d39cf2a7384edc17d189814c3  sheet_1et_2.jpg
51dd50f1cd3d1e1f0d9aea12f4a582075b2f1a4d68e740f44ef4c44d5dc1b11e  TypFloor_finish_v002.png
cb890d9c4575f6cca6b8de2914211786c9d6615b3efac88a0bfd2461d3728f3c  Stylobate_finish_v002.png
0ad5123d0bedc9820002cc4879c9ed9618f24b9f81b08910b8bdcbb30779dd21  k3_parts_finish_evidence_draft_v002.json
```

## Contract compatibility

`finish_sheets: [{image, multi_building}]` is a parts-local image registry, separate
from shared `SourceRef`. Every `finish_refs[].image` must name a registered image.
Single-building references may omit bbox/crop. Explicit empty lists, unknown images,
non-boolean classifications and duplicate sheet paths (including lexical Windows aliases)
are errors. Absent/null optional metadata is omitted from serialization, preserving
legacy approval hashes; adding evidence changes the approval identity.

Removing only `finish_sheets`, `PartEntry.finish_refs`, `FinishSheet` and `FinishRef`
from the new in-memory schema restores the previous registry digest
`821ddc60ea1e8d716f1002dc57e297630045d1f648eaa27978e8444fb5858f38`.
No shared provenance contracts changed.
