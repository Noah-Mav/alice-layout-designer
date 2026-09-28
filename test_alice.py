"""Checks the DESIGN RULES in alice.py (each block names its rule). Run: /opt/homebrew/bin/python3 test_alice.py"""
import copy
import itertools
import math

from alice import (DEFAULT, DEFAULT_60, U, _blocker, _row, collisions, corners, edge_distance, footprint, frame,
                   inside_polygon, keycaps, layout_size, mod_column, place, place_half, solid, to_dxf, to_kle)

ANCHOR, BOTTOM = 2, 3  # 40% row indices

close = lambda a, b, tol=1e-3: abs(a - b) < tol

# Rules 3 + 4, flat layout: plain 19.05 mm grid, rows 1u apart, bottom row aligned to the R2 inner edge.
flat = dict(copy.deepcopy(DEFAULT), curve=0, outer=0)
L = place_half(flat["left"], 0, 0, False)
shift_row = [o for o in L if o[0] == ANCHOR]
assert close(shift_row[0][3], 1.125) and close(shift_row[1][3], 2.75)  # Shift 2.25u then Z
assert all(close(o[4], o[0] + 0.5) for o in L)
bottom = [o for o in L if o[0] == BOTTOM]
assert close(bottom[-1][3] + bottom[-1][2]["w"] / 2, 7.25)  # spacebar inner edge = B inner edge

# Rule 3, curved layout: adjacent keys in a row share their bottom corner exactly (Cherry pitch, no overlap).
curved = copy.deepcopy(DEFAULT)
for half, mirror in (("left", False), ("right", True)):
    ks = place_half(curved[half], 2.0, 4.0, mirror)
    for r in range(4):
        row = sorted((o for o in ks if o[0] == r), key=lambda o: o[1])  # left -> right on screen
        for a, b in zip(row, row[1:]):
            ca, cb = corners(a[3], a[4], a[2]["w"], 1, a[5]), corners(b[3], b[4], b[2]["w"], 1, b[5])
            assert math.dist(ca[2], cb[3]) < 1e-9, (half, r, math.dist(ca[2], cb[3]))

# Rule 4: bottom row inner edge sits on the anchor's inner radial line (curve center at (x0, ANCHOR + 1 + R)).
R = 180 / (math.pi * 2.0)
x0 = 2.25  # curve starts after the longest outer key (Shift)
ks = place_half(curved["left"], 2.0, 0, False)
inner_angle = lambda o: math.atan2(corners(o[3], o[4], o[2]["w"], 1, o[5])[2][0] - x0,
                                   ANCHOR + 1 + R - corners(o[3], o[4], o[2]["w"], 1, o[5])[2][1])
assert close(inner_angle([o for o in ks if o[0] == ANCHOR][-1]), inner_angle([o for o in ks if o[0] == BOTTOM][-1]))

# Rule 6: outer keys (Tab/Ctrl/Shift, Bksp/Enter/Fn) sit at exactly the outer angle on both halves; the rest curve.
for outer in (0, 3.5):
    P = place(dict(copy.deepcopy(DEFAULT), outer=outer))
    for half in ("left", "right"):
        for r in (0, 1, ANCHOR):
            idx = 0 if half == "left" else len(DEFAULT[half][r]["keys"]) - 1
            o = next(o for o in P if (o["half"], o["row"], o["idx"]) == (half, r, idx))
            assert abs(o["ang"] - (outer if half == "left" else -outer)) < 1e-9, (half, r, o["ang"])
    assert abs(next(o for o in P if o["key"]["label"] == "B")["ang"]) > outer + 5  # inner keys still curve

# Rule 9 (match off): the highest point of Tab and of Bksp match, even with uneven stagger and a tilt.
uneven = copy.deepcopy(DEFAULT)
uneven.update(outer=6.0, match_center=False)
uneven["right"][0]["offset"] = 1.25
P = place(uneven)
high = lambda label: min(p[1] for o in P if o["key"]["label"] == label for p in footprint(o))
assert close(high("Tab"), high("Bksp")), (high("Tab"), high("Bksp"))

