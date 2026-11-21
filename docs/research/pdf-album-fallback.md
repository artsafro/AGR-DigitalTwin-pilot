# Cyrillic OCR + targeted vision fallback audit (#1236)

## Scope and verdict

**Implemented, PARTIAL observations, never approved geometry.** [D265] narrows this
card to the existing three real albums, 53 source pages, with references explicitly
**not independent (agent-made reference)**. Seven frozen ROIs on five physical pages
were exercised, not a new full-53-page OCR pass. Every other page is explicitly
`not_requested` in the page accounting. Customer PDFs/renders are not committed.

The references were visually transcribed by `dt-worker-codex / gpt-6.1-sol` on
2026-11-12 before automatic scoring (commit `14cc1ef6`):
[`fallback-reference.json`](../../tools/research/pdf_album/fallback-reference.json).
It records source SHA-256, physical page, PDF-point bbox, original labels, author/date
and unresolved source constraints. These are text-audit references, not expert
row/element labels or independent calibration. Original three-album source provenance
is in [the research report](pdf-album-pipeline.md#corpus-authority-and-reproducibility).

## Adapter and outputs

- `src/dt_ai/album/fallback.py`: `run_fallback(pdf, output, regions, ocr=..., vision=...)`.
  Explicit ROI routing permits outlined annotations even on searchable pages. All
  region IDs, kinds, pages and finite positive-area bboxes are validated before writes.
- `fallback_backends.py`: local RapidOCR Cyrillic PP-OCRv5 mobile recognizer, retaining
  raw lines, pixel boxes and confidence; optional read-only Codex CLI vision ROI checks.
  Shared detector is PP-OCRv6 small. No new production dependency is required.
- Output: source-hash-bound `observations.json`, `questions.json`, per-page metering.
  Every requested region and **all its raw labels/values** are retained in a question
  with physical page/bbox, recipient `architect`, OCR and vision variants and open gates.
  This is conservative region-envelope questioning, not an atomic semantic value parser.
- Scale/units remain unverified, binding/ground truth/approval open, `passed=false`
  and `measured_geometry=null` even when OCR and vision agree. No default material.
  Failed/missing OCR, vision or billing stays failed/unresolved, never a successful check.
- Concrete rendering rejects out-of-page ROIs, encryption, unsupported render budgets
  and pixel allocation at/over the cap. No silently clamped ROI or perspective measurement.
- New output directories only; input hashes checked before/after observation. Existing
  aliases, report hardlinks, stale output and duplicate locators are refused; exclusive
  report creation never truncates a source or deletes a sentinel. No fixed `.partial`
  path is used. Before/after hashes do not detect mutation restored between snapshots;
  this is not an adversarial concurrent-filesystem transaction or a PDF worker timeout.

The COD chain remains **69600 + 17800 = 87400 vs printed 87450 mm** (50 mm disagreement).
Its architect question preserves the printed figures; the adapter does not silently
repair totals or infer a winning geometry. Equipment length/section approval remains
open. TEC26 is visualization-only; its title is readable but no dimensional/material
schedule denominator is invented. D108/D112 are unchanged.

## Text quality against default OCR

Scoring is **Cyrillic word-multiset precision/recall**, case-insensitive, retaining word
multiplicity but ignoring punctuation, line wrapping and word order. It measures text
recovery, NOT full-row identity, element binding or semantic correctness. The tiny
selected-ROI denominators are not an estimate for an entire album. Empty prediction
precision is unknown, not perfect. Numeric-only ROIs are scored separately as exact
bounded token presence, not included in the Cyrillic-word denominator.

| Album | Cyrillic words | Historical default recall / precision | Same-ROI default recall / precision | Cyrillic recall / precision | Vision recall / precision |
|---|---:|---|---|---|---|
| ELV | 30 | 0/30 / unknown | 0/30 / unknown | 29/30 / 29/31 | 29/30 / 29/30 |
| COD20207 | 51 | 0/51 / unknown | 0/51 / unknown | 50/51 / 50/52 | 50/51 / 50/52 |
| TEC26 title only | 4 | 0/4 / unknown | 0/4 / unknown | 4/4 / 4/4 | 4/4 / 4/4 |
| Total audit words | 85 | 0/85 / unknown | 0/85 / unknown | 83/85 / 83/87 | 83/85 / 83/86 |

Historical baseline is the report's sealed `*-D-all-v001/result.json`, 150 dpi full-page
OCR, source/hash-bound and rescored only for word boxes whose centres lie in the frozen
ROIs. Same-ROI controlled baseline reruns RapidOCR 3.10.0 bundled default at 300 dpi,
matching Cyrillic ROI rendering/detection. Different dpi/cropping means historical and
controlled runs are **not interchangeable latency benchmarks**. Both default routes
emit no Cyrillic words in these ROIs. The Cyrillic result still has transcription errors;
vision did not eliminate them. Do not retune frozen references to make either perfect.
ELV/COD sampled dimension tokens were recovered 3/3 each by default, Cyrillic and vision;
that is not evidence of model scale, unit or view/axis binding.

| Album | Controlled default OCR seconds | Cyrillic OCR seconds | Whole targeted album execution seconds |
|---|---:|---:|---:|
| ELV, 3 ROIs | 13.457 | 7.119 | 54.283 |
| COD20207, 3 ROIs | 2.696 | 3.150 | 44.364 |
| TEC26, 1 ROI | 0.953 | 0.966 | 10.934 |

Model setup was 1.867 seconds separately; package installation excluded. OCR seconds
include rendering. These single-run workstation observations are not statistical
latency guarantees. Full-album historical baseline timings remain in the original report.

## Metered vision and proposed budget

Codex CLI used existing ChatGPT authentication, read-only sandbox, ephemeral sessions,
no model tool calls and a cropped image at 300 dpi. The configured model observed on
this workstation was `gpt-6.1-sol`, reasoning effort `medium`. OCR text is **not** sent
to the checker, to avoid copying the proposed answer. Customer drawing text is data,
not executable instructions. A known ignored CLI configuration warning is preserved in
raw events; arbitrary error/tool events or missing/repeated completion are rejected.

| Album / PDF page | ROI calls | Input tokens | Output tokens | Vision seconds |
|---|---:|---:|---:|---:|
| ELV / 18 | 2 | 65764 | 237 | 22.825 |
| ELV / 27 | 1 | 28482 | 109 | 10.790 |
| COD20207 / 1 | 2 | 65194 | 344 | 27.492 |
| COD20207 / 5 | 1 | 32665 | 99 | 11.010 |
| TEC26 / 3 | 1 | 32507 | 19 | 9.001 |

Total: **225420 session tokens, 81.118 seconds**. Input usage includes repository/system
context and cached input; this is total session usage reported by `turn.completed`,
**not isolated image-token billing**. Seconds include render/startup/inference, not
inference-only latency. Currency charges are **not measured** under subscription auth;
there is no asserted zero cost or fabricated dollar conversion. Exact input/output
usage and raw JSONL/elapsed receipts are retained per ROI.

Proposed conservative budget: max **2 vision calls per physical page**, **80000 total
session tokens/page**, **180 seconds/page**, **180 seconds per CLI call**, and strictly
less than **16000000 rendered pixels/ROI**. Call count/pixel limits are hard preflight
limits; token/time thresholds are **post-call circuit breakers**, not a provider-side
spending cap: a single call may overshoot. At/above either threshold stop subsequent
calls and question the page. Missing usage also opens the circuit; excluded regions
remain accounted and questioned. Measured pages stayed below these limits. Expensive
whole-session context suggests deploying a genuinely metered image endpoint before
claiming an economical production default; do not claim ROI image billing from this CLI.

## Reproduction and sealed evidence

```bash
uv run --with rapidocr==3.10.0 --with onnxruntime --with pymupdf python tools/research/pdf_album/fallback_eval.py --corpus C:/x/pdf-album-research/t_5b23c219 --out tmp/fallback-fresh
```

Requires existing authenticated Codex CLI; no secret is copied or committed. Model
weights and exact package versions/hashes are in `fallback-results/frozen-manifest.json`.
Compact per-album observations/questions, scores, 53-page accounting and timings:
[`fallback-results/`](../../tools/research/pdf_album/fallback-results/).
Historical baseline re-scoring uses box centres in PDF coordinates (`px * 72 / 150`)
and the same `text_scores` function; no ground-truth change.

Large evidence: `G:/Мой диск/AGR-evidence/pdf-album/1236/t_b6312eb3-v001/`.
`SHA256SUMS.txt` digest `33ad632ada427efb865a767a297ebcc686a488871d67ea57f0e7e695bf3ecfec`;
44/44 members independently read back and verified after copy, including raw ROI PNGs,
JSONL, original run outputs, references and public model weights. Mounted-Drive copy
verification is **not** verified cloud synchronization. The earlier research seal holds
customer PDF copies; original input corpus was not overwritten or re-exported.

## Remaining gates / follow-up

A larger **>=6 real customer album corpus with independent expert-labelled rows and
elements** is explicitly a follow-up under D265, not delivered or silently passed here.
Needed: nominated expert identity/date, source hashes, page/bbox, complete row/element
references and approval, then frozen semantic recall/precision evaluation. Full-album
precision, row/element association, independently calibrated geometry and architect
approval remain unknown. No production model is built, modified or accepted by this audit.
