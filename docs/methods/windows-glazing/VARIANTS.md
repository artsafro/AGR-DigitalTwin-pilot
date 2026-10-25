# windows-glazing - variants (stub)

Windows, frames and glass: modelled frames vs atlas planes vs trim sheets. Status: **stub** - planned variants, nothing measured yet. Each entry gets idea, tool, inputs,
steps, script path and limits when it is built ([README](../README.md)); benchmarks: kpp1, ac08, tow02.

1. Modelled frames + glass mesh (kernel `src/dt_ai/parts`).
2. Window atlas planes (jobs/WINDOW-ATLAS): one textured plane per window, no frame geometry.
3. Inset glass only + frame texture (trim sheet).
