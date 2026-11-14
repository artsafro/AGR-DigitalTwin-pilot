# Job checklist template

`job.yaml` here is the minimal checklist a new job starts from (#1310, F17). It walks
cleanly: exit 1 (nothing has passed yet) and no errors.

1. Copy `job.yaml` to `jobs/<ID>/job.yaml`; set `job_id`, `run_id` and `synthetic`.
2. Replace the single `inputs` row (this README, a placeholder) with the real source
   inventory: one row per file, each path once, SHA-256 of the bytes; external sources go
   through one `manifest: external-inputs/1` row (`docs/procedure/TASK_TO_MODEL.md`).
3. A gate that has not started stays `status: missing`; `note` and `evidence` may be omitted.
   Any other status needs a `note`; `pass` needs evidence.
4. Walk it: `uv run python -m dt_ai.procedure jobs/<ID>/job.yaml --root .`
