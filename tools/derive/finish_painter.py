"""new-case: shared deterministic finish painting for the atlas and TEC26 replay (#1902)."""
import math

import numpy as np
from PIL import Image


def periodic_noise(n, scale, seed):
    """Tileable noise on an n x n cell: random spectrum low-passed at `scale` px (FFT is periodic)."""
    rng = np.random.default_rng(seed)
    w = rng.standard_normal((n, n))
    f = np.fft.fftfreq(n)
    fx, fy = np.meshgrid(f, f)
    k = np.exp(-((fx ** 2 + fy ** 2) * (scale ** 2)))
    out = np.real(np.fft.ifft2(np.fft.fft2(w) * k))
    return (out - out.mean()) / (out.std() + 1e-9)


def tile(cell, size):
    reps = -(-size // cell.shape[0])
    return np.tile(cell, (reps, reps))[:size, :size]


def uv_grid(size, S=4.096):
    """Pixel centres in tile metres (u right, v up); S metres per tile (KPP: 4.096 m -> 1 px = 1 mm)."""
    u = (np.arange(size) + 0.5) * S / size
    v = (size - np.arange(size) - 0.5) * S / size
    return np.meshgrid(u, v)


def normal_from_height(h, strength):
    """DirectX normal map from a height field in px units (image rows grow downward)."""
    dhdx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / 2
    dhdrow = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) / 2
    nx, ny_up, nz = -dhdx * strength, dhdrow * strength, np.ones_like(h)  # v up = -row
    ln = np.sqrt(nx ** 2 + ny_up ** 2 + nz ** 2)
    nx, ny_up, nz = nx / ln, ny_up / ln, nz / ln
    rgb = np.stack([(nx * 0.5 + 0.5), (-ny_up * 0.5 + 0.5), (nz * 0.5 + 0.5)], -1)  # DirectX: G = -Y
    return (rgb * 255).round().astype(np.uint8)


def load_user_texture(st):
    """The user's source image as float RGB, after the sha256 in the spec matched (fail-closed otherwise)."""
    import hashlib
    raw = open(st["path"], "rb").read()
    got = hashlib.sha256(raw).hexdigest()
    if got != st["sha256"]:
        raise ValueError(f"source texture {st['path']}: sha256 {got} != spec {st['sha256']}")
    import io
    return np.asarray(Image.open(io.BytesIO(raw)).convert("RGB"), float)


