"""Alice-style layout designer (40% and 60/65%): design a curved split layout key by key, export it for
case/plate CAD.

Run:   /opt/homebrew/bin/python3 alice.py      (needs Tk 8.6+: brew install python-tk@3.14;
Test:  /opt/homebrew/bin/python3 test_alice.py  macOS's /usr/bin/python3 has Tk 8.5, no rotated text)

DESIGN RULES — the behaviour this tool promises. Code comments say "rule N" where each is enforced,
and test_alice.py checks each one. Change a rule here first, then the code, then its test.

 1. Layout: Alice-style split, two halves. 40% = 4 rows per half (top -> bottom): Top (QWERTY),
    Home, R2 "anchor" (the shift row, the reference row for everything), Bottom (spacebars).
    60/65% = the same plus a Number row on top (5 rows); its default is the Neo Ergo (rule 16). The anchor is always the second row
    from the bottom. The halves are edited independently. The right half is the mirror image in
    code: built outer -> inner, then flipped.
 2. Keys: every keycap has an editable label and width (0.25u steps, min 0.25u). A key can be a
    spacer: an empty gap that takes up room but isn't a key (not exported, ignored for collisions,
    extents and "outermost / innermost key" lookups), or a WK blocker (rule 14). Add/delete keys
    freely, max 10 per row per half (blockers and spacers included), min 1.
 3. Cherry spacing: 1u = 19.05 mm. Neighbours in a row share their bottom corners, so the pitch
    along every row is exactly 19.05 mm; rows are 1u apart (plus rule 10's fraction of a mm).
 4. Stagger: per row, 0.125u steps, + = toward the center. Every row above R2 (Number, Top,
    Home) is measured from the R2 row's OUTER edge. The Bottom row is measured from the R2 row's INNER edge (the edge of B/N):
    its inner end sits on the same radial (curve) or perpendicular (straight bend) line. Per half, the
    Bottom row can instead be measured from the R2 OUTER edge (`"align": "outer"`), e.g. to line up
    arrow keys under an up arrow in the straight part.
 5. Curve (`bend`: "curve", the default; rule 16 is the straight alternative): `curve` = degrees per
    1u key (0.05° steps), a gentle curve down toward the center. The same rate on
    both halves (uniform angles). All rows of a half bend around one shared center (concentric
    arcs 1u apart).
 6. Outer keys straight: the outermost real key of every row from the top down to R2
    (Tab/Ctrl/Shift, Bksp/Enter/Fn, plus Esc etc. on 60/65%) is exactly at `outer` degrees (0 = square to the case edge); spacers in front don't count. The
    Bottom row isn't forced straight: its outer key sits under the letters and follows the curve.
 7. Bend start: rows stay straight up to the inner edge of that half's longest outer key, plus
    `straight_run` u more if set (0.125u steps, same on both halves), then bend. (Starting earlier
    let long straight keys like a 2.25u Enter push their row into the row above.)
 8. Match center keys (`match_center`, default on): the half whose modifiers reach further starts
    curving later by the difference, so both R2 rows curve over the same length and B and N end at
    the same angle and height, while the degrees per key stay equal (rule 5).
 9. Level halves: with match on, B and N centers are level; with it off, the tops of the top row's
    outer keys (Tab/Bksp on 40%). Either way the modifier rows (Tab/Bksp, Ctrl/Enter, Shift/Fn, ...)
    stay level with each other, because both halves use identical row spacing.
10. No collisions: no two real keys' 19.05 mm footprints may overlap, so the plate works. Rectangles
    on concentric arcs can overlap ~0.1 mm at a stagger, so place() widens just those row gaps (the
    same on both halves) until clear. A slightly bigger gap is fine; overlap is not. The UI shows
    the overlap count and export asks before writing if any remain. Gap between halves >= 0.
11. Files: Save/Open = the layout JSON (this module's DEFAULT shape, with "size": "40" or "60"). Export DXF = mm, y up,
    layers KEYCAP_1U (19.05 mm footprints) and SWITCH_14MM (MX plate cutouts). Export KLE =
    keyboard-layout-editor.com JSON, one rotated key per row (KLE-site rx/ry semantics).
12. Size tabs: the window has a 40% tab and a 60/65% tab with the same options. Each tab keeps its
    own layout while you switch. Opening a file made for the other size is refused with a message
    to switch tabs; files without "size" (older saves) are recognised by their row count.
13. Case outline (`frame`, off by default; `frame_margin` mm, default 8): a simple case outline drawn
    behind the keys, shaped like an Alice case, with every edge exactly the margin from its nearest
    key: one straight top edge across both halves, each outer end square to that side's outer keys,
    and one bottom edge per half angled to hug that half's bottom keys, the two meeting in a V in the
    middle (5 corners). If that can't hold every key, the bottom edges step across the middle
    instead. Preview only: it isn't exported.
14. WK blockers (`"blocker": true`): a solid piece of case filling a key position, like the blanks
    beside a winkeyless bottom row. Bottom row only (the UI only offers it there and files with a
    blocker elsewhere are refused). Width is chosen like any key. Blockers take part in placement,
    collisions and the frame like keys, but have no switch or keycap: the DXF puts their outline on
    a WK_BLOCKER layer, and KLE gets them as decals.
15. Mod column (both sizes, like a Neo Ergo's macro column; `mod` in the layout): per half, an extra
    column of keys outside the main block at the outer angle (rule 6), one per row from the top.
    Each half sets it on/off, how many keys (`count`, from the top), a vertical offset (`offset`,
    0.125u steps, + = down) and its distance from the main keys (`gap`, 0.125u steps), measured from
    the outermost main key of the rows it spans. Every mod key is its own: label, width, key or
    spacer, and a left/right nudge (`dx`, 0.125u steps, + = toward the main keys), all set by
    clicking it. Mod keys are ordinary keys everywhere else: collisions, frame, DXF, KLE.
16. Straight bend (`bend`: "straight"): instead of curving, each row turns once by `line_angle`
    degrees (the angle of the whole angled line) where rule 7's straight part ends; the turns are
    mitered so rows stay 1u apart. A key is either wholly flat or wholly on the angled line (by where
    its middle falls), never in between, like two rigid blocks. Rows stay exactly 1u apart in both the
    flat and the angled part: where a key at the turn would clip the next row, that row's angled keys
    slide inward along their line just far enough to clear (a small wedge gap at the turn), instead
    of rule 10 spreading the rows. The 60/65% default uses this to
    reproduce the Qwertykeys Neo Ergo: flat outer keys, 10° alphas, a stepped 4-key macro column.

Units: geometry is computed in u (1u = 19.05 mm) with y pointing down and angles in degrees clockwise;
place() returns mm.
"""
import json
import math
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

