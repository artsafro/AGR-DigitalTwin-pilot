"""Build a single NPM atlas from the newly normalised VPM UDIMs.

new-case: source-colour truba UDIM-to-atlas conversion with separate RGB opacity.
Source RGB/layout are authoritative (Artem, card comment 2026-10-22 18:46).
The KPP/AC08 recipe is retained: derive NPM pixels from VPM, not a second palette.
"""
from pathlib import Path
import json
import sys
import shutil
import numpy as np
from PIL import Image


def main(root):
    root = Path(root).resolve()
    generated = root / 'textures-vpm-source'
    vpm = root / 'textures-vpm'
    npm = root / 'textures-npm'
    if vpm.exists() or npm.exists():
        raise ValueError('new version required; map output already exists')
    files = sorted(generated.glob('T_Truba_1_*_1.1*.png'))
    if len(files) != 18:
        raise ValueError(f'expected 18 fresh VPM maps in {generated}, got {len(files)}')
    vpm.mkdir()
    npm.mkdir()
    for path in files:
        shutil.copy2(path, vpm / path.name)
    diffuse = Image.new('RGB', (2048, 2048), (173, 173, 173))
    opacity = Image.new('RGB', (2048, 2048), 'white')
    regions = {}
    for udim in range(1001, 1007):
        # The detailed railing gets most of the atlas; solid finishes need only swatches.
        x, y, cell = ((udim - 1001) * 256, 1792, 256) if udim < 1006 else (0, 0, 1792)
        pad, inner = 8, cell - 16
        with Image.open(vpm / f'T_Truba_1_Diffuse_1.{udim}.png') as source:
            rgba = source.convert('RGBA').resize((inner, inner), Image.Resampling.BOX)
            rgb = np.array(rgba.convert('RGB'))
            alpha = np.array(rgba.getchannel('A'))
        for target, pixels in ((diffuse, rgb), (opacity, np.repeat(alpha[..., None], 3, axis=2))):
            plate = np.pad(pixels, ((pad, pad), (pad, pad), (0, 0)), mode='edge')
            target.paste(Image.fromarray(plate), (x, y))
        regions[str(udim)] = {'u0': (x+pad)/2048, 'v0': 1-(y+pad+inner)/2048,
                              'size': inner/2048, 'cell_px': [x,y,cell], 'padding_px': pad}
    for suffix, image in [('d', diffuse), ('o', opacity)]:
        image.save(npm / f'T_Truba_1_003_Main_{suffix}_1.png', optimize=True)
    (root/'atlas-layout.json').write_text(json.dumps(regions, indent=2)+'\n')
    print('MAPS_READY', len(files), 'VPM PNG; NPM 1 atlas, 2048 RGB diffuse + opacity')


if __name__ == '__main__':
    main(sys.argv[1])
