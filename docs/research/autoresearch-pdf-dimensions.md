# PDF dimension autoresearch (#1321)

## Кратко для Артёма

Baseline #1302 воспроизведён: KPP1 L03 — 7/82, КНС разрез — 8/12,
КНС план — 0/6. TUNE — первые два листа (15/94); HOLD-OUT — план (6).
Лист без положительных привязок сохраняет precision=null и отдельный
zero-prediction PASS [D277]. Масштаб не угадывается, `passed=false`.
Исследование запущено; итоговые раунды и остановка будут записаны ниже.

## Frozen protocol

Baseline production: `3f8b3712cd91f077d9ca4fcb957a8410a9ecc16f` (#1302 final fix),
identical binder at repository base `af2a90f2`. No oracle selection after tuning.
[Corpus](../../tools/research/pdf_album/dimension-autoresearch/corpus.json) freezes
all three native DIMENSION sheets documented by #1302, source DWG/DXF/PDF hashes,
evaluator-only registrations, 100 native handles and split/guard. [Baseline](../../tools/research/pdf_album/dimension-autoresearch/baseline.json)
binds its corpus hash and exact axes/levels/verdict signatures. No binaries in git.

Score is the unchanged #1302 source-location comparator: native measurement
strictly <0.5 mm, both projected extension ends AND dimension-line location
strictly <0.5 pt, one-to-one source handles. All positive semantic predictions
count, including wrong/duplicate/unsupported ones. Raw unbound spans earn no credit.
Non-cardinal floor-plan predictions cannot earn credit without independently
registered geometry; the current cardinal binder produces none. That hold-out is
weak evidence of generalisation (same KNS project and zero baseline predictions),
not an independent expert-labelled or rotated-chain benchmark. It is never used
to choose rules or parameters. No OCR/vision, scale guess, or endpoint-identity relaxation.

Every candidate changes only `src/dt_ai/album/`; control owns trial commit/revert.
Keep iff TUNE recall rises AND guard passes; report HOLD-OUT on every trial.
Stop: recall >=0.8, three consecutive gains <0.01 absolute recall, or 8h
(card runtime cap 120min is stricter). No existing tests may be loosened.

## Baseline and final accounting

Pending experiment results. Baseline: L03 found/correct/wrong/missed=7/7/0/75;
KNS=8/8/0/4; HOLD-OUT=0/0/0/6 (precision null, recall 0).

## Reproduction

One-time extraction uses `ezdxf.readfile(copy).modelspace().query('DIMENSION')`,
`get_measurement()`, `defpoint2/3`, `defpoint`, `text_midpoint` and native block
MTEXT. The #1302 frozen registration locates native labels within 3pt and must
find exactly one matching run; it never enters `bind_album`. Existing headless
AutoCAD plots from #1290/#1302 are reused byte-for-byte; originals are not reopened
or saved. Extraction driver and hashes are sealed with the experiment evidence.

```bash
uv sync --extra pdf-review
uv run --with ezdxf python -m tmp.freeze_dimensions
uv run python -m tools.research.pdf_album.dimension_autoresearch
uv run python -m tools.research.pdf_album.dimension_autoresearch --guard
```

The evaluator has no output/report/temp-path API: stdout only. It re-hashes inputs
before and after the complete run and rejects aliased inputs and stale corpus
receipts. Source mutation restored between hash snapshots is not detected; single
writer ownership and frozen copies remain prerequisites, not a claimed OS lock.
