# bpy 5.1.2 wheel vs blender.exe benchmark parity

Synthetic harness for hypothesis **#89** (CONFIRMED on engine dumps of B01, B02 and B02t, no UVs).
It does not approve a wheel lane. `delivery_passed=false`. blender.exe stays the default.

Confirmed numbers, worst case across the model matrix (no UV fixture in that run):

| Check | Result |
|---|---|
| Completion | 72/72 exit 0; 24/24 readbacks `readback_ok=true` |
| Lanes vs exe/exe, and rep2 vs rep1 | max ΔXYZ **0** |
| World geometry vs the engine dump | max ΔXYZ **1.72e-6 m** (threshold **1e-5 m**) |
| Transform parity | location/scale 0, Euler 0 |

This folder adds a synthetic 4-quad UV fixture so `udim_tiles` (1001, 1002, 1011, 1012) is checked as well.
That fixture was not part of the 72-process confirmation.

```text
uv run python experiments/bpy-benchmark-parity/build_dumps.py <work>/common
uv run python experiments/bpy-benchmark-parity/run_matrix.py <work> [--blender PATH] [--wheel PATH] [--reps 2]
uv run python experiments/bpy-benchmark-parity/compare.py <work>
```

`run_matrix` reads dumps from `<work>/common`. `compare` prints the summary and exits 1 when not ok.

Environment:

- `DT_BLENDER` — blender.exe. Default: `C:/Program Files/Blender Foundation/Blender 5.1/blender.exe`.
- `DT_BPY_PYTHON` — CPython that has `bpy==5.1.2`. No default; the matrix refuses to run without it.
- `--blender` and `--wheel` override the environment.

Limits: synthetic engine proxies and one synthetic UV mesh; not a material, normal or delivery certification.
`delivery_passed` is false. A green compare does not make the wheel an approved export lane.
