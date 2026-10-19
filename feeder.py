#!/usr/bin/env python3
"""
Parametric AUTOMATIC RABBIT FEEDER  (CadQuery)
=============================================
Run:   python feeder.py            -> stl/*.stl, docs/assembly.png, docs/checks.md
Needs: pip install cadquery pillow numpy

Coordinate system of the ASSEMBLY (millimetres)
  origin = centre of the pocket wheel,   Y = wheel axis,   Z = up
  +X     = towards the rabbit pen (chute leaves the housing towards +X)
  -Y     = motor / electronics side,  +Y = bearing-cap side

Every dimension is a named variable in the PARAMETERS block below.  All parts
are modelled directly in assembly coordinates and re-oriented for printing in
PRINT_ORIENT (so the assembly render is always consistent with the STLs).
"""
import math
import os
import sys

import cadquery as cq
from cadquery import Vector as V

# =============================================================================
# PARAMETERS
# =============================================================================
# ---- food -------------------------------------------------------------------
pellet_diameter = 5.0            # mm
pellet_length_max = 15.0         # mm (8-15 mm, soft crumbly pellets)
bulk_density = 0.65              # g/ml

# ---- dosing -----------------------------------------------------------------
feed_times = ("07:00", "19:00")  # configurable in firmware
dose_default_g = 20.0
dose_min_g = 10.0
dose_max_g = 40.0
fed_g_per_day_max = 40.0         # used for the days-of-food estimate

# ---- printing / safety ------------------------------------------------------
print_volume = (220.0, 220.0, 250.0)
wall_min = 2.4                   # absolute minimum wall (unreachable parts)
wall_reach = 3.0                 # minimum wall on rabbit-reachable parts
wall = 4.0                       # standard structural wall used everywhere
ext_fillet = 1.5                 # fillet on reachable external edges
gap_forbidden = (6.0, 25.0)      # mm: toe/head entrapment window

# ---- pocket wheel -----------------------------------------------------------
wheel_od = 80.0                  # 70-80 mm
wheel_w = 28.0                   # axial width
n_pockets = 6
pocket_web = 4.0                 # constant web thickness between pockets
pocket_floor_r = 24.0            # radius of the pocket floor
wheel_side_wall = 3.0            # axial side walls of the wheel
pocket_w = wheel_w - 2 * wheel_side_wall      # axial pocket width (22)
wheel_clear = 0.7                # radial AND axial running clearance
pocket_rim_fillet = 1.5          # rounds the web crests (no pellet wedging)
shaft_d = 5.0                    # NEMA17 D-shaft
shaft_flat_across = 4.5          # across-flats dimension of the D
shaft_len = 24.0
hub_d = 16.0                     # hub boss carrying the D-bore
pin_d = 8.0                      # bearing pin on the cap (fits blind hole in wheel)
pin_clear = 0.3
magnet_d = 6.0                   # home magnet (disc)
magnet_h = 3.0
magnet_r = 20.0                  # radius at which the magnet sits

# ---- housing ----------------------------------------------------------------
housing_half = 45.5              # block is 2*housing_half square (XZ)
housing_back_wall = 8.0          # motor-side wall thickness
housing_corner_r = 8.0
cap_t = 8.0                      # bearing cap thickness
port_top_x = 30.0                # hopper outlet / top port (tangential)
port_bot_x = 40.0                # discharge port (>= pocket mouth)
insert_d = 4.2                   # M3 heat-set insert hole
insert_depth = 5.0
screw_clear_d = 3.4
tongue_gap = 4.0                 # tongue/groove around hopper port
tongue_w = 2.4
tongue_h = 1.8

# ---- motor mount (NEMA 17) --------------------------------------------------
nema_hole_pitch = 31.0
nema_pilot_d = 22.0
nema_len = 40.0
standoff_len = 14.0              # housing wall -> motor plate (hub grub screw access)
motor_plate_t = 5.0
motor_plate_size = 70.0
post_pos = 30.0                  # standoff posts at (+-post_pos, +-post_pos)
post_d = 9.0

# ---- hopper -----------------------------------------------------------------
hopper_volume_ml = 1200.0        # USABLE volume (up to the fill line)
hopper_d_in = 100.0              # inner diameter, >= 90 (wide mouth)
hop_wall = 3.8                   # horizontal wall offset (normal thickness >= 3.3)
funnel_h = 76.0
hopper_dx = -8.0                 # hopper axis offset away from the pen wall (x)
headroom = 24.0                  # space above fill line for the lid plug
flange_t = 5.0
flange_x = 84.0
flange_y = 52.0
flange_hole_x = 36.0
flange_hole_y = 12.0
hopper_lugs = 3
lug_depth = 4.0                  # radial protrusion of lugs
lug_ang = 40.0                   # hopper lug angular width
plug_lug_ang = 34.0
lid_t = 5.0
lid_gasket_w = 2.2               # groove for 2 mm cord
lid_gasket_d = 1.5
window_enabled = True
window_w = 8.0
window_strip_t = 1.0
window_strip_w = 14.0
sensor_pad = True                # low-food sensor pad on hopper wall

