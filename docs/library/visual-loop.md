# Version-bound library visual loop

Use with [TASK_TO_MODEL](../procedure/TASK_TO_MODEL.md), its visual gate [D104, D119].
Notification is not acceptance. A code review, successful render or delivered Telegram
message cannot substitute for Artem's answer.

## Freeze before asking

1. Select one exact asset/object and its complete dependency boundary. Record source
   container/map SHA-256 and sizes; keep source bytes and UVs unchanged. Distinguish
   a source asset from a certified profile export and a cultivar from a generic species.
2. Open a **copy**, starting read-only. Record application/version, document, units,
   object selector and native inventory. Acquire the shared Max session lock through
   `dcc_batch.py`; never operate on another agent's/user's live scene.
3. Render to an unused, versioned evidence directory. Read the actual image back and
   inspect framing, transparency and obvious defects. Retain native logs, source/map
   hashes and SHA256SUMS outside Git. Source/render exit 0 is not visual acceptance.
4. Put the review question and picture on the owning board card; Telegram only
   notifies the owner. Use the configured gateway send route, **once per request**.
   Include asset/object, full version SHA-256, preview path/image and the question:
   `принимаешь эту версию?` with `принять / отклонить + причина`.
   If send fails, record `not_sent`; never call an unsent draft `pending`.

## Identity and answer

The A101 v002 example uses the SHA-256 of UTF-8 canonical JSON:
`json.dumps(identity, sort_keys=True, separators=(',', ':')).encode()`.
`identity` contains exactly `scene_sha256`, `object`, `rgba_sha256`,
`diffuse_sha256`, `opacity_sha256` (all strings). It excludes review status,
transport metadata and paths, so recording an answer does not change asset identity.
File SHA-256 is still checked separately. A path or version label alone is not identity.

A `library-visual-verdict-v1` record contains:

- request ID, asset label, exact version digest and the complete `identity`;
- preview SHA-256, bytes and retained evidence path;
- native application/document/units/object measurements and bounded scope;
- exact question; observed transport platform/message ID, success and mirror result;
- `status=pending`, `answer=null`, `answer_source=null` until an answer exists;
- after a reply: verbatim answer and source message ID **replying to that request**,
  or an operator's explicit hash-bound relay, then `approved` or `rejected`.

Read the transport response back; where available check its gateway mirror and reply
identity. Do not resend because an answer has not yet arrived. Do not infer approval
from a different thread, an earlier v001 approval, an agent's confidence or silence.
Update only `maps.json[latin].versions[version_sha256]` and that matching version in
the release manifest; do not promote unreviewed high/low siblings. A changed object,
container, RGBA, RGB/alpha pair or preview requires a new request/record; retain the old
one rather than overwriting its evidence or transferring its verdict.

Technical QA, source-asset visual approval, botanical/profile suitability and project
publication remain separate. A101 native atlas approval does not authorize binding it
to unrelated v003 library geometry or substituting a cultivar in a planting schedule.

## Executed example

[#1316 receipt](outside-retrieval-1316.md) and
[`visual-verdict-1316.json`](../../library/flora/visual-verdict-1316.json): Tilia
A101 low v002, request 4696, reply 4697 `Да, липа норм`, exact version
`a95cdd49b7a4e0dd8b495e8947165a2f62cf21301440d17e4e6927dde57c4480`.
Acer Royal Red has a separate request/record and no inherited Tilia approval.
