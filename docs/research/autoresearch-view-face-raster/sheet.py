"""Raster elevation sheet -> per-view window column profiles (#141, OBSERVE).

Reads only the raster images of a PDF page (Revit-style export: facade raster + vector annotation);
titles, axis bubbles, callouts and every vector path are dropped. Scale comes from the signed level
marks (e.g. "+29,300") on the same page: Theil-Sen slope of value vs text baseline, median over the page.
Frozen: 0.1 m/px, dark (window) luma < 0.45, body rows = rows whose non-white fraction over the view
width >= 0.9 and dark fraction <= 0.6, view split on >= 3 m empty columns, views narrower than 5 m dropped.
"""
import re

import numpy as np
import pymupdf as fitz

RES = 0.1
DARK = 0.45
WHITE = 0.95


def page_scale(page):
    ws = [w for w in page.get_text("words") if re.fullmatch(r"[+-]\d{1,2},\d{3}", w[4])]
    v = np.array([float(w[4].replace(",", ".")) for w in ws])
    y = np.array([w[3] for w in ws])
    sl = [(v[i] - v[j]) / (y[i] - y[j]) for i in range(len(v)) for j in range(i) if abs(y[i] - y[j]) > 20]
    if len(sl) < 3:
        raise ValueError("fewer than 3 level-mark pairs; no scale")
    return float(-np.median(sl)), len(ws)


def raster_only(doc, page, clip, m_per_pt):
    nd = fitz.open()
    npg = nd.new_page(width=page.rect.width, height=page.rect.height)
    for info in page.get_image_info(xrefs=True):
        npg.insert_image(fitz.Rect(info["bbox"]), pixmap=fitz.Pixmap(doc, info["xref"]))
    zoom = m_per_pt / RES
    pm = npg.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=fitz.Rect(*clip), colorspace=fitz.csGRAY)
    return np.frombuffer(pm.samples, np.uint8).reshape(pm.height, pm.width).astype(np.float32) / 255.0


def split_views(luma, gap_px=30, min_w_px=50):
    ink = luma < WHITE
    col = ink.any(axis=0)
    xs = np.flatnonzero(col)
    groups, start, prev = [], None, None
    for x in xs:
        if start is None:
            start = prev = x
        elif x - prev > gap_px:
            groups.append((start, prev + 1))
            start = x
        prev = x
    if start is not None:
        groups.append((start, prev + 1))
    views = []
    for a, b in groups:
        sub = ink[:, a:b]
        rows = np.flatnonzero(sub.mean(axis=1) >= 0.2)
        if not len(rows):
            continue
        cols = np.flatnonzero(sub[rows[0]:rows[-1] + 1].mean(axis=0) >= 0.2)
        if not len(cols) or cols[-1] - cols[0] + 1 < min_w_px:
            continue
        views.append((int(rows[0]), int(rows[-1] + 1), int(a + cols[0]), int(a + cols[-1] + 1)))
    return views


def drop_tall_runs(mask, max_run_px):
    """R2: remove vertical runs of dark pixels taller than max_run_px (cladding bands, not glass)."""
    out = mask.copy()
    h = mask.shape[0]
    for x in range(mask.shape[1]):
        col = mask[:, x]
        y = 0
        while y < h:
            if col[y]:
                e = y
                while e < h and col[e]:
                    e += 1
                if e - y > max_run_px:
                    out[y:e, x] = False
                y = e
            else:
                y += 1
    return out


def view_profile(crop, max_run_px=None):
    ink = crop < WHITE
    dark = crop < DARK
    glass = drop_tall_runs(dark, max_run_px) if max_run_px else dark
    body = (ink.mean(axis=1) >= 0.9) & (dark.mean(axis=1) <= 0.6)
    if not body.any():
        return np.zeros(crop.shape[1]), 0
    return glass[body].mean(axis=0), int(body.sum())


def read_sheet(pdf, page_index, clip, max_run_px=None):
    doc = fitz.open(pdf)
    page = doc[page_index]
    m_per_pt, nmarks = page_scale(page)
    luma = raster_only(doc, page, clip, m_per_pt)
    out = []
    for r0, r1, c0, c1 in split_views(luma):
        crop = luma[r0:r1, c0:c1]
        prof, nbody = view_profile(crop, max_run_px)
        out.append({"box_px": [r0, r1, c0, c1], "width_m": round((c1 - c0) * RES, 2),
                    "height_m": round((r1 - r0) * RES, 2), "body_rows": nbody, "crop": crop, "profile": prof})
    return {"m_per_pt": m_per_pt, "level_marks": nmarks, "views": out, "luma_shape": list(luma.shape)}