# ---- chute ------------------------------------------------------------------
chute_angle = 60.0               # deg above horizontal (>=60 satisfies both readings)
chute_in = 40.0                  # internal square section (35-40)
chute_wall = 4.0
chute_x0 = 3.0                   # chute axis x at the housing underside
drop_height = 80.0               # chute outlet -> bowl floor (60-100)

# ---- cage interface ---------------------------------------------------------
plate_t = 4.0                    # bracket plate
cage_wall_t = 5.0                # thickness of the pen wall / bars
base_gap = 2.0                   # pen wall -> bowl base
plate_y = 150.0
plate_zmax = 33.0
plate_zmin_margin = 5.0
plate_hole_clear = 0.4

# ---- bowl (change for dwarf / giant rabbits) --------------------------------
bowl_diameter = 140.0            # inner diameter at the brim (130-150)
bowl_depth = 45.0                # inner depth at the brim (40-50)
rim_height = 32.0                # rabbit-facing rim height above the ground
bowl_floor_t = 4.0
bowl_wall = 4.0
bowl_foot_d = 100.0              # flat foot diameter
bowl_notch_w = 80.0
bowl_screw_r = 40.0              # M4 heat-set inserts in the bowl foot
bowl_rim_fillet = 1.5

# ---- bowl base --------------------------------------------------------------
base_ratio = 1.2                 # base diameter / bowl diameter (>= 1.2)
base_t = 16.0
base_recess_depth = 10.0
base_recess_clear = 4.4          # radial clearance foot -> recess wall
weight_d = 106.0                 # steel weight plate
weight_t = 3.2
steel_density = 7.85             # g/cm3

# ---- electronics enclosure --------------------------------------------------
enc_wall = 3.0
enc_frame_t = 6.0
enc_extra = 30.0                 # space behind the motor for the boards
lid_enc_t = 4.0
board_w, board_h = 70.0, 50.0    # perfboard that carries ESP32/RTC/driver
board_hole_dx, board_hole_dy = 64.0, 44.0

# ---- derived ----------------------------------------------------------------
R_w = wheel_od / 2
R_i = R_w + wheel_clear
Y_in = wheel_w / 2 + wheel_clear
Y_back = -(Y_in + housing_back_wall)             # outer face of motor-side wall
Y_cap = Y_in + cap_t
HB = housing_half
tan_a = math.tan(math.radians(chute_angle))
sin_a = math.sin(math.radians(chute_angle))
cos_a = math.cos(math.radians(chute_angle))
base_d = base_ratio * bowl_diameter
base_r = base_d / 2
hub_end_y = Y_back - 8.0                         # hub protrudes 8 mm past the wall
hub_len = (-wheel_w / 2) - hub_end_y             # hub length from wheel face
motor_plate_y1 = Y_back - standoff_len           # +Y face of the motor plate
motor_plate_y0 = motor_plate_y1 - motor_plate_t  # -Y face (motor face)
shaft_tip_y = motor_plate_y0 + shaft_len
enc_len = standoff_len + motor_plate_t + nema_len + enc_extra
enc_y_end = Y_back - enc_len                     # open end of the enclosure tube

# geometry of the cage side ----------------------------------------------------
x_plate0 = HB
x_plate1 = HB + plate_t
x_base_edge = x_plate1 + cage_wall_t + base_gap
x_bowl = x_base_edge + base_r                    # bowl / outlet centre X
dz_chute = (x_bowl - chute_x0) * tan_a           # vertical drop of the chute
z_chute_top = -HB                                # housing underside
z_out = z_chute_top - dz_chute                   # chute outlet plane
# bowl numbers
bowl_foot_z_above_ground = (base_t - base_recess_depth) + weight_t   # 9.2
bowl_apex_above_ground = bowl_foot_z_above_ground + bowl_floor_t
z_floor = z_out - drop_height                    # bowl inner floor (apex)
z_ground = z_floor - bowl_apex_above_ground
z_bowl_foot = z_ground + bowl_foot_z_above_ground

# =============================================================================
# SMALL HELPERS
# =============================================================================
ORI = V(0, 0, 0)
AX_X, AX_Y, AX_Z = V(1, 0, 0), V(0, 1, 0), V(0, 0, 1)


def W(shape):
    return cq.Workplane("XY").newObject([shape])


def box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def cylX(r, x0, x1, y=0.0, z=0.0):
    return cq.Solid.makeCylinder(r, x1 - x0, V(x0, y, z), AX_X)


def cylY(r, y0, y1, x=0.0, z=0.0):
    return cq.Solid.makeCylinder(r, y1 - y0, V(x, y0, z), AX_Y)


