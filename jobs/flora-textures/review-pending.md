# Three-species cut-out review — approved by Artem, 2026-10-15

Test list only, not an asserted GROUND-PROJECTION planting schedule.
No botanical reference pictures or URLs were supplied for this test list; the sheet
states that absence rather than relabelling generated sources as references.
Prompts: [generation-plan.json](generation-plan.json).

**External visual evidence (no binaries in git):**

- `C:/x/flora-textures/review-v001/review.html` — actual diffuse, opacity, prompts,
  full candidate IDs and LANCZOS receipts.
- `C:/x/flora-textures/review-sheet-v001.png` — companion contact sheet: diffuse,
  binary mask and masked plant on checkerboard, for all three species.
- `C:/x/flora-textures/review-v001/candidates.json` — content-addressed candidates.
- `C:/x/flora-textures/evidence-v001.json` — actual readback modes/sizes/hashes.

Generation tool: Codex CLI built-in `image_gen.imagegen`; actual model and generation
IDs are not exposed. Trace session: `01a140c4-9c1c-71e2-b91a-02affb5e81b5`.

> source 1254x1254 (codex image_generation, no size control) -> upscaled 2048x2048 LANCZOS, accepted by the user

Artem via orchestrator, card comment 2026-10-15 20:44 / COORDINATION_RULES 27.
That earlier decision accepted source quality and technical upscaling only.
The separate cut-out approval below now releases the atlas gate.
Original files remain unchanged, despite their historical `rejected-non2k-v001.png`
filenames. No additional image generation was performed.

| Species | Candidate ID | Actual maps | Cut-out approval | Atlas |
|---|---|---|---|---|
| Betula pendula | `70a1e5c8ebe1f57f3802bf7f8de0e5db703e8fa1ad40beb463a847a870ce0ea6` | 2048 RGB diffuse + binary L opacity | Approved Artem, 2026-10-15 | atlas-v001 |
| Pinus sylvestris | `d88194c2d7acb59eb633bb292e20ba0d32e00ef1f98d6a7971a652a8c9715680` | 2048 RGB diffuse + binary L opacity | Approved Artem, 2026-10-15 | atlas-v001 |
| Spiraea japonica | `e7dbb8cc2817dc62f8a606322ebdbe93d31d48d14e42ea3c74a845feba910750` | 2048 RGB diffuse + binary L opacity | Approved Artem, 2026-10-15 | atlas-v001 |

Review HTML SHA-256: `12bd38d37108372d6263e101cc7be5140b07942feca80c8041edbe3d8dfdb556`.
Companion PNG SHA-256: `6868cc6651590d18630b2bb3408a9ce2cc9a8d23401c44e2b57c4b0feaf3b068`.

Readback verified 6/6 maps: 2048 square, RGB/L respectively, no transparency metadata,
strictly 0/255 opacity. Real-batch missing-approval probe: 1/1 rejected before creating
`atlas-v001`. Visual inspection of the contact sheet shows silhouettes and internal
foliage gaps; it is not botanical correctness or user acceptance. Review pale birch
bark/leaves and fine branches at full resolution, halos, flowers and proportions.

## Explicit approval and atlas evidence

> «Одобряю» — Artem, 2026-10-15 ~21:58, Telegram via orchestrator.

Scope: all three exact cut-out/opacity pairs in `review-sheet-v001.png` above,
as delivered in the operator's direct message on card `t_4005c4b2` and confirmed
by the owner's [issue #190 comment](https://github.com/artsafro/AGR-DigitalTwin-pilot/issues/190).
The minute is approximate; no exact timestamp/timezone was supplied. The external
`approvals-v001.json` records date-only ISO `reviewed_at`, quote, source, candidate
IDs and unchanged review hash. No new species inherit this approval.

Packed `C:/x/flora-textures/atlas-v001/` using `--max-tile-size 768`:

| File | Bytes | SHA-256 |
|---|---:|---|
| Flora_d_1.png | 2416707 | `3fbf6704bdfc25245b21efff22efda681746e32e164192f4d586e3b854692b72` |
| Flora_o_1.png | 61294 | `3295e7c2a20433ab8b37594c5ad6e313f3c3e0c3b51025f46f8aa8264ebedb7b` |
| atlas.json | — | `b3cba5b706f8a1debf823e4efd989a2072cc410d5452d1e1fef37e64c7ce0dec` |

Readback: 2/2 maps 2048 square, RGB/L, no alpha/transparency metadata, opacity
only 0/255, both <=3 MiB. Manifest: 3/3 approved IDs, exact pixel-to-UV conversion,
3/3 rectangle pairs separated, >=8px border margins. Full numeric report:
`C:/x/flora-textures/atlas-evidence-v001.json`. Worker viewed both atlas maps:
three distinct unclipped silhouettes with foliage gaps, no obvious corruption.
This is texture-candidate approval, not an FBX/package or full NPM delivery pass.
