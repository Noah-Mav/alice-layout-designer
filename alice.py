"""Alice-style 40% layout designer: design a curved split layout key by key, export it for case/plate CAD.

Run:   /opt/homebrew/bin/python3 alice.py      (needs Tk 8.6+: brew install python-tk@3.14;
Test:  /opt/homebrew/bin/python3 test_alice.py  macOS's /usr/bin/python3 has Tk 8.5, no rotated text)

DESIGN RULES — the behaviour this tool promises. Code comments say "rule N" where each is enforced,
and test_alice.py checks each one. Change a rule here first, then the code, then its test.

 1. Layout: Alice-style 40%, two halves, 4 rows each (top -> bottom): Top (QWERTY), Home,
    R2 "anchor" (the shift row, the reference row for everything), Bottom (spacebars).
    The halves are edited independently. The right half is the mirror image in code: built
    outer -> inner, then flipped.
 2. Keys: every keycap has an editable label and width (0.25u steps, min 0.25u). A key can be a
    spacer: an empty gap that takes up room but isn't a key (not exported, ignored for collisions,
    extents and "outermost / innermost key" lookups). Add/delete keys freely, max 10 per row per
    half, min 1.
 3. Cherry spacing: 1u = 19.05 mm. Neighbours in a row share their bottom corners, so the pitch
    along every row is exactly 19.05 mm; rows are 1u apart (plus rule 10's fraction of a mm).
 4. Stagger: per row, 0.125u steps, + = toward the center. Top and Home are measured from the
    R2 row's OUTER edge. The Bottom row is measured from the R2 row's INNER edge (the edge of B/N):
    its inner end sits on the same radial line.
 5. Curve: `curve` = degrees per 1u key (0.05° steps), a gentle curve down toward the center. The same rate on
    both halves (uniform angles). All rows of a half bend around one shared center (concentric
    arcs 1u apart).
 6. Outer keys straight: the outermost real key of Top/Home/R2 (Tab/Ctrl/Shift, Bksp/Enter/Fn) is
    exactly at `outer` degrees (0 = square to the case edge); spacers in front don't count. The
    Bottom row isn't forced straight: its outer key sits under the letters and follows the curve.
 7. Curve start: rows stay straight up to the inner edge of that half's longest outer key, then
    curve. (Starting earlier let long straight keys like a 2.25u Enter push their row into the
    row above.)
 8. Match center keys (`match_center`, default on): the half whose modifiers reach further starts
    curving later by the difference, so both R2 rows curve over the same length and B and N end at
    the same angle and height, while the degrees per key stay equal (rule 5).
 9. Level halves: with match on, B and N centers are level; with it off, the tops of Tab and Bksp.
    Either way the modifier rows (Tab/Bksp, Ctrl/Enter, Shift/Fn) stay level with each other,
    because both halves use identical row spacing.
10. No collisions: no two real keys' 19.05 mm footprints may overlap, so the plate works. Rectangles
    on concentric arcs can overlap ~0.1 mm at a stagger, so place() widens just those row gaps (the
    same on both halves) until clear. A slightly bigger gap is fine; overlap is not. The UI shows
    the overlap count and export asks before writing if any remain. Gap between halves >= 0.
11. Files: Save/Open = the layout JSON (this module's DEFAULT shape). Export DXF = mm, y up,
    layers KEYCAP_1U (19.05 mm footprints) and SWITCH_14MM (MX plate cutouts). Export KLE =
    keyboard-layout-editor.com JSON, one rotated key per row (KLE-site rx/ry semantics).

Units: geometry is computed in u (1u = 19.05 mm) with y pointing down and angles in degrees clockwise;
place() returns mm.
"""
import json
import math
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

U = 19.05       # Cherry MX key pitch, mm
CAP = 18.0      # typical keycap bottom size, only used for drawing
SWITCH = 14.0   # MX plate cutout
MAX_KEYS = 10   # per row, per half (rule 2)
TOP, HOME, ANCHOR, BOTTOM = range(4)
ROW_NAMES = ["Top", "Home", "Anchor (R2)", "Bottom"]