# Rules 2 + 6: a leading spacer (or extra outer spacer on the right) doesn't steal the "outer key" role.
spaced = copy.deepcopy(DEFAULT)
for r in (0, 1):
    spaced["left"][r]["keys"].insert(0, {"label": "", "w": 0.5, "spacer": True})
    spaced["right"][r]["keys"].append({"label": "", "w": 0.5, "spacer": True})
P = place(dict(spaced, outer=3.0, match_center=False))
assert close(min(p[1] for o in P if o["key"]["label"] == "Tab" for p in footprint(o)),
             min(p[1] for o in P if o["key"]["label"] == "Bksp" for p in footprint(o)))  # still level
for label, want in (("Tab", 3.0), ("Ctrl", 3.0), ("Bksp", -3.0), ("Enter", -3.0)):
    assert abs(next(o for o in P if o["key"]["label"] == label)["ang"] - want) < 1e-9, label

# Rule 1: mirrored halves are symmetric and separated by exactly `gap`.
sym = copy.deepcopy(DEFAULT)
sym["right"] = [dict(row, keys=row["keys"][::-1]) for row in sym["left"]]
P = place(sym)
width = max(p[0] for o in solid(P) for p in footprint(o))
lefts = sorted((o["row"], o["idx"], o) for o in P if o["half"] == "left")
rights = {(o["row"], len(sym["right"][o["row"]]["keys"]) - 1 - o["idx"]): o for o in P if o["half"] == "right"}
for r, i, o in lefts:
    m = rights[(r, i)]
    assert close(m["x"], width - o["x"]) and close(m["y"], o["y"]) and close(m["ang"], -o["ang"])
lmax = max(p[0] for o in solid(P) if o["half"] == "left" for p in footprint(o))
rmin = min(p[0] for o in solid(P) if o["half"] == "right" for p in footprint(o))
assert close(rmin - lmax, sym["gap"] * U)

# Rule 10: no two real keys' 19.05 mm footprints overlap. ergoV1 is the layout that used to collide
# (right top row sank into the home row next to a 2.25u Enter).
ergo_v1 = {
    "curve": 2.5, "outer": 0.0, "gap": 0.25,
    "left": [_row(0.25, ("Tab", 1.5), *"QWERT"), _row(0.125, ("Ctrl", 1.75), *"ASDFG"),
             _row(0, ("Shift", 2.25), *"ZXCVB"), _row(-0.125, ("", 1), ("", 1.5), ("Code", 2.25), ("", 1))],
    "right": [_row(0.25, *"YUIOP", ("Bksp", 1.5)), _row(0.125, *"HJKL", ("Enter", 2.25)),
              _row(0, *"NM<>", ("Shift", 1.75), "Fn"), _row(-0.125, ("", 2.75), ("Lower", 1.5), ("", 1))],
}
for base, curve, outer, off, match, bend in itertools.product((DEFAULT, ergo_v1, DEFAULT_60), (0, 1, 2.5, 5), (-10, 0, 8),
                                                               (-0.5, 0, 0.75), (True, False), ("curve", "straight")):
                lay = copy.deepcopy(base)
                lay.update(curve=curve, line_angle=curve * 4, outer=outer, match_center=match, bend=bend)
                for h in ("left", "right"):
                    lay[h][0]["offset"] += off
                    lay[h][-1]["offset"] -= off
                hits = collisions(place(lay))
                assert not hits, (curve, outer, off, match, bend, hits[:3])

# Rules 5 + 8: B and N end at the same height and mirrored angle, with the same degrees per key
# both sides (ergoV1's left modifiers are 0.625u longer, so the left curve starts 0.625u later).
for curve, outer in ((2.5, 0), (1.5, 4), (4, -3)):
    P = place(dict(copy.deepcopy(ergo_v1), curve=curve, outer=outer, match_center=True))
    b, n = (next(o for o in P if o["key"]["label"] == lab) for lab in "BN")
    assert abs(b["y"] - n["y"]) < 1e-6 and abs(b["ang"] + n["ang"]) < 1e-3, (curve, b["y"], n["y"], b["ang"], n["ang"])
    g, h = (next(o for o in P if o["key"]["label"] == lab) for lab in "GH")
    assert abs(g["y"] - h["y"]) < 0.05 and abs(g["ang"] + h["ang"]) < 1e-6  # same row lengths -> matches too

