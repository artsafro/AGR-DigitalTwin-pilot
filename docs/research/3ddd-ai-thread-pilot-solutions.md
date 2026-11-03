# 3ddd.ru "AI – Нейросети" thread: solutions useful for the pilot

Status: research report (no code changed)
Date: 2026-11-03
Source: https://3ddd.ru/forum/thread/show/ai_neiroseti, pages 1–278 (2023-05-01 – 2026-11-02), all pages read
by four scouts. Page dates: p.1–90 to 2025-12, p.91–170 to 2026-08, p.171–230 to 2026-10-01, p.231–278 to
2026-11-02. Everything below is a **forum claim** unless marked *verified* (checked on the vendor page).
About 60 % of pages are off-topic. Nothing was posted, logged in to or downloaded.

## TL;DR

The thread confirms our approach rather than replacing it. Its strongest results come from an agent working
**inside a template** (reference model + atlas + naming rules) or **editing existing geometry**. Generating
from drawings fails on dimensions every time it is tried. Worth acting on:

1. **GeoAGR** (paid MaxScript tool for AGR by forum user GeorgiyS, p.240): auto-generates UCX for buildings
   "like VHACD / CoACD". This is the only direct analogue of our pipeline in the thread. Find the author or
   the product and compare it with our UCX path.
2. **Template-driven Flora** (p.199): an agent got a ДГП reference bush in 3 sizes, an overlap atlas,
   texture naming rules, example diffuse and mask maps and a plant booklet, and produced "80–90 %" of the
   material in under 5 minutes. This is the pattern for P11 Flora and P10 MAF.
3. **Agent edits existing glazing** (p.222): an agent re-placed broken mullions in an FBX to match new
   facades, reportedly saving "12 hours". The same class of task as our BODY/windows corrections.
4. **MAX Ultra MCP** (p.208, *verified*: https://maxpkg.dev/catalog/max-ultra-mcp, 3DGROUND, Max 2022–2027,
   multi-instance, 9 skills, source on github.com/maxpkg-dev/max-ultra-mcp, licence not stated): compare its
   tool set with our `3dsmax-mcp` and take ideas, not a replacement.
5. **Local image-to-3D in Blender** (p.278, *verified*: https://superhivemarket.com/products/imageto3d,
   $18 GPL add-on, TRELLIS / Pixal3D / Hunyuan, NVIDIA 8–12 GB VRAM, ~90 GB weights, Blender 4.2–5.2;
   check the model licences separately). A cheap local way to test image-to-3D on 2–3 MAF items.

## Candidates by pilot area