def _row(offset, *keys):
    return {"offset": offset, "keys": [{"label": k, "w": 1.0} if isinstance(k, str) else {"label": k[0], "w": k[1]} for k in keys]}


DEFAULT = {
    "curve": 2.0, "outer": 0.0, "gap": 0.5, "match_center": True,
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
        return (0 if r == ANCHOR else rows[r]["offset"]) + sum(k["w"] for _, k in keys[:n + 1])
    return max(lead(r) for r in (TOP, HOME, ANCHOR))


def center_key(rows, mirror):
    """Rule 8: (idx, inner-edge position in u) of the anchor row's innermost real key: B on the left, N on the right."""
    keys = walk(rows, ANCHOR, mirror)
    n = max((n for n, (_, k) in enumerate(keys) if not k.get("spacer")), default=len(keys) - 1)
    return keys[n][0], sum(k["w"] for _, k in keys[:n + 1])


def place_half(rows, curve, outer, mirror, extra=(0.0, 0.0, 0.0), delay=0.0):
    """Lay out one half in u. Returns [(row, idx, key, x, y, ang)] with x pointing toward the center
    (flipped for the right half) and y pointing down.

    Every row is straight up to x0 (rule 7), then bends around one shared center (rule 5). Each key's bottom
    edge is a chord of its row's track whose ends are exactly w apart, so neighbours share bottom corners
    (rule 3) and rows can't drift into each other. Keys inside the straight part come out at exactly
    `outer` degrees (rule 6).
    extra[r] = added space (u) between row r and r+1; place() raises it only where keys would collide.
    delay = how much later (u) this half starts curving; place() uses it to match the center keys."""
    R = 180 / (math.pi * curve) if curve else math.inf  # bottom-edge radius of the anchor row
    cy0 = ANCHOR + 1 + R                                  # curve center y (x = x0)
    ybot = [1 - extra[0] - extra[1], 2 - extra[1], ANCHOR + 1.0, 4 + extra[2]]  # straight-part bottom edges
    x0 = curve_start(rows, mirror) + delay

    def track(s, r):  # point on row r's bottom edge, s u along it from the outer end
        if s <= x0 or not curve:
            return s, ybot[r]
        rho = cy0 - ybot[r]
        phi = (s - x0) / rho
        return x0 + rho * math.sin(phi), cy0 - rho * math.cos(phi)

    def step(s, r, w, sign):  # track position exactly w (straight-line) away from track(s), in direction sign
        if not curve or (s + w <= x0 if sign > 0 else s <= x0):
            return s + sign * w
        p, lo, hi = track(s, r), w, w * 1.5  # the track between chord ends is at least w long
        for _ in range(40):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if math.dist(track(s + sign * mid, r), p) < w else (lo, mid)
        return s + sign * hi

    t = math.radians(outer)
    out = []
    anchor_end = 0.0
    for r in range(4):
        keys, spans = walk(rows, r, mirror), []
        if r == BOTTOM:  # rule 4: walk inner -> outer from the anchor's inner-edge radial line
            rho_a, rho_b = cy0 - ybot[ANCHOR], cy0 - ybot[BOTTOM]
            s = (x0 + (anchor_end - x0) * rho_b / rho_a if curve and anchor_end > x0 else anchor_end) + rows[r]["offset"]
            for idx, key in reversed(keys):
                s2 = step(s, r, key["w"], -1)
                spans.append((idx, key, s2, s))
                s = s2
            spans.reverse()
        else:
            s = 0.0 if r == ANCHOR else rows[r]["offset"]  # rule 4: stagger from the R2 outer edge
            for idx, key in keys:
                s2 = step(s, r, key["w"], 1)
                spans.append((idx, key, s, s2))
                s = s2
            if r == ANCHOR:
                anchor_end = s
        for idx, key, a, b in spans:
            (ax, ay), (bx, by) = track(a, r), track(b, r)
            ang = math.atan2(by - ay, bx - ax)
            w, ca, sa = key["w"], math.cos(ang), math.sin(ang)
            cx, cy = ax + w / 2 * ca + 0.5 * sa, ay + w / 2 * sa - 0.5 * ca
            cx, cy = cx * math.cos(t) - cy * math.sin(t), cx * math.sin(t) + cy * math.cos(t)
            deg = math.degrees(ang) + outer
            out.append((r, idx, key, -cx if mirror else cx, cy, -deg if mirror else deg))
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
    quad = lambda o: corners(o[3], o[4], o[2]["w"], 1, o[5])
    extra = [0.0] * 3  # rule 10: shared by both halves so the modifier rows stay level (rule 9)
    match = lay.get("match_center", True) and lay["curve"]
    delay = {"left": 0.0, "right": 0.0}
    if match:  # rule 8: same degrees per key both sides, so give both R2 rows the same curved length up to B/N:
        # the half with the longer modifiers starts curving later, and B and N end at the same angle
        run = {h: center_key(lay[h], h == "right")[1] - curve_start(lay[h], h == "right") for h in delay}
        longer = max(run, key=run.get)
        delay[longer] = run[longer] - min(run.values())
    for _ in range(20):  # rule 10: widen only the row gaps where 1u footprints would collide
        halves = {h: place_half(lay[h], lay["curve"], lay["outer"], h == "right", extra, delay[h]) for h in delay}
        moved = False
        for r in (TOP, HOME, ANCHOR):
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
        ref = {h: next(y for (r, i, k, x, y, a) in ks if r == ANCHOR and i == center_key(lay[h], h == "right")[0])
               for h, ks in halves.items()}
    else:      # highest points of Tab and Bksp at the same height
        ref = {h: min(p[1] for (r, i, k, x, y, a) in ks if r == TOP and i == outer_idx(h)
                      for p in corners(x, y, k["w"], 1, a)) for h, ks in halves.items()}
    dy = ref["left"] - ref["right"]
    out = [{"half": h, "row": r, "idx": i, "key": k, "x": (x + (dx if h == "right" else 0)) * U,
            "y": (y + (dy if h == "right" else 0)) * U, "ang": a}
           for h, ks in halves.items() for r, i, k, x, y, a in ks]
    pts = [p for o in solid(out) for p in footprint(o)]
    x0, y0 = min((p[0] for p in pts), default=0), min((p[1] for p in pts), default=0)
    for o in out:
        o["x"] -= x0
        o["y"] -= y0
    return out


def collisions(placed):
    """Rule 10: [(label_a, label_b, overlap_mm)] for every pair of real keys whose 19.05 mm footprints overlap."""
    ks = solid(placed)
    name = lambda o: o["key"]["label"] or f'{o["half"]} {ROW_NAMES[o["row"]].lower()} key {o["idx"] + 1}'
    return [(name(a), name(b), d) for i, a in enumerate(ks) for b in ks[i + 1:]
            if (d := overlap(footprint(a), footprint(b))) > 1e-3]


def solid(placed):
    return [o for o in placed if not o["key"].get("spacer")]


def footprint(o, w=None, h=U):
    return corners(o["x"], o["y"], o["key"]["w"] * U if w is None else w, h, o["ang"])


def to_dxf(placed):
    """Rule 11: R12 DXF (mm, y up): 1u footprints on KEYCAP_1U, 14 mm switch cutouts on SWITCH_14MM."""
    out = ["0", "SECTION", "2", "ENTITIES"]
    for o in solid(placed):
        for layer, c in (("KEYCAP_1U", footprint(o)), ("SWITCH_14MM", footprint(o, SWITCH, SWITCH))):
            for (x1, y1), (x2, y2) in zip(c, c[1:] + c[:1]):
                out += ["0", "LINE", "8", layer, "10", f"{x1:.4f}", "20", f"{-y1:.4f}", "11", f"{x2:.4f}", "21", f"{-y2:.4f}"]
    return "\n".join(out + ["0", "ENDSEC", "0", "EOF"]) + "\n"


def to_kle(placed):
    """Rule 11: keyboard-layout-editor.com JSON. Every key is its own row so it can carry its own rotation
    (KLE only allows r/rx/ry on a row's first key; the KLE site resets x/y to rx/ry when they're set)."""
    return [[{"r": round(o["ang"], 4), "rx": round(o["x"] / U, 4), "ry": round(o["y"] / U, 4),
              "x": -o["key"]["w"] / 2, "y": -0.5, "w": o["key"]["w"]}, o["key"]["label"]] for o in solid(placed)]


class App:
    def __init__(self, root):
        self.root = root
        self.lay = json.loads(json.dumps(DEFAULT))
        self.sel = ("left", 0, 0)
        self.loading = False
        self.bound = []  # (StringVar, getter) pairs refreshed by sync()
        root.title("Alice 40% Layout Designer")

        self.cv = tk.Canvas(root, bg="#1e2227", highlightthickness=0, width=1100, height=600)
        self.cv.pack(side="left", fill="both", expand=True)
        self.cv.bind("<Configure>", lambda e: self.draw())
        self.cv.bind("<Button-1>", self.click)

        p = tk.Frame(root, padx=10, pady=10)
        p.pack(side="right", fill="y")

        self.section(p, "Shape")
        self.spin(p, "Curve (° per 1u key)", 0, 5, 0.05, lambda: self.lay["curve"], lambda v: self.lay.update(curve=v))  # rule 5
        self.spin(p, "Outer key angle (°)", -10, 20, 0.5, lambda: self.lay["outer"], lambda v: self.lay.update(outer=v))
        self.match_var = tk.BooleanVar()
        tk.Checkbutton(p, text="Match center keys (B/N same height + angle)", variable=self.match_var,
                       command=lambda: (self.lay.update(match_center=self.match_var.get()), self.draw())).pack(anchor="w")
        self.spin(p, "Gap between halves (u)", 0, 5, 0.125, lambda: self.lay["gap"], lambda v: self.lay.update(gap=v))

        for half in ("left", "right"):
            self.section(p, f"{half.title()} stagger (u, + = toward center)")
            for r in (TOP, HOME, BOTTOM):
                self.spin(p, ROW_NAMES[r], -4, 4, 0.125, lambda h=half, r=r: self.lay[h][r]["offset"],  # rule 4
                          lambda v, h=half, r=r: self.lay[h][r].update(offset=v))

        self.section(p, "Selected key (click one)")
        self.sel_info = tk.Label(p, anchor="w", justify="left")
        self.sel_info.pack(fill="x")
        f = tk.Frame(p)
        f.pack(fill="x")
        tk.Label(f, text="Label").pack(side="left")
        self.label_var = tk.StringVar()
        self.label_var.trace_add("write", self.label_changed)
        e = tk.Entry(f, textvariable=self.label_var, width=12)
        e.pack(side="right")
        e.bind("<Return>", lambda ev: self.cv.focus_set())
        self.spin(p, "Width (u)", 0.25, 10, 0.25, lambda: self.cur()["w"], lambda v: self.cur().update(w=v))  # rule 2
        self.spacer_var = tk.BooleanVar()
        tk.Checkbutton(p, text="Spacer (empty gap, not a key)", variable=self.spacer_var,
                       command=self.spacer_changed).pack(anchor="w")
        f = tk.Frame(p)
        f.pack(fill="x", pady=4)
        tk.Button(f, text="◀ Add", command=lambda: self.insert(0)).pack(side="left")
        tk.Button(f, text="Add ▶", command=lambda: self.insert(1)).pack(side="left")
        tk.Button(f, text="Delete", command=self.delete).pack(side="left")

        self.section(p, "File")
        f = tk.Frame(p)
        f.pack(fill="x")
        tk.Button(f, text="Open…", command=self.load).pack(side="left")
        tk.Button(f, text="Save…", command=self.save).pack(side="left")
        f = tk.Frame(p)
        f.pack(fill="x")
        tk.Button(f, text="Export DXF…", command=lambda: self.export("dxf")).pack(side="left")
        tk.Button(f, text="Export KLE…", command=lambda: self.export("json")).pack(side="left")
        self.size_info = tk.Label(p, anchor="w", justify="left", pady=8)
        self.size_info.pack(fill="x")
        self.sync()

    def section(self, parent, text):
        tk.Label(parent, text=text, font=("Helvetica", 12, "bold"), anchor="w").pack(fill="x", pady=(10, 2))

    def spin(self, parent, text, lo, hi, step, get, put):
        f = tk.Frame(parent)
        f.pack(fill="x")
        tk.Label(f, text=text).pack(side="left")
        v = tk.StringVar()
        tk.Spinbox(f, from_=lo, to=hi, increment=step, textvariable=v, width=7, format="%.3f").pack(side="right")

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

    def cur(self):
        h, r, i = self.sel
        return self.lay[h][r]["keys"][i]

    def sync(self):
        """Push layout values into the controls without triggering writes back."""
        self.loading = True
        for v, get in self.bound:
            v.set(f"{get():g}")
        self.label_var.set(self.cur()["label"])
        self.spacer_var.set(bool(self.cur().get("spacer")))
        self.match_var.set(bool(self.lay.get("match_center", True)))
        self.loading = False
        self.draw()

    def label_changed(self, *_):
        if not self.loading:
            self.cur()["label"] = self.label_var.get()
            self.draw()

    def spacer_changed(self):
        self.cur()["spacer"] = self.spacer_var.get()
        self.draw()

    def insert(self, after):
        h, r, i = self.sel
        keys = self.lay[h][r]["keys"]
        if len(keys) >= MAX_KEYS:  # rule 2
            messagebox.showinfo("Row full", f"A row can hold at most {MAX_KEYS} keys.")
            return
        keys.insert(i + after, {"label": "", "w": 1.0})
        self.sel = (h, r, i + after)
        self.sync()

    def delete(self):
        h, r, i = self.sel
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
        W, H = max(cv.winfo_width(), 200), max(cv.winfo_height(), 200)
        s = min((W - 60) / bw, (H - 60) / bh)
        ox, oy = (W - bw * s) / 2, (H - bh * s) / 2
        self.xf = (s, ox, oy)
        flat = lambda c: [v for x, y in c for v in (ox + x * s, oy + y * s)]
        for o in self.placed:
            k = o["key"]
            sel = (o["half"], o["row"], o["idx"]) == self.sel
            if k.get("spacer"):
                cv.create_polygon(flat(footprint(o)), fill="", outline="#e5c07b" if sel else "#5c6370", dash=(4, 4))
            else:
                cv.create_polygon(flat(footprint(o)), fill="", outline="#3a3f47")
                cv.create_polygon(flat(footprint(o, k["w"] * U - (U - CAP), CAP)),
                                  fill="#e5c07b" if sel else "#2c313a", outline="#9aa3ad")
            text = k["label"] + ("" if k["w"] == 1 else f"\n{k['w']:g}u")
            cv.create_text(ox + o["x"] * s, oy + o["y"] * s, text=text, angle=-o["ang"], justify="center",
                           fill="#1e2227" if sel and not k.get("spacer") else "#d7dae0",
                           font=("Helvetica", max(7, int(s * 3.2))))
        h, r, i = self.sel
        o = next(o for o in self.placed if (o["half"], o["row"], o["idx"]) == self.sel)
        self.sel_info.config(text=f"{h} · {ROW_NAMES[r]} · key {i + 1}/{len(self.lay[h][r]['keys'])}\n"
                                  f"center {o['x']:.2f}, {o['y']:.2f} mm · {o['ang']:.2f}°")
        hits = collisions(self.placed)
        self.size_info.config(text=f"Footprint {bw:.2f} × {bh:.2f} mm\n" +
                              (f"⚠ {len(hits)} overlapping key pairs" if hits else "No overlapping keys"),
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
            place(lay)  # validate before replacing the current layout
        except (OSError, ValueError, KeyError, TypeError, IndexError) as err:
            messagebox.showerror("Can't open layout", str(err))
            return
        self.lay, self.sel = lay, ("left", 0, 0)
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
