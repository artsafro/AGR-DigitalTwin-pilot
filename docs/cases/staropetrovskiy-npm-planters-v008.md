# Staropetrovskiy — NPM planter shrubs — Max v008

## User feedback and scope

On 2026-11-20 Artem corrected the workflow: find the soil by its pixel on the atlas, not by material ID; do not change MAF materials (15:28); use shrubs from the scene at their existing size (15:44); shrink only until the intersection disappears (15:53); keep GroundEl, Flora and Ground textures separate (14:39). Source: issue #1733, citing incidents 1, 4 and 5 of the Staropetrovskiy NPM/VPM retro. The issue records corrections and the v008 result, not an explicit user sign-off for that version.

## Inputs, corrections and reuse

The external job root is `C:/x/staropetrovskiy-maf-claude/`; all paths below are relative to it. The Max source is `site4/in_20.11/staropetrovskiy_maf_site_v005.max`, with customer Flora and maps in the same job. The early attempt used material IDs to locate planting spots and made shrubs too small. The corrected run selected upward triangles by their three UV corners in the sand slot and copied the original shrubs A and C from the source Flora mesh. The Flora mesh kept its own material. Source bitmap paths were resolved locally, not repacked into a combined atlas.

| External job script | Role and retained outputs |
|---|---|
| `site4/work/inspect_soil2.py` | Max read-only scene inspection: UV channel 1, job-specific sand slot and upward-normal cutoff; `inv_soil2.json` and `planters_full2.json`. |
| `site4/work/plan_shrubs3.py`, `site4/work/fix_plan3.py` | Plan from the spot inventory and MAF triangles, then recheck against the MAF readback. Retained plan: `site4/work/shrubs_plan3.json`. |
| `site4/work/shrubs_max3.py` | Copy and attach customer shrub geometry into the Flora object on a new scene version, `site4/staropetrovskiy_maf_site_v008.max`; `site4/work/shrubs_max3_report.json`. |
| `site4/work/dump_flora3.py`, `site4/work/check_shrubs3.py` | Read v008 Flora world triangles into `flora_v008.json`; check card crossings and sample soil/crown clearance against the retained MAF triangles. |

The v008 plan used crown widths of 1.225, 1.10, 0.98, 0.87, 0.77, 0.68, 0.60 and 0.55 m in descending order. **313 shrubs** were attached, **231 at full size (1.225 m, reported as 1.23 m)**; 13 reached the **0.55 m floor**. The widths, atlas coordinates and thresholds are job parameters, not defaults. The spot finder stays a job script; the reusable procedure and checklist are in [`model-flora`](../../.agents/skills/model-flora/SKILL.md#planting-into-maf-planters-npm). No shared code is promoted from this single site.

## Evidence and limits

- The retained Max report records 1,832 → 4,336 Flora triangles and 81,674 visible scene triangles. The latter is a scene count, not an exported Ground FBX budget receipt.
- Read-only replay of `check_shrubs3.py` from `site4/work` on the retained arrays gave 0 proper new-vs-any card crossings and 0 sampled crown/soil failures. The nine-ray clearance sampling and strict card-crossing predicate do not certify all geometric intersections. No fresh native readback, visual approval, SINTEZ or package QA was performed for this case capture; it does not establish delivery acceptance.
- Current retained SHA-256 (not hashes recorded during the historical run): v005 `dd1d878358639b7cb3790410f876c128ae458cb720702790409b2142344aa1f1`; v008 `391a715d6b8f3750a33dd3e2aba1a05f6287b677a7513c014f91973d053e35cb`; `shrubs_plan3.json` `bb85e7e3e8205fd45c63b626099beb482ecaf17724ef267726562df9844a3721`.
- The original job remains outside Git. This write-up and the [case index](../cases.md) are the repository record; no new job skeleton or state is created for this retrospective capture.
