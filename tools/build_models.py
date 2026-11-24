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

# ================= NOUVELLES PIECES =================
M["orange"] = mat("Orange", (0.95, 0.38, 0.05), 0.1, 0.45)
M["canvas"] = mat("Canvas", (0.85, 0.85, 0.82), 0.0, 0.8)

# ---------- AILE DE PLANEUR (5 m, grand allongement) ----------
gm, gc = taper_wing("GliderWing", 5.0, 1.2, 0.5, 0.18, 0.76, 0.04, 0.4, 0.13)
root("part_wingLong", [gm, gc])

# ---------- PLAN CANARD (1,8 m, profil cambre) ----------
cst = [(-0.92, 0.27, 0.48, 0.5)] + [(x, 0.3, 0.55, 1.0) for x in (-0.9, -0.45, 0.0, 0.45, 0.9)] + [(0.92, 0.27, 0.48, 0.5)]
cm = surface("CanardMain", cst, 0.0, 0.68, 0.03, 0.4, 0.11, M["paint"])
cc = surface("CanardControl", [(x, 0.3, 0.55, 1.0) for x in (-0.9, -0.45, 0.0, 0.45, 0.9)], 0.692, 1.0, 0.03, 0.4, 0.11, M["accent"])
set_hinge(cc, Vector((0, 0.3 - 0.68 * 0.55, 0)), Vector((1, 0.3 - 0.68 * 0.55, 0)))
root("part_canard", [cm, cc])

# ---------- NEZ PROFILE ----------
nose = body("NoseCone", [(-0.5, 1, 1, 0), (-0.47, 1, 1, 0), (-0.1, 0.96, 0.96, 0), (0.2, 0.78, 0.78, 0), (0.42, 0.48, 0.48, 0), (0.56, 0.16, 0.16, 0), (0.6, 0.0, 0.0, 0)], M["paint"])
bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.018, radius2=0.012, depth=0.5)
pitot = make_obj("Pitot", bm, M["metal"]); pitot.rotation_euler = (math.radians(90), 0, 0); pitot.location = (0.0, 0.8, 0.0)
nring = body("NoseRing", [(-0.44, 1.012, 1.012, 0), (-0.36, 1.012, 1.012, 0)], M["accent"], subsurf=1)
root("part_nose", [nose, pitot, nring])

# ---------- RESERVOIR LARGABLE ----------
tank = body("TankBody", [(-1.0, 0.0, 0.0, 0), (-0.95, 0.18, 0.18, 0), (-0.75, 0.42, 0.42, 0), (-0.3, 0.55, 0.55, 0), (0.4, 0.55, 0.55, 0), (0.75, 0.42, 0.42, 0), (0.95, 0.16, 0.16, 0), (1.0, 0.0, 0.0, 0)], M["metal"], p=2.0)
tband = body("TankBand", [(0.05, 0.565, 0.565, 0), (0.15, 0.565, 0.565, 0)], M["orange"], p=2.0, subsurf=1)
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
pylon = make_obj("Pylon", bm, M["dark"], smooth=False); pylon.scale = (0.06, 0.8, 0.22); pylon.location = (0, 0, 0.36)
root("part_tank", [tank, tband, pylon])

# ---------- FLOTTEUR D'HYDRAVION ----------
flt = body("FloatHull", [(-1.6, 0.0, 0.0, 0.05), (-1.55, 0.2, 0.16, 0.05), (-1.2, 0.46, 0.4, 0.0), (-0.2, 0.6, 0.5, 0.0), (0.6, 0.6, 0.5, 0.0), (1.2, 0.52, 0.4, 0.06), (1.5, 0.34, 0.26, 0.14), (1.62, 0.0, 0.0, 0.2)], M["paint"], p=2.4)
fstripe = body("FloatStripe", [(-0.4, 0.612, 0.2, 0.06), (0.9, 0.612, 0.2, 0.06)], M["accent"], p=2.4, subsurf=1)
struts = []
for yy in (-0.6, 0.6):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.035, radius2=0.035, depth=0.75)
    s_ = make_obj("FloatStrut", bm, M["dark"]); s_.location = (0, yy, 0.6); struts.append(s_)
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
fmount = make_obj("FloatMount", bm, M["paint"], smooth=False); fmount.scale = (0.3, 1.5, 0.06); fmount.location = (0, 0, 0.98)
froot = root("part_float", [flt, fstripe, fmount] + struts)
froot.scale = (1.25, 1.4, 1.15)   # flotteur de 4,5 m : taille realiste pour un avion d'une tonne

