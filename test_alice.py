"""Checks the DESIGN RULES in alice.py (each block names its rule). Run: /opt/homebrew/bin/python3 test_alice.py"""
import copy
import itertools
import math

from alice import ANCHOR, BOTTOM, DEFAULT, U, _row, collisions, corners, place, place_half, solid, footprint

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
for base, curve, outer, off, match in itertools.product((DEFAULT, ergo_v1), (0, 1, 2.5, 5), (-10, 0, 8),
                                                         (-0.5, 0, 0.75), (True, False)):
                lay = copy.deepcopy(base)
                lay.update(curve=curve, outer=outer, match_center=match)
                for h in ("left", "right"):
                    lay[h][0]["offset"] += off
                    lay[h][3]["offset"] -= off
                hits = collisions(place(lay))
                assert not hits, (curve, outer, off, match, hits[:3])

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

print("ok")