U = 19.05       # Cherry MX key pitch, mm
CAP = 18.0      # typical keycap bottom size, only used for drawing
SWITCH = 14.0   # MX plate cutout
MAX_KEYS = 10   # per row, per half (rule 2)
TOP = 0         # row indices run top -> bottom; the anchor (R2) is always len(rows) - 2 (rule 1)
SIZES = {"40": 4, "60": 5}                  # size -> rows per half (rules 1, 12)
SIZE_NAMES = {"40": "40%", "60": "60/65%"}
ROLE_NAMES = ["Bottom", "Anchor (R2)", "Home", "Top", "Number"]  # counted from the bottom up


def anchor(rows):
    return len(rows) - 2


def row_name(r, n):
    return ROLE_NAMES[n - 1 - r]


def _row(offset, *keys):
    """Row shorthand: "Q" = 1u key, ("Tab", 1.5) = sized key, a dict (e.g. _blocker()) is used as-is."""
    key = lambda k: {"label": k, "w": 1.0} if isinstance(k, str) else k if isinstance(k, dict) else {"label": k[0], "w": k[1]}
    return {"offset": offset, "keys": [key(k) for k in keys]}


DEFAULT = {
    "size": "40", "curve": 2.0, "outer": 0.0, "gap": 0.5, "match_center": True,
    "left": [
        _row(0.5, ("Tab", 1.5), *"QWERT"),
        _row(0.25, ("Ctrl", 1.75), *"ASDFG"),
        _row(0, ("Shift", 2.25), *"ZXCVB"),
        _row(0, ("Alt", 1.5), ("Code", 1.25), ("", 2.25)),
    ],
    "right": [
        _row(0.5, *"YUIOP", ("Bksp", 1.5)),
        _row(0.25, *"HJKL;", ("Enter", 1.75)),
        _row(0, "Raise", *"NM,./", ("Fn", 1.25)),
        _row(0, ("", 2.25), ("Lower", 1.25), ("Code", 1.25), ("Alt", 1.25)),
    ],
}

def _blocker(w=1.0):
    return {"label": "", "w": w, "blocker": True}


def _mod(on, labels, dx=None, count=None):
    """Mod column shorthand (rule 15)."""
    return {"on": on, "offset": 0.0, "gap": 0.5, "count": count or len(labels),
            "keys": [{"label": l, "w": 1.0, "dx": (dx or [0.0] * len(labels))[i]} for i, l in enumerate(labels)]}


DEFAULT["mod"] = {h: _mod(False, ["M1", "M2", "M3", "M4"]) for h in ("left", "right")}

# 60/65%: the Qwertykeys Neo Ergo (65%, 68 keys), from its VIA layout: outer keys flat, alphas on a 10°
# straight bend, a 4-key macro column on the left that steps with the row stagger, WKL-style bottom
# row with arrows lined up under the up arrow.
DEFAULT_60 = {
    "size": "60", "bend": "straight", "line_angle": 10.0, "curve": 2.0, "straight_run": 0.75,
    "outer": 0.0, "gap": 0.75, "match_center": True,
    "left": [
        _row(0.75, "Esc", *"123456"),
        _row(0.5, ("Tab", 1.5), *"QWERT"),
        _row(0.25, ("Ctrl", 2), *"ASDFG"),
        _row(0, ("Shift", 2.5), *"ZXCVB"),
        dict(_row(-0.25, ("Ctrl", 1.5), ("Win", 1.25), ("Alt", 1.5), ("", 2.25)), align="outer"),
    ],
    "right": [
        _row(0.5, *"7890-=", ("Bksp", 2)),
        _row(0.25, *"YUIOP[]", ("\\", 1.5)),
        _row(0.25, *"HJKL;'", ("Enter", 2.25)),
        _row(0, *"BNM,./", "↑", ("Shift", 1.75)),
        dict(_row(0.75, ("", 2.25), ("Alt", 1.5), "←", "↓", "→"), align="outer"),
    ],
    "mod": {"left": _mod(True, ["Home", "PgUp", "PgDn", "End", "M5"], dx=[0.75, 0.5, 0.25, 0.0, 0.0], count=4),
            "right": _mod(False, ["M1", "M2", "M3", "M4", "M5"], count=4)},
}
DEFAULTS = {"40": DEFAULT, "60": DEFAULT_60}


def mod_column(lay, h):
    """Rule 15: half h's mod column settings, filled in with defaults for older files. One key slot per row;
    `count` of them are used, from the top. Every key has its own label, width and left/right nudge (dx)."""
    cfg = lay.setdefault("mod", {}).setdefault(h, {"on": False, "offset": 0.0, "gap": 0.5})
    n = len(lay[h])
    cfg["keys"] = (cfg.get("keys", []) + [{"label": f"M{i + 1}"} for i in range(n)])[:n]
    old_w = cfg.pop("w", 1.0)  # files from when the column had one key size
    for k in cfg["keys"]:
        k.setdefault("w", old_w)
    cfg["count"] = int(min(max(cfg.get("count", n), 1), n))
    return cfg


def layout_size(lay):
    """Rule 12: which size tab a layout belongs to ("40" or "60"). Uses its "size", or for older files
    its row count. Raises ValueError if the halves don't have the right number of rows."""
    counts = {len(lay["left"]), len(lay["right"])}
    size = lay.get("size") or next((k for k, n in SIZES.items() if counts == {n}), None)
    if size not in SIZES or counts != {SIZES[size]}:
        raise ValueError(f"expected both halves to have 4 rows (40%) or 5 rows (60/65%), got {sorted(counts)}")
    return size


def corners(cx, cy, w, h, ang):
    """Corners of a w x h rectangle centered at (cx, cy), rotated `ang` degrees clockwise (y points down)."""
    a = math.radians(ang)
    c, s = math.cos(a), math.sin(a)
    return [(cx + dx * c - dy * s, cy + dx * s + dy * c)
            for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]


def walk(rows, r, mirror):
    """Row r's keys as (idx, key), outer -> inner."""
    return list(enumerate(rows[r]["keys"]))[::-1 if mirror else 1]


def curve_start(rows, mirror):
    """Rule 7: where the rows stop being straight: the inner edge of the longest outer key
    (Tab/Ctrl/Shift), spacers in front of it included (rule 6)."""
    def lead(r):
        keys = walk(rows, r, mirror)
        n = next((n for n, (_, k) in enumerate(keys) if not k.get("spacer")), 0)
        return (0 if r == anchor(rows) else rows[r]["offset"]) + sum(k["w"] for _, k in keys[:n + 1])
    return max(lead(r) for r in range(anchor(rows) + 1))


def center_key(rows, mirror):
    """Rule 8: (idx, inner-edge position in u) of the anchor row's innermost real key: B on the left, N on the right."""
    keys = walk(rows, anchor(rows), mirror)
    n = max((n for n, (_, k) in enumerate(keys) if not k.get("spacer")), default=len(keys) - 1)
    return keys[n][0], sum(k["w"] for _, k in keys[:n + 1])