# ---------- TURBOPROPULSEUR (4 pales, 2,4 m) ----------
tn = body("TurboNacelle", [(-1.1, 1.0, 1.0, 0), (-1.07, 1.0, 1.0, 0), (-0.5, 1.0, 1.04, 0), (0.3, 0.96, 1.0, -0.02), (0.75, 0.82, 0.84, 0), (0.95, 0.6, 0.6, 0), (1.0, 0.5, 0.5, 0)], M["paint"], p=2.3)
tin = body("TurboIntake", [(0.55, 0.0, 0.0, -0.46), (0.5, 0.36, 0.16, -0.45), (0.0, 0.38, 0.18, -0.46)], M["dark"], p=2.0, subsurf=1)
stacks = []
for side in (-1, 1):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.09, radius2=0.11, depth=0.28)
    sk = make_obj("TurboStack", bm, M["dark"]); sk.rotation_euler = (0, math.radians(90), 0); sk.location = (side * 0.5, 0.15, 0.05); stacks.append(sk)
thub = bpy.data.objects.new("Prop", None); scn.collection.objects.link(thub); thub.location = (0, 1.02, 0)
tsp = body("TurboSpinner", [(0.0, 0.48, 0.48, 0), (0.2, 0.42, 0.42, 0), (0.42, 0.24, 0.24, 0), (0.55, 0.0, 0.0, 0)], M["metal"], p=2.0); tsp.parent = thub
for k in range(4):
    b = blade_loft("TurboBlade", M["prop"], 0.15, 1.2, 0.24, 0.1, 42, 14, axis_rot=k * math.pi / 2); b.parent = thub; b.location = (0, 0.1, 0)
    tb = blade_loft("TurboBladeTip", M["tip"], 1.13, 1.215, 0.115, 0.095, 15, 13.5, n=2, thick=0.105, axis_rot=k * math.pi / 2); tb.parent = thub; tb.location = (0, 0.1, 0)
root("part_turboprop", [tn, tin, thub] + stacks)

# ---------- ROULETTE DE QUEUE ----------
th = bpy.data.objects.new("Tire", None); scn.collection.objects.link(th); th.location = (0, 0, -0.16)
ttire = torus("TailTire", 0.12, 0.06, M["rubber"], seg=32, rs=12); ttire.parent = th
bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=0.1, radius2=0.1, depth=0.09)
trim_ = make_obj("TailRim", bm, M["metal"]); trim_.rotation_euler = (0, math.radians(90), 0); trim_.parent = th
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
tfork = make_obj("TailFork", bm, M["dark"], smooth=False); tfork.scale = (0.16, 0.06, 0.22); tfork.location = (0, 0.02, 0.0)
bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=14, radius1=0.035, radius2=0.03, depth=0.3)
tpost = make_obj("TailPost", bm, M["metal"]); tpost.location = (0, 0, 0.2)
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
tmount = make_obj("TailMount", bm, M["paint"], smooth=False); tmount.scale = (0.2, 0.24, 0.05); tmount.location = (0, 0, 0.36)
root("part_tailwheel", [th, tfork, tpost, tmount])

# ---------- PARACHUTE DE CELLULE ----------
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
box = make_obj("ChuteBox", bm, M["paint"], smooth=False); box.scale = (0.5, 0.7, 0.26); box.location = (0, 0, 0)
bev = box.modifiers.new("Bevel", 'BEVEL'); bev.width = 0.05; bev.segments = 3
bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
lid = make_obj("ChuteLid", bm, M["orange"], smooth=False); lid.scale = (0.44, 0.64, 0.04); lid.location = (0, 0, 0.14)
bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.03, radius2=0.03, depth=0.14)
handle = make_obj("ChuteHandle", bm, M["accent"]); handle.rotation_euler = (0, math.radians(90), 0); handle.location = (0, 0.22, 0.19)
root("part_chute", [box, lid, handle])

