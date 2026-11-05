# Lab experiment L02: `udim.ids_to_udims` (ID → UDIM on a copy)

Plan row: `docs/plans/agr-tools-suite.json`, block `udim`, version 0.8, verdict `take_fix`. This page records how the
GeoAGR 13.64 source behaved in 3ds Max 2024.2.1. The code ran in the AGR Lab runner on synthetic scenes on 04.11.2026,
with the owner's permission for this lab round. It contains **no GeoAGR code**: references are `GeoAGR.ms:<line>` of the
private snapshot (rule #853). Full evidence is in GeoAGR-private, branch `lab-exp/L02`,
`work/lab-experiments/udim.ids_to_udims/`.

## Source
GeoAGR `IDs→UDIMs`: LMB handler at `GeoAGR.ms:35920-36001`, scale spinner (default 0.95) at `GeoAGR.ms:14633`.
The Telegram script `UDIM-MultiSub_Universal.ms` (the reverse direction) is not in any repository I checked, so it was
**not available**.

## Measured (runner job `20261104-230526-0211c2c4`)
- The ID → tile mapping is correct for IDs 1..100: ID n goes to UDIM 1000+n (1001, 1002, 1007, 1011, 1025 were
  checked). Each ID group is fitted to 0.95 and centred in its tile, with the aspect ratio kept.
- All islands of one ID are scaled **as one group**. Two far-apart islands of ID 2 shrank 3 times. Because each ID is
  normalised on its own, texel density changes between IDs.
- **ID > 100** is skipped silently and stays in its old tile, overlapping ID 1 (`GeoAGR.ms:35949`).
- **Multi-selection:** only the first object is processed. The second keeps its UVs and gets no Unwrap
  (`GeoAGR.ms:35929`).
- **UV group with zero extent:** the UVs become NaN, with no warning (division by zero, `GeoAGR.ms:35964`).
- The handler adds `Unwrap_UVW` to the **working object** (`GeoAGR.ms:35933`). This conflicts with D030: IDs are a
  reading scheme, and UDIMs are assigned on export.
- The CTRL branch (place without scaling) was not run, because a script cannot set the keyboard state.

## Recommendation: `take_fix`
Keep the 1000+ID mapping and the "break the ID group and move it" approach. Re-implement it with these fixes:
- run only on an export copy;
- loop over the objects explicitly;
- reject or report IDs outside 1..100;
- skip and report zero-extent groups;
- add a "common scale" mode that preserves texel density;
- write a per-ID report.

## Requirements the tool must meet
- **VPM-2.5-2.1.3.a / VPM-2.5-2.1.3.b** (plan row `reqs`): UDIM tile layout of the VPM material slots on export.
- D030: material IDs stay a reading scheme of the working model. The tool writes UDIMs only on the copy.
- R5 (plan): the "UDIM-MultiSub ID = tile" rule is dropped. The ID → tile mapping is an export step, not a modelling
  rule.

## Minimal acceptance test (proposal)
A synthetic Editable Poly with IDs 1, 2 (two islands, one outside 0..1), 7 (non-square), 11, 25, 101, a zero-extent ID 5,
and a second selected object with ID 4. Run the tool and check:
1. The working objects are unchanged: same UVs, same modifier stack, same node count.
2. On the copies, every face of ID n (1..100) lies inside UDIM 1000+n. The second object is processed too.
3. ID 101 and the zero-extent ID 5 are listed in the report as skipped, and their UVs are not NaN.
4. In "common scale" mode the UV-to-3D area ratio is equal across IDs within 1 %.
5. The exported FBX is read back and the per-face tile check is repeated on the file.
