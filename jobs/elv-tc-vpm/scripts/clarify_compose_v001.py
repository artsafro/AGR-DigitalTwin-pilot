"""elv-tc-vpm customer-clarify-v001: compose the decision pictures A (накладки), B (стемалит), C (фальшпомещения).

py -3 -I clarify_compose_v001.py <job_dir>
Inputs (all read-only): outputs/customer-clarify-v001/data/{renders/*, booklet_p18_300.png, booklet_p19_300.png,
nakl_verts.json, openings.json}, outputs/customer-tz-v001/img_00{1,2,3}.png, outputs/customer-blank-v001/
fbx_tris_ours_v002_uv.npz. Writes PNG sheets (<= 2400 px wide) into outputs/customer-clarify-v001/. Never overwrites.

Calibration (booklet pages at 300 dpi, sheet scale ~39.4 px/m, read off the drawings, +-0.3 m):
  S (sheet 18, 'Фасад в осях 1-10'):   px = 628.5 + 39.4 (x + 43.9),   py = 1986.8 - 39.4 z
  N (sheet 19, 'Фасад в осях 10-1'):   px = 856 + 39.4 (44.37 - x),   py = 914 - 39.4 z
  W (sheet 19, 'Фасад в осях А-И'):    px = 409 + 39.4 (27.7 - y),    py = 1929 - 39.4 z
  E (sheet 18, 'Фасад в осях И-А'):    px = 1522 + 39.4 (y + 26.5),   py = 931.5 - 39.4 z
Renders (clarify_render_v001.py, ortho 30 px/m): S px=(x+46)*30, N px=(46-x)*30, E px=(y+29)*30, W px=(29-y)*30,
py = 285 + (7.5 - z)*30.
"""
import sys, os, json, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None
JOB = sys.argv[1]
OUT = os.path.join(JOB, "outputs", "customer-clarify-v001")
DATA = os.path.join(OUT, "data")
REN = os.path.join(DATA, "renders")
TZ = os.path.join(JOB, "outputs", "customer-tz-v001")
WMAX = 2400
F = "C:/Windows/Fonts/arial.ttf"
FB = "C:/Windows/Fonts/arialbd.ttf"


def font(sz, bold=False):
    return ImageFont.truetype(FB if bold else F, sz)


RED = (220, 0, 0)
MAG = (230, 0, 200)
ORA = (255, 140, 0)
BLK = (0, 0, 0)
WHITE = (255, 255, 255)

# ------------------------------------------------------------------ geometry helpers
BOOK = {"S": ("booklet_p18_300.png", 628.5, 1, -43.9, 1986.8), "N": ("booklet_p19_300.png", 856, -1, 44.37, 914),
        "W": ("booklet_p19_300.png", 409, -1, 27.7, 1929), "E": ("booklet_p18_300.png", 1522, 1, -26.5, 931.5)}
BS = 39.4
REND = {"S": (46, 1), "N": (46, -1), "E": (29, 1), "W": (29, -1)}  # px = (off + sign*c)*30
RS = 30
_cache = {}


def img(path):
    if path not in _cache:
        _cache[path] = Image.open(path).convert("RGB")
    return _cache[path]


def book_px(f, c, z):
    _, a, sg, c0, zy = BOOK[f]
    return a + sg * BS * (c - c0), zy - BS * z


def rend_px(f, c, z):
    off, sg = REND[f]
    return (off + sg * c) * RS, 285 + (7.5 - z) * RS


def bright(im, g=0.55):
    lut = [round(255 * (i / 255) ** g) for i in range(256)]
    return im.point(lut * 3)


def crop_world(src, f, c0, c1, z0, z1, ppm, kind="rend"):
    pf = rend_px if kind == "rend" else book_px
    xa, ya = pf(f, c0, z1)
    xb, yb = pf(f, c1, z0)
    box = (round(min(xa, xb)), round(min(ya, yb)), round(max(xa, xb)), round(max(ya, yb)))
    im = src.crop(box)
    w = max(1, round(abs(c1 - c0) * ppm))
    h = max(1, round((z1 - z0) * ppm))
    return im.resize((w, h), Image.LANCZOS)


