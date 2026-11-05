"""elv-tc-vpm: contact sheet of the delivery-v002 acceptance renders (one PNG), labelled per view.

uv run --no-project --with pillow python contact_renders_v002.py <renders_dir> <out.png>
Rows: elevations S/N, E/W, roof top; day perspectives; side-by-sides with the booklet; night views. Never overwrites.
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

d, out = sys.argv[1], sys.argv[2]
if os.path.exists(out):
    raise SystemExit("output exists: " + out)
P = "elv_delivery_v002_"
ROWS = [
    [("day_south", "Юг (орто)"), ("day_north", "Север (орто)")],
    [("day_east", "Восток, главный фасад И-А (орто)"), ("day_west", "Запад (орто)")],
    [("day_top", "Кровля, вид сверху (орто)"), ("day_s14", "Главный фасад, камера листа 14")],
    [("day_p_se", "День: угол ЮВ (И-А), камера листа 15"), ("day_p_nw", "День: угол СЗ (противоположный)")],
    [("vs_booklet_sheet15", "Сравнение с буклетом, лист 15"), ("vs_booklet_sheet14", "Сравнение с буклетом, лист 14")],
    [("night_p_se", "Ночь: угол ЮВ"), ("night_p_nw", "Ночь: угол СЗ")],
    [("night_main", "Ночь: главный фасад И-А"), None],
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
        im = Image.open(os.path.join(d, P + c[0] + ".png")).convert("RGB")
        s = CW / im.width
        ims.append((im.resize((CW, round(im.height * s)), Image.LANCZOS), c[1]))
    cells.append(ims)
H = 70 + sum(max(i[0].height for i in r if i) + LAB + GAP for r in cells)
sheet = Image.new("RGB", (2 * CW + 3 * GAP, H), (255, 255, 255))
dr = ImageDraw.Draw(sheet)
dr.text((GAP, 16), "SM_Elevatornaya_1A — VPM delivery v002 (FBX из пакета + UDIM текстуры пакета), Eevee, UCX скрыты; "
        "земля, небо, солнце и ночные лампы только для рендера", fill=(0, 0, 0), font=ft)
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
