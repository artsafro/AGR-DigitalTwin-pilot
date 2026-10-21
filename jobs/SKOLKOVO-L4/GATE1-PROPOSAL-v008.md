# Skolkovo L4 — exact-hash Gate 1 design proposal v008c

**This asks permission to START building, not acceptance of a built model.**

PartsList SHA-256: `f1867120b2c7072405d32440a27382a0be8bb2bf9edc56c9fbc2876eb3ff2302`

Canonical external file: `G:/Мой диск/AGR-evidence/353-skolkovo-l4/evidence-v008/parts-gate1-proposal-v008c.json`.

## What is proposed

- 49 parts, 6955 retained source objects, 32961 accounted/unique source rows.
- 7,059 superseded exact-source counterparts; 18 superseded facade-package objects; 18,929 reasoned drops. Whole interior omitted and glazing opaque by the existing decision.
- Planned master allocation 147,000 /150,000 triangles, reserve 3,000. **Not measured output.**
- Five primary mast assemblies: source-bound duplicate/internal-intersection cleanup, weld/retessellation. Fixed supplied FBX position, heights and exterior profile; no PDF-rescale, no replacement mast.
- 108 separate KNS members: source-profile simplification, <=0.02 m silhouette, total target10,000. **This remains a target:** straight/PCA constant-prism analytical attempts gave88,708/85,212, not 10,000. Next route needs varying source sections/profiles; a failed budget or invariant rolls back, never a waiver.
- Facade from the September revision; retained v1 roof/deck/soffit/access source candidates fill what the facade-only file omits. From-face/contour recipes keep only the genuine exterior; fully hidden source faces are reported as drops, not silently retained as internal duplicates.
- F.9 is now linked to22 actual vertical source panels in four source-position columns, not guessed from grey names. Three horizontal caps are separate F.10. See `gate1-lamella-source-match-v008.png` and its exact-row witness.
- Every retained source has an explicit material/legend binding. Revised profiles/plinth use RAL7015. VPM-derived appearance remains reference-derived, NOT independent material validation. No VPM geometry is used in the build.

## Planned joint recipes (not achieved joints)

- 291 conservative part-pair records from 17,355 source object bbox candidates at0.003 m Euclidean gap:240 weld,51 embed.
- A bbox hit is NOT a measured surface contact. Reconcile on actual selected source surfaces; false bbox contacts are rejected/reported, never bridged. These are candidate-conditioned recipes, not a claim that all291 seams physically exist.
- Weld: split true common boundaries, remove proven hidden/internal mating faces, weld that joint only; no global merge-by-distance or artificial bridges. Primary masts never move.
- Opaque glazing/door/frame: keep separate material/output groups;10 mm insertion beneath receiving frame, visible source outline and real seating preserved. Refuse if the source seating does not permit it; no global pane translation or common Shell.
- `extra_edges` is a DESIGN allocation of four endpoints per source candidate, not a measured retopology count or mathematical bound. Refuse/replan if actual required segmentation exceeds it. Added topology must fit the same per-part triangle ceilings; the allocation grants no extra triangles.

## Per-part operation/legend/budget decision table

