# KPP1 mode-A audit — reading guide

Final normalized input: `input-final.json`. Final machine/human reports:
`report-final/report.json` and `report-final/report.md`.
Full methodology, uncertainty and counts:
[`docs/research/pdf-model-audit-mode-a.md`](../../../docs/research/pdf-model-audit-mode-a.md).

**112 evidence rows: 6 match / 4 mismatch / 102 needs manual check.**
These are diagnostic statuses, not delivery approval; `passed=false`.
Four mismatch rows represent three discrepancy subjects (stair finish repeats
on the two schedule pages). The nine extra R1 glass components need semantic
inspection; the 29.4 mm source cap difference needs datum/detail review.

The source album p25–26 is raster, so unavailable grid positions, original
opening marks, unbound levels/finishes and sizes remain manual. No original
source or model was modified. The source FBX has missing material slots; its
Revit-derived declared stair finish is explicitly separate metadata.

Raw binary evidence is outside Git:
`G:/Мой диск/AGR-evidence/1304-kpp1-mode-a/evidence-v003/`.
`evidence-final.json` lists exact bytes/hashes; that directory has `SHA256SUMS.txt`.
Older diagnostic input/report attempts are retained separately in
`G:/Мой диск/AGR-evidence/1304-kpp1-mode-a/diagnostic-attempts-v001/`, not used as
final receipts. Reproduce the comparator into a NEW directory:

```bash
uv run python -m dt_ai.album.compare --input jobs/KPP1/audit-1304/input-final.json --output-dir tmp/audit-reproduction
```

Expected exit **1** (reported discrepancies), not approval. A fresh report has
its own input-inventory SHA256s. Existing output directories are refused.
