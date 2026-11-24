# SkyForge - generation des modeles 3D (Blender 5.x, mode arriere-plan)
# Usage : blender --background --factory-startup --python build_models.py -- <dossier_sortie>
import bpy, bmesh, math, random, os, sys
from mathutils import Vector, Matrix

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else os.path.join(os.path.dirname(__file__), "..", "models")
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene

def sock(node, ident):
    for s in node.inputs:
        if s.identifier == ident:
            return s
    raise KeyError(ident)

def mat(name, color, metal=0.0, rough=0.5, alpha=1.0, emit=None, emit_str=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
    sock(b, "Base Color").default_value = (*color, 1)
    sock(b, "Metallic").default_value = metal
    sock(b, "Roughness").default_value = rough
    sock(b, "Alpha").default_value = alpha
    if alpha < 1.0:
        try:
            m.surface_render_method = 'BLENDED'
        except Exception:
            pass
    if emit:
        sock(b, "Emission Color").default_value = (*emit, 1)
        sock(b, "Emission Strength").default_value = emit_str
    return m

M = {
    "paint": mat("Paint", (0.92, 0.93, 0.95), 0.35, 0.32),
    "accent": mat("Accent", (0.85, 0.18, 0.08), 0.25, 0.35),
    "metal": mat("Metal", (0.55, 0.57, 0.6), 1.0, 0.28),
    "dark": mat("DarkMetal", (0.06, 0.065, 0.07), 0.8, 0.45),
    "glass": mat("Glass", (0.25, 0.35, 0.42), 0.1, 0.05, alpha=0.32),
    "rubber": mat("Rubber", (0.02, 0.02, 0.02), 0.0, 0.85),
    "prop": mat("PropBlade", (0.1, 0.1, 0.11), 0.2, 0.5),
    "tip": mat("PropTip", (0.95, 0.8, 0.05), 0.1, 0.4),
    "glow": mat("Glow", (0.2, 0.1, 0.05), 0.0, 0.6, emit=(1.0, 0.45, 0.12), emit_str=6.0),
    "helmet": mat("Helmet", (0.95, 0.95, 0.92), 0.0, 0.3),
    "bark": mat("Bark", (0.17, 0.11, 0.07), 0.0, 0.9),
    "needles": mat("Needles", (0.05, 0.16, 0.07), 0.0, 0.8),
    "hangar": mat("Hangar", (0.6, 0.62, 0.6), 0.85, 0.42),
    "concrete": mat("Concrete", (0.45, 0.45, 0.43), 0.0, 0.9),
}

def make_obj(name, bm, material, smooth=True, subsurf=0):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    ob = bpy.data.objects.new(name, me)
    scn.collection.objects.link(ob)
    ob.data.materials.append(material)
    if subsurf:
        md = ob.modifiers.new("Sub", 'SUBSURF')
        md.levels = subsurf
        md.render_levels = subsurf
    return ob

def loft_rings(name, rings, material, cap0=True, cap1=True, smooth=True, subsurf=2):
    bm = bmesh.new()
    R = [[bm.verts.new(p) for p in r] for r in rings]
    for a, b in zip(R, R[1:]):
        if len(a) == 1:
            n = len(b)
            for i in range(n):
                bm.faces.new((a[0], b[i], b[(i + 1) % n]))
        elif len(b) == 1:
            n = len(a)
            for i in range(n):
                bm.faces.new((a[i], a[(i + 1) % n], b[0]))
        else:
            n = len(a)
            for i in range(n):
                bm.faces.new((a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]))
    if cap0 and len(R[0]) > 2:
        bm.faces.new(R[0])
    if cap1 and len(R[-1]) > 2:
        bm.faces.new(R[-1])
    return make_obj(name, bm, material, smooth, subsurf)

def sring(y, w, h, cz=0.0, n=40, p=2.6):
    if w < 1e-4:
        return [(0.0, y, cz)]
    out = []
    for i in range(n):
        t = 2 * math.pi * i / n
        c, s = math.cos(t), math.sin(t)
        out.append(((w / 2) * math.copysign(abs(c) ** (2 / p), c), y, (h / 2) * math.copysign(abs(s) ** (2 / p), s) + cz))
    return out

def body(name, secs, material, n=40, p=2.6, subsurf=2):
    return loft_rings(name, [sring(y, w, h, cz, n, p) for (y, w, h, cz) in secs], material, subsurf=subsurf)