| Part | Sources | Operation | Legend | Planned triangles NPM=VPM |
|---|---:|---|---|---:|
| `facade_additional_entrance_details_other_detail_per_profile` | 12 | `detail_per_profile` | `vpm:entrance_detail` | 168 |
| `facade_additional_exterior_doors_door_from_face` | 3 | `from_face` | `F.8` | 36 |
| `facade_additional_exterior_railings_railing_contour_rebuild` | 12 | `contour_rebuild` | `F.6` | 288 |
| `facade_additional_exterior_slabs_access_slab_contour_rebuild` | 18 | `contour_rebuild` | `vpm:exterior_slab_access` | 896 |
| `facade_additional_opaque_panels_wall_from_face` | 1 | `from_face` | `vpm:exterior_panel` | 2 |
| `facade_canopy_slab_from_face` | 1 | `from_face` | `F.7` | 32 |
| `facade_cassette_perimeter_profiles_frame_contour_rebuild` | 2632 | `contour_rebuild` | `F.10` | 21056 |
| `facade_decorative_lamellae_decor_contour_rebuild` | 22 | `contour_rebuild` | `F.9` | 264 |
| `facade_entrance_glazing_door_from_face` | 7 | `from_face` | `F.5.1` | 56 |
| `facade_exterior_substrate_reveals_wall_from_face` | 293 | `from_face` | `vpm:exterior_reveal` | 2344 |
| `facade_external_metal_doors_door_primitive` | 3 | `primitive` | `F.8` | 36 |
| `facade_external_railings_railing_detail_per_profile` | 327 | `detail_per_profile` | `F.6` | 7848 |
| `facade_external_reveals_band_from_face` | 10 | `from_face` | `F.10` | 80 |
| `facade_facade_cassettes_wall_from_face` | 3 | `from_face` | `F.1` | 36 |
| `facade_lamella_top_caps_band_contour_rebuild` | 3 | `contour_rebuild` | `F.10` | 36 |
| `facade_mullions_frame_contour_rebuild` | 407 | `contour_rebuild` | `F.5.1` | 3256 |
| `facade_opaque_glazing_glazing_from_face` | 129 | `from_face` | `F.5.1` | 258 |
| `facade_parapet_flashings_parapet_contour_rebuild` | 2 | `contour_rebuild` | `F.10` | 1024 |
| `facade_perforated_cassettes_wall_from_face` | 477 | `from_face` | `F.2` | 954 |
| `facade_plinth_flashings_band_contour_rebuild` | 10 | `contour_rebuild` | `F.10` | 2560 |
| `facade_plinth_wall_from_face` | 27 | `from_face` | `F.4` | 324 |
| `facade_roof_and_entrance_details_other_contour_rebuild` | 19 | `contour_rebuild` | `source:exterior-detail` | 4864 |
| `facade_roof_screen_ac_screen_from_face` | 4 | `from_face` | `F.3` | 48 |
| `facade_roof_substrate_skins_wall_from_face` | 764 | `from_face` | `vpm:roof_enclosure` | 6112 |
| `facade_roofs_slab_contour_rebuild` | 284 | `contour_rebuild` | `source:roof-membrane` | 6816 |
| `facade_soffits_slab_from_face` | 152 | `from_face` | `source:exterior-soffit` | 2432 |
| `facade_solid_cassettes_wall_from_face` | 733 | `from_face` | `F.1` | 1466 |
| `facade_stemalite_glazing_from_face` | 6 | `from_face` | `F.5.2` | 24 |
| `facade_vent_grilles_grille_detail_per_profile` | 7 | `detail_per_profile` | `F.5.3` | 112 |
| `facade_window_flashings_band_contour_rebuild` | 7 | `contour_rebuild` | `F.10` | 448 |
| `rods_additional_kns_components_rod_ladder_contour_rebuild` | 108 | `contour_rebuild` | `source:preserved_mast` | 10000 |
| `rods_primary_mast_meshes_rod_ladder_contour_rebuild` | 5 | `contour_rebuild` | `source:preserved_mast` | 55230 |
| `v1_additional_exterior_doors_door_from_face` | 1 | `from_face` | `F.8` | 12 |
| `v1_additional_exterior_slabs_access_slab_contour_rebuild` | 48 | `contour_rebuild` | `vpm:exterior_slab_access` | 790 |
| `v1_baseline_entrance_slabs_slab_contour_rebuild` | 2 | `contour_rebuild` | `vpm:roof_deck_or_entrance` | 40 |
| `v1_baseline_external_structure_frame_contour_rebuild` | 92 | `contour_rebuild` | `vpm:exterior_structure` | 3560 |
| `v1_baseline_roof_access_railing_contour_rebuild` | 120 | `contour_rebuild` | `vpm:roof_access` | 7680 |
| `v1_baseline_roof_access_rod_ladder_contour_rebuild` | 3 | `contour_rebuild` | `vpm:roof_access` | 1536 |
| `v1_baseline_rooftop_concrete_wall_from_face` | 35 | `from_face` | `vpm:roof_enclosure` | 902 |
| `v1_baseline_rooftop_decks_slab_contour_rebuild` | 17 | `contour_rebuild` | `vpm:roof_deck_or_entrance` | 912 |
| `v1_exterior_substrate_reveals_wall_from_face` | 19 | `from_face` | `vpm:exterior_reveal` | 152 |
| `v1_external_railings_railing_detail_per_profile` | 22 | `detail_per_profile` | `F.6` | 528 |
| `v1_mullions_frame_contour_rebuild` | 18 | `contour_rebuild` | `F.5.1` | 144 |
| `v1_opaque_glazing_glazing_from_face` | 7 | `from_face` | `F.5.1` | 14 |
| `v1_plinth_flashings_band_contour_rebuild` | 1 | `contour_rebuild` | `F.10` | 256 |
| `v1_roof_and_entrance_details_other_contour_rebuild` | 1 | `contour_rebuild` | `source:exterior-detail` | 256 |
| `v1_roof_substrate_skins_wall_from_face` | 51 | `from_face` | `vpm:roof_enclosure` | 408 |
| `v1_roofs_slab_contour_rebuild` | 28 | `contour_rebuild` | `source:roof-membrane` | 672 |
| `v1_vent_grilles_grille_detail_per_profile` | 2 | `detail_per_profile` | `F.5.3` | 32 |

## Conditions and next steps

1. Artem approves this exact PartsList SHA, or returns specific plan changes. Existing source/interior/mast/material decisions are not being asked again.
2. Only after approval: kernel operations with before/after invariants and true source-bound joints; source/output topology, silhouettes and measured budgets. A refusal/failure is preserved and cannot become pass.
3. Derive NPM/VPM from the same master; new versioned exports and clean-process readback. No input, accepted file or user live scene is overwritten.
4. Source/album/delivered comparison, board review tool and Artem visual approval on exact export hashes, then complete final SINTEZ.
5. Full suite through suite_slot only on the first complete review head, receipts, one PR, dt-reviewer.

**Not performed:** kernel build, achieved 10k reduction, clean topology after cleanup, export/readback, final visual approval, SINTEZ. `passed=false`, no PR.
