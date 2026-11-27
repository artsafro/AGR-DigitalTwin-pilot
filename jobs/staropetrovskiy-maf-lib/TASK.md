# Staropetrovskiy ZU_7_A MAF — rules and materials

Level: `standard` (library metadata, not customer delivery). Decisions: [D357], [D358], [D359].
Artem asked for reusable NPM and VPM versions on 2026-11-21 and answered «Да, все» to the intake recommendations.
Acceptance of the source job is not acceptance of its library drafts.

## Library status at takeover

#1985 registered 28 Moskovsky drafts; #1993 already registered all 51 Staropetrovskiy codes as drafts,
one entry per code. The backfill matches 51/51 NPM and 12/12 VPM FBX hashes; the maximum measured
size delta is 1.8 mm. No catalogue, model, version or acceptance changes in #1783. Future assets go
through the [library-publish route](../../docs/scenarios/library-publish.md) as `draft` [D421].

The historical [batch report](#historical-rules-and-results) is retained at
`G:/Мой диск/AGR-evidence/1783-staropetrovskiy-maf-material-sources-v001/readback/summary_v002.json`
(SHA-256 `97477259c08c14869a23799e599dcd08a34d7c2901a1baeebb5cd224ebfe4b4e`). The enclosing
`SHA256SUMS.txt` also seals the copied material inputs, not model outputs.

## Historical rules and results

- NPM: export each master from a copy of Artem's `staropetrovskiy_maf_library_v003.max`, not from
  the site package. The master's local Z=0 is ground level; preserve the embedment (T01 post: 0.4 m).
  Lifting T01 to set its lowest point to zero would place the seat at 0.91 m. Keep the delivered
  51° smoothing and UVs on 512 atlas v002. FBX has no texture links; maps travel with the asset [D357].
- VPM: take one instance per code from the delivered joined GroundEl, transform to master-local
  coordinates, renumber UDIM from 1001 and use v004 maps. Use only codes within 1 cm both ways of NPM;
  NPM-only on ambiguous identity. Mark vendor originals `vendor-derived` with their source [D357], [D359].
- 51/51 NPM matched masters. VPM: A01, A02, I07, I08, I17, I18, T01, T15, T16, T17, T22, X02.
  34 placed codes wait for a separate rebuild; I04a, I04b, I05a, T23, X05 are showcase-only [D359].
- Preserve xView overlap flags on I07, I08, I19, T20. Loose vertices were removed from the historical
  library copies of I01, I03, I04b; this PR does not edit any mesh.
- Separate VPM rebuild (not started): pilot T02; double segments only on round parts, leave flat parts
  untouched, redo UVs and measure the two-way tolerance [D359]. Follow #1745/#1754. The old segment
  script was for reference only: it deformed flat parts (T02 +14 cm, I10/I10a +19 cm).

## Materials

- `material_ids_v008` adds IDs 34–39 to v007. ID 36 is `#9E5A47` as measured in the delivered diffuse
  map, not the brief's `#8E402A`. The active MAF pointer stays on v007 [D358].
- Shared `materials_v003.json` adds the six keys at IDs 54–59. Released v001 and v002 stay byte-for-byte;
  v003 relocates the inherited Verona reference to a SHA-256-matched Drive copy.
- The v008 change manifest pins the six job inputs and the inherited evidence relocations.
  `uv run python -m tools.library.maf_ids_v008 --help` describes the metadata and tile replay;
  it writes to a new directory and does not read or write model geometry.
