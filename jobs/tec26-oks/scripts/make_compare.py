"""Compose the slide-57 / exported VPM / exported NPM colour-only handoff.

new-case: honest monochrome reference plate beside source-colour tower exports.
No RAL is inferred from the monochrome slide; source geometry remains unchanged.
"""
from pathlib import Path
import sys
from PIL import Image, ImageDraw, ImageFont, ImageOps


def main(root, slide):
    root=Path(root).resolve(); slide=Path(slide).resolve()
    out=root/'compare';out.mkdir(exist_ok=False)
    font_path='C:/Windows/Fonts/arial.ttf'
    title=ImageFont.truetype(font_path,30); font=ImageFont.truetype(font_path,22)
    reference=Image.open(slide).convert('RGB')
    reference.save(out/'slide57.png')
    for view in ['front','angle']:
        plate=Image.new('RGB',(3000,1200),'white');draw=ImageDraw.Draw(plate)
        for x,label in [(0,'SLIDE 57 / monochrome geometry'),(1000,'VPM / UDIM 1001-1006'),(2000,'NPM / one 2048 atlas')]:
            draw.text((x+24,20),label,font=title,fill='black')
        # Front drawing spans 64 m; renders use an 88 m orthographic frame.
        # Keep the source-vs-slide height difference visible, never stretch it away.
        if view=='front':
            crop=reference.crop((79,72,352,398))
            scale=(1000/88)/(320/64)
            crop=crop.resize((round(crop.width*scale),round(crop.height*scale)),Image.Resampling.LANCZOS)
            baseline=500+33.9694*1000/88
            plate.paste(crop,((1000-crop.width)//2,round(80+baseline-(396-72)*scale)))
        else:
            ref=ImageOps.contain(reference,(960,1000))
            plate.paste(ref,((1000-ref.width)//2,80+(1000-ref.height)//2))
        for col,profile in [(1,'vpm'),(2,'npm')]:
            image=Image.open(root/'renders'/f'{profile}_{view}.png').convert('RGB')
            plate.paste(image,(col*1000,80))
        draw.text((24,1100),'Colours: original maps_truba RGB, red-blue-red and greys (Artem, 2026-10-22). Slide 57 has no colour/RAL callout.',font=font,fill='black')
        draw.text((24,1135),'Geometry / UCX unchanged. Slide top +64 m; original mesh top +69.384 m, base -1.446 m. Red line = +/-0.000.',font=font,fill='black')
        draw.text((24,1170),'VPM and NPM use identical cameras / scale. Front reference scaled using its +64 / 0.000 marks; source geometry is NOT fitted to the slide.',font=font,fill='black')
        plate.save(out/f'slide57_VPM_NPM_{view}.png',optimize=True)
    print('COMPARE_READY',out)


if __name__=='__main__':main(*sys.argv[1:])
