"""Standing #51: build a SOURCE-ONLY form key for 63B (floor +7.80..+10.95, type A, east facade box).

Input: G:/.../tower-B/v002/source_sections_and_openings.json (source sections and openings, no body bytes).
Output (key frame = t_563a40f7 label frame, z shifted by +SHIFT so the frozen scorer runs byte-identical):
  <out>/heldout-key-v001.json, <out>/heldout-sections-v001.json, <out>/SHA256SUMS.txt
usage: python make_key63b.py <source_sections_and_openings.json> <out_dir>
"""
import hashlib
import json
import math
import os
import sys

SRC_SHA256 = None  # recorded in the contract; checked by run51.py
FLOOR_INDEX = 1            # floors[1] = +7.80..+10.95, type A
S_RANGE = (22.6, 40.3)     # ring arc length window (m): seg 15 end, seg 16 window, corner 16-17-18, 4 windows on seg 18
MARGIN = 0.8               # box margin (m), covers the 0.71 m reveal backs
SILL = 8.48                # floor bottom 7.80 + 0.68 (all A windows)
SHIFT = round(17.30 - SILL, 2)   # 8.82: maps the 63B sill onto the frozen G22 band (scorer loops 17.0..17.6)
LABEL_Z = ["16.85", "17.8", "18.2", "19.8"]   # frozen scorer section labels


def main(src, out):
    d = json.load(open(src, encoding="utf-8"))
    ring = d["modules"]["A"]["ring"]
    n = len(ring)
    cum = [0.0]
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))

    def at(s):
        i = max(k for k in range(n) if cum[k] <= s)
        a, b = ring[i], ring[(i + 1) % n]
        t = (s - cum[i]) / (cum[i + 1] - cum[i])
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), i

    pts = [at(S_RANGE[0] + k * 0.05)[0] for k in range(int((S_RANGE[1] - S_RANGE[0]) / 0.05) + 1)]
    pts += [tuple(ring[i]) for i in range(n) if S_RANGE[0] <= cum[i] <= S_RANGE[1]]
    box = [round(min(p[0] for p in pts) - MARGIN, 3), round(min(p[1] for p in pts) - MARGIN, 3),
           round(max(p[0] for p in pts) + MARGIN, 3), round(max(p[1] for p in pts) + MARGIN, 3)]

    def inbox(p):
        return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]

    idx = [i for i in range(n) if inbox(ring[i])]
    idx = sorted(set(idx) | {idx[0] - 1, idx[-1] + 1})
    floor = d["floors"][FLOOR_INDEX]
    assert (floor["bottom"], floor["top"], floor["type"]) == (7.8, 10.95, "A"), floor["bottom"]
    openings, outside = [], []
    for o in sorted(floor["openings"], key=lambda o: o["s0"]):
        mid, i = at((o["s0"] + o["s1"]) / 2)
        if not (S_RANGE[0] <= o["s0"] and o["s1"] <= S_RANGE[1]):
            if inbox(mid):
                raise SystemExit(f"opening {o['ref']} straddles the box: choose another S_RANGE")
            outside.append(o["ref"])
            continue
        i0 = at(o["s0"])[1]
        assert at(o["s1"] - 1e-6)[1] == i0, f"opening {o['ref']} spans two ring segments"
        assert i0 in idx and i0 + 1 in idx
        openings.append({
            "id": o["ref"].split("[")[-1].rstrip("]") if "[" in o["ref"] else o["ref"][-12:],
            "source_object": o["ref"], "curtain": o["curtain"], "contour_segment": [i0, i0 + 1],
            "segment_len_m": round(cum[i0 + 1] - cum[i0], 3),
            "edge_s_m": [round(o["s0"] - cum[i0], 4), round(o["s1"] - cum[i0], 4)],
            "width_m": round(o["s1"] - o["s0"], 4),
            "sill_head_z_m": [round(o["z0"] + SHIFT, 4), round(o["z1"] + SHIFT, 4)],
            "sill_head_z_real_m": [o["z0"], o["z1"]], "reveal_depth_m": o["depth"]})
    # key sections: the source ring polyline (closed contour, no openings: the contour sections are below sill
    # and above head, where the source has no window gap; no curtain is inside the box - asserted)
    assert not any(o["curtain"] for o in openings)
    segs = [[list(map(lambda v: round(v, 4), ring[i % n])), list(map(lambda v: round(v, 4), ring[(i + 1) % n]))]
            for i in range(idx[0], idx[-1])]
    ksec = {z: segs for z in LABEL_Z}
    key = {
        "schema": "heldout-key/1 (t_563a40f7 format; source-only key built by standing #51)",
        "card": "t_fb3a0b98", "fragment": "63B typical floor +7.80..+10.95 (type A, sill +8.48), east facade, ring arc "
        f"{S_RANGE[0]}..{S_RANGE[1]} m", "box_xy_m": box,
        "z_band_m": [round(SILL + SHIFT, 2), round(10.45 + SHIFT, 2)], "units": "m",
        "frame": f"xy = FBX world metres of the 63B review exports (ring of source_sections_and_openings.json); "
                 f"z label = real z + {SHIFT}",
        "z_shift_m": SHIFT, "label_to_real_z": {z: round(float(z) - SHIFT, 2) for z in LABEL_Z},
        "accepted_bytes": None, "basis": "SOURCE ONLY (no accepted body bytes used); v002..v006 were built from this "
        "same JSON, v007 from floor_from_dump (different chain)",
        "contour_vertices_in_box": [{"ring_index": i, "xy": [round(ring[i % n][0], 4), round(ring[i % n][1], 4)]}
                                    for i in idx],
        "openings": openings, "negatives": [], "openings_outside_box": len(outside),
        "sections_z_m": [float(z) for z in LABEL_Z],
        "section_segments_in_box": {z: len(segs) for z in LABEL_Z}}
    os.makedirs(out, exist_ok=True)
    kp, sp = os.path.join(out, "heldout-key-v001.json"), os.path.join(out, "heldout-sections-v001.json")
    json.dump(key, open(kp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(ksec, open(sp, "w", encoding="utf-8"), indent=0)
    with open(os.path.join(out, "SHA256SUMS.txt"), "w", encoding="utf-8") as f:
        for p in (kp, sp):
            f.write(f"{hashlib.sha256(open(p, 'rb').read()).hexdigest()} *{os.path.basename(p)}\n")
    print(json.dumps({"box": box, "ring_idx": [idx[0], idx[-1]], "openings": [(o["id"], o["contour_segment"],
                      o["edge_s_m"], o["reveal_depth_m"]) for o in openings], "shift": SHIFT}, ensure_ascii=False))


if __name__ == "__main__":
    main(*sys.argv[1:3])
