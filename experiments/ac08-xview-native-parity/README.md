# AC08 native xView parity (opt-in)

Pinned real fixtures for S00, S12 and S14. Six hashes and seven mesh polygon
counts live in `run.py`. Binary FBX and companion readbacks are not in git.

Set `AC08_XVIEW_FIXTURE_ROOT` to a local copy of
`G:/Мой диск/AGR-evidence/752-ac08-kernel-ops/v002/`. The default is unset.
Missing files skip; they are not replaced with synthetic meshes.

`delivery_passed` stays false. The harness reuses
`tools/qa/xview_parity.py:compare` and `dt_ai.ops.inv_xview.part_report`.
Contact faces are `xview_faces`. Polygon corners stay 1-based until `compare`
converts them once.

```text
uv run python experiments/ac08-xview-native-parity/run.py prepare --work W --source %AC08_XVIEW_FIXTURE_ROOT%
uv run python experiments/ac08-xview-native-parity/run.py compare --work W --baseline-only --out W/baseline.json
```

`prepare` writes `native.ms` (`holdMaxFile` / `fetchMaxFile`). A native result
is opt-in: `AC08_XVIEW_NATIVE_DUMP` points at the Max `native.json`. pytest
`-m native_max` may ping the bridge, and without that dump the test skips.
It does not launch 3ds Max and it does not pass on an empty compare.
Do not commit the dump. Certification rejects a nonempty `failures` list,
`import_ok` other than true, `geometry_unchanged` other than true, a duplicate
`(state, rep)`, any class other than `Editable_Poly`, and any units or
tolerances other than metres, 2 mm vertices and 5 mm faces.