def place_half(rows, curve, outer, mirror, extra=None, delay=0.0, mod=None, bend="curve", slide=None):
    """Lay out one half in u. Returns [(row, idx, key, x, y, ang)] with x pointing toward the center
    (flipped for the right half) and y pointing down.

    Every row is straight up to x0 (rule 7), then bends around one shared center (rule 5). Each key's bottom
    edge is a chord of its row's track whose ends are exactly w apart, so neighbours share bottom corners
    (rule 3) and rows can't drift into each other. Keys inside the straight part come out at exactly
    `outer` degrees (rule 6).
    extra[r] = added space (u) between row r and r+1; place() raises it only where keys would collide.
    delay = how much later (u) this half starts curving; place() uses it to match the center keys.
    mod = this half's mod column settings when it's switched on (rule 15); its keys come back with idx -1.
    bend = "curve" (`curve` is degrees per 1u key) or "straight" (rule 16: `curve` is the angle of the whole line).
    slide = {row: u} to slide a row's angled keys inward along their line (straight bend only, set by place())."""
    A, B = anchor(rows), len(rows) - 1                   # anchor (R2) and bottom row indices
    extra = extra or [0.0] * B
    straight = bend == "straight"                         # rule 16
    R = 180 / (math.pi * curve) if curve and not straight else math.inf  # bottom-edge radius of the anchor row
    theta = math.radians(curve) if straight else 0.0
    ux, uy, tt = math.cos(theta), math.sin(theta), math.tan(theta / 2)
    cy0 = A + 1 + R                                       # curve center y (x = x0)
    # straight-part bottom edges: the anchor's is fixed, rows above move up / the bottom row down by `extra`
    ybot = [r + 1 - sum(extra[r:A]) for r in range(A)] + [A + 1.0, A + 2 + extra[A]]
    x0 = curve_start(rows, mirror) + delay
    # rule 16: in straight mode every row turns once; the turns are mitered so the rows stay 1u apart
    kink = lambda r: x0 + (ybot[A] - ybot[r]) * tt

    def track(s, r):  # point on row r's bottom edge, s u along it from the outer end
        if straight and curve:
            k = kink(r)
            return (s, ybot[r]) if s <= k else (k + (s - k) * ux, ybot[r] + (s - k) * uy)
        if s <= x0 or not curve:
            return s, ybot[r]
        rho = cy0 - ybot[r]
        phi = (s - x0) / rho
        return x0 + rho * math.sin(phi), cy0 - rho * math.cos(phi)

    def step(s, r, w, sign):  # track position exactly w (straight-line) away from track(s), in direction sign
        if not curve or straight or (s + w <= x0 if sign > 0 else s <= x0):
            return s + sign * w
        p, lo, hi = track(s, r), w, w * 1.5  # the track between chord ends is at least w long
        for _ in range(40):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if math.dist(track(s + sign * mid, r), p) < w else (lo, mid)
        return s + sign * hi

    t = math.radians(outer)
    out = []
    anchor_end = 0.0
    edges = {}  # row -> outermost x of its real main keys (rule 15 measures the mod column's distance from it)
    for r in range(len(rows)):
        keys, spans = walk(rows, r, mirror), []
        if r == B and rows[r].get("align") != "outer":  # rule 4: walk inner -> outer from the anchor's inner edge
            L = anchor_end - x0  # how far the anchor runs into the bend
            if curve and L > 0:  # the same radial (curve) or perpendicular (straight) line on the bottom row
                inner = x0 + L + 2 * (ybot[A] - ybot[B]) * tt if straight else x0 + L * (cy0 - ybot[B]) / (cy0 - ybot[A])
            else:
                inner = anchor_end
            s = inner + rows[r]["offset"]
            for idx, key in reversed(keys):
                s2 = step(s, r, key["w"], -1)
                spans.append((idx, key, s2, s))
                s = s2
            spans.reverse()
        else:  # rule 4: stagger from the R2 outer edge (the bottom row too, if set to align "outer")
            s = 0.0 if r == A else rows[r]["offset"]
            for idx, key in keys:
                s2 = step(s, r, key["w"], 1)
                spans.append((idx, key, s, s2))
                s = s2
            if r == A:
                anchor_end = s
        real = [a for _, k, a, _ in spans if not k.get("spacer")]
        if real:
            edges[r] = track(real[0], r)[0]
        for idx, key, a, b in spans:
            if straight and curve:  # rule 16: a key is wholly flat or wholly on the angled line, never between
                k = kink(r)
                d = a - k + (slide or {}).get(r, 0.0)  # distance along the angled line
                (ax, ay), ang = ((a, ybot[r]), 0.0) if (a + b) / 2 <= k else ((k + d * ux, ybot[r] + d * uy), theta)
            else:
                (ax, ay), (bx, by) = track(a, r), track(b, r)
                ang = math.atan2(by - ay, bx - ax)
            w, ca, sa = key["w"], math.cos(ang), math.sin(ang)
            cx, cy = ax + w / 2 * ca + 0.5 * sa, ay + w / 2 * sa - 0.5 * ca
            cx, cy = cx * math.cos(t) - cy * math.sin(t), cx * math.sin(t) + cy * math.cos(t)
            deg = math.degrees(ang) + outer
            out.append((r, idx, key, -cx if mirror else cx, cy, -deg if mirror else deg))
    if mod:  # rule 15: one key per row from the top, `gap` u outside those rows' main keys, each nudged by dx
        count = int(mod["count"])
        inner = min((edges[r] for r in range(count) if r in edges), default=0.0) - mod["gap"]  # column's inner line
        for r, key in enumerate(mod["keys"][:count]):
            cx, cy = inner - key["w"] / 2 + key.get("dx", 0.0), ybot[r] - 0.5 + mod["offset"]
            cx, cy = cx * math.cos(t) - cy * math.sin(t), cx * math.sin(t) + cy * math.cos(t)
            out.append((r, -1, key, -cx if mirror else cx, cy, -outer if mirror else outer))
    return out


def overlap(a, b):
    """How far two convex quads overlap, in their units (<= 0 means they don't touch). Separating-axis test."""
    depth = math.inf
    for q in (a, b):
        for (x1, y1), (x2, y2) in ((q[0], q[1]), (q[0], q[3])):
            n = math.hypot(x2 - x1, y2 - y1)
            ax, ay = (x2 - x1) / n, (y2 - y1) / n
            pa, pb = [x * ax + y * ay for x, y in a], [x * ax + y * ay for x, y in b]
            depth = min(depth, min(max(pa), max(pb)) - max(min(pa), min(pb)))
    return depth


