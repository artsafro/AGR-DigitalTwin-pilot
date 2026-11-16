# Manual openings command (#1511)

`agr openings` delegates to `tools/source/openings.py`. Geometry/classification lives in
`adapters/max/agr_tools/openings_core.py` (stdlib only, importable from embedded Max Python).
No Max or Revit session is opened. The existing mesh-border reader is unchanged.

## Inputs and usage

```bash
# Saved Revit route: export sidecar bboxes in feet; census object bounds in metres.
uv run agr openings --revit SOURCE/curtain.export.json --census CENSUS --profile KPP1 --output NEW.json
# Explicit handle/frame map; measured rectangular LINE/LWPOLYLINE outlines, not bbox guesses.
uv run agr openings --dxf facade.dxf --mapping mapping.json --output NEW.json
# Existing DWG->DXF converter (AutoCAD 2025 on a hashed copy), then the same DXF reader.
uv run agr openings --dwg facade.dwg --mapping mapping.json --workdir C:/x/CARD/readback-v001 --output NEW.json
```

DWG workdir must be new, ASCII and compatible with the existing converter's script-path rules;
output must be outside it. DXF/DWG uses the existing
`tools/methods/body/facade_openings_from_dxf.py`; its module docstring defines the exact mapping
schema and complete entity/drop accounting. ezdxf/shapely are allowed in that adapter, never imported
by the shared core. DWG intermediate DXF, conversion receipt, copy and logs remain in workdir.
This command does not select handles, infer semantic kinds or resolve source conflicts.

Revit supports the **explicit legacy KPP1 profile only**, using the saved JSON route from
[routes/revit-intake.md](../../routes/revit-intake.md). It does not accept RVT, arbitrary Revit
families, TwinPack JSON or invent a facade mapping for another building. KPP1's existing facade
thresholds, feature id 1832606, 12 mm containment tolerance and 2.1 m door convention are retained;
they are not new generic modelling rules. Family matching preserves #1336 Latin-C homoglyph handling.
The job-local script calls the same reader and retains its two legacy JSON files field for field.
Both writers now refuse existing destinations, including aliases, rather than overwriting a prior run.

## Output JSON contract: `agr-openings/1`

All output lengths are metres. The document is a **source-tagged union**, not a universal cutter
or window-library schema: source-specific measured facts retain their original representation.

| Key | Required value / shape |
|---|---|
| `format` | `"agr-openings/1"` |
| `source_kind` | `"revit"` or `"drawing"` (DXF or converted DWG) |
| `status` | `"measured"`; never delivery/architectural acceptance |
| `units` | `"m"` |
| `facade_binding` | Revit: `{profile:"KPP1", frame:"Revit internal coordinates", S,N,W,E}`; S/N use `plane_y_m` −0.33/11.33 and `u:"x"`; W/E use `plane_x_m` −0.33/27.33 and `u:"y"`. Drawing: original `facades` map `{name:{origin_mm:[x,y],direction:1 or -1,datum_m:number}}`; origin is explicitly in drawing mm. |
| `source_refs` | Array of `{path:absolute_path,sha256:64_lowercase_hex}` for every input; DWG also includes the intermediate DXF. Revit order: sidecar, curtain objects, openings objects. Drawing order: original source, mapping, optional converted DXF. |
| `data` (Revit) | `{spec:{S,N,W,E}, dropped:[{name,group,reason}], unlocated_references:[{elementId,type,reason:"no boundingBox"}]}`. Each facade has `surrounds`, `doors`, `portals`, `features`, `grilles`. Surround/feature: `{id,rect,bays,mullions}`; bay: `{id,rect,windows,glass}`. Portals: `{id,rect}`; doors: `{name,rect,double}`. Rectangles, windows, glass, mullions and grilles use `[u0,u1,z0,z1]` in m. Source sidecar ids are retained; census names identify dropped objects. |
| `data` (drawing) | Unchanged extractor schedule: `{status:"measured",units:"m",source,mapping,openings,entities}`. Opening: `{id,kind:"window" or "door",facade,source_handles,left_m,right_m,sill_m,head_m,width_m,height_m}`. Entity: `{handle,type,layer,status:"used",opening}` or `{handle,type,layer,status:"dropped",reason}`. |
| `conversion` | DWG only: unchanged `dwg-to-dxf/1` receipt from the existing converter; must have status `pass`, distinct from the output's `measured`. |

Revit sidecar records are bounding-box/type reference inventory, not an independent list of body
holes. The classifier accounts for every census object in the spec or the reasoned dropped list;
unknown families are reported drops, not guessed windows. No door/window choice, opening depth,
world placement, body modelling or delivery pass is inferred from a drawing outline.

Errors exit nonzero, no output is reused as success. CLI JSON rejects duplicate keys; required
numeric fields must be finite, bbox spans and measured opening dimensions strictly positive.
Outputs use exclusive creation; existing outputs, hardlinks and resolved input aliases are refused.
No predictable `.partial` is created or deleted. Input byte snapshots are checked before publication;
this detects persistent changes, not edits restored between snapshots or a change after the final
check. Sole input ownership through the run remains required. An I/O failure can leave an incomplete
new file: its nonzero exit is not a measurement receipt; use another new path, never consume it.

## Not done (explicitly deferred)

- `--pdf` exits 2: `PDF input: not implemented, needs an agreed sample`. An agreed PDF sample and
  extraction contract are needed before implementation; no manual JSON pretends to analyse PDF.
- AGR Tools stage-0 `source.intake` button and live Max validation: deferred by the scope update.
- Generic Revit profiles and TwinPack integration are not claimed by the KPP1 compatibility reader.
