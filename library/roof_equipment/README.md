# Roof equipment — first source-derived form library

Format: [AGR library/1](../../docs/library/TEMPLATE.md), schema
`schemas/library_catalogue.schema.json`. Research: [roof-equipment](../../docs/research/roof-equipment.md).
This is a library review candidate, **not a building delivery or confirmed engineering catalogue**.

## Release and authority

- Catalogue release `v001`, successful immutable build attempt:
  `G:/Мой диск/AGR-evidence/1257-roof-equipment/library-v005/`.
- `catalogue.json`: byte-identical to that root's catalogue; 12 types, 24 native profile files.
- `extraction.json`: exact original FBX SHA-256, object name and polygon indices per prototype.
  Source files are copied, never edited. `R01`–`R10` come from Garibaldi G01;
  `R11`–`R12` from Olympic OLY. IDs are permanent form IDs, not project object IDs.
- [D263]: one observed delivery profile per research object is enough; roof equipment can
  use the same geometry in both library profiles. Counterprofile *source measurements*
  remain unavailable, not fabricated from this equality.
- `observations.json`: five source exports, observed profile per object, 45 form rows and
  a hash-pinned external context/unclassified list. Counts are geometric components,
  **not assembled MEP-device counts**. A shaft body and its cap can be separate rows.
- Every asset's engineering identity is `unconfirmed`. `ready` means reusable native files
  pass the common cleanliness checker, not architectural acceptance or regulatory QA.
- Imported world axes are retained. Only bottom-center translation and reunion of exactly
  equal split vertices are applied. No simplification, guessed closure, bevel or source repair.
  Open shaft bodies and separate caps are intentional modules; do not place an uncapped
  body as a complete roof unit without checking the owning project's source.
- Original UV coordinates remain in `SourceAtlasUV`. **No customer atlas is offered**.
  `matid_1` / integer `agr_material_id=1` is an explicitly neutral *library-local* material,
  not a recovered customer finish ID. Integration requires project-specific finish authority.

Preview/showcase: `previews/roof-sheet.png` (6 × 2 labelled native Blender grid),
`previews/roof-showcase.blend`. Each cell is fitted independently; this is not one display scale.
The asset files themselves contain no cameras, lights, text or helpers.
Research diagnostics, roof views and source-page images:
`G:/Мой диск/AGR-evidence/1257-roof-equipment/research-v002/`.
All large files stay outside git; both version roots have `SHA256SUMS.txt`.
Failed/earlier `library-v001`–`library-v004` attempts are **not this release**.

## Reproduce into a new version

Use native forward-slash Windows paths, not Git Bash `$PWD` (`/c/...`) for Blender arguments.
The two source arguments must match exactly the two hashes in `extraction.json`; their order
is irrelevant. Missing, extra, duplicated, aliased or preflight hash-mismatched inputs fail
before output. Persistent input changes during a build prevent final catalogue publication;
a partially created failed version must not be offered as a release.

```bash
REPO='C:/Users/artsafro/agr-pilot/AGR-DigitalTwin/.worktrees/t_d0a92d95'
BLENDER='C:/Program Files/Blender Foundation/Blender 5.1/blender.exe'
"$BLENDER" --background --factory-startup --disable-autoexec --threads 1 \
  --python-exit-code 1 --python tools/library/build_roof_blender.py -- \
  "$REPO" 'G:/Мой диск/AGR-evidence/1257-roof-equipment/library-v006' \
  "$REPO/tmp/roof-research-v002/inputs/G01/0707_Garibaldi_22_01.fbx" \
  "$REPO/tmp/roof-research-v002/inputs/OLY/SM_OlimpijskijPrKt_Vld_16_Str_4.fbx"
uv run python tools/library/check_library.py library/roof_equipment/catalogue.json \
  --root 'G:/Мой диск/AGR-evidence/1257-roof-equipment/library-v005'
uv run dt qa xview \
  'G:/Мой диск/AGR-evidence/1257-roof-equipment/library-v005/assets/R01/npm.blend' \
  --out tmp/R01-npm-new-xview.json --profile NPM-OKS --coords local
```

The first command is a **new build**, so hashes will differ; use its generated catalogue
for its checker. The second command checks the frozen offered release, not the rebuild.
The complete xView batch used every R01–R12 npm/vpm file, with NPM-OKS/VPM-OKS respectively;
raw reports are in research evidence `xview-v005/`. All 24 exited 0, all contact/area/vertex
and bow-tie counters zero. Common checker: 12 ready / 24 variants / 0 errors / no quarantine.
Neither result is a SINTEZ certificate or the user's visual approval.
