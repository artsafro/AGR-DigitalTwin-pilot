# tec26-oks3-truba

Status: **DCC packages, checks and renders are on disk**. Not a delivery (`passed` is not claimed).
SINTEZ, GeoJSON, MSK-77 and the manual gates are still open.

## Done

- Finish census and `make_textures.py` (previous run). Normalised PNGs stay in
  `C:/x/tec26-oks/textures-v001/`.
- Multi/Sub census of `Tuba` / `Material #75`. Mapping is
  `scripts/multisub-map.json`. Four empty slots (ids 4, 8, 9, 10) have no faces
  and were not given a finish.
- VPM and NPM FBX, separate UCX FBX, both zips, scanline renders.
  Working Max file: `C:/x/tec26-oks/max-v001/truba_named.max`.
- Readback, xView overlaps, winding and outside-ray back faces:
  `scripts/qa-receipt.json`.
- Copies of the packages, renders and `SHA256SUMS.txt` are on Drive
  `G:/Мой диск/AGR-evidence/560-tec26-oks3-truba/`.

## Not done

- SINTEZ AGR Checker.
- GeoJSON, district code, MSK-77 placement.
- Manual gates V015–V017.
- The Max FBX importer rebuilds the Multi/Sub container as `MultiMat_0`.
  The six sub-material names in the FBX are `M_Truba_1_Main_1_<Finish>` and
  `M_Truba_1_003_Main_1_<Finish>`.

Do not treat this job as a delivery package.