def place(lay):
    """Full layout in mm, origin at the top-left of the key footprints. Spacers are placed but excluded
    from the extents, the collision check and the exports."""
    n = SIZES[layout_size(lay)]
    for h in ("left", "right"):  # rule 14
        if any(k.get("blocker") for row in lay[h][:-1] for k in row["keys"]):
            raise ValueError("WK blockers are only allowed in the bottom row")
    mods = {h: mod_column(lay, h) for h in ("left", "right")}  # rule 15
    mods = {h: (m if m.get("on") else None) for h, m in mods.items()}
    quad = lambda o: corners(o[3], o[4], o[2]["w"], 1, o[5])
    extra = [0.0] * (n - 1)  # rule 10: shared by both halves so the modifier rows stay level (rule 9)
    bend = lay.get("bend", "curve")  # rule 16
    amount = lay.get("line_angle", 10.0) if bend == "straight" else lay["curve"]
    match = lay.get("match_center", True) and amount
    delay = {"left": 0.0, "right": 0.0}
    if match:  # rule 8: same degrees per key both sides, so give both R2 rows the same curved length up to B/N:
        # the half with the longer modifiers starts curving later, and B and N end at the same angle
        run = {h: center_key(lay[h], h == "right")[1] - curve_start(lay[h], h == "right") for h in delay}
        longer = max(run, key=run.get)
        delay[longer] = run[longer] - min(run.values())
    for h in delay:  # rule 7: optional extra straight run before the bend, the same on both halves
        delay[h] += lay.get("straight_run", 0.0)
    slides = {h: None for h in delay}
    if bend == "straight" and amount:  # rule 16: clear the turn by sliding angled keys, not by spreading rows
        slides = {h: turn_slides(place_half(lay[h], amount, lay["outer"], h == "right", None, delay[h], mods[h], bend),
                                 h == "right", amount, lay["outer"]) for h in delay}
    for _ in range(20):  # rule 10: widen only the row gaps where 1u footprints would collide
        halves = {h: place_half(lay[h], amount, lay["outer"], h == "right", extra, delay[h], mods[h], bend, slides[h])
                  for h in delay}
        moved = False
        for r in range(n - 1):
            d = max((overlap(a, b) for ks in halves.values()
                     for a in [quad(o) for o in ks if o[0] == r and not o[2].get("spacer")]
                     for b in [quad(o) for o in ks if o[0] == r + 1 and not o[2].get("spacer")]), default=-1)
            if d > -1e-5:  # keep a hair (~0.0002 mm) of clearance
                extra[r] += d + 2e-5
                moved = True
        if not moved:
            break
    xs = {h: [p[0] for (_, _, k, x, y, a) in ks if not k.get("spacer") for p in corners(x, y, k["w"], 1, a)]
          for h, ks in halves.items()}
    dx = max(xs["left"], default=0) + max(lay["gap"], 0) - min(xs["right"], default=0)  # rule 10: gap >= 0
    # rule 9: level the halves
    def outer_idx(h):  # outermost real key of the top row (spacers skipped)
        keys = lay[h][TOP]["keys"]
        order = list(range(len(keys)))[::1 if h == "left" else -1]
        return next((i for i in order if not keys[i].get("spacer")), order[0])
    if match:  # B and N centers at the same height
        ref = {h: next(y for (r, i, k, x, y, a) in ks if r == n - 2 and i == center_key(lay[h], h == "right")[0])
               for h, ks in halves.items()}
    else:      # highest points of the top row's outer keys (Tab / Bksp on 40%) at the same height
        ref = {h: min(p[1] for (r, i, k, x, y, a) in ks if r == TOP and i == outer_idx(h)
                      for p in corners(x, y, k["w"], 1, a)) for h, ks in halves.items()}
    dy = ref["left"] - ref["right"]
    out = [{"half": h, "row": r, "rname": "Mod column" if i < 0 else row_name(r, n), "idx": i, "mod": i < 0, "key": k,
            "x": (x + (dx if h == "right" else 0)) * U,
            "y": (y + (dy if h == "right" else 0)) * U, "ang": a}
           for h, ks in halves.items() for r, i, k, x, y, a in ks]
    pts = [p for o in solid(out) for p in footprint(o)]
    x0, y0 = min((p[0] for p in pts), default=0), min((p[1] for p in pts), default=0)
    for o in out:
        o["x"] -= x0
        o["y"] -= y0
    return out


def turn_slides(ks, mirror, angle, outer):
    """Rule 16: where a row turns, a key partly before the turn tips up into the row above (or a flat key
    runs under the angled row above). For each row whose angled keys hit a flat key, find the smallest
    slide inward along its line (u) that clears it. Rows stay exactly 1u apart; each stays straight."""
    a = math.radians(outer + angle)
    ux, uy = (-math.cos(a) if mirror else math.cos(a)), math.sin(a)
    quad = lambda o: corners(o[3], o[4], o[2]["w"], 1, o[5])
    real = [o for o in ks if not o[2].get("spacer")]
    flat = [(o[0], quad(o)) for o in real if abs(abs(o[5]) - abs(outer)) < 1e-9]
    out = {}
    for r in {o[0] for o in real}:
        mine = [quad(o) for o in real if o[0] == r and o[1] >= 0 and abs(abs(o[5]) - abs(outer)) > 1e-9]
        near = [q for rr, q in flat if abs(rr - r) <= 1]
        hit = lambda d: any(overlap([(x + d * ux, y + d * uy) for x, y in q], f) > -1e-5 for q in mine for f in near)
        if not mine or not hit(0.0):
            continue
        lo, hi = 0.0, 0.25
        while hit(hi) and hi < 8:
            lo, hi = hi, hi * 2
        for _ in range(30):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if hit(mid) else (lo, mid)
        out[r] = hi
    return out


def collisions(placed):
    """Rule 10: [(label_a, label_b, overlap_mm)] for every pair of real keys whose 19.05 mm footprints overlap."""
    ks = solid(placed)
    name = lambda o: ("WK blocker" if o["key"].get("blocker") else o["key"]["label"]) or \
        (f'{o["half"]} mod key {o["row"] + 1}' if o["mod"] else f'{o["half"]} {o["rname"].lower()} key {o["idx"] + 1}')
    return [(name(a), name(b), d) for i, a in enumerate(ks) for b in ks[i + 1:]
            if (d := overlap(footprint(a), footprint(b))) > 1e-3]


def solid(placed):
    """Everything physical: keys and WK blockers (not spacers)."""
    return [o for o in placed if not o["key"].get("spacer")]


def keycaps(placed):
    """Real keys only: no spacers, no WK blockers (rule 14)."""
    return [o for o in solid(placed) if not o["key"].get("blocker")]


def footprint(o, w=None, h=U):
    return corners(o["x"], o["y"], o["key"]["w"] * U if w is None else w, h, o["ang"])


def hull(pts):
    """Convex hull of 2D points (monotone chain)."""
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for side, seq in ((lower, pts), (upper, reversed(pts))):
        for p in seq:
            while len(side) >= 2 and cross(side[-2], side[-1], p) <= 0:
                side.pop()
            side.append(p)
    return lower[:-1] + upper[:-1]


