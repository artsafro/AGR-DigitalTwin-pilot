"""#298 D125 diagrams from exported-model measurements and the real SPOZU adapter.

new-case: job-local source overlay, material legend and relief section plots.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from PIL import Image, ImageDraw
from shapely.geometry import Polygon, shape
from shapely.ops import unary_union

folder = Path(sys.argv[1])
evidence = json.loads((folder / 'evidence.json').read_text())
adapter = json.loads(Path('C:/x/t_d94665f2/paving_ground_inputs_v4.json').read_text(encoding='utf-8'))
# Ground origin offset: optional 2nd argument (v015: textured/readback_npm.json); default the v014 run.
offset_file = sys.argv[2] if len(sys.argv) > 2 else 'C:/x/t_d94665f2/ground_v014/readback_npm.json'
offset = json.loads(Path(offset_file).read_text())['placement_offset']
cam = evidence['views']['top']
scale = 768 / cam['ortho_scale']

def project(x, y):
    return ((x - offset[0] - cam['camera_location'][0]) * scale + 384,
            384 - (y - offset[1] - cam['camera_location'][1]) * scale)


def rings(geom):
    if geom.is_empty:
        return
    if geom.geom_type == 'Polygon':
        yield geom.exterior.coords
        for ring in geom.interiors:
            yield ring.coords
    elif hasattr(geom, 'geoms'):
        for g in geom.geoms:
            yield from rings(g)


base = Image.open(folder / 'material_ids_top.png').convert('RGBA')
canvas = Image.new('RGBA', base.size, (245, 245, 245, 255))
canvas.alpha_composite(base)
draw = ImageDraw.Draw(canvas)
source_slots = {'tile_light': 'TileLight', 'tile_red': 'TileRed', 'tile_dark': 'TileDark', 'pebbles': 'Pebbles', 'gravel_screening': 'Gravel', 'decking': 'Decking', 'mulch': 'Mulch', 'lawn_reinforced': 'LawnReinforced', 'lawn_rolled': 'LawnRolled'}
source = defaultdict(list)
for key, value in adapter['coverings'].items():
    slot = 'FlowerBed' if key.startswith('flower_bed') else source_slots[key]
    geom = shape(value['geometry'])
    source[slot].append(geom)
    for ring in rings(geom):
        draw.line([project(*p[:2]) for p in ring], fill=(0, 80, 0, 180), width=1)
for ring in evidence['source_overlay']['boundary']:
    draw.line([tuple(p) for p in ring], fill=(255, 255, 0, 255), width=3)
for key, color in [('planting', (0, 255, 255, 220)), ('maf', (255, 40, 0, 255))]:
    for x, y in evidence['source_overlay'][key]:
        draw.ellipse((x-1, y-1, x+1, y+1), fill=color)
draw.rectangle((0, 0, 767, 36), fill='white')
draw.text((8, 5), 'Model ID render + SPOZU: green=hatch edge; yellow=568BF; cyan=planting; red=MAF', fill='black')
canvas.convert('RGB').save(folder / 'spozu_overlay.png')

# Material-ID legend is independent of the shader's pseudo-colour meaning.
legend_image = Image.new('RGB', (820, max(200, len(evidence['legend']) * 24 + 40)), 'white')
ld = ImageDraw.Draw(legend_image)
ld.text((8, 8), 'Delivered material IDs (not an approval of the covering colour)', fill='black')
for row, (name, info) in enumerate(evidence['legend'].items()):
    y = 36 + row * 24
    color = tuple(round(c ** (1 / 2.2) * 255) for c in info['rgb'])
    ld.rectangle((8, y, 30, y + 18), fill=color)
    ld.text((40, y), f"{info['id']}: {name}", fill='black')
legend_image.save(folder / 'material_id_legend.png')

actual = defaultdict(list)
for name, coords in json.loads((folder / 'ground-polygons.json').read_text()):
    slot = re.sub(r'\.\d+$', '', name).removeprefix('M_Vatutino_Ground_')
    if slot in source:
        actual[slot].append(Polygon([(x + offset[0], y + offset[1]) for x, y in coords]))
actual = {k: unary_union(v) for k, v in actual.items()}
# Method C: TileLight is the lower base, hidden by every upper covering.
if 'TileLight' in actual:
    upper = unary_union([v for k, v in actual.items() if k != 'TileLight'])
    actual['TileLight'] = actual['TileLight'].difference(upper)
boundary = shape(adapter['boundary'])
area_rows = []
diff = Image.new('RGB', (768, 768), 'white')
dd = ImageDraw.Draw(diff)
for slot, geometries in source.items():
    expected = unary_union(geometries).intersection(boundary)
    observed = actual.get(slot, Polygon())
    excess, missing = observed.difference(expected), expected.difference(observed)
    area_rows.append({'slot': slot, 'source_hatch_union_m2': expected.area, 'model_visible_projected_m2': observed.area,
                      'delta_m2': observed.area - expected.area, 'extra_m2': excess.area, 'missing_m2': missing.area})
    for geometry, color in [(missing, '#ff4040'), (excess, '#4060ff')]:
        for ring in rings(geometry):
            dd.line([project(*p[:2]) for p in ring], fill=color, width=2)
for ring in evidence['source_overlay']['boundary']:
    dd.line([tuple(p) for p in ring], fill='black', width=1)
dd.text((8, 8), 'Covering differences: red=source not in matching model slot; blue=model excess', fill='black')
diff.save(folder / 'covering_differences.png')
(folder / 'covering_deviations.json').write_text(json.dumps(area_rows, indent=1))

for i, section in enumerate(evidence['sections']):
    spot = section['spot']
    values = [z for x, z in section['samples'] if z is not None] + [spot['source_z']]
    z0, z1 = min(values) - .05, max(values) + .05
    image = Image.new('RGB', (1000, 360), 'white')
    sd = ImageDraw.Draw(image)
    sd.text((10, 8), f"VP {spot['ref']} y={spot['y']:.3f}; source={spot['source_z']:.3f}; model={spot['model_z']}; dz={spot['deviation_m']}", fill='black')
    previous = None
    for j, (x, z) in enumerate(section['samples']):
        if z is None:
            previous = None
            continue
        p = (40 + j * 9.2, 310 - (z - z0) / (z1-z0) * 250)
        if previous:
            sd.line((previous, p), fill='blue', width=2)
        previous = p
    y = 310 - (spot['source_z'] - z0) / (z1-z0) * 250
    sd.ellipse((495, y-5, 505, y+5), fill='red')
    sd.text((10, 330), 'Blue=delivered Ground section (+/-5m X); red=source spot; gaps=no Ground hit (not zero error)', fill='black')
    image.save(folder / f'section_{i+1:02d}.png')
print('DIAGRAMS', folder, len(area_rows), 'covering rows;', len(evidence['sections']), 'sections')
