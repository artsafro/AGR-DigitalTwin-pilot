# Real-file dry run for #1445

Read-only run on the three original versioned 4bk-k3 sources named by TASK.md at
`6aa786d9` (acceptance scope dated 2026-11-14). Files were hashed anew for this run;
these are not reconstructed historical hashes or a new acceptance of current production.
No DCC was opened and no geometry files were written.

Manifest: `docs/procedure/evidence/1445/accepted-2026-11-14.json`
SHA-256: `7a05296671c2b57cfeb1dbb7e5a7282c4fccc57f49fbdfe0583b4cca129f9862`.

Commands (`ROOT` is the asset directory recorded in the manifest):

```bash
ROOT='C:/Users/artsafro/Desktop/!3D viz/!А101/63_4BK_vlad/build/gf_parts'
uv run python tools/state/accepted_set.py --job 4bk-k3 --accepted-set docs/procedure/evidence/1445/accepted-2026-11-14.json --inputs "gf_body_A=$ROOT/gf_body_A/gf_body_A_v004.blend" "gf_windows_A=$ROOT/gf_windows_A/v003/gf_windows_A_v003.blend" "gf_roof_A=$ROOT/gf_roof_A/gf_roof_A_v003.blend"
# exit 0: passed=true; all three inputs accepted
uv run python tools/state/accepted_set.py --job 4bk-k3 --accepted-set docs/procedure/evidence/1445/accepted-2026-11-14.json --inputs "gf_body_A=$ROOT/gf_body_A/gf_body_A_v008e.blend"
# exit 1: passed=false; gf_body_A rejected (sha256 mismatch)
```

Raw stdout: [accepted-v004.json](accepted-v004.json), [rejected-v008e.json](rejected-v008e.json).

| Part/version | Actual SHA-256 | Verdict |
|---|---|---|
| gf_body_A v004 | 88e56689be9f78e94e207381eb2b99424897aa509062709e15fc082fc7165c6a | accepted |
| gf_windows_A v003 | 68ce3fc7014c65abbb37290d5ae4f2730d256459c2e07355b70adb98ab93425e | accepted |
| gf_roof_A v003 | 8402a26707a5589ce7e889d49a9c7d94d0f71d3e6f70cb1ccdbb01b64d862a23 | accepted |
| gf_body_A v008e | 2a5f44ec6a5e4eb238984c4356bb08b7d15e0b35b87fb8ee6150766cc8094f0e | rejected |

The historical manifest is deliberately outside `jobs/4bk-k3/accepted.json`:
TASK.md also records later user-authorized UV cuts and hand-finished finals. This card
must not silently replace their acceptance with the historical v004 regression case.
On machines without these external files the same command fails, never fabricates a pass.