def cylZ(r, z0, z1, x=0.0, y=0.0):
    return cq.Solid.makeCylinder(r, z1 - z0, V(x, y, z0), AX_Z)


def U(a, *b):
    return a.fuse(*b).clean() if b else a


def D(a, *b):
    return a.cut(*b).clean() if b else a


def I(a, b):
    return a.intersect(b).clean()


def fil(shape, r, selector):
    return W(shape).edges(selector).fillet(r).val()


def rot(shape, axis, deg):
    return shape.rotate(ORI, axis, deg)


def vol_ml(shape):
    return shape.Volume() / 1000.0


def ring_xy(ox, oy, ix, iy, z0, z1):
    """rectangular ring (outer ox x oy, inner ix x iy), centred on the origin"""
    return D(box(-ox / 2, ox / 2, -oy / 2, oy / 2, z0, z1),
             box(-ix / 2, ix / 2, -iy / 2, iy / 2, z0 - 1, z1 + 1))


def insert_holes_z(pts, z_face, direction):
    """vertical insert holes starting at z_face, going direction (+1 up / -1 down)"""
    out = []
    for (x, y) in pts:
        if direction < 0:
            out.append(cylZ(insert_d / 2, z_face - insert_depth, z_face + 1, x, y))
        else:
            out.append(cylZ(insert_d / 2, z_face - 1, z_face + insert_depth, x, y))
    return out


def insert_holes_y(pts, y_face, direction):
    """insert holes along Y from y_face; pts = (x,z); direction +1 -> into +Y"""
    out = []
    for (x, z) in pts:
        if direction > 0:
            out.append(cylY(insert_d / 2, y_face - 1, y_face + insert_depth, x, z))
        else:
            out.append(cylY(insert_d / 2, y_face - insert_depth, y_face + 1, x, z))
    return out


# =============================================================================
# 4. POCKET WHEEL
# =============================================================================
def pocket_prism(r_out):
    """wedge-shaped pocket (constant web between neighbours), centred on +Z"""
    half = math.radians(180.0 / n_pockets)
    a = (pocket_web / 2) / math.sin(half)            # apex shift for constant web
    L = r_out + 30
    pts = [(0, a), (L * math.sin(half), a + L * math.cos(half)),
           (-L * math.sin(half), a + L * math.cos(half))]
    prism = cq.Workplane("XZ").polyline(pts).close().extrude(pocket_w / 2, both=True).val()
    ring = D(cylY(r_out, -pocket_w, pocket_w), cylY(pocket_floor_r, -pocket_w, pocket_w))
    return I(prism, ring)


def d_bore(y0, y1):
    """D-shaped bore for the 5 mm D-shaft, flat on the +X side"""
    r = shaft_d / 2 + 0.1
    flat_x = shaft_d / 2 - (shaft_d - shaft_flat_across) + 0.1
    return I(cylY(r, y0, y1), box(-r - 1, flat_x, y0 - 1, y1 + 1, -r - 1, r + 1))


def wheel():
    blank = cylY(R_w, -wheel_w / 2, wheel_w / 2)
    pockets = [rot(pocket_prism(R_w + 6), AX_Y, k * 360.0 / n_pockets) for k in range(n_pockets)]
    body = D(blank, *pockets)
    # round the crest of the webs so a pellet fragment can not wedge
    crest = [e for e in body.Edges()
             if e.geomType() == "LINE"
             and abs(e.endPoint().y - e.startPoint().y) > pocket_w * 0.9
             and abs(math.hypot(e.Center().x, e.Center().z) - R_w) < 0.3]
    body = body.fillet(pocket_rim_fillet, crest)
    hub = cylY(hub_d / 2, hub_end_y, -wheel_w / 2 + 0.5)
    w = U(body, hub)
    cuts = [d_bore(hub_end_y - 1, hub_end_y + 15),
            cylX(1.3, 0, hub_d / 2 + 1, y=hub_end_y + 4.0),            # grub screw (M3 tap)
            cylY((pin_d + 2 * pin_clear) / 2, wheel_w / 2 - 6.0, wheel_w / 2 + 1),   # bearing pin hole
            cylY(magnet_d / 2 + 0.1, -wheel_w / 2 - 1, -wheel_w / 2 + magnet_h + 0.2, z=magnet_r)]
    return D(w, *cuts)


def pocket_volume_ml(w):
    blank = cylY(R_w, -wheel_w / 2, wheel_w / 2)
    bore_hub = 0.0
    removed = blank.Volume() - (w.Volume() - hub_vol_outside_blank(w))
    return removed / n_pockets / 1000.0


def hub_vol_outside_blank(w):
    # volume of the hub that lies outside the wheel disc, minus bore + grub screw hole
    outside = I(w, cylY(R_w + 5, hub_end_y - 1, -wheel_w / 2 - 0.0001))
    return outside.Volume()


