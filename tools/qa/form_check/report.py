"""Form check v1 - result table and Russian summary sheet (PNG)."""
from __future__ import annotations

COLS = [("pair", "Пара"), ("variant", "Вариант"), ("artem", "Артём"), ("detector", "Детектор"),
        ("agree_detector", "совп."), ("judge", "Судьи"), ("agree_judge", "совп."), ("not_measured", "Не измерено")]
GOOD = {"ok", "Same", "accepted"}
BAD = {"defect", "Different", "rejected"}


def agree(tool, artem):
    """Tool verdict vs Artem's recorded verdict: 'yes' / 'no' / 'n/a' (tool undecided or no Artem verdict)."""
    a = "good" if artem in ("accepted",) else "bad" if artem in ("rejected",) else None
    t = "good" if tool in ("ok",) else "bad" if tool in ("defect",) else None
    if a is None or t is None:
        return "n/a"
    return "yes" if a == t else "no"


def markdown_table(rows):
    head = "| " + " | ".join(c for c, _ in COLS) + " |"
    sep = "|" + "---|" * len(COLS)
    body = ["| " + " | ".join(str(r.get(c, "")).replace("|", "/") for c, _ in COLS) + " |" for r in rows]
    return "\n".join([head, sep, *body]) + "\n"


def sheet_png(rows, notes_ru, out_png, title="Проверка формы v1 — замер на парах Артёма (наблюдение)"):
    from PIL import Image, ImageDraw, ImageFont

    def font(sz, bold=False):
        for f in (("arialbd.ttf" if bold else "arial.ttf"), "DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(f, sz)
            except OSError:
                continue
        return ImageFont.load_default()

    f_t, f_h, f_b = font(34, True), font(22, True), font(21)
    widths = [190, 190, 130, 200, 80, 220, 80, 900]
    W = sum(widths) + 60
    rh = 34
    H = 140 + rh * (len(rows) + 1) + 40 + 30 * len(notes_ru) + 40
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    d.text((30, 25), title, fill="black", font=f_t)
    y = 100
    x = 30
    for (c, lab), w in zip(COLS, widths):
        d.rectangle([x, y, x + w, y + rh], fill=(225, 225, 225), outline="black")
        d.text((x + 6, y + 5), lab, fill="black", font=f_h)
        x += w
    for r in rows:
        y += rh
        x = 30
        for (c, _), w in zip(COLS, widths):
            v = str(r.get(c, ""))
            col = {"yes": (210, 240, 210), "no": (250, 210, 210)}.get(v, "white")
            d.rectangle([x, y, x + w, y + rh], fill=col, outline="black")
            maxc = max(4, int(w / 11))
            d.text((x + 6, y + 6), v if len(v) <= maxc else v[: maxc - 1] + "…", fill="black", font=f_b)
            x += w
    y += rh + 30
    for line in notes_ru:
        d.text((30, y), line, fill="black", font=f_b)
        y += 30
    im.save(out_png)
    return out_png
