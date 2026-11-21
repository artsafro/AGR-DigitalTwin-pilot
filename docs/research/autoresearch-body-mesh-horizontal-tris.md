# Standing #27 — horizontal-triangle area share: G22 etalon vs rejected bodies (OBSERVE)

## Frozen contract

Continues #26 (`origin/research/autoresearch-standing-26` `9e1de4d8`) next target and #19 (`autoresearch-body-mesh-r3-localize.md`):
the R3 signal on rejected 63B v001–v005 was 100 % horizontal triangles, while the G22 etalon (#25) carries
7733/1589/1873 residual triangles after the #1618 rejoin. Question: does the **placement** of triangles (horizontal
faces) separate accepted from rejected bodies, where the plain triangle count (R3) did not? Diagnostic only — no
scorer, rule, builder, geometry or delivered package changes. Not duplicated: #1736/#1742 (builder), #1649 (atlas),
#1609/#1627 (KPP1 corners), #1722 (63B stage 2), #1315/#1622/#1738/#1608 (cold runs), #1748/#1751 (skeleton), #1615 (suite).
No speed target: the quality target is not blocked.

**Metric (one number):** worst separation margin `M = min(H rejected) − max(H accepted)`, where per corpus
`H = area(triangles with |n_z| ≥ cos 1°) / area(all faces with |n_z| ≥ cos 1°)`. Normals and areas by Newell's
formula on the stored polygon (no triangulation of n-gons, no welding, no z clipping beyond the stored band).
Median of three reads per corpus; paired spread must be 0.

**Keep threshold (for the diagnostic feature, still OBSERVE):** `M > 0` (every rejected body has a higher horizontal
triangle share than every accepted one). Secondary, reported but not deciding: the same margin without 63B v006
(#19: its defect is degenerate quads, not triangles) and the vertical-triangle share `V` (|n_z| ≤ sin 1°) for context.
A pass keeps NO code: it only nominates the feature for a later, separately frozen penalty experiment.

**Fixture (labels from #17/#19/#25, frozen; SHA-256 of the exact file read):**

| Corpus | Label | File | SHA-256 |
|---|---|---|---|
| 63B v001 | rejected | `C:/x/ar15/r1/tmp/63B-v001.1/dump.json` | `d98a129ee2035c1436763a5c47c0705edd39a5c4ccf7675584d87b4f0a3a6f57` |
| 63B v002 | rejected | `C:/x/ar15/r1/tmp/63B-v002.1/dump.json` | `b1d2098f34e97a07578adf06b4c83f96279f70564c4383f66f9221ee09979981` |
| 63B v003 | rejected | `C:/x/ar15/r1/tmp/63B-v003.1/dump.json` | `1263be647aa9fd3b09714c6763d46676c735a13939dff587ccd342cb498b2a3d` |
| 63B v004 | rejected | `C:/x/ar15/r1/tmp/63B-v004.1/dump.json` | `bf115523c6dde6387a8c929342cf501fd179c8b22df1810ba6784280497ff30b` |
| 63B v005 | rejected | `C:/x/ar15/r1/tmp/63B-v005.1/dump.json` | `03db41df0ce700bad640633246590cf08a33d85a551e9a8391d45bbc785d9554` |
| 63B v006 | rejected | `C:/x/ar15/r1/tmp/63B-v006.1/dump.json` | `fc41ff9ef238e5adceb114b7198f75bec2d08ebca12564bba925f02aca91fa04` |
| 63C v001 | rejected | `C:/x/ar15/r1/tmp/63C-v001.1/dump.json` | `d8e64e2a54a66b2b1b377ae4e9c1b2f21ac3e53deadd26e25f361631e88197a7` |
| KPP1 v003 corners | rejected | `C:/x/ar15/r1/tmp/KPP1-v003-corners.1/dump.json` | `4565eabf45a333868ea410358aa240a8c89dcac56175d67a697a098c36867596` |
| 63B v007 | accepted | `C:/x/ar15/r1/tmp/63B-v007.1/dump.json` | `c8d65372d76148d38ffeb6a14e0dbc0c3449536f2ddb627bbd7a3c24ff6ca416` |
| 63C v002 | accepted | `C:/x/ar15/r1/tmp/63C-v002.1/dump.json` | `19ee7c2046e37a5eeff76522a4b62a3f468f4fb02f1fd210cf912a8b2274ae7e` |
| 63A v005 | accepted | `C:/x/ev_t_f55bc192/63A.dump.json` | `3960fbdbc38f86d3f167128c1e7761928802d10a1f0d5726514a9afc2aa02b32` |
| G22 k2 v002r1 | accepted | `C:/x/ev_1619/r7/k2_v002r1.mq.json` | `2e922754e8b77f854627267fc75b1ba9c22c41a7c4713333fc34ba0ffaff431b` |
| G22 etalon k1 | accepted (etalon) | `C:/x/ev_1619/r2/etalon_k1.mq.json` | `413515339be03d1aa8eb88d23c487ce81f1605eced51d3b822d2919141acefb1` |
| G22 etalon k2 | accepted (etalon) | `C:/x/ev_1619/r4/etalon_k2.mq.json` | `50df5fb7252078a3fc1edc9076b9e0043051f897bb3aa363b2014b404e6f8d0d` |
| G22 etalon k3 | accepted (etalon) | `C:/x/ev_1619/r1/etalon_k3.mq.json` | `dc389b008673016871591e1cb42f151379b63aa2ffe271590c52b3009a7d4a13` |

Frames: agent bodies are whole-body readbacks; G22 bands are the #1619 z bands (same JSON as #25/#26). H is a ratio
inside each corpus, so band clipping changes the denominator and numerator together; it is still a frame difference
and is reported as such.

**Clean checks:** input hashes before and after; three identical reads per corpus; triangle counts of the etalon equal
#25/#26 (7733/1589/1873); every corpus has non-zero horizontal area. **Injected:** a wrong expected hash must fail
closed before geometry is read; swapping one rejected label to accepted must change M (oracle is live).
**Not measured:** fresh DCC readback, editable source topology, semantics of the triangles (floor vs roof vs cap),
any new penalty or recalibration, builds or delivery checks.

Replay: `../../.venv/Scripts/python.exe docs/research/autoresearch-body-mesh-horizontal-tris-harness/replay.py C:/x NEW.json`.

**Budget / stop rule:** one baseline measurement (this is a feature read, not a tuned candidate), zero new candidates,
three reads per corpus; stop on one complete receipt, a provenance/parity failure, or 5 minutes wall. Forbidden:
retuning the 1° tolerance after seeing data, relabelling corpora, dropping corpora, test deselection, weakened checks,
edits to scorer/builders/geometry/delivered packages or other cards' files.

## Round log

(filled after measurement)
