# OKS trail Step 3: modelling plan before geometry (#1896)

For `oks-npm` and `oks-vpm`. This is an offline, read-only preparation step before
`body`, not a second modelling route, a DCC import, or human approval.

```text
uv run python tools/methods/body/modelling_plan.py SPLIT.json ACCEPTED.fbx RECIPE.json NEW_DIR --font CYRILLIC.ttf
```

1. After Step 0, read back the **human-corrected** scene, not the proposal. Export the
   normalized `agr-oks-split/1` inventory below using the exact corrected layer and
   object names and externally documented family labels. The tool verifies the scene
   digest, not FBX internals or the authenticity of the human attestation. The Step 0
   operator owns the readback and the acceptance reference; do not convert a proposal by
   relabelling it. For an intentionally unaccepted proof sheet only, use `--preview`
   with `status: proposed` and `approval_ref: null`.
2. Propose a disposition for **each exact `(layer, family)`** present, even if the
   same family appears on multiple layers or is omitted. Preserve accepted membership:
   if a family needs two dispositions in one layer, get explicit family subdivisions
   in the inventory before planning. Do not guess or move objects at this step.
3. Show the single `modelling_plan.png` and obtain Artem's approval of that picture
   before modelling. `modelling_plan.json` carries the exact input hashes, per-row
   object names (including omissions), reasons, and the PNG SHA-256. Exit 0, a
   `pending_picture_acceptance` status, and preview `draft_unaccepted_split` are all
   **not** modelling approval. Record the approval separately against the exact hashes
   (first case: Sokolniki plan sokolniki-v002 on split v004, accepted [D407]).

## Input contract

- `SPLIT.json`: `schema: agr-oks-split/1`, `status: accepted|proposed`, `object` (display
  name), `scene_sha256` (hex SHA-256 of the exact scene argument), `approval_ref`
  (nonempty reference to Artem's decision in accepted mode), `layers` (ordered exact
  name list; may include empty layers), `objects` (nonempty rows with unique `name`,
  `layer`, and `family`). Populated `00_…` is unresolved and cannot be planned.
- `RECIPE.json`: `schema: agr-oks-modelling-recipe/1`, `split_sha256` (hex SHA-256 of
  the full split JSON bytes), `profile: npm|vpm`, `simplification_cm` (5–10 cm),
  `simplification` (what is simplified and what is protected), `typical_floors`
  (repeated module and unique levels, or a reason not to repeat),
  `expected_triangles`, `planning_ceiling_triangles`, `comparison` (historical
  observations or an explicit unavailable reason), and `rows`. Each row has `layer`,
  `family`, `representation: geometry|inset|texture|not_shown`, `reason`. Use Russian
  display text. The estimate must be positive and strictly below the declared planning
  ceiling (leave headroom), which is bounded by the 150,000 project target [D010].
  This is not the VPM regulatory limit or a measured export count.
- Optionally pass `--evidence MANIFEST.json` to record the comparison evidence's
  digest, and `--split-image SOURCE.png --reference-image REFERENCE.png` to display
  two existing renders. The tool binds bytes, not the truth of narrative claims.

The 5–10 cm field is a **planning proposal**, not blanket permission to move vertices:
protect the silhouette, openings, roof levels and finish boundaries. Use planar walls
and consider merging redundant niches; keep required relief even when simplified
with primitives. Follow the OKS inset/texture split [D336] and request explicit
approval for exceptions. Images do not replace geometry QA or delivery gates.

Use a clean output directory whose parent already exists. A rerun must use a new
name. On errors exit 2; ignore incomplete directories from interrupted writes. No
scene writes, no reclassification, no DCC launch. The final snapshot check detects
input bytes changed across reads, not edits made and restored between reads.
