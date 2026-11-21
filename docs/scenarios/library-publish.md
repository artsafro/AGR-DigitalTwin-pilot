# Library publish (agent-made assets → AGR library)

**Кратко:** собрал МАФ / Флору / окна / крышное оборудование — публикуй одной командой
`agr library publish <партия>`; запись остаётся черновиком, пока Артём не скажет «ок» [D360].

## Read first

- [`docs/library/PUBLISH.md`](../library/PUBLISH.md) — stages, commands, read path.
- [`docs/library/TEMPLATE.md`](../library/TEMPLATE.md) — file cleanliness and pivot conventions.
- `docs/agents/SKELETONS.md`, cell `library-publish`; `docs/agents/skeletons.json`.

## Route

`intake` → `identify` → `name` → `qa` → `register` → `sheet`, all in `tools/library/publish.py`, one command.
Work on a copy of the batch (`C:/x/library-publish/inbox/<batch>` + SHA256SUMS); the `_inbox` original stays
read-only. Names by [D358]; files on Drive and catalogue in git by [D357]; an immutable `vNNN` per publish [D359];
kinds by [D361]. Send Artem the sheet path; `agr library accept|reject` only with his words.

## Stop

- A duplicate of an A101 record is not registered: use the existing record.
- No manufacturer source: the name is `AGR_<kind>_<Name>_<NNN>`; never invent a manufacturer or article.
- Never accept on Artem's behalf; never overwrite a version.