# =============================================================================
# 3. WHEEL HOUSING (+ bearing cap)
# =============================================================================
def housing():
    body = box(-HB, HB, Y_back, Y_in, -HB, HB)
    body = fil(body, housing_corner_r, "|Y")
    cuts = [cylY(R_i, -Y_in, Y_in + 1),
            cylY(hub_d / 2 + 0.4, Y_back - 1, -Y_in + 0.5),
            box(-port_top_x / 2, port_top_x / 2, -pocket_w / 2, pocket_w / 2, 0, HB + 1),
            box(-port_bot_x / 2, port_bot_x / 2, -pocket_w / 2, pocket_w / 2, -HB - 1, 0)]
    # M3 heat-set inserts: top flange, bottom flange, cap (+Y face), enclosure/motor posts (-Y face)
    fl = [(sx * flange_hole_x, sy * flange_hole_y) for sx in (-1, 1) for sy in (-1, 1)]
    cuts += insert_holes_z(fl, HB, -1)
    cuts += insert_holes_z(fl, -HB, +1)
    corner = [(sx * 39.0, sz * 39.0) for sx in (-1, 1) for sz in (-1, 1)]
    cuts += insert_holes_y(corner, Y_in, -1)
    cuts += insert_holes_y(corner, Y_back, +1)                       # enclosure frame screws
    posts = [(sx * post_pos, sz * post_pos) for sx in (-1, 1) for sz in (-1, 1)]
    cuts += insert_holes_y(posts, Y_back, +1)                        # motor-mount posts
    # bracket plate screws into the +X face
    plate_pts = [(sy * 12.0, sz * 27.0) for sy in (-1, 1) for sz in (-1, 1)]
    for (y, z) in plate_pts:
        cuts.append(cylX(insert_d / 2, HB - insert_depth, HB + 1, y, z))
    # reed-switch pocket in the outer face of the motor-side wall
    cuts.append(box(-2.6, 2.6, Y_back - 1, Y_back + 5.0, magnet_r - 8, magnet_r + 8))
    h = D(body, *cuts)
    tongue = ring_xy(port_top_x + 2 * (tongue_gap + tongue_w), pocket_w + 2 * (tongue_gap + tongue_w),
                     port_top_x + 2 * tongue_gap, pocket_w + 2 * tongue_gap, HB - 0.01, HB + tongue_h)
    return U(h, tongue)


def bearing_cap():
    plate = fil(box(-HB, HB, Y_in, Y_cap, -HB, HB), housing_corner_r, "|Y")
    pin = cylY(pin_d / 2, Y_in - 5.7, Y_in + 0.5)
    holes = [cylY(screw_clear_d / 2, Y_in - 1, Y_cap + 1, sx * 39.0, sz * 39.0)
             for sx in (-1, 1) for sz in (-1, 1)]
    return D(U(plate, pin), *holes)


# =============================================================================
# 5. MOTOR MOUNT (plate + standoff posts)
# =============================================================================
def motor_mount():
    h = motor_plate_size / 2
    plate = fil(box(-h, h, motor_plate_y0, motor_plate_y1, -h, h), 4.0, "|Y")
    posts = [cylY(post_d / 2, motor_plate_y1 - 0.01, Y_back + 0.0, sx * post_pos, sz * post_pos)
             for sx in (-1, 1) for sz in (-1, 1)]
    m = U(plate, *posts)
    cuts = [cylY(nema_pilot_d / 2 + 0.4, motor_plate_y0 - 1, motor_plate_y1 + 1)]
    for sx in (-1, 1):
        for sz in (-1, 1):
            cuts.append(cylY(1.7, motor_plate_y0 - 1, motor_plate_y1 + 1,
                             sx * nema_hole_pitch / 2, sz * nema_hole_pitch / 2))
            cuts.append(cylY(screw_clear_d / 2, motor_plate_y0 - 1, Y_back + 1,
                             sx * post_pos, sz * post_pos))
    return D(m, *cuts)


# =============================================================================
# 1. HOPPER BODY
# =============================================================================
z_f0 = HB + flange_t                      # funnel start (outlet)
z_f1 = z_f0 + funnel_h                    # funnel end / cylinder start


def _funnel(off):
    return (cq.Workplane("XY").workplane(offset=z_f0)
            .rect(port_top_x + 2 * off, pocket_w + 2 * off)
            .workplane(offset=funnel_h).center(hopper_dx, 0).circle(hopper_d_in / 2 + off).loft(combine=True).val())


V_funnel_ml = vol_ml(_funnel(0.0))
cyl_h = (hopper_volume_ml * 1000.0 - V_funnel_ml * 1000.0) / (math.pi * (hopper_d_in / 2) ** 2)
z_fill = z_f1 + cyl_h
z_rim = z_fill + headroom
r_hi = hopper_d_in / 2
r_ho = r_hi + hop_wall


