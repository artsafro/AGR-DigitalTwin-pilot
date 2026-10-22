"""new-case: AC06 presentation sandwich maps, shared source profile and recolouring.

The AC08 source uses 600 px; slide39/40 require 200 px at 1000 px/m.
Keep the eight-pixel source joint, remove only flat panel columns. This is
not a replacement of the original source texture. Both legend colours use
identical profile/noise coordinates. No horizontal joints are introduced.
"""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image


def sandwich(src, rgb, size, period, joint):
    """Return a vertical source-profile tile in the requested legend colour."""
    a, b = joint
    if not isinstance(period, int) or period <= b-a or size <= 0:
        raise ValueError('period must exceed joint width')
    if src.ndim != 3 or src.shape[2] != 3 or not 0 <= a < b <= src.shape[1]:
        raise ValueError('invalid RGB source or joint')
    centre = (a+b)//2
    offsets = (np.arange(size) + period//2) % period - period//2
    if centre + offsets.min() < 0 or centre + offsets.max() >= src.shape[1]:
        raise ValueError('source does not contain full profile')
    cols = src[np.arange(size) % src.shape[0]][:, centre+offsets].astype(float)
    return np.clip(cols * (np.asarray(rgb)/np.array([34, 113, 179])), 0, 255).round().astype(np.uint8)


def main(spec_path, root):
    scripts = Path(__file__).resolve().parents[1] / 'scripts'
    sys.path.insert(0, str(scripts))
    import finish_map
    import make_textures as mt
    s = json.loads(Path(spec_path).read_text())
    finish_map.validate_spec(s, finish_map.load_kpp())
    st = s['sandwich_source']
    raw = Path(st['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest() != st['sha256']:
        raise ValueError('source texture SHA256 mismatch')
    import io
    src = np.asarray(Image.open(io.BytesIO(raw)).convert('RGB'))
    if src.shape != (4096, 4096, 3):
        raise ValueError('source texture must be 4096 RGB')
    root = Path(root)
    finish_map.fresh_out_dir(str(root), [spec_path, st['path'], str(scripts)])
    vd, nd = root/'textures-vpm', root/'textures-npm'
    vd.mkdir(); nd.mkdir()
    atlas = np.zeros((2048,2048,3), np.uint8)
    layout = {}
    for k, (name, t) in enumerate(sorted(s['finishes'].items(), key=lambda x:x[1]['udim'])):
        u, size = t['udim'], s['size_full'] if t['kind']=='full' else 256
        if t['kind']=='full':
            if t['pattern'] != 'ac06_sandwich' or t['S'] != 4.096 or t['P'] != [0.2,0.2]:
                raise ValueError(f'unsupported sandwich contract {name}')
            d = sandwich(src, t['rgb'], size, 200, st['first_joint_px'])
            mask = np.abs((np.arange(size)+100)%200-100+0.5) < 4
            h = np.broadcast_to(np.where(mask, -3., 0.), (size,size))
            normal = mt.normal_from_height(h, 0.5)
            rough = np.broadcast_to(np.where(mask, 230, round(t['rough']*255)), (size,size))
            erm = np.stack([np.zeros_like(rough),rough,np.zeros_like(rough)],-1).astype(np.uint8)
        else:
            d = np.full((size,size,3), t['rgb'], np.uint8)
            erm = np.full((size,size,3), [0,round(t['rough']*255),round(t['metal']*255)],np.uint8)
            normal = np.full((size,size,3), [128,128,255],np.uint8)
        for role, arr in [('Diffuse',d),('ERM',erm),('Normal',normal)]:
            Image.fromarray(arr).save(vd/f'T_{s["address"]}_{role}_1.{u}.png',optimize=True)
        cell, pad, region = 409,6,397
        cx,cy=(k%5)*cell,(k//5)*cell
        reg=np.asarray(Image.fromarray(d).resize((region,region),Image.Resampling.LANCZOS))
        atlas[cy:cy+cell,cx:cx+cell]=np.pad(reg,((pad,pad),(pad,pad),(0,0)),mode='edge')
        layout[name]={'udim':u,'u0':(cx+pad)/2048,'v0':1-(cy+pad+region)/2048,'size':region/2048,'px_per_m':region/t['S'] if t['kind']=='full' else None}
    Image.fromarray(atlas).save(nd/f'T_{s["address"]}_001_Main_d_1.png',optimize=True)
    Image.fromarray(np.full((2048,2048,3),255,np.uint8)).save(nd/f'T_{s["address"]}_001_Main_o_1.png',optimize=True)
    (nd/'npm_atlas.json').write_text(json.dumps({'atlas':2048,'cell':409,'pad':6,'region':397,'finishes':layout},indent=2))
    print('AC06-MAPS-OK', root)


if __name__ == '__main__':
    main(*sys.argv[1:])