def rv(view, var):
    im = img(os.path.join(REN, f"{view}_{var}.png"))
    return bright(im) if var == "ours_tex" else im


def bk(f):
    return img(os.path.join(DATA, BOOK[f][0]))


class Sheet:
    def __init__(self, title, w=WMAX):
        self.w = w
        self.parts = []
        self.title(title)

    def add(self, im, pad=8):
        self.parts.append((im, pad))

    def title(self, t, sz=46):
        self.text(t, sz, bold=True, bg=(235, 235, 235), pad=14)

    def text(self, t, sz=30, bold=False, color=BLK, bg=WHITE, pad=6, width=None):
        fnt = font(sz, bold)
        width = width or self.w - 40
        lines = []
        for para in t.split("\n"):
            cur = ""
            for word in para.split(" "):
                tst = (cur + " " + word).strip()
                if fnt.getlength(tst) > width and cur:
                    lines.append(cur)
                    cur = word
                else:
                    cur = tst
            lines.append(cur)
        lh = int(sz * 1.28)
        im = Image.new("RGB", (self.w, lh * len(lines) + 2 * pad), bg)
        d = ImageDraw.Draw(im)
        for i, l in enumerate(lines):
            d.text((20, pad + i * lh), l, font=fnt, fill=color)
        self.parts.append((im, 0))

    def row(self, ims, labels=None, gap=12, lab_sz=28):
        """images side by side scaled to a common height filling the sheet width."""
        hs = [i.height for i in ims]
        H = max(hs)
        ims = [i.resize((round(i.width * H / i.height), H), Image.LANCZOS) for i in ims]
        tw = sum(i.width for i in ims) + gap * (len(ims) - 1)
        k = min(1.0, (self.w - 20) / tw) if tw > self.w - 20 else (self.w - 20) / tw
        ims = [i.resize((max(1, round(i.width * k)), max(1, round(i.height * k))), Image.LANCZOS) for i in ims]
        lab_h = int(lab_sz * 1.5) if labels else 0
        canvas = Image.new("RGB", (self.w, ims[0].height + lab_h), WHITE)
        d = ImageDraw.Draw(canvas)
        x = 10
        for i, im in enumerate(ims):
            if labels:
                d.text((x, 2), labels[i], font=font(lab_sz, True), fill=BLK)
            canvas.paste(im, (x, lab_h))
            d.rectangle((x, lab_h, x + im.width - 1, lab_h + im.height - 1), outline=(160, 160, 160))
            x += im.width + gap
        self.parts.append((canvas, 6))

    def save(self, name):
        H = sum(p.height + pad for p, pad in self.parts) + 20
        out = Image.new("RGB", (self.w, H), WHITE)
        y = 0
        for p, pad in self.parts:
            out.paste(p, ((self.w - p.width) // 2 if p.width < self.w else 0, y + pad))
            y += p.height + pad
        fp = os.path.join(OUT, name)
        if os.path.exists(fp):
            raise SystemExit("output exists: " + fp)
        out.save(fp, optimize=True)
        print("SAVED", name, out.size)


def label_img(im, text, sz=30, color=WHITE, bg=(0, 0, 0)):
    d = ImageDraw.Draw(im)
    fnt = font(sz, True)
    w = fnt.getlength(text)
    d.rectangle((0, 0, w + 16, sz + 12), fill=bg)
    d.text((8, 4), text, font=fnt, fill=color)
    return im


def tag(d, x, y, t, sz=24, fill=RED, fg=WHITE):
    fnt = font(sz, True)
    w = fnt.getlength(t)
    d.rectangle((x - w / 2 - 5, y - sz / 2 - 4, x + w / 2 + 5, y + sz / 2 + 4), fill=fill)
    d.text((x - w / 2, y - sz / 2 - 1), t, font=fnt, fill=fg)


# ------------------------------------------------------------------ data
NK = json.load(open(os.path.join(DATA, "nakl_verts.json"), encoding="utf-8"))
OP = json.load(open(os.path.join(DATA, "openings.json"), encoding="utf-8"))
GROUPS = [
    ("joint_h", lambda f, n: "FS-8P" in f, (230, 0, 0), "Нащельник на гориз. шве сэндвича (FS-8P), RAL 7021"),
    ("base", lambda f, n: f.startswith("(SC)-Batten (SC)-Batten_RAL7021"), (255, 140, 0), "Цокольный отлив (Batten RAL7021)"),
    ("cap", lambda f, n: "Batten_top" in f or "parapet_170" in f, (0, 90, 255), "Парапетные крышки (Batten_top, parapet_170)"),
    ("gate", lambda f, n: "Batten_Gate" in f, (0, 170, 0), "Обрамление ворот (Batten_Gate)"),
    ("edge_4_7", lambda f, n: "FS11" in f, (140, 70, 20), "Кромка консоли/витража (FS11, RAL 5025/1002)"),
    ("vertical", lambda f, n: n.startswith("RZ_Nakl_V"), (0, 200, 220), "Вертикальные угловые нащельники (FS2.2/FS4)"),
    ("roof", lambda f, n: True, (150, 0, 200), "Отливы надстроек на кровле (Batten_windows.2, FS4.1)"),
]
gstat = {k: {"n": 0, "L": 0.0, "z": set(), "h": set(), "dep": set()} for k, *_ in GROUPS}
for r in NK:
    g = next(k for k, t, *_ in GROUPS if t(r["fam"], r["name"]))
    v = np.array(r["verts"])
    hor = np.ptp(v[:, :2], axis=0)
    L = float(np.hypot(*hor))
    hz = float(np.ptp(v[:, 2]))
    s = gstat[g]
    s["n"] += 1
    if g == "vertical":
        s["L"] += hz
    else:
        s["L"] += L
    s["z"].add((round(v[:, 2].min(), 2), round(v[:, 2].max(), 2)))
    s["h"].add(round(hz, 3))
    s["dep"].add(round(r["depth"], 3))
D = np.load(os.path.join(JOB, "outputs", "customer-blank-v001", "fbx_tris_ours_v002_uv.npz"))


def tri_area_n(t):
    n = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    a = np.linalg.norm(n, axis=1) / 2
    return a, n / (2 * a[:, None] + 1e-12)


ma, mn = tri_area_n(D["Main_tri"])
ga, gn = tri_area_n(D["Glass_tri"])
mcx = D["Main_tri"].mean(axis=1)
gcx = D["Glass_tri"].mean(axis=1)
east_m = (mcx[:, 0] > 38) & (mn[:, 0] > 0.3)
east_g = (gcx[:, 0] > 38) & (np.abs(gn[:, 0]) > 0.3)
E_STEM = float(ma[east_m & (D["Main_udim"] == 1008)].sum())
E_GLASS = float(ga[east_g].sum()) / 1.0
E_GLASS_LOW = float(ga[east_g & (gcx[:, 2] < 4.7)].sum())
E_STEM_LOW = float(ma[east_m & (D["Main_udim"] == 1008) & (mcx[:, 2] < 4.75)].sum())
E_DOOR = float(ma[east_m & (D["Main_udim"] == 1009)].sum())

# ================================================================== A1
s = Sheet("A1. «Накладки» — что пишет и рисует заказчик (ТЗ 2026-11-05)")
s.text("Заметка N1, п.4 на доске заказчика: «4) швы горизонтальные накладки сделать.»", 34, bold=True, color=RED)
s.row([img(os.path.join(TZ, "img_002.png")).crop((0, 0, 2080, 1000))],
      ["img_002 (рендер буклета, сервисная сторона): красные линии вокруг фасада на ≈ +4.6 и ≈ +10.4"])
s.row([img(os.path.join(TZ, "img_003.png")).crop((1450, 120, 2190, 800)),
       img(os.path.join(TZ, "img_001.png")).crop((60, 380, 1080, 800))],
      ["img_003: те же 2 линии на тёмном фасаде", "img_001: линии на сэндвиче не отмечены (там окна/входы)"])
b = bk("W")
crop = crop_world(b, "W", 27.7, -26.6, -0.5, 16.3, 44, "book")
d = ImageDraw.Draw(crop)
for zz, t in ((4.62, "шов +4.6"), (10.37, "шов +10.4")):
    y = (16.3 - zz) * 44
    d.line((0, y, 60, y), fill=RED, width=5)
    tag(d, 160, y, t, 26)
s.row([crop], ["Буклет, лист 19, «Фасад в осях А-И» (запад): горизонтальные двойные линии на сэндвиче = швы с нащельником"])
leg = b.crop((3240, 2870, 4800, 3040))
s.row([leg], ["Буклет, легенда листов 18/19: поз. 14 «нащельник, цвет RAL 7021»"])
s.text("Вывод A1: в ТЗ «накладки» = горизонтальные полосы по швам сэндвич-панелей на ≈ +4.6 и ≈ +10.4 "
       "(обходят весь сэндвич-фасад, не кассеты). В буклете это позиция 14 «нащельник RAL 7021».", 32, bold=True)
s.save("A1_nakladki_TZ.png")

# ================================================================== A2
s = Sheet("A2. Сцена заказчика: коллекция RZshow_SRC_Накладки (131 объект) — что это и где")
s.text("Все 131 объекта — контуры (4 вершины, 0 граней) экземпляров Revit-семейств «(SC)-Batten…» из того же FBX, "
       "что у нас. В выгрузку заказчика (SM_Elevatornaya_Vl_1_A_001) они НЕ входят. Цвет полос = группа (легенда внизу). "
       "Серое — модель заказчика; сиреневые пятна — его фальшпомещения.", 28)
ppm = 25.6
for f, lab, c0, c1 in (("S", "Юг (оси 1-10), вид с юга", -44.6, 44.6), ("W", "Запад (оси А-И), вид с запада", 28.0, -27.0),
                       ("N", "Север (оси 10-1), вид с севера", 44.6, -44.6), ("E", "Восток И-А (главный), вид с востока", -27.0, 28.0)):
    im = crop_world(rv(f, "theirs_nakl"), f, c0, c1, -1.2, 16.6, ppm)
    d = ImageDraw.Draw(im)
    for zz, t in ((4.62, "+4.535…+4.700"), (10.37, "+10.285…+10.450")):
        if f in ("S", "W", "N"):
            y = (16.6 - zz) * ppm
            tag(d, im.width - 150, y - 22, t, 22)
    s.row([im], [lab])
# legend table
rows = []
for k, t, col, name in GROUPS:
    st = gstat[k]
    zs = sorted(st["z"])
    if k == "joint_h":
        zt = "+4.535…4.700, +10.285…10.450; ТП: +5.92…6.08, +11.92…12.08"
        sec = "165 × 22 мм (выс × вылет)"
    elif k == "base":
        zt = "+0.13…+0.52"
        sec = "267 мм; глуб. 0.22–0.26"
    elif k == "cap":
        zt = "+12.73…+16.25 (верх парапетов)"
        sec = "120 мм; шир. 0.30–0.60"
    elif k == "gate":
        zt = "+0.20…+4.11"
        sec = "стойка 0.24×0.10"
    elif k == "edge_4_7":
        zt = "+4.64…+4.78"
        sec = "110–120 мм; глуб. 0.15"
    elif k == "vertical":
        zt = "+0.2…+13.85 (углы), +11.0…+15.4 (надстр.)"
        sec = "0.20–0.26 × 0.20–0.26"
    else:
        zt = "+12.5…+14.5"
        sec = "выс 120–170 мм"
    rows.append((col, name, st["n"], st["L"], sec, zt))
fnt = font(25)
fb = font(25, True)
th = 44
tab = Image.new("RGB", (WMAX, th * (len(rows) + 1) + 10), WHITE)
d = ImageDraw.Draw(tab)
cols = [20, 80, 880, 950, 1080, 1420]
for x, t in zip(cols[1:], ("Группа (семейство Revit)", "шт", "длина, м", "сечение", "отметки")):
    d.text((x, 6), t, font=fb, fill=BLK)
for i, (col, name, n, L, sec, zt) in enumerate(rows, 1):
    y = i * th + 4
    d.rectangle((cols[0], y + 6, cols[0] + 44, y + 32), fill=col, outline=BLK)
    d.text((cols[1], y + 6), name, font=fb if i == 1 else fnt, fill=BLK)
    d.text((cols[2], y + 6), str(n), font=fnt, fill=BLK)
    d.text((cols[3], y + 6), f"{L:.0f}", font=fnt, fill=BLK)
    d.text((cols[4], y + 6), sec, font=fnt, fill=BLK)
    d.text((cols[5], y + 6), zt[:80], font=fnt, fill=BLK)
s.add(tab)
s.text("Красная группа — единственная, что совпадает с линиями ТЗ (+4.6 / +10.4): 24 полосы, ≈413 м всего "
       "(часть идёт за деревянными кассетами юга и на севере утоплена в стену заказчика — на рендере не видна). "
       "Остальные группы — отливы и крышки, которые у нас уже есть геометрией (цоколь, парапеты) или в текстуре.", 28, bold=True)
s.save("A2_nakladki_customer_scene.png")

# ================================================================== A3
s = Sheet("A3. Те же места: заказчик (накладки) · наша модель v002 · буклет")
s.row([rv("pS", "theirs_nakl"), rv("pS", "ours_tex")],
      ["Заказчик: красные полосы = нащельники FS-8P (165×22 мм)", "Наша v002: шов только в текстуре (тонкая линия)"])
ppm = 44
for f, c0, c1, lab in (("W", 27.7, -26.6, "Запад (А-И)"), ):
    a = crop_world(bk(f), f, c0, c1, 3.0, 12.2, ppm, "book")
    t_ = crop_world(rv(f, "theirs_nakl"), f, c0, c1, 3.0, 12.2, ppm)
    o_ = crop_world(rv(f, "ours_tex"), f, c0, c1, 3.0, 12.2, ppm)
    for im in (a, t_, o_):
        d = ImageDraw.Draw(im)
        for zz in (4.62, 10.37):
            y = (12.2 - zz) * ppm
            d.line((0, y, 25, y), fill=RED, width=6)
    s.row([a], [f"Буклет лист 19, {lab}, z +3.0…+12.2: двойные линии швов"])
    s.row([t_], [f"Заказчик, {lab}: нащельники (красные) — только в скрытой коллекции, не в его модели"])
    s.row([o_], [f"Наша v002, {lab} (осветлено): швы в текстуре (тонкие линии, в этом масштабе едва видны); полос-геометрии нет"])
# zoom of the joint: theirs vs ours at the same spot
zt = rv("pS", "theirs_nakl").crop((120, 230, 1000, 620))
zo = rv("pS", "ours_tex").crop((120, 230, 1000, 620))
# section sketch
sk = Image.new("RGB", (760, 480), WHITE)
d = ImageDraw.Draw(sk)
k = 1.6  # px per mm
x0 = 300
d.rectangle((x0 - 150 * k / 2, 20, x0, 230), fill=(120, 122, 128), outline=BLK)
d.rectangle((x0 - 150 * k / 2, 250, x0, 460), fill=(120, 122, 128), outline=BLK)
d.rectangle((x0, 240 - 165 * k / 2, x0 + 22 * k, 240 + 165 * k / 2), fill=RED, outline=BLK)
d.text((x0 + 50, 150), "нащельник FS-8P\n165 × 22 мм, RAL 7021", font=font(26, True), fill=RED)
d.text((x0 + 50, 300), "шов панелей ≈ 20 мм\n(у нас — линия в текстуре)", font=font(24), fill=BLK)
d.text((20, 20), "сэндвич 150", font=font(22), fill=WHITE)
d.text((20, 440), "схема, не масштаб 1:1", font=font(20), fill=(90, 90, 90))
s.row([zt, zo, sk], ["Заказчик, крупно: шов +10.4", "Наша v002: шов +10.4 (линия текстуры)", "Сечение (по FBX)"])
s.text("Гипотезы, по одной строке:", 32, bold=True)
s.text("1) Горизонтальные нащельники на швах сэндвич-панелей — ДА (факт): FS-8P 165×22 мм, RAL 7021, +4.535…4.700 и "
       "+10.285…10.450 (+ТП 5.9/11.9), ≈413 м; совпадает с линиями ТЗ и с поз. 14 буклета. У нас — только текстура.", 28)
s.text("2) Отливы/фартуки (flashing) — частично: в той же коллекции есть цоколь, парапетные крышки, обрамление ворот, "
       "углы; но их ТЗ не отмечает (линии ТЗ только на +4.6/+10.4), а цоколь и крышки у нас уже геометрия.", 28)
s.text("3) Накладки на швы кассет — НЕТ: на дереве и металлических кассетах заказчик накладок не рисует; "
       "FS-8P на юге проходит за деревянными кассетами (скрыт).", 28)
s.save("A3_nakladki_ours_vs_customer_vs_booklet.png")

# ================================================================== B1
s = Sheet("B1. Стемалит на главном фасаде И-А (восток): ТЗ · буклет · наша v002 · заказчик")
s.text("Заметка N1, п.5: «5) окна и входные группы на переднем фасаде со стемалитом прорезать.»", 34, bold=True, color=RED)
s.row([img(os.path.join(TZ, "img_001.png")).crop((1000, 150, 2270, 860))],
      ["img_001 (рендер, правая часть = фасад И-А): красным — ламели и входы 1-го этажа под ними"])
ppm = 40
c0, c1 = -27.0, 28.0
a = crop_world(bk("E"), "E", c0, c1, -0.6, 16.6, ppm, "book")
s.row([a], ["Буклет, лист 18, «Фасад в осях И-А»: стемалит (поз. 6, синяя штриховка) — полосы; стекло (поз. 7) — окна и входы"])
oi = crop_world(rv("E", "ours_id"), "E", c0, c1, -0.6, 16.6, ppm)
s.row([oi], ["Наша v002 по ID: синий = стемалит ID13 (в Main), голубой = стекло (меш MainGlass), "
             "малиновый = револьверная дверь, чёрные рамки = F50"])
ot = crop_world(rv("E", "ours_tex"), "E", c0, c1, -0.6, 16.6, ppm)
s.row([ot], ["Наша v002 с текстурами (осветлено)"])
ti = crop_world(rv("E", "theirs_id"), "E", c0, c1, -0.6, 16.6, ppm)
s.row([ti], ["Модель заказчика: на И-А нет ни стекла, ни стемалита, ни входов — сплошные дерево/кассета (стекло у него 0 м² на востоке)"])
s.text(f"Факты по нашей v002 на И-А: стекло (MainGlass, отдельный меш, прозрачное) {E_GLASS:.0f} м², из них 1-й этаж "
       f"{E_GLASS_LOW:.0f} м²; стемалит (ID13, непрозрачный, в Main) {E_STEM:.0f} м², из них на 1-м этаже {E_STEM_LOW:.0f} м² "
       f"(полоса над витражом); двери входов {E_DOOR:.1f} м² (ID14). Окна и входы стоят в сетке F50 как в буклете: "
       "стемалит только в полосах, проёмы — стекло, не «стекло за стемалитом».", 28, bold=True)
s.save("B1_stemalit_front_facade.png")

s = Sheet("B2. Стемалит И-А крупно: вход и витражи 1-го этажа")
s.row([rv("pE2", "ours_tex"), rv("pE2", "ours_id")], ["Наша v002 (текстура)", "Наша v002 по ID (синий = стемалит, голубой = стекло)"])
s.row([rv("pE", "ours_tex"), rv("pE", "theirs_id")], ["Наша v002, угол юг-восток", "Заказчик, тот же ракурс"])
s.text("Вывод B: у нас окна и входные группы И-А уже «прорезаны»: стекло — отдельный прозрачный меш MainGlass в своих "
       "ячейках, двери и револьверная дверь — геометрия; стемалит — только глухие полосы, как в буклете (D06). "
       "Пункт 5 ТЗ относится к модели заказчика, где на И-А нет проёмов вообще. Догадка: если заказчик под «прорезать» "
       "понимает реальную глубину (стекло утоплено в проём), то у нас стекло стоит в плоскости витража F50 за накладками F50 — проверить с ним.", 28, bold=True)
s.save("B2_stemalit_closeup.png")

# ================================================================== C1 (map + table)
s = Sheet("C1. Фальшпомещения и ниши заказчика — где они (план + таблица)")
top = rv("T", "ours_id")
ppm_t = 30
pl = top.crop((0, 0, top.width, top.height)).convert("RGB")
pl = Image.blend(pl, Image.new("RGB", pl.size, WHITE), 0.55)
d = ImageDraw.Draw(pl)
for r in OP:
    px = (r["x"] + 46) * ppm_t
    py = (29 - r["y"]) * ppm_t
    col = MAG if r["theirs_fake_room"] else ORA
    d.ellipse((px - 16, py - 16, px + 16, py + 16), fill=col, outline=BLK)
    off = {"S": (0, 34), "N": (0, -34), "W": (-40, 0)}[r["facade"]]
    tag(d, px + off[0], py + off[1], str(r["no"]), 22, fill=col)
for t, xy in (("ЮГ (1-10)", (1300, 1700)), ("СЕВЕР (10-1)", (1150, 170)), ("ЗАПАД (А-И)", (20, 900)), ("ВОСТОК И-А", (2470, 960))):
    d.text(xy, t, font=font(36, True), fill=BLK)
s.row([pl], ["План (сверху, наша v002 бледно). Малиновый — проём с фальшпомещением у заказчика (26), оранжевый — проём без него (8)"])
# table
hdr = ("№", "фасад", "тип", "x / y, м", "z, м", "проём Ш×В, м", "фальшпом. Ш×Г×В, м", "ниша у закз.", "у нас (фальшпом. нет нигде)", "ниша у нас")
cw = [60, 110, 100, 200, 170, 200, 320, 190, 420, 200]
th = 36
tab = Image.new("RGB", (WMAX, th * (len(OP) + 1) + 10), WHITE)
d = ImageDraw.Draw(tab)
x = 20
for h_, w_ in zip(hdr, cw):
    d.text((x, 4), h_, font=font(24, True), fill=BLK)
    x += w_
NAMES = {"S": "Юг", "N": "Север", "W": "Запад"}
for i, r in enumerate(OP, 1):
    y = i * th + 2
    if i % 2:
        d.rectangle((10, y, WMAX - 10, y + th - 2), fill=(245, 245, 245))
    fr = r["theirs_fake_room"]
    if fr:
        fw, fd = (fr[0], fr[1]) if r["facade"] != "W" else (fr[1], fr[0])
        frs = f"{fw:.2f} × {fd:.2f} × {fr[2]:.2f}"
    else:
        frs = "нет"
    ours = " + ".join({"door": "дверь", "window_frame": "окно", "glass": "стекло"}[e] for e in r["ours_elements"]) or "не найдено авт."
    vals = (str(r["no"]), NAMES[r["facade"]], "дверь" if r["kind"] == "door" else "окно",
            f"{r['x']:.1f} / {r['y']:.1f}", f"{r['z0']:.2f}…{r['z1']:.2f}", f"{r['w']:.2f} × {r['h']:.2f}", frs,
            f"{r['theirs_recess']:.2f}" if r["theirs_recess"] is not None else "—", ours,
            (f"{r['ours_recess']:.2f}" + (" (?)" if r["ours_recess"] > 0.6 else "")) if r["ours_recess"] is not None else "—")
    x = 20
    for v, w_, j in zip(vals, cw, range(10)):
        d.text((x, y + 4), v, font=font(23, j == 6 and fr is not None), fill=MAG if (j == 6 and fr) else BLK)
        x += w_
s.add(tab)
s.text("Ниша = глубина полотна двери/окна от плоскости стены. У заказчика 0.14 м везде (север 0.20–0.28), у нас: двери 0.20, "
       "окна 0.125 — ниши у нас ЕСТЬ. Нет у нас только фальшпомещений: коробка 0.80 м (север-запад 0.92) за стеклом/дверью, "
       "у заказчика плитка 1003. Отметка «(?)» и «не найдено авт.» — автоматический замер не сработал, смотреть картинку C2/C3.", 27, bold=True)
s.save("C1_fake_rooms_map_table.png")

# ================================================================== C2/C3 elevations + close-ups
ppm = 25.6


def elev_pair(s, f, c0, c1, lab):
    t_ = crop_world(rv(f, "theirs_id"), f, c0, c1, -0.6, 13.0, ppm)
    o_ = crop_world(rv(f, "ours_tex"), f, c0, c1, -0.6, 13.0, ppm)
    b_ = crop_world(bk(f), f, c0, c1, -0.6, 13.0, ppm, "book")
    for im in (t_, o_, b_):
        d = ImageDraw.Draw(im)
        for r in OP:
            if r["facade"] != f:
                continue
            c = r["x"] if f in "SN" else r["y"]
            u = (c - c0) / (c1 - c0) * im.width
            v = (13.0 - r["z1"] - 0.55) * ppm
            tag(d, u, v, str(r["no"]), 20, fill=MAG if r["theirs_fake_room"] else ORA)
    s.row([t_], [f"{lab}: заказчик (малиновый = фальшпомещение, оранжевый = откосы, красный = рамы/полотна)"])
    s.row([o_], [f"{lab}: наша v002 (осветлено)"])
    s.row([b_], [f"{lab}: буклет"])


def closeups(s, nos):
    cells = []
    for r in OP:
        if r["no"] not in nos or not r["theirs_fake_room"]:
            continue
        f = r["facade"]
        c = r["x"] if f in "SN" else r["y"]
        sgn = 1 if f in "SE" else -1
        half = max(1.9, r["w"] / 2 + 0.5)
        a0, a1 = c - sgn * half, c + sgn * half
        zc_ = (r["z0"] + r["z1"]) / 2
        z0, z1 = zc_ - 1.55, zc_ + 1.55
        k = 110
        ims = [crop_world(rv(f, "theirs_id"), f, a0, a1, z0, z1, k), crop_world(rv(f, "ours_tex"), f, a0, a1, z0, z1, k),
               crop_world(bk(f), f, a0, a1, z0, z1, k, "book")]
        H = 300
        ims = [i.resize((round(i.width * H / i.height), H), Image.LANCZOS) for i in ims]
        fr = r["theirs_fake_room"]
        dep = fr[1] if f != "W" else fr[0]
        txt = (f"№{r['no']} {NAMES[f]}, {'дверь' if r['kind'] == 'door' else 'окно'} {r['w']:.2f}×{r['h']:.2f} м, "
               f"z {r['z0']:.2f}; фальшпом. глуб. {dep:.2f} м")
        W_ = sum(i.width for i in ims) + 20
        cell = Image.new("RGB", (W_, H + 44), WHITE)
        dd = ImageDraw.Draw(cell)
        dd.text((4, 6), txt, font=font(22, True), fill=BLK)
        x = 0
        for i, nm in zip(ims, ("закз.", "наша", "буклет")):
            cell.paste(i, (x, 40))
            dd.text((x + 4, 44), nm, font=font(20, True), fill=(255, 255, 0) if nm != "буклет" else RED)
            x += i.width + 10
        cells.append(cell)
    for i in range(0, len(cells), 2):
        s.row(cells[i:i + 2], gap=30)


s = Sheet("C2. Юг (оси 1-10): фальшпомещения заказчика vs наша v002 vs буклет")
s.row([rv("pS", "theirs_id"), rv("pS", "ours_tex")], ["Заказчик 3/4: малиновые коробки 0.8 м за стеклом и дверями", "Наша v002 3/4: проёмы с откосами, без коробок"])
elev_pair(s, "S", -44.6, 44.6, "Юг")
s.save("C2_fake_rooms_south.png")

s = Sheet("C3. Север (10-1) и запад (А-И): фальшпомещения заказчика vs наша v002 vs буклет")
s.row([rv("pN", "theirs_id"), rv("pN", "ours_tex")], ["Заказчик 3/4 (север, оси 3-5)", "Наша v002, то же"])
s.row([rv("pW", "theirs_id"), rv("pW", "ours_tex")], ["Заказчик 3/4 (запад, ТП)", "Наша v002, то же"])
elev_pair(s, "N", 44.6, -44.6, "Север")
elev_pair(s, "W", 28.0, -27.0, "Запад")
s.save("C3_fake_rooms_north_west.png")

s = Sheet("C4. Каждое фальшпомещение крупно: заказчик · наша v002 · буклет (юг)")
closeups(s, set(range(1, 16)))
s.save("C4_fake_rooms_closeups_south.png")
s = Sheet("C5. Каждое фальшпомещение крупно: заказчик · наша v002 · буклет (север, запад)")
closeups(s, set(range(16, 35)))
s.save("C5_fake_rooms_closeups_north_west.png")
print("DONE")