def naca(x, m, pp, t):
    yt = 5 * t * (0.2969 * math.sqrt(max(x, 0)) - 0.1260 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1036 * x ** 4)
    if m == 0:
        return x, yt, x, -yt
    if x < pp:
        yc = m / pp ** 2 * (2 * pp * x - x * x); dy = 2 * m / pp ** 2 * (pp - x)
    else:
        yc = m / (1 - pp) ** 2 * ((1 - 2 * pp) + 2 * pp * x - x * x); dy = 2 * m / (1 - pp) ** 2 * (pp - x)
    th = math.atan(dy)
    return x - yt * math.sin(th), yc + yt * math.cos(th), x + yt * math.sin(th), yc - yt * math.cos(th)

def airfoil(x0, x1, m, pp, t, n=26):
    up, lo = [], []
    for i in range(n + 1):
        x = x0 + (x1 - x0) * (1 - math.cos(math.pi * i / n)) / 2
        xu, yu, xl, yl = naca(x, m, pp, t)
        up.append((xu, yu)); lo.append((xl, yl))
    if x0 == 0:
        return up + lo[n:0:-1]
    return up + lo[::-1]

def surface(name, stations, x0, x1, m, pp, t, material, axis='X', n=26, subsurf=1):
    prof = airfoil(x0, x1, m, pp, t, n)
    rings = []
    for (s, le, ch, ts) in stations:
        rings.append([((s, le - x * ch, y * ch * ts) if axis == 'X' else (y * ch * ts, le - x * ch, s)) for (x, y) in prof])
    return loft_rings(name, rings, material, subsurf=subsurf)

def root(name, children):
    e = bpy.data.objects.new(name, None)
    scn.collection.objects.link(e)
    for c in children:
        c.parent = e
    return e

def set_hinge(ctrl, h0, h1):
    ctrl.data.transform(Matrix.Translation(-h0))
    ctrl.location = h0
    ax = (h1 - h0).normalized()
    ctrl["hinge"] = [ax.x, ax.y, ax.z]

# Repere Blender : avant = +Y, haut = +Z, droite = +X  (devient -Z / +Y / +X dans three.js)

# ---------- COCKPIT ----------
ck = body("CockpitBody", [(-1.0, 1.0, 1.0, 0), (-0.97, 1.0, 1.0, 0), (-0.4, 1.0, 1.0, 0), (0.25, 0.96, 0.92, -0.03), (0.62, 0.8, 0.74, -0.08), (0.88, 0.52, 0.48, -0.11), (1.0, 0.22, 0.22, -0.12), (1.03, 0.0, 0.0, -0.12)], M["paint"])
can = body("Canopy", [(-0.72, 0.0, 0.0, 0.47), (-0.62, 0.3, 0.16, 0.47), (-0.35, 0.56, 0.34, 0.5), (0.0, 0.64, 0.46, 0.53), (0.3, 0.56, 0.36, 0.49), (0.52, 0.3, 0.16, 0.44), (0.6, 0.0, 0.0, 0.43)], M["glass"], p=2.0)
fr = body("CanopyFrame", [(-0.035, 0.665, 0.49, 0.53), (0.0, 0.675, 0.5, 0.533), (0.035, 0.665, 0.49, 0.53)], M["dark"], p=2.0, subsurf=1)
bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16, radius=0.15)
hel = make_obj("Helmet", bm, M["helmet"]); hel.location = (0, -0.12, 0.6)
st = body("Stripe", [(0.05, 1.01, 1.0, -0.01), (0.12, 1.01, 1.0, -0.01)], M["accent"], subsurf=1)
root("part_cockpit", [ck, can, fr, hel, st])

# ---------- FUSELAGE ----------
fu = body("FuselageBody", [(-0.5, 1, 1, 0), (-0.48, 1, 1, 0), (0.48, 1, 1, 0), (0.5, 1, 1, 0)], M["paint"])
band = body("Band", [(-0.06, 1.012, 1.012, 0), (0.06, 1.012, 1.012, 0)], M["accent"], subsurf=1)
root("part_fuselage", [fu, band])

# ---------- QUEUE ----------
tc = body("TailBody", [(1.0, 1, 1, 0), (0.97, 1, 1, 0), (0.35, 0.92, 0.92, 0.03), (-0.35, 0.58, 0.62, 0.17), (-0.85, 0.26, 0.3, 0.29), (-1.0, 0.12, 0.15, 0.32), (-1.02, 0.0, 0.0, 0.32)], M["paint"])
root("part_tail", [tc])