def inside_polygon(pt, poly):
    """Point in (possibly concave) polygon, by ray casting."""
    x, y = pt
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def _meet(p1, p2, q1, q2):
    """Where line p1-p2 crosses line q1-q2 (None if parallel)."""
    d = (p2[0] - p1[0]) * (q2[1] - q1[1]) - (p2[1] - p1[1]) * (q2[0] - q1[0])
    if abs(d) < 1e-9:
        return None
    t = ((q1[0] - p1[0]) * (q2[1] - q1[1]) - (q1[1] - p1[1]) * (q2[0] - q1[0])) / d
    return p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1])


def frame(placed, margin):
    """Rule 13: the sample case outline (mm), like an Alice case, with every edge exactly `margin` from its
    nearest key: one straight top edge across both halves, each outer end square to that side's outer
    keys, and one bottom edge per half angled to hug its bottom keys; the two bottom edges meet in the
    middle. Returned as a list holding one polygon (falls back to a plain hull if a layout can't take it)."""
    ks = solid(placed)
    pts = {h: [p for o in ks if o["half"] == h for p in footprint(o)] for h in ("left", "right")}
    top = ((0.0, min(p[1] for q in pts.values() for p in q) - margin), (1.0, min(p[1] for q in pts.values() for p in q) - margin))
    x_mid = (max(p[0] for p in pts["left"]) + min(p[0] for p in pts["right"])) / 2
    ends, bottoms = {}, {}
    for h, side in (("left", -1), ("right", 1)):
        # outer end: along the outermost key's height axis (rule 6), `margin` past the half's keys
        a = math.radians(max(((p, o) for o in ks if o["half"] == h for p in footprint(o)), key=lambda po: side * po[0][0])[1]["ang"])
        c, s_ = math.cos(a), math.sin(a)
        reach = max(side * (x * c + y * s_) for x, y in pts[h]) + margin
        e1 = (side * reach * c, side * reach * s_)
        ends[h] = (e1, (e1[0] - s_, e1[1] + c))
        x_end = side * reach * c
        # bottom edge: try each hull edge's direction (and level), keep the one that hugs the keys best
        hp = hull(pts[h])
        angles = {0.0} | {(math.atan2(y2 - y1, x2 - x1) + math.pi / 4) % (math.pi / 2) - math.pi / 4
                          for (x1, y1), (x2, y2) in zip(hp, hp[1:] + hp[:1])}
        best = None
        for phi in angles:
            nx, ny = -math.sin(phi), math.cos(phi)  # downward normal (y points down)
            off = max(x * nx + y * ny for x, y in pts[h]) + margin
            y_at = lambda x: (off - x * nx) / ny
            area = abs(x_mid - x_end) * ((y_at(x_end) + y_at(x_mid)) / 2 - top[0][1])
            if best is None or area < best[0] - 1e-9:
                best = (area, (x_end, y_at(x_end)), (x_mid, y_at(x_mid)))
        bottoms[h] = best[1:]
    lt, rt = _meet(*ends["left"], *top), _meet(*ends["right"], *top)
    lb, rb = _meet(*ends["left"], *bottoms["left"]), _meet(*ends["right"], *bottoms["right"])
    v = _meet(*bottoms["left"], *bottoms["right"])
    candidates = []
    if v and lb and rb and lb[0] < v[0] < rb[0]:
        candidates.append([lt, rt, rb, v, lb])                                        # straight top, V bottom
    candidates.append([lt, rt, rb, bottoms["right"][1], bottoms["left"][1], lb])      # small step in the middle
    corners_ = [p for q in pts.values() for p in q]
    for poly in candidates:  # every key inside, at least `margin` from every edge
        if all(p is not None for p in poly) and all(
                (inside_polygon(c, poly) or edge_distance(c, poly) < 1e-6) and edge_distance(c, poly) >= margin * 0.999 - 1e-6
                for c in corners_):
            return [poly]
    return [hull([p for o in ks for p in footprint(o, o["key"]["w"] * U + 2 * margin, U + 2 * margin)])]


def edge_distance(pt, poly):
    """Shortest distance from pt to the polygon's outline."""
    best = math.inf
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        dx, dy = x2 - x1, y2 - y1
        t = max(0.0, min(1.0, ((pt[0] - x1) * dx + (pt[1] - y1) * dy) / (dx * dx + dy * dy or 1)))
        best = min(best, math.hypot(pt[0] - x1 - t * dx, pt[1] - y1 - t * dy))
    return best


def to_dxf(placed):
    """Rule 11: R12 DXF (mm, y up): 1u footprints on KEYCAP_1U, 14 mm switch cutouts on SWITCH_14MM,
    WK blocker outlines on WK_BLOCKER (rule 14)."""
    out = ["0", "SECTION", "2", "ENTITIES"]
    for o in solid(placed):
        shapes = ((("WK_BLOCKER", footprint(o)),) if o["key"].get("blocker") else
                  (("KEYCAP_1U", footprint(o)), ("SWITCH_14MM", footprint(o, SWITCH, SWITCH))))
        for layer, c in shapes:
            for (x1, y1), (x2, y2) in zip(c, c[1:] + c[:1]):
                out += ["0", "LINE", "8", layer, "10", f"{x1:.4f}", "20", f"{-y1:.4f}", "11", f"{x2:.4f}", "21", f"{-y2:.4f}"]
    return "\n".join(out + ["0", "ENDSEC", "0", "EOF"]) + "\n"


def to_kle(placed):
    """Rule 11: keyboard-layout-editor.com JSON. Every key is its own row so it can carry its own rotation
    (KLE only allows r/rx/ry on a row's first key; the KLE site resets x/y to rx/ry when they're set)."""
    return [[{"r": round(o["ang"], 4), "rx": round(o["x"] / U, 4), "ry": round(o["y"] / U, 4),
              "x": -o["key"]["w"] / 2, "y": -0.5, "w": o["key"]["w"], **({"d": True} if o["key"].get("blocker") else {})},
             o["key"]["label"]] for o in solid(placed)]


BG, CASE, EDGE, KEY, KEY_EDGE, TEXT, MUTED, SELECT = (
    "#1e2227", "#15171b", "#5c6370", "#2c313a", "#9aa3ad", "#d7dae0", "#8b929c", "#e5c07b")