# Rule 9: with match on or off, the modifier rows (Tab/Bksp, Ctrl/Enter, Shift/Fn) stay level.
for match in (True, False):
    P = place(dict(copy.deepcopy(ergo_v1), match_center=match))
    for r in (0, 1, ANCHOR):
        high = {h: min(p[1] for o in P if o["half"] == h and o["row"] == r and o["idx"] == (0 if h == "left" else len(ergo_v1[h][r]["keys"]) - 1)
                       for p in footprint(o)) for h in ("left", "right")}
        assert abs(high["left"] - high["right"]) < 1e-3, (match, r, high)

# Rules 1, 6, 8, 9 on the 60/65% layout: number-row outer keys straight too, B/N matched, modifier rows level.
for curve, outer in ((2.0, 0), (3.0, 5)):
    P = place(dict(copy.deepcopy(DEFAULT_60), curve=curve, outer=outer))
    for h, sign in (("left", 1), ("right", -1)):
        for r in range(4):  # Number, Top, Home, R2
            idx = 0 if h == "left" else len(DEFAULT_60[h][r]["keys"]) - 1
            o = next(o for o in P if (o["half"], o["row"], o["idx"]) == (h, r, idx))
            assert abs(o["ang"] - sign * outer) < 1e-9, (h, r, o["ang"])
    b, n = (next(o for o in P if (o["half"], o["row"], o["idx"]) == key) for key in (("left", 3, 5), ("right", 3, 0)))  # B, Raise
    assert b["key"]["label"] == "B" and abs(b["y"] - n["y"]) < 1e-6 and abs(b["ang"] + n["ang"]) < 1e-3, (b["y"], n["y"])
    assert next(o for o in P if o["key"]["label"] == "Esc")["rname"] == "Number"

# Rule 12: sizes are recognised (older files by row count) and a wrong row count is refused.
assert layout_size(DEFAULT) == "40" and layout_size(DEFAULT_60) == "60" and layout_size(ergo_v1) == "40"
for bad in (dict(DEFAULT, size="60"), dict(DEFAULT, right=DEFAULT_60["right"])):
    try:
        layout_size(bad)
        raise AssertionError("should have been refused")
    except ValueError:
        pass

# Rule 13: the case outline has a straight top, square outer ends and a V bottom (5 corners); every key is inside
# and every edge is exactly `margin` from its nearest key, at any margin.
def inside(pt, poly):
    return inside_polygon(pt, poly)
for lay, outer, margin in itertools.product((DEFAULT, ergo_v1, DEFAULT_60), (0, 6), (0.0, 3.0, 8.0, 15.0)):
    P = place(dict(copy.deepcopy(lay), outer=outer))
    pieces = frame(P, margin)
    assert len(pieces) == 1
    q = pieces[0]
    assert len(q) == 5, len(q)
    pts = [pt for o in solid(P) for pt in footprint(o)]
    assert all(inside_polygon(pt, q) or edge_distance(pt, q) < 1e-6 for pt in pts)
    for a, b in zip(q, q[1:] + q[:1]):  # no edge floats further out than the margin
        assert abs(min(edge_distance(pt, [a, b]) for pt in pts) - margin) < 1e-6, (outer, margin, a, b)
    assert abs(q[0][1] - q[1][1]) < 1e-9  # straight, level top
    for (x1, y1), (x2, y2) in ((q[4], q[0]), (q[1], q[2])):  # outer ends run along the outer keys' height axis
        end_angle = (math.degrees(math.atan2(x2 - x1, -(y2 - y1))) + 90) % 180 - 90
        assert abs(abs(end_angle) - outer) < 1e-6, (end_angle, outer)