def taper_wing(prefix, span, croot, ctip, sweep, cut, m, pp, t, axis='X'):
    st_main, st_ctrl = [], []
    for i in range(7):
        f = i / 6; s = span * f; ch = croot + (ctip - croot) * f; le = (croot / 2) - sweep * f
        st_main.append((s, le, ch, 1.0)); st_ctrl.append((s, le, ch, 1.0))
    st_main.append((span + 0.04, (croot / 2) - sweep - 0.03, ctip * 0.9, 0.55))
    main = surface(prefix + "Main", st_main, 0.0, cut, m, pp, t, M["paint"], axis)
    ctrl = surface(prefix + "Control", st_ctrl, cut + 0.012, 1.0, m, pp, t, M["accent"], axis)
    if axis == 'X':
        h0 = Vector((0, croot / 2 - cut * croot, 0)); h1 = Vector((span, croot / 2 - sweep - cut * ctip, 0))
    else:
        h0 = Vector((0, croot / 2 - cut * croot, 0)); h1 = Vector((0, croot / 2 - sweep - cut * ctip, span))
    set_hinge(ctrl, h0, h1)
    return main, ctrl

# ---------- AILE (NACA 2412) ----------
wm, wc = taper_wing("Wing", 3.0, 1.4, 0.8, 0.35, 0.72, 0.02, 0.4, 0.12)
root("part_wing", [wm, wc])

# ---------- STABILISATEUR (NACA 0010) ----------
stt = [(-1.24, 0.35, 0.7, 0.5)] + [(x, 0.4, 0.8, 1.0) for x in (-1.2, -0.6, 0.0, 0.6, 1.2)] + [(1.24, 0.35, 0.7, 0.5)]
sm = surface("StabMain", stt, 0.0, 0.66, 0, 0, 0.1, M["paint"])
sc = surface("StabControl", [(x, 0.4, 0.8, 1.0) for x in (-1.2, -0.6, 0.0, 0.6, 1.2)], 0.672, 1.0, 0, 0, 0.1, M["accent"])
set_hinge(sc, Vector((0, 0.4 - 0.66 * 0.8, 0)), Vector((1, 0.4 - 0.66 * 0.8, 0)))
root("part_stab", [sm, sc])

# ---------- DERIVE ----------
fm, fc = taper_wing("Fin", 1.4, 1.1, 0.6, 0.45, 0.66, 0, 0, 0.1, axis='Z')
root("part_fin", [fm, fc])

def blade_loft(name, mat_, r0, r1, c0, c1, tw0, tw1, n=8, thick=0.1, axis_rot=0.0):
    prof = airfoil(0.0, 1.0, 0.03, 0.4, thick, 14)
    rings = []
    for i in range(n + 1):
        f = i / n; r = r0 + (r1 - r0) * f; c = c0 + (c1 - c0) * f * f; th = math.radians(tw0 + (tw1 - tw0) * f)
        ring = []
        for (x, y) in prof:
            px, py = (x - 0.35) * c, y * c
            X = px * math.cos(th) - py * math.sin(th); Y = -px * math.sin(th) - py * math.cos(th)
            ca, sa = math.cos(axis_rot), math.sin(axis_rot)
            ring.append((X * ca - r * sa, Y, X * sa + r * ca))
        rings.append(ring)
    return loft_rings(name, rings, mat_, subsurf=1)

# ---------- MOTEUR A HELICE ----------
cow = body("Cowling", [(-0.75, 1.0, 1.0, 0), (-0.72, 1.0, 1.0, 0), (-0.1, 0.98, 0.98, 0), (0.3, 0.92, 0.92, 0), (0.52, 0.84, 0.84, 0), (0.58, 0.74, 0.74, 0)], M["paint"], p=2.3)
intake = body("Intake", [(0.575, 0.76, 0.76, 0), (0.6, 0.62, 0.62, 0), (0.6, 0.0, 0.0, 0)], M["dark"], p=2.0, subsurf=1)
pipes = []
for side in (-1, 1):
    for k in range(3):
        bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.04, radius2=0.045, depth=0.16)
        p = make_obj("Exhaust", bm, M["dark"]); p.rotation_euler = (0, math.radians(90), 0)
        p.location = (side * 0.5, 0.05 - k * 0.16, -0.12); pipes.append(p)