# ================= VILLAGES (decor, origine au sol, avant = +Y) =================
M["plaster"] = mat("Plaster", (0.86, 0.83, 0.76), 0.0, 0.85)
M["stone"] = mat("Stone", (0.48, 0.45, 0.41), 0.0, 0.9)
M["wood"] = mat("Wood", (0.33, 0.2, 0.11), 0.0, 0.8)
M["barnred"] = mat("BarnRed", (0.45, 0.09, 0.06), 0.0, 0.75)
M["roofred"] = mat("RoofTiles", (0.55, 0.2, 0.12), 0.0, 0.7)
M["slate"] = mat("Slate", (0.17, 0.18, 0.2), 0.1, 0.6)
M["window"] = mat("Window", (0.08, 0.11, 0.14), 0.3, 0.15)
M["shutter"] = mat("Shutter", (0.15, 0.32, 0.2), 0.0, 0.6)
M["white"] = mat("SockWhite", (0.95, 0.95, 0.93), 0.0, 0.6)

def box(name, sx, sy, sz, loc, material, bevel=0.0):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    o = make_obj(name, bm, material, smooth=False); o.scale = (sx, sy, sz); o.location = loc
    if bevel:
        b = o.modifiers.new("Bevel", 'BEVEL'); b.width = bevel; b.segments = 2
    return o

def gable(name, w, l, h, z0, over, material, thick=0.18):
    bm = bmesh.new()
    W, L = w / 2 + over, l / 2 + over
    v = [bm.verts.new(p) for p in [(-W, -L, z0), (W, -L, z0), (W, L, z0), (-W, L, z0), (0, -L, z0 + h), (0, L, z0 + h)]]
    bm.faces.new((v[0], v[3], v[5], v[4])); bm.faces.new((v[1], v[4], v[5], v[2]))
    o = make_obj(name, bm, material, smooth=False)
    s = o.modifiers.new("Thick", 'SOLIDIFY'); s.thickness = thick
    return o

def gable_wall(name, w, l, h, z0, material):
    bm = bmesh.new()
    for y in (-l / 2, l / 2):
        a = bm.verts.new((-w / 2, y, z0)); b = bm.verts.new((w / 2, y, z0)); c = bm.verts.new((0, y, z0 + h))
        bm.faces.new((a, b, c))
    o = make_obj(name, bm, material, smooth=False)
    s = o.modifiers.new("Thick", 'SOLIDIFY'); s.thickness = 0.2
    return o

def windows_on(prefix, w, l, rows, cols, z0, dz, ww=0.9, wh=1.2, shutters=False):
    objs = []
    for r_ in range(rows):
        z = z0 + r_ * dz
        for side in (-1, 1):                       # facades longues (x = +-w/2)
            for c_ in range(cols):
                y = -l / 2 + l * (c_ + 0.5) / cols
                objs.append(box(prefix + "Win", 0.12, ww, wh, (side * w / 2, y, z), M["window"]))
                if shutters:
                    for s2 in (-1, 1):
                        objs.append(box(prefix + "Sh", 0.1, 0.38, wh, (side * (w / 2 + 0.02), y + s2 * (ww / 2 + 0.2), z), M["shutter"]))
    return objs

# chalet : rez de pierre, etage en bois, toit d'ardoise
ha = [box("ChaletBase", 8, 10, 3, (0, 0, 1.5), M["stone"]), box("ChaletUpper", 8.1, 10.1, 2.6, (0, 0, 4.3), M["wood"]),
      gable_wall("ChaletGable", 8.1, 10.1, 3.4, 5.6, M["wood"]), gable("ChaletRoof", 8.1, 10.1, 3.4, 5.6, 0.9, M["slate"]),
      box("ChaletDoor", 0.15, 1.2, 2.1, (4.02, -2.5, 1.05), M["wood"]), box("Chimney", 0.8, 0.8, 2.4, (2.0, 2.5, 8.2), M["stone"])]
ha += windows_on("Chalet", 8, 10, 2, 3, 1.6, 2.8, shutters=True)
root("deco_houseA", ha)