| Area | Solution | Pages | What users report | Fit |
|---|---|---|---|---|
| UCX | GeoAGR (MaxScript, written with Gemini), VHACD/CoACD-style decomposition | 240 | paid, no link; Gemini writes good MaxScript with a sample script and step-by-step guidance | high |
| Flora / MAF | agent fills a template: reference model + atlas + naming + example maps | 199 | "80–90 %" in < 5 min; polycount and acceptance not reported | high |
| BODY / windows | agent edits existing FBX geometry (mullions) | 222 | "Справилась", ~12 h saved; needs ready parts to assemble from | high |
| Scripting | Claude (Opus) for MaxScript; Codex runs and tests Max itself | 192, 220, 240–273 | 80+ scripts in a month (material dedupe, MatID panel, UVW copy, reset xform); Claude is the only model that knows MaxScript well; fails on dotNet interop in MaxScript; Codex ~€200/month | high |
| Scripting | MAX Ultra MCP | 208 | link only, no reviews | medium |
| MAF | Tripo (cloud; Smart Mesh, quads, new smart UV, 8K) | 110–273 | organics and far plane only; heavy meshes, one texture for everything, not to size; real cost ~$10 per model, not $2 | medium |
| MAF / Flora | Hunyuan3D 3.x (local in ComfyUI or the add-on above) | 48–278 | best open model; 1–2 M polys, lighting baked into diffuse, weak on hard surface | medium |
| MAF | Hitem3D (Spark), Meshy, Autodesk Wonder 3D | 124, 145 | Hitem3D better on hard surface; Wonder 3D promises "correct geometry", untested | medium |
| MAF / Flora | pipeline AI mesh → retopo → RizomUV → reproject texture (StableProjectorZ, tyDiffusion) → bake | 53, 59, 73, 79 | slow, mid-quality textures; retopo can take longer than modelling from scratch | benchmark for buy-vs-build |
| Textures | Substance 3D Sampler (material from a sample, upscale node) | 132–133 | semi-automatic, works | high |
| Textures | GPT image: seamless "UV-ready" maps, height/normal/roughness from a photo | 229 | "просто песня" with a 3D-artist prompt; Gemini worse; repeated patterns in asphalt and foliage persist | medium-high, with manual tiling checks |
| Textures | Nano Banana, Flux.2 img2img (low denoise), SeedVR2 / Upscayl upscale | 91–275 | not truly seamless, ~1–2K cap, upscalers eat detail | low-medium (preprocessing only) |
| Facade photos | Camera Raw Remove Reflections; FLUX Kontext / Qwen Edit | 57–67 | works, but generative editors change geometry and scale | medium (raster only, never a size source) |
| QA / process | Git repo of contracts and instructions; corrections drawn on screenshots | 268 | "Opus honestly said it does NOT see what it models"; idea of formula-based fences and curbs (~4 KB file) | medium (matches our harness) |
| QA | SAM segmentation; ID / depth / material passes as conditioning | 143, 242 | segmentation services fail on overlaps and reflections | low-medium |
| Reading drawings | GPT Astra, getleo.ai, custom GPT: DWG/DXF → model or general plan | 164–272 | "размеры по бороде", ~20 % wrong categories, heights ignored; fixing takes longer than doing it by hand | low |
| Local stack | Gemma 4 31B 4-bit (16 GB VRAM + 32 GB RAM, 10–15 tok/s, good Russian), Qwen 3.5, ComfyUI | 123, 141, 266–278 | fragile, version-bound; images need ≥ 16 GB VRAM | medium (offline reviewer or fallback) |
| Fallback agent | opencode (open-source CLI, any provider or local model) | 275 | for bans and KYC blocks from RU | low-medium |
| Asset library | Project Manager (3ds Max, AI asset categorisation) | 165–167 | search "стал шикарно" | medium |

Not recommended: GPU firmware unlock patches (risk of bricking the card), DLSS-5 render enhancers (they alter
the image, harmful for QA), tools for opening .max files without Max (unproven), SD 1.5 / A1111 / Fooocus /
TripoSR (superseded).

## Recurring lessons from the thread

1. **AI geometry is a draft.** Sizes, proportions, window heights and roof logic come out wrong, and the
   model cannot see its result. External readback is mandatory (our `validate-delivery` and gates).
2. **A script beats screen control.** Generated MaxScript or Python plus a check works; driving a DCC from
   screenshots is slow and unreliable. Single-shot code breaks on context: groups, pivots, legacy code,
   engine versions. Give the agent the API documentation for the exact version.
3. **Template, rules, reference.** The good results (ДГП bushes, mullions) all had a reference model, an
   atlas and naming rules. A free-form prompt produces slop.
4. **Image-to-3D only for organics and the far plane.** One texture, no material split, not to size:
   retopo, bake, repack into our 512 atlas and a size check are still needed. A stock model is often faster.
5. **Agents do unrequested work and burn limits.** Users report unasked patches, exports and previews
   (a WSJ retelling says GPT-6.1 Astra was delayed for this reason). This supports our guard, read-only start
   and versioned output paths.
6. **Generated images are not a reference.** Views are inconsistent between angles even with a fixed seed,
   so a generated view can never be a QA etalon.
7. **Access from RU** (payment, VPN, +86 phone, KYC) drives the choice of cloud services. Keep a local
   or open-source fallback.

## Suggested next steps (none started)

- Find GeoAGR / GeorgiyS on 3ddd: what the UCX decomposition does and how it compares with our UCX checks.
- P11 / P10: write the Flora and MAF agent task as a template (reference + atlas + naming + example maps),
  following the p.199 pattern.
- Run the local Image to 3D add-on (or Hunyuan3D in ComfyUI) on 2–3 MAF items from a specification and
  measure poly count, topology and fit to the 512 atlas. Needs the user's yes: a $18 purchase and ~90 GB of
  weights.
- Compare the MAX Ultra MCP tool list with `3dsmax-mcp` (multi-instance selection, skills).