hub = bpy.data.objects.new("Prop", None); scn.collection.objects.link(hub); hub.location = (0, 0.66, 0)
spin = body("Spinner", [(0.0, 0.3, 0.3, 0), (0.12, 0.27, 0.27, 0), (0.24, 0.16, 0.16, 0), (0.3, 0.0, 0.0, 0)], M["metal"], p=2.0)
spin.parent = hub
for k in range(3):
    b = blade_loft("Blade", M["prop"], 0.1, 0.92, 0.17, 0.07, 38, 12, axis_rot=k * 2 * math.pi / 3)
    b.parent = hub; b.location = (0, 0.06, 0)
    tb = blade_loft("BladeTip", M["tip"], 0.86, 0.935, 0.088, 0.066, 13.5, 11.5, n=2, thick=0.105, axis_rot=k * 2 * math.pi / 3)
    tb.parent = hub; tb.location = (0, 0.06, 0)
root("part_prop", [cow, intake, hub] + pipes)

# ---------- REACTEUR ----------
nac = body("Nacelle", [(1.0, 0.84, 0.84, 0), (0.97, 0.92, 0.92, 0), (0.9, 0.96, 0.96, 0), (0.3, 0.98, 0.98, 0), (-0.6, 0.9, 0.9, 0), (-0.93, 0.74, 0.74, 0), (-0.97, 0.7, 0.7, 0)], M["paint"], p=2.0)
lip = body("Lip", [(1.0, 0.86, 0.86, 0), (1.02, 0.82, 0.82, 0), (1.0, 0.76, 0.76, 0)], M["metal"], p=2.0, subsurf=1)
inner = body("IntakeDuct", [(0.99, 0.76, 0.76, 0), (0.8, 0.72, 0.72, 0), (0.78, 0.0, 0.0, 0)], M["dark"], p=2.0, subsurf=1)
fan = bpy.data.objects.new("Fan", None); scn.collection.objects.link(fan); fan.location = (0, 0.8, 0)
fcone = body("FanCone", [(0.0, 0.22, 0.22, 0), (0.1, 0.16, 0.16, 0), (0.16, 0.0, 0.0, 0)], M["metal"], p=2.0); fcone.parent = fan
for k in range(18):
    b = blade_loft("FanBlade", M["metal"], 0.1, 0.36, 0.12, 0.09, 50, 30, n=3, thick=0.06, axis_rot=k * 2 * math.pi / 18)
    b.parent = fan
noz = body("Nozzle", [(-0.95, 0.72, 0.72, 0), (-1.1, 0.62, 0.62, 0), (-1.25, 0.52, 0.52, 0)], M["dark"], p=2.0, subsurf=1)
glow = body("Glow", [(-1.0, 0.5, 0.5, 0), (-1.02, 0.0, 0.0, 0)], M["glow"], p=2.0, subsurf=1)
tcone = body("TailCone", [(-0.9, 0.3, 0.3, 0), (-1.15, 0.18, 0.18, 0), (-1.3, 0.0, 0.0, 0)], M["metal"], p=2.0)
root("part_jet", [nac, lip, inner, fan, noz, glow, tcone])

# ---------- TRAIN D'ATTERRISSAGE ----------
def torus(name, R, r, mat_, seg=40, rs=16):
    bm = bmesh.new(); rings = []
    for i in range(seg):
        a = 2 * math.pi * i / seg; ring = []
        for j in range(rs):
            b = 2 * math.pi * j / rs; rad = R + r * math.cos(b)
            ring.append(bm.verts.new((r * math.sin(b) * 1.25, rad * math.cos(a), rad * math.sin(a))))
        rings.append(ring)
    for i in range(seg):
        A, B = rings[i], rings[(i + 1) % seg]
        for j in range(rs):
            bm.faces.new((A[j], A[(j + 1) % rs], B[(j + 1) % rs], B[j]))
    return make_obj(name, bm, mat_, subsurf=1)

tire_hub = bpy.data.objects.new("Tire", None); scn.collection.objects.link(tire_hub); tire_hub.location = (0, 0, -0.25)
tire = torus("TireRubber", 0.2, 0.095, M["rubber"]); tire.parent = tire_hub
bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=0.17, radius2=0.17, depth=0.15)
rim = make_obj("Rim", bm, M["metal"]); rim.rotation_euler = (0, math.radians(90), 0); rim.parent = tire_hub
bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=0.05, radius2=0.04, depth=0.62)
strut = make_obj("Strut", bm, M["metal"]); strut.location = (0.0, 0.0, 0.17)
bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=0.07, radius2=0.07, depth=0.22)
oleo = make_obj("Oleo", bm, M["dark"]); oleo.location = (0, 0, 0.38)
forks = []
for side in (-1, 1):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    fk = make_obj("Fork", bm, M["dark"], smooth=False); fk.scale = (0.03, 0.08, 0.3); fk.location = (side * 0.11, 0, -0.12); forks.append(fk)
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
yoke = make_obj("Yoke", bm, M["dark"], smooth=False); yoke.scale = (0.26, 0.09, 0.05); yoke.location = (0, 0, 0.04)
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
mount = make_obj("Mount", bm, M["paint"], smooth=False); mount.scale = (0.3, 0.36, 0.06); mount.location = (0, 0, 0.5)
root("part_wheel", [tire_hub, strut, oleo, yoke, mount] + forks)

