# Sokolniki #1784 — measured railings pilot

Cell `oks-npm`; [R3](../../docs/procedure/node-r3-fence-railing-gates.md#shared-headless-builder),
standard geometry pilot, not delivery. [D384] authorizes
source-section measurements from the pinned Revit FBX; [D378] pins the receiving
body v005. Neither the accepted native file nor the separate inset work changes.
No connection to the active step-3 config is made while the railing set is incomplete.

- Revit FBX SHA-256 `feaae5271831802bb588fd4a440ef130fced0332fa3064a311072b2bfc96fe9c`.
- Accepted body `.blend` SHA-256 `6e644c9e1ef0ba14f8e670892e920ac1c63b3eb842075a86d55c2b31794c132c`.
- Blender 4.4.0, model-local XYZ in metres; no centring, vertical shift or
  geographic-axis claim. Both source hashes were checked again after execution.
- Modelling split [D336]: railings are separate inset members; no texture
  substitutions or changes to the existing body/plinth split in this pilot.

## FBX census and pilot outcome

The keys below are observed Revit FBX parent groups, not a full native RVT
schedule. The four bare hex keys are FBX labels, not Revit ElementIds. One FBX
node can contain several closed members. A zero is an explicit omission, not a
statement about whether a railing is required.

| FBX group | Family | Input nodes | Built solids | Readback triangles | Sampled max deviation, mm |
|---|---|---:|---:|---:|---:|
| `add86fe` | h1200 | 15 | 29 | 348 | 0.002329 |
| `6c6f31d` | h1200 | 12 | 26 | 344 | 0.001550 |
| `c830ee7` | h1200 | 13 | 27 | 324 | 0.003667 |
| `567204d` | h1200 | 12 | 26 | 344 | 0.001846 |
| `2272786` | MGN h900 | 28 | 0 | 0 | — |
| `2274014` | MGN h900 | 28 | 0 | 0 | — |
| `2274733` | MGN h900 | 28 | 0 | 0 | — |
| `2274966` | MGN h900 | 19 | 0 | 0 | — |
| `2274977` | MGN h900 | 20 | 0 | 0 | — |
| `2275433` | MGN h900 | 28 | 0 | 0 | — |
| `2275445` | MGN h900 | 24 | 0 | 0 | — |
| **Total** | **11 groups** | **227** | **108** | **1360** | **0.003667 (h1200 only)** |

For h1200, measure the centres and ordered rims of rectangular sections from
closed FBX shells. Rebuild with `agr railing ... --type posts_handrail --profile npm`;
append the results as separate collections to a new v005 review copy. After
reopening it, all four body mesh arrays, face-material indices and transforms
match their baseline; the 108 new bodies are quad meshes. Verification samples
native vertices, triangle-edge midpoints and triangle centroids against the
other surface in both directions (float64 point-to-triangle distances, not an
exact Hausdorff bound). Diagnostic role IDs are not approved materials, and no
production UV or delivery-package pass is claimed.

All seven MGN rail meshes retain 302–346 open edges even after a diagnostic
0.25 mm coordinate weld and removal of collapsed and duplicate triangles; six
also retain edges incident to more than two triangles. The repeated 73-vertex
part of each group retains 22 open edges. No sweep end, section or join was
inferred across those openings. Need an RVT or an export of the MGN paths,
sections and end/junction details; converting the incomplete source surfaces
as-is would be a different, separately approved scope. This is not an
acceptance request for the complete railing set.

## External evidence

`G:/Мой диск/AGR-evidence/1784-sokolniki-lattice/railings-v001/`:
`SHA256SUMS.txt`, `source-vs-built.csv`, `native-report.json`,
`sokolniki-railings-v001-diagnostic.pdf`, paired orthographic local-axis facade
projections and four close-up checks, measured inputs and source bindings,
and `review-v005-plus-railings.blend` (partial diagnostic). The overview is
explicitly an X-ray projection: it preserves depth-independent alignment but
is not a claim about street visibility.

`SHA256SUMS.txt` SHA-256: `a2c4f0bc7a6d4d66e49aaa68043dce0067a38b701766cd5dcde5497c3b33e916`
(31 evidence files verified against the manifest).

For a core-only replay, read the four `<group>.json` inputs under `measurements/`
in this Drive directory; `measurements/references.json` holds the extracted h1200
source surfaces. These are retained measurements, not replacement copies of the
original FBX or v005 body. The original input hashes above bind the historical
native run. Do not rebuild the receiving body or extend this pilot to MGN while
the separate railing task waits for Artem's RVT.
