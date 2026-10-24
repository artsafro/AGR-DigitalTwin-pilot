"""Native indexed-PNG/color-management controls for texture diagnosis (#369).

Pattern: n/a | new-case: record native bitmap pixels without changing source scenes/maps.
"""
import json
import os
from pathlib import Path
from pymxs import runtime as rt


def main():
    job=json.loads(Path(os.environ['FLORA_DIAG_JOB']).read_text(encoding='utf-8'))
    work=Path(job['work']).resolve();output=work/'native-texture-controls.json'
    if output.exists():raise ValueError('fresh control output required')
    result={'version':str(rt.maxVersion()),'scene_modes':{},'decoder':[]}
    for scene in job['scenes']:
        path=Path(scene['copy']).resolve()
        if not path.is_relative_to(work):raise ValueError('scene must be a private copy')
        rt.resetMaxFile(rt.Name('noPrompt'))
        if not rt.loadMaxFile(str(path),quiet=True):raise RuntimeError('load failed')
        result['scene_modes'][scene['tag']]=str(rt.ColorPipelineMgr.Mode)
    rt.resetMaxFile(rt.Name('noPrompt'));rt.ColorPipelineMgr.Mode=rt.Name('Gamma')
    for source,decoded in job['diagnostic_decode'].items():
        row={'source_copy':source,'pixel_identical_rgba_copy':decoded,'pixels':{}}
        for label,path in [('indexed',source),('rgba',decoded)]:
            if not Path(path).resolve().is_relative_to(work):raise ValueError('bitmap must be a private copy')
            bitmap=rt.openBitmap(path)
            samples=[]
            for u,v in [(0,0),(.5,.5),(.85,.5)]:
                x,y=int(u*(bitmap.width-1)),int(v*(bitmap.height-1))
                color=rt.getPixels(bitmap,rt.point2(x,y),1)[0]
                samples.append({'xy':[x,y],'rgba':[float(color.r),float(color.g),float(color.b),float(color.a)]})
            row['pixels'][label]=samples
            rt.close(bitmap)
        result['decoder'].append(row)
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('TEXTURE_CONTROLS',len(result['decoder']),result['scene_modes'])


if __name__=='__main__':main()