# ---------- SAPIN ----------
random.seed(7)
bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.28, radius2=0.06, depth=9.0)
trunk = make_obj("Trunk", bm, M["bark"]); trunk.location = (0, 0, 4.5)
bm = bmesh.new()
for (z, rad, hgt) in [(1.8, 2.6, 3.6), (3.4, 2.2, 3.2), (4.9, 1.8, 2.9), (6.3, 1.4, 2.5), (7.6, 1.0, 2.1), (8.7, 0.6, 1.7)]:
    seg = 14; base = []; mid = []
    for i in range(seg):
        a = 2 * math.pi * i / seg + random.uniform(-0.1, 0.1); rr = rad * random.uniform(0.82, 1.12)
        base.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), z + random.uniform(-0.25, 0.1))))
    for i in range(seg):
        a = 2 * math.pi * (i + 0.5) / seg; rr = rad * 0.55
        mid.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), z + hgt * 0.42)))
    top = bm.verts.new((random.uniform(-0.08, 0.08), random.uniform(-0.08, 0.08), z + hgt))
    for i in range(seg):
        bm.faces.new((base[i], base[(i + 1) % seg], mid[i]))
        bm.faces.new((mid[i], base[(i + 1) % seg], mid[(i + 1) % seg]))
        bm.faces.new((mid[i], mid[(i + 1) % seg], top))
    bm.faces.new(base[::-1])
foliage = make_obj("Foliage", bm, M["needles"], smooth=True)
root("deco_tree", [trunk, foliage])

# ---------- HANGAR ----------
R0, L = 11.0, 26.0
rings = []
for k in range(3):
    y = -L / 2 + L * k / 2; ring = []
    for i in range(121):
        a = math.pi * i / 120; r = R0 + 0.07 * math.sin(i * math.pi / 2)
        ring.append((r * math.cos(a), y, r * math.sin(a)))
    rings.append(ring)
bm = bmesh.new(); RR = [[bm.verts.new(p) for p in r] for r in rings]
for a, b in zip(RR, RR[1:]):
    for i in range(120):
        bm.faces.new((a[i], a[i + 1], b[i + 1], b[i]))
shell = make_obj("Shell", bm, M["hangar"], smooth=True)
sol = shell.modifiers.new("Thick", 'SOLIDIFY'); sol.thickness = 0.15
bm = bmesh.new(); ctr = bm.verts.new((0, -L / 2, 0)); arc = []
for i in range(41):
    a = math.pi * i / 40; arc.append(bm.verts.new((R0 * math.cos(a), -L / 2, R0 * math.sin(a))))
for i in range(40):
    bm.faces.new((ctr, arc[i + 1], arc[i]))
back = make_obj("BackWall", bm, M["hangar"], smooth=False)
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
slab = make_obj("Slab", bm, M["concrete"], smooth=False); slab.scale = (26, 34, 0.3); slab.location = (0, 2, -0.15)
posts = []
for side in (-1, 1):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    d = make_obj("DoorPost", bm, M["dark"], smooth=False); d.scale = (0.5, 0.5, 9.5); d.location = (side * 9.2, L / 2, 4.75); posts.append(d)
root("deco_hangar", [shell, back, slab] + posts)

# ---------- EXPORT ----------
vl = bpy.context.view_layer
sizes = {}
for r in [o for o in scn.objects if o.parent is None]:
    objs = [r] + list(r.children_recursive)
    for o in scn.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    vl.objects.active = r
    fp = os.path.join(OUT, r.name.split("_", 1)[1] + ".glb")
    bpy.ops.export_scene.gltf(filepath=fp, export_format='GLB', use_selection=True, export_apply=True,
                              export_extras=True, export_yup=True, export_cameras=False, export_lights=False)
    sizes[r.name] = os.path.getsize(fp)
print("SKYFORGE_EXPORT", sizes)