# A TGR Alice-style 60% (ANSI widths, WK blockers) to test 60/65% things besides the Neo Ergo default.
tgr_60 = {
    "size": "60", "curve": 2.0, "outer": 0.0, "gap": 0.5,
    "left": [_row(0, "Esc", *"123456"), _row(0, ("Tab", 1.5), *"QWERT"), _row(0, ("Caps", 1.75), *"ASDFG"),
             _row(0, ("Shift", 2.25), *"ZXCVB"), _row(0, ("Ctrl", 1.5), _blocker(), ("Alt", 1.5), ("", 2.25))],
    "right": [_row(0, *"7890-=", ("Bksp", 2)), _row(0, *"YUIOP[]", ("\\", 1.5)), _row(0, *"HJKL;'", ("Enter", 2.25)),
              _row(0, *"NM,./", ("Shift", 1.75), "Fn"), _row(0, ("", 2.75), ("Alt", 1.5), _blocker(), ("Ctrl", 1.5))],
}

# Rule 14: WK blockers are solid case (placed, collision-checked, framed) but get no switch or keycap.
P = place(tgr_60)
blockers = [o for o in P if o["key"].get("blocker")]
assert len(blockers) == 2 and all(o["row"] == 4 for o in blockers) and not collisions(P)
dxf = to_dxf(P).split("\n")
assert dxf.count("WK_BLOCKER") == 4 * len(blockers) and dxf.count("SWITCH_14MM") == 4 * len(keycaps(P))
assert sum(1 for k in to_kle(P) if k[0].get("d")) == len(blockers)
for h in ("left", "right"):  # anywhere but the bottom row is refused
    bad = copy.deepcopy(DEFAULT)
    bad[h][1]["keys"].append(_blocker())
    try:
        place(bad)
        raise AssertionError("blocker outside the bottom row should be refused")
    except ValueError:
        pass

# Rule 15: the mod column (both sizes) sits `gap` u outside the main keys of the rows it spans, `count` keys
# from the top, each at the outer angle with its own width and dx nudge; no overlaps; the frame covers it.
for base, outer, gap, offset, count in itertools.product((DEFAULT, tgr_60, DEFAULT_60), (0, 4, -3), (0.0, 0.5, 1.25),
                                                         (0, 0.5), (None, 3)):
    lay = copy.deepcopy(base)
    lay.update(outer=outer)
    n = len(lay["left"])
    for h in ("left", "right"):
        cfg = mod_column(lay, h)
        cfg.update(on=True, gap=gap, offset=offset, count=count or n)
        for i, k in enumerate(cfg["keys"]):
            k.update(w=(1.0, 1.25, 1.5)[i % 3], dx=0.0)
    P = place(lay)
    assert not collisions(P), (base.get("size"), outer, gap, offset, count, collisions(P)[:3])
    for h, sign in (("left", 1), ("right", -1)):
        mods = [o for o in P if o["mod"] and o["half"] == h]
        assert len(mods) == (count or n) and all(abs(o["ang"] - sign * outer) < 1e-9 for o in mods)
        assert [o["key"]["w"] for o in mods] == [(1.0, 1.25, 1.5)[i % 3] for i in range(count or n)]
        if outer == 0:  # distance from the spanned rows' main keys to the column's inner line
            main = [pt[0] for o in solid(P) if o["half"] == h and not o["mod"] and o["row"] < (count or n) for pt in footprint(o)]
            col = [pt[0] for o in mods for pt in footprint(o)]
            dist = (min(main) - max(col)) if h == "left" else (min(col) - max(main))
            assert abs(dist - gap * U) < 1e-6, (h, dist)
    assert all(inside_polygon(pt, frame(P, 8.0)[0]) for o in P if o["mod"] for pt in footprint(o))
lay = copy.deepcopy(tgr_60)  # dx moves one key toward the main keys without touching the others
for h in ("left", "right"):
    mod_column(lay, h)["on"] = True
before = {(o["half"], o["row"]): o["x"] for o in place(lay) if o["mod"]}
lay["mod"]["left"]["keys"][1]["dx"] = 0.25
after = {(o["half"], o["row"]): o["x"] for o in place(lay) if o["mod"]}
assert abs(after[("left", 1)] - before[("left", 1)] - 0.25 * U) < 1e-6
assert all(abs(after[k] - before[k]) < 1e-6 for k in before if k != ("left", 1))
assert not any(o["mod"] for o in place(tgr_60)) and not any(o["mod"] for o in place(DEFAULT))  # off unless switched on

