# AGR Tools 0.1.0 — 3ds Max 2024 / 2026

Own implementations only; no team scripts or encrypted plugins are distributed.
This is a diagnostic/export-copy tool, not a delivery validator or production job.

## Build and install

`python tools/max/build_agr_tools.py <new-path>/AGR-Tools-0.1.0.mzp`

The builder prints SHA256; sorted ZIP_STORED entries, fixed timestamps/permissions,
LF normalization and exclusively created output make repeated inputs reproducible.
Existing files (including input aliases) are never overwritten. No Git LFS.
Drag the MZP into Max or run `fileIn "...mzp"`. Restart for startup registration.
Category **AGR Tools** exposes the three actions and **AGR Tools** dialog launcher;
add them to a toolbar with Customize User Interface. Headless installation registers
macros without opening a dialog. No Python dependencies need to be installed in Max.

## Rollout (text)

```
AGR Tools
[xView check]
[Pre-export clean-up (dry-run)]
[Apply preview to new export copies]
[MatID check]
<JSON report in Listener; offending object names and component IDs>
```

Selection is checked when nonempty; otherwise all geometry. Unsupported objects,
empty scenes/meshes, failed native checks and missing UV channel 1 are errors,
never a clean result. Objects are identified by unique Max handles as well as names.

- **xView check**: native OverlappingVertices at **2 mm**, OverlappingFaces at
  **5 mm**; check evaluated temporary copies, select original offending objects.
  Scene units are converted; native tolerance values are restored. No topology
  conversion of working objects. Pilot #370 / BODY-J/K; native xView semantics,
  not the kernel's additional projected-area diagnostic. Exactly 2 mm vertices
  follow native Max's strict boundary; a float32 ambiguity band (relative 2e-7)
  around exactly 2 mm returns an explicit error, never clean, without changing
  either native threshold. The kernel intentionally uses inclusive vertices.
- **Pre-export clean-up**: first shows a dry-run from the existing
  `twinqa.export_hygiene.repair_plan` (generated stdlib-only slice, not a rewrite).
  CA owners: node, base, modifiers, recursive material tree; clear UDP except map
  names; name channel 1 `UV`; remove extra map channels per the existing hygiene
  policy (reg p.31 §2.1.1 / pilot #547). Apply requires an unchanged preview and
  creates independent export-copy nodes/materials; it never cleans originals.
  Reports planned actions and re-inspected results. Nothing is saved/exported.
- **MatID check**: face IDs >= **1001**, unassigned ID 0, missing materials,
  unresolved or empty Multi/Sub slots; lists face IDs and selects offending nodes.
  Pilot #548 / D030. This is not the complete semantic 1–35 reading-scheme gate;
  no arbitrary ID remapping, empty-slot fallback or UDIM renumbering is done.

## Headless evidence

Run the synthetic fixture runner through the shared `dcc_batch.py max --file ...`
wrapper, never directly through 3dsmaxbatch. See `tests/max_tools/` and the committed
text evidence. Only new synthetic fixture copies are opened; no production asset.
An exit-zero wrapper alone does not prove a fixture pass: the runner asserts exact
results, writes the report exclusively and emits a completion marker at the end.

## Roadmap (not implemented)

UV integer-tile nudge; UDIM -> NPM atlas; collision generator; texel-density
readout; checked export. Those require their own fixtures, profile gates and
measured comparisons before adding buttons. No licensing, obfuscation or GeoAGR
source/decryption is included.
