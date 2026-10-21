# Ground v015 strict-remesh plan

Status: **NOT_DELIVERY**. Authorized by Artem on card #371, 2026-10-21 22:57.
Base: `7ac17a9`; retained geometry: CPU v009. This plan replaces pair-only construction,
not the acceptance rules. Previous 90k Steiner and 4/5/6 m coarsening routes remain rejected.

## Frozen gates

- Public unchanged `texel_ready`: aspect <=8, NPM size <=50.8 m, VPM edge <=4 m;
  prefer <=3.9 m to avoid padded-tile review. No texel exception.
- Surface <=50,000 polygons; NPM whole Ground <=180,000 triangle-equivalent,
  with remaining MAF/Flora capacity reported, never silently spent.
- Original semantic contours within 2.2 mm, except the explicitly approved D169 triangle.
- TIN relief <=10 mm; v014/source silhouette and surface reach checked separately.
- Ours and final Max xView 0/0 at 0.002/0.005 m. Check float32 and both diagonals,
  including mixed neighbouring fans, normal layer gaps and UV winding.
- D150 exact accepted world samples and frozen maxima remain separate from raw gap counts;
  no new/increased >20 mm sample is accepted by this plan. Re-pinning requires correspondence,
  not rewriting the exception file to match a changed result.
- Fixed 12 texture material IDs; both profiles from one source master; native/FBX/readback,
  collision, placement and review publication remain final-file gates.

## Construction sequence and stop conditions

1. **Remove artificial tessellation constraints, not physical boundaries.** Extract connected
   same-slot/same-level planar patches from v009 fixed-fan triangles. Preserve every source face
   in exactly one patch and all material/level/crease boundaries; freeze D150 neighbourhoods.
   Test disconnected coplanar components, near-coplanar drift, winding, partial/nonfinite inputs.
   Compare exact planar union and source/output area; source membership is not shape proof.
2. **Contour-first constrained re-meshing.** Generate a quality-sized mesh inside the planar
   patch boundaries; use quad recombination and local contour-following strips for narrow bands.
   Discard old 4 m grid diagonals and unnecessary source interior samples. Do not subdivide all
   v014 triangles into Steiner quads (already rejected). Do not use unconstrained coarsening.
   Prove shared boundary node agreement before stitching. Run cheap real-size count/texel/xView
   and gap probes before DCC. A failed diagnostic remains NOT_DELIVERY.
3. **Bounded local repair only.** If quality fails at physical slivers, retain their coordinates
   and identities. Try geometric construction fixes under the existing contour/relief bounds,
   not a material-priority change, hole fill or source deletion. If a physical source conflict
   remains, preserve its exact witness and ask only the required model decision.
4. **Derive and publish only after CPU gates.** Rebuild profile UV charts and semantic IDs;
   export quads without triangulation; read back real loop triangles, exact raw IDs and maps.
   Rebuild UCX and placement receipts for the new master hash. Run final-file Max xView,
   directed shape probes, DCC tests, slotted final full suite, review scene/pending entry and PR.

No old CPU, Max or texture receipt transfers to a new remesh. A successful primitive or
budget probe is not model acceptance, and no failed candidate is sent to review.

## ID integration

Origin/main's D156 belongs to TOW02. Our historical Ground-only 90k permission was mechanically
renumbered to D170 on integration; D157 supersedes D170. Original session narratives keep their
historical D156 spelling where reporting past events. Main TOW02 content is unchanged.