# maison enduite a deux niveaux, tuiles rouges
hb = [box("HouseWalls", 7, 9, 5.6, (0, 0, 2.8), M["plaster"]), gable_wall("HouseGable", 7, 9, 2.8, 5.6, M["plaster"]),
      gable("HouseRoof", 7, 9, 2.8, 5.6, 0.55, M["roofred"]), box("HouseDoor", 1.1, 0.15, 2.1, (0.8, 4.52, 1.05), M["wood"]),
      box("HouseBase", 7.2, 9.2, 0.5, (0, 0, 0.25), M["stone"])]
hb += windows_on("House", 7, 9, 2, 3, 1.5, 2.6, shutters=True)
root("deco_houseB", hb)

# grange rouge
br = [box("BarnWalls", 10, 14, 5, (0, 0, 2.5), M["barnred"]), gable_wall("BarnGable", 10, 14, 4.2, 5, M["barnred"]),
      gable("BarnRoof", 10, 14, 4.2, 5, 0.5, M["slate"]), box("BarnDoor", 4, 0.15, 4, (0, 7.02, 2), M["wood"]),
      box("BarnDoorX1", 4.2, 0.18, 0.25, (0, 7.05, 2), M["white"]), box("BarnLoft", 1.6, 0.15, 1.4, (0, 7.02, 6.4), M["wood"])]
root("deco_barn", br)

# eglise : nef, clocher, fleche
ch = [box("Nave", 9, 20, 8, (0, 0, 4), M["plaster"]), gable_wall("NaveGable", 9, 20, 5, 8, M["plaster"]),
      gable("NaveRoof", 9, 20, 5, 8, 0.5, M["slate"]),
      box("Tower", 4.6, 4.6, 17, (0, 11.8, 8.5), M["stone"]), box("TowerTop", 5.0, 5.0, 0.5, (0, 11.8, 17.2), M["stone"]),
      box("Belfry", 4.7, 4.7, 2.2, (0, 11.8, 14.6), M["window"]), box("ChurchDoor", 1.6, 0.2, 3, (0, 14.12, 1.5), M["wood"])]
bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=4, radius1=3.4, radius2=0.05, depth=9)
sp = make_obj("Spire", bm, M["slate"], smooth=False); sp.location = (0, 11.8, 21.9); sp.rotation_euler = (0, 0, math.radians(45))
ch.append(sp)
for i in range(4):
    for side in (-1, 1):
        ch.append(box("ChurchWin", 0.15, 1.2, 3.6, (side * 4.52, -7.5 + i * 5, 4.4), M["window"]))
root("deco_church", ch)

# tour de controle
tw = [box("TowerBase", 4, 4, 9, (0, 0, 4.5), M["plaster"]), box("TowerCab", 5.2, 5.2, 2.8, (0, 0, 10.4), M["window"]),
      box("TowerRoof", 5.8, 5.8, 0.4, (0, 0, 12.0), M["dark"]), box("TowerFloor", 5.6, 5.6, 0.3, (0, 0, 9.05), M["dark"]),
      box("TowerDoor", 1.1, 0.15, 2.1, (0, 2.02, 1.05), M["wood"])]
bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=0.05, radius2=0.03, depth=3)
ant = make_obj("Antenna", bm, M["metal"]); ant.location = (1.8, 1.8, 13.7); tw.append(ant)
root("deco_tower", tw)

# manche a air (rayee orange et blanc, orientee vers +Y)
ws = []
bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=0.08, radius2=0.06, depth=6)
pole = make_obj("SockPole", bm, M["metal"]); pole.location = (0, 0, 3); ws.append(pole)
for i in range(5):
    r0, r1 = 0.45 - i * 0.06, 0.45 - (i + 1) * 0.06
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=False, segments=16, radius1=r0, radius2=r1, depth=0.7)
    s_ = make_obj("Sock", bm, M["orange"] if i % 2 == 0 else M["white"]); s_.rotation_euler = (math.radians(-90), 0, 0)
    s_.location = (0, 0.35 + i * 0.7 + 0.1, 5.7); ws.append(s_)
root("deco_windsock", ws)

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
