"""elv-tc-vpm WHOLE building: procedural VPM UDIM maps (Diffuse, ERM, Normal) from tex_spec_v002.json + uv_layout_v002.
= make_textures_pilot.py (accepted pilot, same patterns and parameters) + 'joint_axes' (u / v / uv, default uv) for the
gate sections and the deck boards, + placeholder 'emit' -> ERM R (glow strength) for the light IDs 28-33.

uv run --no-project --with numpy --with pillow python make_textures_full.py <spec.json> <layout.json> <new_out_dir>

Writes T_Elevatornaya_1A_{Diffuse|ERM|Normal}_1.<UDIM>.png (reg p.34 §4.3), 8-bit RGB, no alpha.
- full tiles: 4096 px over S metres (layout px_per_m); pattern = function of (u - phi_u, v - phi_v) in metres, joints
  centred on the P_lat lattice lines (the UV pass anchored the faces so these lines land on the FBX panel joints),
  colour/grain variation periodic with P_tex (faces are shifted by whole P_tex only); joints anti-aliased;
- placeholders: 256 px single colour (reg p.31 §3), flat normal; a full tile whose ERM has no variation also gets a
  256 ERM placeholder (TEC26/KPP1 rule, SINTEZ 2.5.3.1);
- ERM: R = 0 (no emission in the pilot), G roughness, B metallic; Normal DirectX (G = -Y), reg p.30 §5.1.7.
Helpers reused from jobs/TEC26-OKS/scripts/make_textures.py (normal_from_height, save). Deterministic (fixed seeds).
Colours approximate RAL sRGB, not calibrated; the wood grain is generated (user has no wood texture, D01).
"""
import json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "TEC26-OKS", "scripts"))
from make_textures import normal_from_height, save  # noqa: E402


def aniso_noise(ny, nx, sx, sy, seed):
    """periodic (ny, nx) noise, smooth over sx px across columns and sy px along rows (FFT, periodic)"""
    rng = np.random.default_rng(seed)
    w = rng.standard_normal((ny, nx)).astype(np.float32)
    fy, fx = np.meshgrid(np.fft.fftfreq(ny), np.fft.fftfreq(nx), indexing="ij")
    k = np.exp(-(((fx * sx) ** 2) + ((fy * sy) ** 2)) * 4.0)
    out = np.real(np.fft.ifft2(np.fft.fft2(w) * k)).astype(np.float32)
    return (out - out.mean()) / (out.std() + 1e-9)