def make_user_vjoints(t, size):
    """TEC26 panels ([D169]): VERTICAL joints only, from the user's texture. The tile period is the facade
    rib contract P[0] (finish_map.validate_facades: field / ribs from the colour-solution sheet), in px
    Pp = P[0] * size / S, generally NOT an integer and NOT the source image's own joint spacing (the image gives the
    look of ONE joint plus colour/noise only - Artem: the repeat comes from the sheet). Tile column x takes the source
    column at the same integer offset floor(d) from a source joint centre, d = signed distance of the column centre to
    the nearest tile joint at x = k * Pp; so joints sit at u' = k * P (finish_map.facade_joint_uv), whole-period u
    shifts keep the phase, the joint profile is copied 1:1 (no resampling) and rows are the source rows (no horizontal
    joints). The user's colour, noise and joint profile are kept unchanged: the panel median must already equal the
    spec/KPP RGB within 3 levels and the declared joint columns must be dark, else ValueError. A wider `joint_half_mm`
    (NPM, >= 1.5 px) paints the extra joint width in the source joint median colour."""
    st = t["source_texture"]
    src = load_user_texture(st)
    H, W = src.shape[:2]
    per, (j0, j1) = st["period_px"], st["first_joint_px"]
    Pp = t["P"][0] * size / t["S"]
    if H != size or W < 2 * per:
        raise ValueError(f"source texture {W}x{H}: needs height {size} and >= 2 joint periods")
    if not (math.isfinite(Pp) and Pp >= 4 * (j1 - j0)):
        raise ValueError(f"tile period {Pp} px leaves no panel between {j1 - j0} px joints")
    ce = (j0 + j1) // 2 + per                  # centre (pixel edge) of the second joint: room on both sides
    half = int(math.ceil(Pp / 2)) + 1
    if ce + half > W:
        ce -= per
    if ce - half < 0 or ce + half > W:
        raise ValueError(f"source texture {W} px: no source joint with {half} px of panel on both sides")
    d = (np.arange(size) + 0.5 + Pp / 2) % Pp - Pp / 2           # signed distance (px) to the nearest tile joint
    p = np.floor(d).astype(int)                                # integer source offset (1:1 joint profile)
    col = src[:, ce + p]
    src_joint = (p >= j0 - (j0 + j1) // 2) & (p < j1 - (j0 + j1) // 2)
    panel = col[:, ~src_joint].reshape(-1, 3)
    med = np.median(panel, 0)
    if np.abs(med - np.array(t["rgb"], float)).max() > 3:
        raise ValueError(f"source texture panel median {med.tolist()} != spec rgb {t['rgb']} (> 3 levels)")
    jcol = col[:, src_joint].reshape(-1, 3)
    if not len(jcol) or jcol.mean() >= 0.6 * panel.mean():
        raise ValueError(f"declared joint columns {st['first_joint_px']} are not dark in the source texture")
    jw = t.get("joint_half_mm", 4) * size / (t["S"] * 1000)  # half joint width in px
    joint = np.abs(p + 0.5) < jw
    extra = joint & ~src_joint
    col[:, extra] = np.median(jcol, 0)
    h = np.zeros((size, size))
    h[:, joint] = -3.0
    rough = np.full((size, size), t["rough"])
    rough[:, joint] = 0.9
    oz = t.get("outline_z_m")
    if oz:  # the sheet's thin dark field outline: joint_half_mm inside the field's bottom and top edge (v = world z)
        z = (size - np.arange(size) - 0.5) * t["S"] / size          # world z of each tile row
        w = t.get("joint_half_mm", 4) / 1000
        rows = ((z >= oz[0]) & (z <= oz[0] + w)) | ((z >= oz[1] - w) & (z <= oz[1]))
        col[rows, :] = np.median(jcol, 0)
        h[rows, :] = -3.0
        rough[rows, :] = 0.9
    dif = np.clip(col, 0, 255).round().astype(np.uint8)
    erm = np.stack([np.zeros((size, size)), rough * 255, np.full((size, size), t["metal"] * 255)], -1)
    return dif, None, erm.round().astype(np.uint8), normal_from_height(h, 0.5)


def make_elevations(t, size):
    """Trim sheet of whole window / door elevations (#1925 [D416], windows shown as texture): `cells` maps a name
    to {box: [u0, v0, u1, v1] tile metres (v up), size: [w, h] metres, panes: [[x0, x1, z0, z1], ...] metres from
    the drawing's lower-left}. Everything that is not a pane is profile (frame, mullion, transom, sash, leaf) in
    `rgb`; panes are `glass_rgb`, lighter at the top, with a dark 12 mm gasket line. Deterministic."""
    S = t["S"]
    px = size / S
    rgb = np.array(t["rgb"], float)
    glass = np.array(t["glass_rgb"], float)
    n = tile(periodic_noise(512, 24, 5), size) * 0.012
    col = rgb[None, None, :] * (1 + n[..., None])
    h = np.zeros((size, size))
    rough = np.full((size, size), t["rough"])
    for c in t["cells"].values():
        u0, v0, u1, v1 = c["box"]
        w, hh = c["size"]
        sx, sz = (u1 - u0) / w, (v1 - v0) / hh
        g = max(1, round(t.get("gasket_m", 0.012) * sx * px))
        for x0, x1, z0, z1 in c["panes"]:
            c0, c1 = round((u0 + x0 * sx) * px), round((u0 + x1 * sx) * px)
            r0, r1 = round((S - v0 - z1 * sz) * px), round((S - v0 - z0 * sz) * px)
            if c1 - c0 < 1 or r1 - r0 < 1:
                continue
            ramp = np.linspace(1.18, 0.82, r1 - r0)[:, None, None]       # sky at the top, darker below
            col[r0:r1, c0:c1] = glass[None, None, :] * ramp
            col[r0:r0 + g, c0:c1] = col[r1 - g:r1, c0:c1] = rgb * 0.55
            col[r0:r1, c0:c0 + g] = col[r0:r1, c1 - g:c1] = rgb * 0.55
            h[r0:r1, c0:c1] = -2.0
            rough[r0:r1, c0:c1] = 0.05
    dif = np.clip(col, 0, 255).round().astype(np.uint8)
    erm = np.stack([np.zeros((size, size)), rough * 255, np.full((size, size), t["metal"] * 255)], -1)
    return dif, None, erm.round().astype(np.uint8), normal_from_height(h, 0.5)


def make_full(t, size):
    if t["pattern"] == "elevations":
        return make_elevations(t, size)
    u, v = uv_grid(size, t.get("S", 4.096))
    rgb = np.array(t["rgb"], float)
    h = np.zeros((size, size))
    alpha = None
    rough = np.full((size, size), t["rough"])
    pat = t["pattern"]
    if pat == "user_vjoints":
        return make_user_vjoints(t, size)
    if pat == "tile300":  # porcelain 300x300, 4 mm joints at multiples of 0.3 m (world-aligned)
        jw = t.get("joint_half_mm", 2)
        ju = np.abs(((u * 1000 + jw) % 300) - jw) < jw
        jv = np.abs(((v * 1000 + jw) % 300) - jw) < jw
        joint = ju | jv
        n = tile(periodic_noise(300, 6, 1), size) * 0.025
        col = rgb[None, None, :] * (1 + n[..., None])
        col[joint] = rgb * 0.62
        h[joint] = -1.5
        rough[joint] = 0.85
    elif pat == "asphalt":  # 1.3 m periodic grain + aggregate speckles
        n1 = tile(periodic_noise(1300, 40, 2), size) * 0.06
        n2 = tile(periodic_noise(1300, 2, 3), size)
        col = rgb[None, None, :] * (1 + n1[..., None] + 0.12 * n2[..., None])
        h = n2 * 0.6
    elif pat == "cassette":  # metal cassettes: 8 mm open joints (dark), slight sheen noise
        ph = t.get("phase", [0.0, 0.0])
        jw = t.get("joint_half_mm", 4)
        ju = np.abs((((u - ph[0]) * 1000 + jw) % (t["P"][0] * 1000)) - jw) < jw
        jv = (np.abs((((v - ph[1]) * 1000 + jw) % (t["P"][1] * 1000)) - jw) < jw) if t.get("h_joints") else np.zeros_like(ju)
        joint = ju | jv
        n = tile(periodic_noise(600, 30, 4), size) * 0.015
        col = rgb[None, None, :] * (1 + n[..., None])
        col[joint] = rgb * 0.35
        h[joint] = -3.0
        rough[joint] = 0.9
    elif pat == "perforated":  # perforated cassette 0.6 x 0.6: holes d 50 mm, pitch 120 mm, joints 8 mm
        ph = t.get("phase", [0.0, 0.0])
        uu, vv = (u - ph[0]) % 0.6, (v - ph[1]) % 0.6
        jw = t.get("joint_half_mm", 4) / 1000
        joint = (np.minimum(uu, 0.6 - uu) < jw) | (np.minimum(vv, 0.6 - vv) < jw)
        cu, cv = (uu % 0.12) - 0.06, (vv % 0.12) - 0.06
        hole = (cu ** 2 + cv ** 2 < 0.025 ** 2) & ~joint
        col = np.broadcast_to(rgb, (size, size, 3)).copy().astype(float)
        col[hole] = (60, 62, 66)
        col[joint] = rgb * 0.45
        h[hole | joint] = -2.0
        rough[hole] = 0.95
    elif pat in ("railing", "ladder", "cage"):
        solid = np.zeros((size, size), bool)
        if pat == "railing":  # posts every 0.9 m (40 mm), top rail at 1.2 m (40 mm), 4 guide bars (20 mm)
            base = v - 0.05
            inside = (base >= 0) & (base <= 1.2)
            post = (np.abs(((u * 1000 + 20) % 900) - 20) < 20) & inside
            top = (base >= 1.16) & (base <= 1.2)
            bars = np.zeros_like(solid)
            for hb in (0.25, 0.5, 0.75, 1.0):
                bars |= np.abs(base - hb) < 0.01
            solid = post | top | (bars & inside)
        elif pat == "ladder":  # stiles 50 mm at u 0.04..0.09 / 0.79..0.84, rungs 30 mm every 0.372 m
            within = (u >= 0.04) & (u <= 0.84)
            stile = ((u >= 0.04) & (u <= 0.09)) | ((u >= 0.79) & (u <= 0.84))
            rung = (np.abs(((v * 1000 + 15) % 372) - 15) < 15) & within
            solid = stile | rung
        else:  # cage: vertical ties every 0.46 m (20 mm), hoops every 0.833 m (50 mm)
            tie = np.abs(((u * 1000 + 10) % 460) - 10) < 10
            hoop = np.abs(((v * 1000 + 25) % 833) - 25) < 25
            solid = tie | hoop
        col = np.broadcast_to(rgb, (size, size, 3)).copy()
        if pat == "railing" and "rgb_top" in t:  # handrail RAL 1021 (Revit 'Поручень ... (RAL 1021)', ИД)
            col[top & inside] = t["rgb_top"]
        alpha = np.where(solid, 255, 0).astype(np.uint8)
        h = np.where(solid, 1.0, 0.0)
    else:
        raise ValueError(pat)
    dif = np.clip(col, 0, 255).round().astype(np.uint8)
    erm = np.stack([np.zeros((size, size)), rough * 255, np.full((size, size), t["metal"] * 255)], -1)
    erm = erm.round().astype(np.uint8)
    nrm = normal_from_height(h, 0.5) if pat not in ("railing", "ladder", "cage") else None
    return dif, alpha, erm, nrm
