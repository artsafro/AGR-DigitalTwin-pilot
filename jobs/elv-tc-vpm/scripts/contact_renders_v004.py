"""v004 copy of contact_renders_v003.py: prefix elv_delivery_v004_day_, title v004, last row adds the old/new wood
swatch (elv_delivery_v004_wood_swatch.png, pick_wood_colour_v005.py).
elv-tc-vpm: contact sheet of the delivery-v003 renders (renders-v003), labelled per view (= contact_renders_v002.py
layout, new rows for the v003 close-ups).

uv run --no-project --with pillow python contact_renders_v003.py <renders_dir> <out.png>
Never overwrites.
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

d, out = sys.argv[1], sys.argv[2]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
P = "elv_delivery_v004_day_"
ROWS = [
    [("south", "Юг (орто)"), ("north", "Север (орто)")],
    [("east", "Восток, главный фасад И-А (орто)"), ("west", "Запад (орто)")],
    [("p_se", "Угол ЮВ (И-А), камера листа 15"), ("p_nw", "Угол СЗ")],
    [("c_strip", "Нащельник 165×22 RAL 7021 (юг, +4.535…4.700)"), ("c_south", "Южный вход: двери №4 (смотровое окно), №5, №9")],
    [("c_cap1b", "Капсула за окном юг, ELV-01 +6.90 (скользящий взгляд)"), ("c_cap2b", "Капсула за окном север, ELV-01 +6.90 (скользящий взгляд)")],
    [("c_cap3", "Капсула за верхним витражом И-А"), ("c_cap4", "Капсула за нижним витражом И-А и дверями")],
    [("c_door30b", "Запад: дверь №30 (ELV-08), вид с ЮЗ"), ("@elv_delivery_v004_wood_swatch", "Дерево: v003 #C4ABAA (розовое) → v004 #C1AE93 (тёплый беж)")],
]
CW, GAP, LAB = 1200, 16, 34
try:
    f = ImageFont.truetype("arial.ttf", 24)
    ft = ImageFont.truetype("arial.ttf", 34)
except OSError:
    f = ft = ImageFont.load_default()
cells = []
for row in ROWS:
    ims = []
    for c in row:
        if c is None:
            ims.append(None)
            continue
        im = Image.open(os.path.join(d, (c[0][1:] if c[0][0] == "@" else P + c[0]) + ".png")).convert("RGB")
        s = CW / im.width
        ims.append((im.resize((CW, round(im.height * s)), Image.LANCZOS), c[1]))
    cells.append(ims)
H = 70 + sum(max(i[0].height for i in r if i) + LAB + GAP for r in cells)
sheet = Image.new("RGB", (2 * CW + 3 * GAP, H), (255, 255, 255))
dr = ImageDraw.Draw(sheet)
dr.text((GAP, 16), "SM_Elevatornaya_Vl_1_A_001 — VPM delivery v004 (FBX из пакета + UDIM текстуры пакета), Eevee, UCX "
        "скрыты; земля, небо и солнце только для рендера", fill=(0, 0, 0), font=ft)
y = 70
for r in cells:
    h = max(i[0].height for i in r if i)
    for k, c in enumerate(r):
        if c is None:
            continue
        x = GAP + k * (CW + GAP)
        dr.text((x, y + 4), c[1], fill=(0, 0, 0), font=f)
        sheet.paste(c[0], (x, y + LAB))
    y += h + LAB + GAP
sheet.save(out)
print("SAVED", out, sheet.size)