def hopper():
    dx = V(hopper_dx, 0, 0)
    outer = U(_funnel(hop_wall), cylZ(r_ho, z_f1, z_rim).translate(dx))
    flange = box(-flange_x / 2, flange_x / 2, -flange_y / 2, flange_y / 2, HB, HB + flange_t)
    h = U(outer, flange)
    cuts = [_funnel(0.0), cylZ(r_hi, z_f1, z_rim + 1).translate(dx),
            box(-port_top_x / 2, port_top_x / 2, -pocket_w / 2, pocket_w / 2, HB - 1, z_f0 + 1)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            cuts.append(cylZ(screw_clear_d / 2, HB - 1, HB + flange_t + 1, sx * flange_hole_x, sy * flange_hole_y))
    # tongue-and-groove (groove in the flange underside, 0.4 mm clearance per side)
    cuts.append(ring_xy(port_top_x + 2 * (tongue_gap + tongue_w) + 0.8, pocket_w + 2 * (tongue_gap + tongue_w) + 0.8,
                        port_top_x + 2 * tongue_gap - 0.8, pocket_w + 2 * tongue_gap - 0.8,
                        HB - 0.01, HB + tongue_h + 0.4))
    h = D(h, *cuts)
    # inward bayonet lugs near the rim
    lugs = []
    gap_c = 360.0 / hopper_lugs
    for k in range(hopper_lugs):
        a0 = 90.0 + k * gap_c - lug_ang / 2
        lugs.append(_ring_sector(r_hi - lug_depth, r_hi + 0.5, a0, a0 + lug_ang, z_rim - 9.0, z_rim - 4.0).translate(dx))
    h = U(h, *lugs)
    # fill-level window (slot + recess for a clear strip) on the -X (outside) face
    if window_enabled:
        z0w, z1w = z_f1 + 10.0, z_fill - 8.0
        slot = box(-r_ho - 2, -r_hi + 1, -window_w / 2, window_w / 2, z0w, z1w)
        recess = I(D(cylZ(r_ho + 1, z0w - 2, z1w + 2), cylZ(r_ho - window_strip_t, z0w - 3, z1w + 3)),
                   box(-r_ho - 3, 0, -window_strip_w / 2, window_strip_w / 2, z0w - 2, z1w + 2))
        h = D(h, slot.translate(dx), recess.translate(dx))
    # low-food sensor pad (capacitive sensor module glued in the pocket), -Y side
    if sensor_pad:
        zs = z_f1 + 16.0
        yb = -(r_ho + 3.0)
        pad = box(-14, 14, yb, -(r_hi + 1.0), zs - 17, zs + 17).translate(dx)
        pocket = box(-10, 10, yb - 1, -(r_hi + wall_min + 0.2), zs - 13, zs + 13).translate(dx)
        h = D(U(h, pad), pocket)
    return h


def _ring_sector(r0, r1, a0, a1, z0, z1):
    """annular sector from angle a0..a1 (deg, from +X, CCW) between z0..z1"""
    ring = D(cylZ(r1, z0, z1), cylZ(r0, z0 - 1, z1 + 1))
    n = 12
    pts = [(0, 0)] + [((r1 + 5) * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                       (r1 + 5) * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
    wedge = cq.Workplane("XY").workplane(offset=z0 - 1).polyline(pts).close().extrude(z1 - z0 + 2).val()
    return I(ring, wedge)


# =============================================================================
# 2. HOPPER LID (bayonet plug, gasket groove, grip ribs, finger dishes)
# =============================================================================
def hopper_lid():
    z0 = z_rim
    disc = cylZ(r_ho, z0, z0 + lid_t)
    plug_r = r_hi - lug_depth - 0.6
    plug = D(cylZ(plug_r, z0 - 16.0, z0 + 0.01), cylZ(plug_r - 5.5, z0 - 17.0, z0 + 0.0))
    lugs = []
    gap_c = 360.0 / hopper_lugs
    for k in range(hopper_lugs):
        c = 30.0 + k * gap_c                       # insertion angle (between hopper lugs)
        lugs.append(_ring_sector(plug_r - 0.5, r_hi - 0.3, c - plug_lug_ang / 2, c + plug_lug_ang / 2,
                                 z0 - 13.5, z0 - 10.0))
    lid = U(disc, plug, *lugs)
    cuts = []
    # gasket groove on the underside, on the rim contact ring
    g_r = (r_hi + r_ho) / 2
    cuts.append(D(cylZ(g_r + lid_gasket_w / 2, z0 - 0.01, z0 + lid_gasket_d),
                  cylZ(g_r - lid_gasket_w / 2, z0 - 1, z0 + lid_gasket_d + 1)))
    # two finger dishes on top
    for sx in (-1, 1):
        dish = cq.Solid.makeSphere(22.0, V(sx * 30.0, 0, z0 + lid_t + 22.0 - 2.2), AX_Z, -90, 90, 360)
        cuts.append(dish)
    lid = D(lid, *cuts)
    # grip ribs on the rim (shallow, rounded - flush rim, nothing to lever)
    ribs = []
    for k in range(24):
        a = math.radians(k * 15.0)
        ribs.append(cylZ(0.8, z0 + 0.5, z0 + lid_t - 0.5, (r_ho - 0.1) * math.cos(a), (r_ho - 0.1) * math.sin(a)))
    lid = D(lid, *ribs)
    return lid.translate(V(hopper_dx, 0, 0))


# =============================================================================
# 6. CHUTE (single piece, flange down when printed)
# =============================================================================
def _tube(half, s0, s1):
    """square tube envelope of half-width `half` along the chute axis"""
    t = box(s0, s1, -half, half, -half, half)
    t = rot(t, AX_Y, chute_angle)
    return t.translate(V(chute_x0, 0, z_chute_top))


def chute(for_plate_cut=False):
    L = dz_chute / sin_a
    oh = chute_in / 2 + chute_wall
    outer = I(_tube(oh, -80, L + 80), box(-300, 300, -300, 300, z_out, z_chute_top))
    flange = box(-flange_x / 2, flange_x / 2, -flange_y / 2, flange_y / 2, z_chute_top - flange_t, z_chute_top)
    c = U(outer, flange)
    cuts = [_tube(chute_in / 2, -80, L + 80)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            cuts.append(cylZ(screw_clear_d / 2, z_chute_top - flange_t - 1, z_chute_top + 1,
                             sx * flange_hole_x, sy * flange_hole_y))
    return D(c, *cuts)


def chute_flap():
    """TPU sleeve with a living-hinge flap that closes the outlet (prevents anything entering from the bowl)"""
    oh = chute_in / 2 + chute_wall
    L = dz_chute / sin_a
    sleeve_len = 16.0
    sl_outer = I(_tube(oh + 1.6, L - sleeve_len / sin_a - 10, L + 80),
                 box(-300, 300, -300, 300, z_out, z_out + sleeve_len))
    sl = D(sl_outer, _tube(oh - 0.4, -80, L + 120))
    # flap: 1.2 mm plate under the outlet hinged on the -X edge by a 0.6 mm film
    xc = x_bowl
    w_x = (chute_in + 2 * chute_wall) / sin_a   # horizontal width of outlet
    flap = box(xc - w_x / 2 + 1.0, xc + w_x / 2 - 1.0, -(oh - 1.0), oh - 1.0, z_out - 1.2, z_out)
    film = box(xc - w_x / 2 - 0.5, xc - w_x / 2 + 1.5, -(oh - 6.0), oh - 6.0, z_out - 0.6, z_out)
    return U(sl, flap, film)


# =============================================================================
# 10. BRACKET PLATE (cage interface)  - chute passes through a slanted hole
# =============================================================================
def bracket():
    s_mid = (x_plate0 + plate_t / 2 - chute_x0) / cos_a          # axis parameter at the plate mid-plane
    z_cross = z_chute_top - s_mid * sin_a
    oh = chute_in / 2 + chute_wall + plate_hole_clear
    z_bot = z_cross - oh / cos_a - (plate_t / 2) * tan_a - plate_zmin_margin
    plate = fil(box(x_plate0, x_plate1, -plate_y / 2, plate_y / 2, z_bot, plate_zmax), 8.0, "|X")
    cuts = [_tube(oh, -200, 400)]
    for (y, z) in [(sy * 12.0, sz * 27.0) for sy in (-1, 1) for sz in (-1, 1)]:
        cuts.append(cylX(screw_clear_d / 2, x_plate0 - 1, x_plate1 + 1, y, z))
    # slots for zip-ties / cage hooks (5 x 14 mm: nothing between 6 and 25 mm)
    for y in (-60.0, 60.0):
        for z in (z_cross + 60.0, z_cross, z_cross - 60.0):
            if z_bot + 12 < z < plate_zmax - 12:
                cuts.append(box(x_plate0 - 1, x_plate1 + 1, y - 2.5, y + 2.5, z - 7, z + 7))
    return D(plate, *cuts)


# =============================================================================
# 8. BOWL, 9. BASE
# =============================================================================
bowl_r = bowl_diameter / 2
R_cap = (bowl_r ** 2 + bowl_depth ** 2) / (2 * bowl_depth)      # spherical cavity radius
bowl_zc = bowl_floor_t + R_cap
bowl_ztop = bowl_floor_t + bowl_depth
bowl_rout_rim = math.sqrt((R_cap + bowl_wall) ** 2 - (bowl_zc - bowl_ztop) ** 2)
bowl_front_z = rim_height - bowl_foot_z_above_ground            # notch floor (bowl local z)


def _bowl_local():
    outer = (cq.Workplane("XZ").polyline([(0, 0), (bowl_foot_d / 2, 0), (bowl_rout_rim, bowl_ztop), (0, bowl_ztop)])
             .close().revolve(360, (0, 0, 0), (0, 1, 0)).val())
    sph = cq.Workplane("XY").sphere(R_cap).val().translate(V(0, 0, bowl_zc))
    cav = I(sph, box(-R_cap - 1, R_cap + 1, -R_cap - 1, R_cap + 1, bowl_floor_t - 1, bowl_ztop + 3))
    return outer, cav


def bowl_cavity_volume_ml():
    _, cav = _bowl_local()
    return vol_ml(I(cav, box(-R_cap - 1, R_cap + 1, -R_cap - 1, R_cap + 1, 0, bowl_ztop)))


def bowl():
    outer, cav = _bowl_local()
    b = D(outer, cav)
    top = [e for e in b.Edges() if abs(e.Center().z - bowl_ztop) < 0.05]
    b = b.fillet(bowl_rim_fillet, top)
    # low rabbit-facing rim: U-shaped notch
    cutter = box(0, bowl_rout_rim + 10, -bowl_notch_w / 2, bowl_notch_w / 2, bowl_front_z, bowl_ztop + 5)
    cutter = fil(cutter, min(12.0, (bowl_ztop - bowl_front_z) * 0.45), "|X and <Z")
    b = D(b, cutter)
    edges = [e for e in b.Edges()
             if e.Center().x > 20 and bowl_front_z - 0.1 < e.Center().z < bowl_ztop - 0.1 and abs(e.Center().z - bowl_ztop) > 0.2
             and e.geomType() in ("LINE", "CIRCLE", "BSPLINE", "ELLIPSE")]
    for r in (1.5, 1.0, 0.6):
        try:
            b = b.fillet(r, edges)
            break
        except Exception:
            continue
    # M4 heat-set inserts in the foot
    ins = [cylZ(2.8, -1, 8.0, bowl_screw_r * math.cos(math.radians(a)), bowl_screw_r * math.sin(math.radians(a)))
           for a in (90, 210, 330)]
    return D(b, *ins)


def bowl_base():
    disc = cylZ(base_r, 0, base_t)
    disc = fil(disc, 4.0, ">Z")
    disc = fil(disc, 1.0, "<Z")
    recess_r = bowl_foot_d / 2 + base_recess_clear
    cuts = [cylZ(recess_r, base_t - base_recess_depth, base_t + 1)]
    for a in (90, 210, 330):
        x, y = bowl_screw_r * math.cos(math.radians(a)), bowl_screw_r * math.sin(math.radians(a))
        cuts.append(cylZ(2.3, -1, base_t, x, y))
        cuts.append(cylZ(4.4, -1, 2.2, x, y))                        # counterbore for M4 flat head
    return D(disc, *cuts)


# =============================================================================
# 7. ELECTRONICS ENCLOSURE (+ lid)
# =============================================================================
def enclosure():
    o = HB
    i = HB - enc_wall
    y0, y1 = enc_y_end, Y_back
    tube = D(fil(box(-o, o, y0, y1, -o, o), 8.0, "|Y"), fil(box(-i, i, y0 - 1, y1 + 1, -i, i), 5.0, "|Y"))
    # inner frame at the housing end (screws into the housing inserts)
    frame = D(box(-i - 0.5, i + 0.5, y1 - enc_frame_t, y1, -i - 0.5, i + 0.5),
              box(-36, 36, y1 - enc_frame_t - 1, y1 + 1, -36, 36))
    cols = []
    for (cx, cz) in ((0, i - 3.5), (0, -(i - 3.5)), (i - 3.5, 0), (-(i - 3.5), 0)):
        cols.append(box(cx - 5, cx + 5, y0, y1 - enc_frame_t + 0.5, cz - 3.5 if cx == 0 else cz - 5,
                        cz + 3.5 if cx == 0 else cz + 5) if cx == 0 else
                    box(cx - 3.5, cx + 3.5, y0, y1 - enc_frame_t + 0.5, cz - 5, cz + 5))
    e = U(tube, frame, *cols)
    cuts = []
    for sx in (-1, 1):
        for sz in (-1, 1):
            cuts.append(cylY(screw_clear_d / 2, y1 - enc_frame_t - 1, y1 + 1, sx * 39.0, sz * 39.0))
    for (cx, cz) in ((0, i - 3.5), (0, -(i - 3.5)), (i - 3.5, 0), (-(i - 3.5), 0)):
        cuts.append(cylY(1.3, y0 - 1, y0 + 14, cx, cz))                  # lid screws (M3 self tap)
    yg = y0 + 45.0
    cuts.append(cylX(6.3, -o - 1, -i + 1, y=yg, z=20.0))                 # power cable gland (PG7)
    cuts.append(cylX(4.6, -o - 1, -i + 1, y=yg, z=-20.0))                # sensor cable gland (PG... 9 mm)
    cuts.append(box(-4.0, 4.0, Y_back - 1, Y_back + 1, -4, 4))           # (clearance only)
    return D(e, *cuts)


def enclosure_lid():
    o, i = HB, HB - enc_wall
    y0 = enc_y_end
    plate = fil(box(-o, o, y0 - lid_enc_t, y0, -o, o), 8.0, "|Y")
    bosses = [cylY(3.5, y0 - 0.01, y0 + 6.0, sx * board_hole_dx / 2, sz * board_hole_dy / 2)
              for sx in (-1, 1) for sz in (-1, 1)]
    lid = U(plate, *bosses)
    cuts = []
    # gasket groove (2 mm cord / foam) centred on the 3 mm enclosure wall land
    mid = o - enc_wall / 2
    g_out = fil(box(-(mid + 0.9), mid + 0.9, y0 - 1.2, y0 + 1, -(mid + 0.9), mid + 0.9), 7.4, "|Y")
    g_in = fil(box(-(mid - 0.9), mid - 0.9, y0 - 2.2, y0 + 2, -(mid - 0.9), mid - 0.9), 5.6, "|Y")
    cuts.append(D(g_out, g_in))
    for (cx, cz) in ((0, i - 3.5), (0, -(i - 3.5)), (i - 3.5, 0), (-(i - 3.5), 0)):
        cuts.append(cylY(screw_clear_d / 2, y0 - lid_enc_t - 1, y0 + 1, cx, cz))
    for sx in (-1, 1):
        for sz in (-1, 1):
            cuts.append(cylY(1.3, y0 - 1, y0 + 7.0, sx * board_hole_dx / 2, sz * board_hole_dy / 2))
    cuts.append(cylY(6.1, y0 - lid_enc_t - 1, y0 + 4, -25.0, 34.0))      # feed-now button (12 mm)
    cuts.append(cylY(2.6, y0 - lid_enc_t - 1, y0 + 4, 15.0, 34.0))       # status LED
    cuts.append(cylY(2.6, y0 - lid_enc_t - 1, y0 + 4, 28.0, 34.0))       # low-food LED
    return D(lid, *cuts)


# =============================================================================
# PART TABLE
# =============================================================================
def build_all():
    P = {}
    P["01_hopper_body"] = hopper()
    P["02_hopper_lid"] = hopper_lid()
    P["03_wheel_housing"] = housing()
    P["03b_bearing_cap"] = bearing_cap()
    P["04_pocket_wheel"] = wheel()
    P["05_motor_mount"] = motor_mount()
    P["06_chute"] = chute()
    P["06b_chute_flap_TPU"] = chute_flap()
    P["07_enclosure"] = enclosure()
    P["07b_enclosure_lid"] = enclosure_lid()
    P["08_bowl"] = None   # bowl is modelled in local coordinates, placed below
    P["09_bowl_base"] = None
    P["10_wall_bracket"] = bracket()
    bw = bowl().translate(V(x_bowl, 0, z_bowl_foot))
    bs = bowl_base().translate(V(x_bowl, 0, z_ground))
    P["08_bowl"] = bw
    P["09_bowl_base"] = bs
    return P


# print orientation: (axis, degrees) applied to the assembly-pose shape, then dropped on the bed
PRINT_ORIENT = {
    "01_hopper_body": None,                       # outlet flange on the bed
    "02_hopper_lid": (AX_X, 180),                 # top face on the bed, plug up
    "03_wheel_housing": (AX_X, 90),               # motor-side wall on the bed, bore vertical
    "03b_bearing_cap": (AX_X, -90),               # outer face down, pin up
    "04_pocket_wheel": (AX_X, 90),                # pin-hole face down, hub up (y -> z)
    "05_motor_mount": (AX_X, 90),                 # motor face down, posts up
    "06_chute": (AX_X, 180),                      # flange mating face on the bed
    "06b_chute_flap_TPU": (AX_X, 180),
    "07_enclosure": (AX_X, -90),                  # housing-side frame on the bed
    "07b_enclosure_lid": (AX_X, 90),
    "08_bowl": None,
    "09_bowl_base": None,
    "10_wall_bracket": (AX_Y, -90),               # lie flat
}


def to_print(name, shape):
    o = PRINT_ORIENT[name]
    s = shape if o is None else rot(shape, o[0], o[1])
    bb = s.BoundingBox()
    cx, cy = (bb.xmin + bb.xmax) / 2, (bb.ymin + bb.ymax) / 2
    return s.translate(V(-cx, -cy, -bb.zmin))


def export_stl(shape, path, tol=0.03, ang=0.1):
    cq.exporters.export(W(shape), path, tolerance=tol, angularTolerance=ang)


if __name__ == "__main__":
    import build
    sys.exit(build.main())
