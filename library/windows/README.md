# Windows reusable library — review release v001

Common format: [TEMPLATE](../../docs/library/TEMPLATE.md).
Audit/coverage/limits: [AUDIT](../../docs/library/AUDIT.md).
Authority: [D204] families, [D258] library-only geometry/cleanliness scope.

`catalogue.json` is the migrated common catalogue: 67 IDs, **59 ready / 8 quarantine**.
Physical root: `G:/Мой диск/AGR-evidence/1259-windows-library/v003/`.
It contains 118 `.blend` files, one asset/profile per file. Do not use the superseded
`v001`/`v002` attempt folders as the current release. The catalogue's `version: v001`
is the logical review release, not the attempt-directory number. No customer binary is in Git.

Showcase: `previews/windows-sheet.png` (4704×6400, 67 labelled grid cells) and
`previews/windows-showcase.blend` under that root. Files/hashes: root `SHA256SUMS.txt`
and `docs/library/EVIDENCE.json`. Visual review by Artem is pending.

```bash
uv run python tools/library/check_library.py library/windows/catalogue.json \
  --root "G:/Мой диск/AGR-evidence/1259-windows-library/v003"
```

Exit 0 means the **offered subset** is clean, including actual saved-file readback;
quarantine rows are accounted for, not passed assets. Output is stdout JSON only.
The checker never trusts the old `quality.json`. No mapped drive / missing Blender is
an error, not a pass. Explicit `--blender <Blender 5.1.2+ executable>` is supported.

Edit existing `window_types.json`, `confirmations.json`, `standard.json` and `sources/`
through their existing workflows, then rebuild to a **new** external version. Never edit
the common catalogue by hand or overwrite the source MAX/old preview. The full census
rebuild command with `--sashes` is in TEMPLATE: #246 candidates are reapplied **after**
the census rebuild, and kept unconfirmed. Tests prove every record's readings, null
confirmed `sashes`/`handing`, status and ID order survive this step.

Current quarantine: D04/CW_021/CW_022 untyped; WT-02 standard inapplicable;
ELV-16/ELV-17 source/standard quality failures; D03/D03_W native frame vertex
spacing <=2 mm. Exact reasons remain in catalogue. These sources are not removed,
reinterpreted or silently replaced. Further repair requires a geometry task and readback.

These are **standard-generated templates**, not copies of approved delivery geometry.
NPM is a UV-ready plane (no baked atlas); VPM is separate geometric frame and flat glass.
Existing source consumers continue unchanged. Library cleanliness is not a building
certificate, no C35 decision is implied, and no unconfirmed sash/handing is a design fact.