# Rule 16: a straight bend puts every key either flat or on the angled line (exactly `outer` or `outer`+angle),
# keeps B/N matched, and never overlaps.
for base, angle, outer in itertools.product((DEFAULT, ergo_v1, tgr_60, DEFAULT_60), (5, 10, 15), (0, 3)):
    lay = dict(copy.deepcopy(base), bend="straight", line_angle=angle, outer=outer)
    P = place(lay)
    assert not collisions(P), (angle, outer, collisions(P)[:3])
    for o in solid(P):
        sign = 1 if o["half"] == "left" else -1
        assert min(abs(o["ang"] - sign * outer), abs(o["ang"] - sign * (outer + angle))) < 1e-9, (o["key"]["label"], o["ang"])
    left_b = max((o for o in P if o["half"] == "left" and o["row"] == len(lay["left"]) - 2 and not o["mod"]), key=lambda o: o["idx"])
    right_b = min((o for o in P if o["half"] == "right" and o["row"] == len(lay["right"]) - 2 and not o["mod"]), key=lambda o: o["idx"])
    assert abs(left_b["y"] - right_b["y"]) < 1e-6 and abs(left_b["ang"] + right_b["ang"]) < 1e-9

# Rule 16: in straight mode the rows are exactly 1u apart in the flat part and in the angled part (turn clashes
# are cleared by sliding angled keys along their line, not by spreading rows).
for base, angle in itertools.product((DEFAULT, ergo_v1, tgr_60, DEFAULT_60), (5, 10, 15)):
    P = place(dict(copy.deepcopy(base), bend="straight", line_angle=angle, outer=0))
    for h, sign in (("left", 1), ("right", -1)):
        ks = [o for o in solid(P) if o["half"] == h and not o["mod"]]
        n = len(base[h])
        flat_y = [next(o["y"] for o in ks if o["row"] == r and abs(o["ang"]) < 1e-9) for r in range(n - 1)]  # rows above the bottom
        assert all(abs(b - a - U) < 1e-3 for a, b in zip(flat_y, flat_y[1:])), (h, angle, flat_y)  # 1e-3 mm: rule 10 keeps a hair of clearance
        a = math.radians(sign * angle)
        nx, ny = -math.sin(a), math.cos(a)
        rows = [[o["x"] * nx + o["y"] * ny for o in ks if o["row"] == r and abs(o["ang"]) > 1e-9] for r in range(n)]
        d = [sum(v) / len(v) for v in rows if v]
        assert all(max(v) - min(v) < 1e-6 for v in rows if v)  # each angled row is one straight line
        assert all(abs(b - a - U) < 1e-3 for a, b in zip(d, d[1:])), (h, angle, d)

# The 60/65% default is the Neo Ergo: the same keys flat / angled as its VIA layout, the 4-key macro column
# stepping with the rows, and ↓ exactly under ↑ (rule 4's outer-edge bottom row).
P = place(DEFAULT_60)
assert not collisions(P)
angled = {h: sorted(o["key"]["label"] for o in solid(P) if o["half"] == h and not o["mod"] and abs(o["ang"]) > 1e-9) for h in ("left", "right")}
assert angled["left"] == sorted(list("3456WERTSDFGXCVB") + ["Alt", ""]), angled["left"]
assert angled["right"] == sorted(list("7890YUIOHJKLBNM,") + ["Alt", ""]), angled["right"]
mods = [o for o in P if o["mod"]]
assert [o["key"]["label"] for o in mods] == ["Home", "PgUp", "PgDn", "End"] and all(o["half"] == "left" for o in mods)
up, down = (next(o for o in P if o["key"]["label"] == lab) for lab in "↑↓")
assert abs(up["x"] - down["x"]) < 1e-6 and abs(up["ang"]) < 1e-9 and abs(down["ang"]) < 1e-9
shift = next(o for o in P if o["half"] == "left" and o["key"]["label"] == "Shift")
ctrl = next(o for o in P if o["half"] == "left" and o["row"] == 4 and o["idx"] == 0)
assert abs(min(p[0] for p in footprint(ctrl)) - (min(p[0] for p in footprint(shift)) - 0.25 * U)) < 1e-6

print("ok")