def wood_cell(ny, nx, seed, cells=(1, 1), along="v", tones=None):
    """wood-look grain tone field (mean 1) for one P_tex cell; grain lines run along rows' axis v (or u)"""
    if along == "u":
        f = wood_cell(nx, ny, seed, (cells[1], cells[0]), "v", tones)
        return f.T.copy()
    g_fine = aniso_noise(ny, nx, 1.3, 90, seed)
    g_mid = aniso_noise(ny, nx, 7, 260, seed + 1)
    g_low = aniso_noise(ny, nx, 45, 500, seed + 2)
    X = np.arange(nx, dtype=np.float32)[None, :]
    rings = np.sin(2 * np.pi * (X / 17.0 + 1.8 * g_low + 0.4 * g_mid))
    tone = 1 + 0.03 * g_fine + 0.045 * g_mid + 0.035 * g_low + 0.03 * rings
    knots = np.clip(aniso_noise(ny, nx, 18, 30, seed + 3) - 3.2, 0, None) * 0.25  # rare dark knots
    tone -= knots
    if tones is not None:  # per-cassette tone (render sheets 14/17 show cassette-to-cassette variation)
        cy, cx = cells
        for j in range(cy):
            for i in range(cx):
                tone[j * ny // cy:(j + 1) * ny // cy, i * nx // cx:(i + 1) * nx // cx] += tones[(j * cx + i) % len(tones)]
    return tone / tone.mean()


def joint_cover(x, P, half_m, res):
    """anti-aliased coverage (0..1) of joints centred on x = k*P (metres), half width half_m"""
    d = np.abs(((x + P / 2) % P) - P / 2)
    return np.clip((half_m - d) * res + 0.5, 0, 1).astype(np.float32)


def make_full(t, lay, N):
    S = lay["S"]
    res = N / S
    phi = lay["tiles"][t["key"]]["phi"]
    u = ((np.arange(N) + 0.5) * S / N).astype(np.float64)
    v = ((N - np.arange(N) - 0.5) * S / N).astype(np.float64)
    x, y = u - phi[0], v - phi[1]
    Pt, Pl = t["P_tex"], t["P_lat"]
    nx, ny = int(round(Pt[0] * res)), int(round(Pt[1] * res))
    ix = np.floor(((x % Pt[0]) / Pt[0]) * nx).astype(int).clip(0, nx - 1)
    iy = np.floor(((y % Pt[1]) / Pt[1]) * ny).astype(int).clip(0, ny - 1)
    # cell images are stored with row 0 = lowest v; sample cell[iy, ix]
    pat = t["pattern"]
    rgb = np.array(t["rgb"], np.float32)
    rough = t["rough"]
    if pat in ("wood_cassette", "wood_plain"):
        cells = (int(round(Pt[1] / Pl[1])), int(round(Pt[0] / Pl[0]))) if pat == "wood_cassette" else (1, 1)
        tones = [-0.05, 0.035, 0.02, -0.025] if pat == "wood_cassette" else None
        tone = wood_cell(ny, nx, 11 if pat == "wood_cassette" else 23 + t["udim"], cells, t.get("grain", "v"), tones)
        hgt = (tone - 1) * 6.0
        rvar = -(tone - 1) * 0.6
    elif pat == "plaster":
        n1 = aniso_noise(ny, nx, 1.5, 1.5, 31)
        n2 = aniso_noise(ny, nx, 25, 25, 32)
        tone = 1 + 0.03 * n1 + 0.025 * n2
        hgt, rvar = n1 * 0.8, np.zeros_like(n1)
    elif pat == "membrane":
        n1 = aniso_noise(ny, nx, 2, 2, 41)
        n2 = aniso_noise(ny, nx, 60, 60, 42)
        tone = 1 + 0.02 * n1 + 0.035 * n2
        hgt, rvar = n1 * 0.4, np.zeros_like(n1)
    else:  # cassette / sandwich: smooth painted metal, faint sheen
        n = aniso_noise(ny, nx, 40, 40, 51 if pat == "cassette" else 52)
        tone = 1 + 0.012 * n
        hgt, rvar = np.zeros_like(n), np.zeros_like(n)
    T = tone[iy[:, None], ix[None, :]]
    col = rgb[None, None, :] * T[..., None]
    H = hgt[iy[:, None], ix[None, :]].astype(np.float32)
    R = (rough + rvar[iy[:, None], ix[None, :]]).astype(np.float32)
    if t.get("joint_mm"):
        hw = t["joint_mm"] / 2000.0
        ax = t.get("joint_axes", "uv")
        cu = joint_cover(x, Pl[0], hw, res) if "u" in ax else np.zeros(x.shape, np.float32)
        cv = joint_cover(y, Pl[1], hw, res) if "v" in ax else np.zeros(y.shape, np.float32)
        c = np.maximum(cu[None, :], cv[:, None])
        dark = rgb * (0.30 if pat == "wood_cassette" else 0.35)
        col = col * (1 - c[..., None]) + dark[None, None, :] * c[..., None]
        H = H * (1 - c) - 3.0 * c
        R = R * (1 - c) + 0.9 * c
    dif = np.clip(col, 0, 255).round().astype(np.uint8)
    R = np.clip(R, 0, 1)
    erm = np.stack([np.zeros((N, N), np.float32), R * 255, np.full((N, N), t["metal"] * 255, np.float32)], -1)
    erm = erm.round().astype(np.uint8)
    nrm = normal_from_height(H.astype(np.float64), 0.5)
    return dif, erm, nrm


def main(spec_p, lay_p, out):
    spec = json.load(open(spec_p, encoding="utf-8"))
    lay = json.load(open(lay_p, encoding="utf-8"))
    if os.path.exists(out) and os.listdir(out):
        raise SystemExit("output dir not empty: " + out)
    os.makedirs(out, exist_ok=True)
    a, sl, N, n = spec["address"], spec["slot"], spec["size_full"], spec["size_placeholder"]
    name = lambda kind, udim: os.path.join(out, f"T_{a}_{kind}_{sl}.{udim}.png")  # noqa: E731
    flat_n = np.broadcast_to(np.array([128, 128, 255], np.uint8), (n, n, 3)).copy()
    rep = []
    for t in spec["tiles"]:
        if t["key"] not in lay["tiles"]:
            continue  # tile dropped (no faces)
        udim = lay["tiles"][t["key"]]["udim"]
        t = dict(t, udim=udim)
        if t["kind"] == "placeholder":
            save(np.broadcast_to(np.array(t["rgb"], np.uint8), (n, n, 3)).copy(), name("Diffuse", udim), "RGB")
            e = np.array([round(t.get("emit", 0.0) * 255), round(t["rough"] * 255), round(t["metal"] * 255)], np.uint8)
            save(np.broadcast_to(e, (n, n, 3)).copy(), name("ERM", udim), "RGB")
            save(flat_n, name("Normal", udim), "RGB")
            rep.append((t["key"], udim, "placeholder 256"))
        else:
            dif, erm, nrm = make_full(t, lay, N)
            save(dif, name("Diffuse", udim), "RGB")
            save(nrm, name("Normal", udim), "RGB")
            if (erm == erm[0, 0]).all():
                save(np.broadcast_to(erm[0, 0], (n, n, 3)).copy(), name("ERM", udim), "RGB")
                ek = "ERM 256 placeholder"
            else:
                save(erm, name("ERM", udim), "RGB")
                ek = "ERM 4096"
            rep.append((t["key"], udim, f"full 4096, {ek}, mean diffuse {dif.reshape(-1, 3).mean(0).round(1).tolist()}"))
        print(*rep[-1], flush=True)
    json.dump(rep, open(os.path.join(os.path.dirname(os.path.abspath(out)), "textures_report_v002.json"), "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:4])