class App:
    """The window: size switch + file actions on top, the drawing with a status line, controls on the right."""

    def __init__(self, root):
        self.root = root
        self.size = "40"                                                     # rule 12: one layout per size
        self.layouts = {k: json.loads(json.dumps(v)) for k, v in DEFAULTS.items()}
        self.sels = {k: ("left", 0, 0) for k in DEFAULTS}
        self.lay, self.sel = self.layouts[self.size], self.sels[self.size]
        self.loading = False
        self.bound = []  # (StringVar, getter) pairs refreshed by sync()
        root.minsize(1100, 620)

        top = ttk.Frame(root, padding=(12, 8))
        top.pack(side="top", fill="x")
        ttk.Label(top, text="Size").pack(side="left", padx=(0, 6))
        self.size_var = tk.StringVar(value=self.size)
        for k in DEFAULTS:
            ttk.Radiobutton(top, text=SIZE_NAMES[k], value=k, variable=self.size_var, style="Toolbutton",
                            command=self.switch_size).pack(side="left")
        for text, cmd in (("Export KLE…", lambda: self.export("json")), ("Export DXF…", lambda: self.export("dxf")),
                          ("Save…", self.save), ("Open…", self.load)):
            ttk.Button(top, text=text, command=cmd).pack(side="right", padx=2)

        body = ttk.Frame(root)
        body.pack(fill="both", expand=True)
        panel = ttk.Frame(body, padding=(4, 0, 12, 12))
        panel.pack(side="right", fill="y")
        view = self.view = tk.Frame(body, bg=BG)
        view.pack(side="left", fill="both", expand=True)
        self.cv = tk.Canvas(view, bg=BG, highlightthickness=0, width=880, height=470)
        self.cv.pack(fill="both", expand=True)
        self.cv.bind("<Configure>", lambda e: self.draw())
        self.cv.bind("<Button-1>", self.click)
        self.status = tk.Label(view, bg=BG, fg=MUTED, anchor="w", padx=12, pady=6)
        self.status.pack(fill="x")

        shape = self.box(panel, "Shape")
        bend = ttk.Frame(shape)
        bend.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 2))
        ttk.Label(bend, text="Bend").pack(side="left", padx=(0, 8))
        self.bend_var = tk.StringVar()
        for text, value in (("Curve", "curve"), ("Straight", "straight")):  # rules 5, 16
            ttk.Radiobutton(bend, text=text, value=value, variable=self.bend_var,
                            command=lambda: (self.lay.update(bend=self.bend_var.get()), self.sync())).pack(side="left", padx=(0, 8))
        self.curve_row = self.field(shape, 1, "Curve (° per key)", 0, 5, 0.05, lambda: self.lay["curve"],  # rule 5
                                    lambda v: self.lay.update(curve=v))
        self.angle_row = self.field(shape, 1, "Line angle (°)", 0, 45, 0.05, lambda: self.lay.get("line_angle", 10.0),  # rule 16
                                    lambda v: self.lay.update(line_angle=v))
        self.field(shape, 2, "Straight before bend (u)", 0, 6, 0.125, lambda: self.lay.get("straight_run", 0.0),  # rule 7
                   lambda v: self.lay.update(straight_run=v))
        self.field(shape, 3, "Outer key angle (°)", -10, 20, 0.5, lambda: self.lay["outer"],  # rule 6
                   lambda v: self.lay.update(outer=v))
        self.field(shape, 4, "Gap between halves (u)", 0, 5, 0.125, lambda: self.lay["gap"],  # rule 10
                   lambda v: self.lay.update(gap=v))
        self.match_var = tk.BooleanVar()
        ttk.Checkbutton(shape, text="Match center keys (B / N)", variable=self.match_var,  # rule 8
                        command=lambda: self.set_flag("match_center", self.match_var)).grid(row=5, column=0, columnspan=2, sticky="w")
        self.frame_var = tk.BooleanVar()
        ttk.Checkbutton(shape, text="Show case outline, margin (mm)", variable=self.frame_var,  # rule 13
                        command=lambda: self.set_flag("frame", self.frame_var)).grid(row=6, column=0, sticky="w")
        self.spinbox(shape, 0, 40, 0.5, lambda: self.lay.get("frame_margin", 8.0),
                     lambda v: self.lay.update(frame_margin=v)).grid(row=6, column=1, sticky="e", pady=1)

        stagger = self.box(panel, "Stagger (u, + toward center)")  # rule 4
        ttk.Label(stagger, text="Left", foreground=MUTED).grid(row=0, column=1)
        ttk.Label(stagger, text="Right", foreground=MUTED).grid(row=0, column=2)
        self.number_row = []
        for i, k in enumerate((5, 4, 3, 1), start=1):  # rows counted from the bottom: Number, Top, Home, Bottom
            cells = [ttk.Label(stagger, text=ROLE_NAMES[k - 1])]
            cells[0].grid(row=i, column=0, sticky="w")
            for c, half in enumerate(("left", "right"), start=1):
                cells.append(self.spinbox(stagger, -4, 4, 0.125, lambda h=half, k=k: self.role(h, k).get("offset", 0),
                                          lambda v, h=half, k=k: self.role(h, k).update(offset=v)))
                cells[-1].grid(row=i, column=c, padx=(6, 0), pady=1)
            if k == 5:
                self.number_row = cells  # only shown for 60/65%
        ttk.Label(stagger, text="Bottom from outer edge").grid(row=5, column=0, sticky="w")  # rule 4
        self.align_vars = {}
        for c, half in enumerate(("left", "right"), start=1):
            self.align_vars[half] = tk.BooleanVar()
            ttk.Checkbutton(stagger, variable=self.align_vars[half], command=lambda h=half: self.set_align(h)).grid(row=5, column=c)

        self.mod_box = self.box(panel, "Mod column")  # rule 15
        ttk.Label(self.mod_box, text="Left", foreground=MUTED).grid(row=0, column=1)
        ttk.Label(self.mod_box, text="Right", foreground=MUTED).grid(row=0, column=2)
        ttk.Label(self.mod_box, text="Show").grid(row=1, column=0, sticky="w")
        self.mod_vars = {}
        for c, half in enumerate(("left", "right"), start=1):
            self.mod_vars[half] = tk.BooleanVar()
            ttk.Checkbutton(self.mod_box, variable=self.mod_vars[half],
                            command=lambda h=half: self.set_mod(h, "on", self.mod_vars[h].get())).grid(row=1, column=c)
        for i, (text, name, lo, hi, step) in enumerate((("Keys (from top)", "count", 1, 5, 1),
                                                        ("Offset (u, + down)", "offset", -4, 4, 0.125),
                                                        ("Distance (u)", "gap", 0, 4, 0.125)), start=2):
            ttk.Label(self.mod_box, text=text).grid(row=i, column=0, sticky="w")
            for c, half in enumerate(("left", "right"), start=1):
                self.spinbox(self.mod_box, lo, hi, step, lambda h=half, n=name: self.mod(h)[n],
                             lambda v, h=half, n=name: self.set_mod(h, n, v, redraw=False)).grid(row=i, column=c, padx=(6, 0), pady=1)
        ttk.Label(self.mod_box, text="Click a mod key to edit it", foreground=MUTED).grid(
            row=5, column=0, columnspan=3, sticky="w", pady=(2, 0))

        # the selected key's controls live in a bar under the drawing, next to the keys they edit
        key = ttk.Frame(self.view, padding=(12, 6, 12, 8))
        key.pack(fill="x", before=self.status)
        self.sel_info = ttk.Label(key, foreground=MUTED, justify="left", width=30)
        self.sel_info.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 12))
        ttk.Label(key, text="Label").grid(row=0, column=1, sticky="e")
        self.label_var = tk.StringVar()
        self.label_var.trace_add("write", self.label_changed)
        entry = ttk.Entry(key, textvariable=self.label_var, width=9)
        entry.grid(row=0, column=2, sticky="w", padx=(4, 12))
        entry.bind("<Return>", lambda ev: self.cv.focus_set())
        ttk.Label(key, text="Width (u)").grid(row=0, column=3, sticky="e")
        self.spinbox(key, 0.25, 10, 0.25, lambda: self.cur()["w"], self.set_width).grid(row=0, column=4, sticky="w", padx=(4, 12))  # rules 2, 15
        types = ttk.Frame(key)
        types.grid(row=0, column=5, sticky="w")
        self.type_var = tk.StringVar()
        for text, value in (("Key", "key"), ("Spacer", "spacer"), ("WK blocker", "blocker")):
            b = ttk.Radiobutton(types, text=text, value=value, variable=self.type_var, command=self.type_changed)
            b.pack(side="left", padx=(0, 8))
        self.blocker_only = [b]  # rule 14: bottom row only
        self.row_only = []       # Add / Delete: not for mod keys (rule 15: one per row)
        buttons = self.buttons = ttk.Frame(key)
        buttons.grid(row=1, column=1, columnspan=5, sticky="w", pady=(6, 0))
        dx = self.dx_row = ttk.Frame(key)  # rule 15: a mod key's own left/right offset
        dx.grid(row=1, column=1, columnspan=5, sticky="w", pady=(6, 0))
        ttk.Label(dx, text="Left / right offset (u, + toward the keys)").pack(side="left", padx=(0, 6))
        self.spinbox(dx, -4, 4, 0.125, lambda: self.cur().get("dx", 0.0), lambda v: self.cur().update(dx=v)).pack(side="left")
        for text, cmd, group in (("◀ Add key", lambda: self.insert(0), self.row_only),
                                 ("Add key ▶", lambda: self.insert(1), self.row_only),
                                 ("Delete", self.delete, self.row_only),
                                 ("◀ Add blocker", lambda: self.insert(0, "blocker"), self.blocker_only),
                                 ("Add blocker ▶", lambda: self.insert(1, "blocker"), self.blocker_only)):
            b = ttk.Button(buttons, text=text, command=cmd)
            b.pack(side="left", padx=(0, 4) if text != "Delete" else (0, 16))
            group.append(b)
        self.switch_size()

    def box(self, parent, title):
        f = ttk.LabelFrame(parent, text=title, padding=(10, 4, 10, 8))
        f.pack(fill="x", pady=(0, 8))
        f.columnconfigure(0, weight=1)
        return f

    def field(self, parent, row, text, lo, hi, step, get, put):
        label, box = ttk.Label(parent, text=text), self.spinbox(parent, lo, hi, step, get, put)
        label.grid(row=row, column=0, sticky="w")
        box.grid(row=row, column=1, sticky="e", pady=1)
        return label, box

    def spinbox(self, parent, lo, hi, step, get, put):
        v = tk.StringVar()
        box = ttk.Spinbox(parent, from_=lo, to=hi, increment=step, textvariable=v, width=7, format="%.3f")

        def changed(*_):
            if self.loading:
                return
            try:
                x = float(v.get())
            except ValueError:
                return  # half-typed value
            put(round(min(max(round(x / step) * step, lo), hi), 4))  # snap to the step grid
            self.draw()
        v.trace_add("write", changed)
        self.bound.append((v, get))
        return box

    def mod(self, h):
        return mod_column(self.lay, h)

    def set_mod(self, h, name, value, redraw=True):
        self.mod(h)[name] = value
        if redraw:
            self.draw()

    def set_width(self, v):
        self.cur()["w"] = v  # mod keys have their own width too (rule 15)

    def set_align(self, h):
        self.lay[h][-1]["align"] = "outer" if self.align_vars[h].get() else "inner"  # rule 4
        self.draw()

    def set_flag(self, name, var):
        self.lay[name] = var.get()
        self.draw()

    def role(self, h, k):
        """The row k-th from the bottom of half h (1 = Bottom ... 5 = Number), or {} if this size has none."""
        rows = self.lay[h]
        return rows[-k] if len(rows) >= k else {}

    def switch_size(self):
        """Rule 12: swap in the other size's layout (each keeps its own) and show only its rows."""
        new = self.size_var.get()
        if new != self.size:
            self.sels[self.size] = self.sel
            self.size, self.lay, self.sel = new, self.layouts[new], self.sels[new]
        big = len(self.lay["left"]) >= 5
        for w in self.number_row:
            w.grid() if big else w.grid_remove()
        self.root.title(f"Alice {SIZE_NAMES[self.size]} Layout Designer")
        self.sync()

    def cur(self):
        h, r, i = self.sel
        return self.mod(h)["keys"][r] if i < 0 else self.lay[h][r]["keys"][i]

    def in_bottom_row(self):
        h, r, i = self.sel
        return i >= 0 and r == len(self.lay[h]) - 1

    def sync(self):
        """Push layout values into the controls without triggering writes back."""
        self.loading = True
        for v, get in self.bound:
            v.set(f"{get():g}")
        k = self.cur()
        self.label_var.set(k["label"])
        self.type_var.set("blocker" if k.get("blocker") else "spacer" if k.get("spacer") else "key")
        for w in self.blocker_only:  # rule 14
            w.state(["!disabled"] if self.in_bottom_row() else ["disabled"])
        for w in self.row_only:  # rule 15: mod keys are one per row, no add/delete
            w.state(["disabled"] if self.sel[2] < 0 else ["!disabled"])
        for h, v in self.mod_vars.items():
            v.set(bool(self.mod(h).get("on")))
        for h, v in self.align_vars.items():
            v.set(self.lay[h][-1].get("align") == "outer")
        straight = self.lay.get("bend", "curve") == "straight"  # rule 16: show the matching angle field
        self.bend_var.set("straight" if straight else "curve")
        for w in self.curve_row:
            w.grid_remove() if straight else w.grid()
        for w in self.angle_row:
            w.grid() if straight else w.grid_remove()
        mod_key = self.sel[2] < 0
        (self.buttons.grid_remove if mod_key else self.buttons.grid)()
        (self.dx_row.grid if mod_key else self.dx_row.grid_remove)()
        self.match_var.set(bool(self.lay.get("match_center", True)))
        self.frame_var.set(bool(self.lay.get("frame", False)))
        self.loading = False
        self.draw()

    def label_changed(self, *_):
        if not self.loading:
            self.cur()["label"] = self.label_var.get()
            self.draw()

    def type_changed(self):
        k, t = self.cur(), self.type_var.get()
        if t == "blocker" and not self.in_bottom_row():  # rule 14
            return self.sync()
        k.pop("spacer", None)
        k.pop("blocker", None)
        if t != "key":
            k[t] = True
        self.sync()

    def insert(self, after, kind="key"):
        h, r, i = self.sel
        if i < 0:
            return  # rule 15
        keys = self.lay[h][r]["keys"]
        if kind == "blocker" and not self.in_bottom_row():  # rule 14
            return
        if len(keys) >= MAX_KEYS:  # rule 2
            messagebox.showinfo("Row full", f"A row can hold at most {MAX_KEYS} keys.")
            return
        keys.insert(i + after, _blocker() if kind == "blocker" else {"label": "", "w": 1.0})
        self.sel = (h, r, i + after)
        self.sync()

    def delete(self):
        h, r, i = self.sel
        if i < 0:
            return  # rule 15
        keys = self.lay[h][r]["keys"]
        if len(keys) == 1:
            return  # rule 2: keep one key so the row stays selectable
        del keys[i]
        self.sel = (h, r, min(i, len(keys) - 1))
        self.sync()

    def draw(self):
        cv = self.cv
        cv.delete("all")
        self.placed = place(self.lay)
        pts = [p for o in solid(self.placed) for p in footprint(o)] or [(0, 0), (U, U)]
        bw, bh = max(p[0] for p in pts), max(p[1] for p in pts)
        pieces = frame(self.placed, self.lay.get("frame_margin", 8.0)) if self.lay.get("frame") else []
        view = pts + [p for q in pieces for p in q]  # fit the frame into the window too
        x_lo, y_lo = min(p[0] for p in view), min(p[1] for p in view)
        vw, vh = max(p[0] for p in view) - x_lo, max(p[1] for p in view) - y_lo
        W, H = max(cv.winfo_width(), 200), max(cv.winfo_height(), 200)
        s = min((W - 60) / vw, (H - 60) / vh)
        ox, oy = (W - vw * s) / 2 - x_lo * s, (H - vh * s) / 2 - y_lo * s
        self.xf = (s, ox, oy)
        flat = lambda c: [v for x, y in c for v in (ox + x * s, oy + y * s)]
        for q in pieces:  # rule 13
            cv.create_polygon(flat(q), fill=CASE, outline=EDGE, width=2, joinstyle="miter")
        for o in self.placed:
            k = o["key"]
            sel = (o["half"], o["row"], o["idx"]) == self.sel
            if k.get("spacer"):
                cv.create_polygon(flat(footprint(o)), fill="", outline=SELECT if sel else EDGE, dash=(4, 4))
            elif k.get("blocker"):  # rule 14: a solid bit of case, no keycap
                cv.create_polygon(flat(footprint(o)), fill=CASE, outline=SELECT if sel else EDGE, width=2 if sel else 1)
            else:
                cv.create_polygon(flat(footprint(o)), fill="", outline="#3a3f47")
                cv.create_polygon(flat(footprint(o, k["w"] * U - (U - CAP), CAP)),
                                  fill=SELECT if sel else KEY, outline=KEY_EDGE)
            text = ("WK" if k.get("blocker") else k["label"]) + ("" if k["w"] == 1 else f"\n{k['w']:g}u")
            cv.create_text(ox + o["x"] * s, oy + o["y"] * s, text=text, angle=-o["ang"], justify="center",
                           fill=BG if sel and not (k.get("spacer") or k.get("blocker")) else
                           MUTED if k.get("blocker") else TEXT,
                           font=("Helvetica", max(7, int(s * 3.2))))
        h, r, i = self.sel
        o = next(o for o in self.placed if (o["half"], o["row"], o["idx"]) == self.sel)
        where = f"row {r + 1}" if i < 0 else f"{i + 1} of {len(self.lay[h][r]['keys'])}"
        self.sel_info.config(text=f"{h.title()} · {o['rname']} · {where}\n"
                                  f"center {o['x']:.2f}, {o['y']:.2f} mm · {o['ang']:.2f}°")
        hits = collisions(self.placed)
        self.status.config(text=f"Footprint {bw:.2f} × {bh:.2f} mm" +
                           (f"     Frame {vw:.2f} × {vh:.2f} mm" if pieces else "") + "     " +
                           (f"⚠ {len(hits)} overlapping key pairs" if hits else "✓ No overlapping keys"),
                           fg="#e06c75" if hits else "#98c379")

    def click(self, e):
        s, ox, oy = self.xf
        x, y = (e.x - ox) / s, (e.y - oy) / s
        for o in self.placed:
            a = math.radians(o["ang"])
            dx, dy = x - o["x"], y - o["y"]
            lx, ly = dx * math.cos(a) + dy * math.sin(a), -dx * math.sin(a) + dy * math.cos(a)
            if abs(lx) <= o["key"]["w"] * U / 2 and abs(ly) <= U / 2:
                self.sel = (o["half"], o["row"], o["idx"])
                self.sync()
                return

    def save(self):
        p = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Layout", "*.json")])
        if p:
            Path(p).write_text(json.dumps(self.lay, indent=1))

    def load(self):
        p = filedialog.askopenfilename(filetypes=[("Layout", "*.json")])
        if not p:
            return
        try:
            lay = json.loads(Path(p).read_text())
            lay.setdefault("outer", lay.pop("tilt", 0))  # files saved before "tilt" became "outer"
            size = layout_size(lay)
            if size != self.size:  # rule 12: wrong tab
                messagebox.showerror("Wrong layout size", f"This is a {SIZE_NAMES[size]} layout, but you're on the "
                                     f"{SIZE_NAMES[self.size]} tab.\n\nSwitch to the {SIZE_NAMES[size]} tab to open it.")
                return
            lay["size"] = size
            place(lay)  # validate before replacing the current layout
        except (OSError, ValueError, KeyError, TypeError, IndexError) as err:
            messagebox.showerror("Can't open layout", str(err))
            return
        self.lay = self.layouts[self.size] = lay
        self.sel = ("left", 0, 0)
        self.sync()

    def export(self, ext):
        hits = collisions(self.placed)  # rule 10: never export overlapping keys without asking
        if hits and not messagebox.askyesno("Overlapping keys", f"{len(hits)} key pairs overlap:\n" +
                                            "\n".join(f"{a} / {b}: {d:.3f} mm" for a, b, d in hits[:8]) + "\n\nExport anyway?"):
            return
        p = filedialog.asksaveasfilename(defaultextension="." + ext, filetypes=[(ext.upper(), "*." + ext)])
        if p:
            Path(p).write_text(to_dxf(self.placed) if ext == "dxf" else json.dumps(to_kle(self.placed)))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
