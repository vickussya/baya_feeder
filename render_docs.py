#!/usr/bin/env python3
"""
Generates the explanatory pictures used by README.md into docs/:
  fig_inside.png      cutaway of the whole feeder with numbered components
  fig_mechanism.png   how the pocket wheel works (fill -> turn -> empty)
  fig_electronics.png cutaway of the motor / electronics side
  fig_exploded.png    exploded view of all printed parts
  fig_printparts.png  every printed part in print orientation
  fig_wiring.png      wiring diagram of the electronics
Run after build.py:   python render_docs.py
"""
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import cadquery as cq
import feeder as f
import build as b
from feeder import V, box, cylX, cylY, cylZ, U, D, I

DOC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
os.makedirs(DOC, exist_ok=True)

PELLET = (176, 112, 58)
PEN = (214, 190, 150)
BG = (246, 247, 249)
INK = (30, 30, 40)


def font(size, bold=False):
    for n in (("arialbd.ttf" if bold else "arial.ttf"), "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            pass
    return ImageFont.load_default()


# ----------------------------------------------------------------------------- helpers
def half(shape, x=None, y=None, z=None):
    """keep the part of `shape` inside the given (min,max) ranges (None = unbounded)"""
    big = 2000.0
    r = [(-big, big) if v is None else v for v in (x, y, z)]
    return I(shape, box(r[0][0], r[0][1], r[1][0], r[1][1], r[2][0], r[2][1]))


def mesh(shape, color, tol=0.2, ang=0.25):
    v, t = b.tessellate(shape, tol, ang)
    return (v, t, color)


def badge(d, xy, text, r=17, fill=(255, 255, 255), ink=INK):
    x, y = xy
    d.ellipse([x - r - 2, y - r - 2, x + r + 2, y + r + 2], fill=(20, 20, 30))
    d.ellipse([x - r, y - r, x + r, y + r], fill=fill)
    fnt = font(20 if len(text) < 3 else 15, True)
    w = d.textlength(text, font=fnt)
    d.text((x - w / 2, y - 12 if len(text) < 3 else y - 9), text, fill=ink, font=fnt)


def wrap(d, text, fnt, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=fnt) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def arrow(d, p0, p1, color=(200, 40, 40), width=5):
    d.line([p0, p1], fill=color, width=width)
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    for s in (-1, 1):
        a = ang + math.pi + s * 0.45
        d.line([p1, (p1[0] + 18 * math.cos(a), p1[1] + 18 * math.sin(a))], fill=color, width=width)


def compose(img, title, subtitle, items, legend_w=560, out="fig.png"):
    """image on the left, numbered legend on the right"""
    ft, fs, fh, fb = font(34, True), font(20), font(20, True), font(18)
    probe = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    rows = []
    for badge_txt, head, text in items:
        lines = wrap(probe, text, fb, legend_w - 70)
        rows.append((badge_txt, head, lines))
    legend_h = sum(34 + 23 * len(l) + 14 for _, _, l in rows) + 40
    H = max(img.height, legend_h) + 110
    canvas = Image.new("RGB", (img.width + legend_w + 30, H), BG)
    canvas.paste(img, (0, 100))
    d = ImageDraw.Draw(canvas)
    d.text((24, 16), title, fill=INK, font=ft)
    d.text((24, 60), subtitle, fill=(90, 90, 100), font=fs)
    x0, y = img.width + 20, 110
    for badge_txt, head, lines in rows:
        badge(d, (x0 + 18, y + 18), badge_txt)
        d.text((x0 + 48, y + 6), head, fill=INK, font=fh)
        y += 34
        for ln in lines:
            d.text((x0 + 48, y), ln, fill=(55, 55, 65), font=fb)
            y += 23
        y += 14
    canvas.save(os.path.join(DOC, out))
    print("wrote", out, canvas.size)


def pen_wall():
    oh = f.chute_in / 2 + f.chute_wall + f.plate_hole_clear
    wall = box(f.x_plate1, f.x_plate1 + f.cage_wall_t, 0, 30, f.z_ground, f.z_ground + 440)
    return D(wall, f._tube(oh, -200, 500))


def pellets_hopper(level=0.72):
    z_top = f.z_f1 + f.cyl_h * level
    cav = U(f._funnel(0.0), cylZ(f.r_hi, f.z_f1, z_top).translate(V(f.hopper_dx, 0, 0)))
    return I(cav, box(-300, 300, -300, 300, 0, z_top))


def pellet_stick(cx, cy, cz, ang_deg):
    a = math.radians(ang_deg)
    d = V(math.cos(a), 0, math.sin(a))
    p = V(cx, cy, cz) - d * 5.0
    return cq.Solid.makeCylinder(2.5, 10.0, p, d)


def pocket_pellets(k_list, fill_r=None):
    fr = fill_r or (f.R_w - 0.8)
    out = []
    for k in k_list:
        out.append(f.rot(f.pocket_prism(fr), f.AX_Y, k * 360.0 / f.n_pockets))
    return out


# ----------------------------------------------------------------------------- electronics dummies
def electronics_dummies():
    """simple stand-ins for the bought parts (render only, not printed)"""
    P = {}
    y0 = f.motor_plate_y0
    motor = box(-21.15, 21.15, y0 - f.nema_len, y0, -21.15, 21.15)
    P["motor"] = (U(motor, cylY(f.nema_pilot_d / 2, y0, y0 + 1.9), cylY(f.shaft_d / 2, y0, f.shaft_tip_y)), (60, 60, 70))
    ye = f.enc_y_end
    yb = ye + 6.0
    P["perfboard"] = (box(-35, 35, yb, yb + 1.6, -25, 25), (40, 130, 70))
    P["esp32"] = (box(-27, 24, yb + 1.6, yb + 6, 0, 28), (30, 30, 40))
    P["driver"] = (box(-33, -13, yb + 1.6, yb + 9, -22, -7), (200, 40, 50))
    P["rtc"] = (box(-6, 32, yb + 1.6, yb + 5, -22, -2), (40, 90, 190))
    P["reed"] = (box(-1.35, 1.35, f.Y_back + 1.2, f.Y_back + 3.8, f.magnet_r - 7, f.magnet_r + 7), (220, 220, 230))
    P["magnet"] = (cylY(f.magnet_d / 2, -f.wheel_w / 2, -f.wheel_w / 2 + f.magnet_h, 0, f.magnet_r), (230, 230, 240))
    P["button"] = (cylY(5.8, ye - f.lid_enc_t - 4, ye, -25, 34), (230, 200, 40))
    P["led1"] = (cylY(2.4, ye - f.lid_enc_t - 2, ye, 15, 34), (60, 220, 90))
    P["led2"] = (cylY(2.4, ye - f.lid_enc_t - 2, ye, 28, 34), (240, 90, 60))
    return P


# ----------------------------------------------------------------------------- FIGURE 1: inside
def fig_inside(parts):
    cut = dict(y=(0, 2000))
    names = ["01_hopper_body", "02_hopper_lid", "03_wheel_housing", "03b_bearing_cap", "04_pocket_wheel",
             "06_chute", "06b_chute_flap_TPU", "10_wall_bracket", "08_bowl", "09_bowl_base"]
    meshes = [mesh(half(parts[n], **cut), b.COLORS[n]) for n in names]
    meshes.append(mesh(half(pellets_hopper(), **cut), PELLET))
    meshes.append(mesh(half(pen_wall(), **cut), PEN))
    # a dose of pellets lying in the bowl
    rnd = random.Random(4)
    pile = []
    for i in range(26):
        r = rnd.uniform(0, 26)
        a = rnd.uniform(0, 2 * math.pi)
        x, y = f.x_bowl + r * math.cos(a) - 6, abs(r * math.sin(a)) + 2
        z = f.z_floor + 2.6 + rnd.uniform(0, 4) - 0.00045 * (r ** 2)
        pile.append(pellet_stick(x, y, z, rnd.uniform(0, 180)))
    meshes.append(mesh(U(pile[0], *pile[1:]), PELLET))
    img, proj = b.render_view(meshes, az=10, el=6, width=1250, return_proj=True)
    d = ImageDraw.Draw(img)
    cx = f.hopper_dx
    anchors = {
        "1": (cx, 0, f.z_rim + f.lid_t / 2),
        "2": (cx + 18, 0, f.z_f1 + 60),
        "3": (cx * 0.3, 0, f.z_f0 + 34),
        "4": (0, 0, 0),
        "5": (-37, 0, 38),
        "6": (f.chute_x0 + 105 * f.cos_a, 0, f.z_chute_top - 105 * f.sin_a),
        "7": (f.x_bowl - 40, 0, f.z_floor + 12),
        "8": (f.x_bowl + 62, 0, f.z_ground + 8),
        "9": (f.x_plate0 + f.plate_t / 2, 0, 22),
        "10": (f.x_plate1 + f.cage_wall_t / 2, 0, -235),
        "11": (f.x_bowl + 14, 0, f.z_out + 3),
    }
    for k, p in anchors.items():
        badge(d, proj(p), k)
    # inside / outside captions (in free space left and right of the pen wall)
    px, py = proj((f.x_plate1 + 6, 0, -40))
    d.text((px, py), "INSIDE THE PEN ->", fill=(150, 40, 40), font=font(28, True))
    px, py = proj((-58, 0, -175))
    d.text((px, py), "<- OUTSIDE THE PEN", fill=(30, 90, 60), font=font(28, True))
    items = [
        ("1", "Lid (rabbit-proof)", "Closes the top. Twist it a sixth of a turn to open or close. A cord gasket keeps the pellets dry. It sits flush with the hopper, so a rabbit has nothing to grab or chew."),
        ("2", "Hopper", "The food store. Holds about 1.2 litres = 780 g of pellets, roughly 3 weeks of food. You refill it from the top."),
        ("3", "Funnel", "The sloped walls (60 deg or steeper) make the pellets slide down by themselves, so they never get stuck."),
        ("4", "Pocket wheel", "The heart of the feeder. 6 pockets, each holds about 6.8 g. It turns one pocket at a time, so you always get exactly the same amount."),
        ("5", "Wheel housing", "A tight case around the wheel. It makes sure only the pocket under the funnel is filling and only the pocket above the chute is emptying."),
        ("6", "Chute", "A smooth slide at 60 deg (steep and wide, so pellets cannot clog). It carries the food through the pen wall to the bowl."),
        ("7", "Bowl", "140 mm wide, 45 mm deep, with a low front edge so the rabbit can reach in easily. Smooth and rounded, easy to wash."),
        ("8", "Base + steel plate", "A wide, heavy base (222 g steel plate inside) so the rabbit cannot tip or carry the bowl away. Three screws hold the bowl on."),
        ("9", "Wall bracket", "A plate that fills the gap in the pen wall around the chute and holds the feeder to the wall."),
        ("10", "Pen wall", "Your own pen or cage wall (not part of the kit). Everything with electricity stays on the outside."),
        ("11", "Flap (soft TPU)", "A little flexible door at the chute's end. Pellets push it open as they fall; it closes again so nothing can be pushed up into the chute."),
    ]
    compose(img, "Inside the feeder - what each part does",
            "Cut in half lengthwise. Brown = pellets. Beige strip = your pen wall.", items, out="fig_inside.png")


# ----------------------------------------------------------------------------- FIGURE 2: mechanism
def fig_mechanism(parts):
    cut = dict(y=(0, 2000))
    zlo, zhi = -125.0, 165.0

    def crop(shape, xr=(-75, 120)):
        return half(shape, x=xr, y=(0, 2000), z=(zlo, zhi))
    meshes = [mesh(crop(parts["01_hopper_body"]), b.COLORS["01_hopper_body"]),
              mesh(crop(parts["03_wheel_housing"]), b.COLORS["03_wheel_housing"]),
              mesh(crop(parts["04_pocket_wheel"]), b.COLORS["04_pocket_wheel"]),
              mesh(crop(parts["06_chute"]), b.COLORS["06_chute"])]
    hop = I(pellets_hopper(0.30), box(-300, 300, 0, 300, 0, zhi))
    meshes.append(mesh(hop, PELLET))
    full = pocket_pellets([0, 1, 2, 4, 5])
    meshes.append(mesh(half(U(full[0], *full[1:]), y=(0, 2000)), PELLET))
    # pellets falling out of the bottom pocket
    rnd = random.Random(7)
    sticks = []
    for i, z in enumerate((-50, -58, -66, -74, -82, -90, -99, -108)):
        sticks.append(pellet_stick(-10 + 4 * i + rnd.uniform(-8, 8) + i * 4.5, rnd.uniform(3, 8), z, rnd.uniform(0, 180)))
    meshes.append(mesh(U(sticks[0], *sticks[1:]), PELLET))
    img, proj = b.render_view(meshes, az=0, el=0, width=1150, return_proj=True)
    d = ImageDraw.Draw(img)
    # pocket numbers & arrows
    R = f.R_w * 0.62
    for k, (txt) in enumerate(["A", "B", "B", "C", "", ""]):
        if not txt:
            continue
        ang = math.radians(k * 60)
        p = proj((R * math.sin(ang), 0, R * math.cos(ang)))
        badge(d, p, txt, fill=(255, 235, 150))
    # rotation arrow (clockwise as seen here)
    cx0, cy0 = proj((0, 0, 0))
    rr = (proj((f.R_w + 9, 0, 0))[0] - cx0)
    for a0 in range(-60, 80, 6):
        a1 = a0 + 6
        p0 = (cx0 + rr * math.sin(math.radians(a0)), cy0 - rr * math.cos(math.radians(a0)))
        p1 = (cx0 + rr * math.sin(math.radians(a1)), cy0 - rr * math.cos(math.radians(a1)))
        d.line([p0, p1], fill=(200, 40, 40), width=6)
    pe = (cx0 + rr * math.sin(math.radians(84)), cy0 - rr * math.cos(math.radians(84)))
    ps = (cx0 + rr * math.sin(math.radians(70)), cy0 - rr * math.cos(math.radians(70)))
    arrow(d, ps, pe)
    fall = proj((-4, 0, -70))
    arrow(d, (fall[0] - 120, fall[1] - 60), (fall[0] - 70, fall[1] - 10), color=(30, 120, 70))
    items = [
        ("A", "Fill", "The pocket at the top sits right under the funnel. The pellets fall in and fill it. Nothing else can fall through because the wheel closes the opening."),
        ("B", "Carry", "Each step the motor turns the wheel 60 degrees (one pocket). The full pockets travel round the side, held in by the wall of the housing. They cannot spill."),
        ("C", "Empty", "When a pocket reaches the bottom, its mouth is open to the chute, so the pellets fall out and slide down to the bowl. The motor then waits a moment so all pellets drop."),
        ("x3", "Dose = pockets", "One pocket is about 6.8 g. A 20 g dose = 3 steps (half a turn). A 40 g dose = 6 steps (a full turn). The software counts the steps."),
        ("home", "How the wheel knows where it is", "A tiny magnet in the wheel passes a reed switch once per turn. Before every meal the wheel turns until it sees the magnet, so it starts from the same place each time."),
    ]
    compose(img, "How the pocket wheel measures the food",
            "Cutaway seen from the front. The red arrow shows the turning direction.", items, out="fig_mechanism.png")


# ----------------------------------------------------------------------------- FIGURE 3: electronics
def fig_electronics(parts):
    keep = ["03_wheel_housing", "03b_bearing_cap", "04_pocket_wheel", "05_motor_mount", "07_enclosure", "07b_enclosure_lid"]
    cutx = (-2000, 0)
    meshes = [mesh(half(parts[n], x=cutx), b.COLORS[n]) for n in keep]
    dummies = electronics_dummies()
    for k, (shape, col) in dummies.items():
        c = half(shape, x=cutx)
        if c.Volume() > 1e-3:                      # skip pieces that lie on the removed half
            meshes.append(mesh(c, col))
    img, proj = b.render_view(meshes, az=90, el=8, width=1250, return_proj=True)
    d = ImageDraw.Draw(img)
    ye = f.enc_y_end
    yb = ye + 6
    A = {
        "1": (-32, 0, f.hub_end_y + 8, 0),
        "2": (0, 0, 0, 0),
        "3": (0, 0, f.Y_cap - 2, 20),
        "4": (0, 0, f.hub_end_y + 3, 0),
        "5": (0, 0, f.Y_back - f.standoff_len + 3, f.post_pos),
        "6": (0, 0, f.motor_plate_y0 - 20, 0),
        "7": (0, 0, f.Y_back + 2.5, f.magnet_r + 14),
        "8": (0, 0, yb + 4, 12),
        "9": (0, 0, yb + 6, -12),
        "10": (0, 0, ye - f.lid_enc_t - 2, 34),
        "11": (0, 0, ye + 20, -(f.HB - 1.5)),
        "12": (0, 0, ye + 45, 20),
    }
    # (x unused, y, z) -> point (0, y, z); entry order: (x, _, y, z)
    pos = {"1": (0, f.hub_end_y + 8, 0), "2": (0, 8, f.R_w * 0.0 + 28), "3": (0, f.Y_cap - 3, 30),
           "4": (0, f.Y_back - 9, 0), "5": (0, f.Y_back - f.standoff_len / 2, f.post_pos),
           "6": (0, f.motor_plate_y0 - 20, 12), "7": (0, f.Y_back + 2.5, f.magnet_r - 7),
           "8": (0, yb + 4, 12), "9": (0, yb + 6, -14),
           "10": (0, ye - f.lid_enc_t - 1, 34), "11": (0, ye + 55, f.HB - 1.5), "12": (0, ye + 30, -f.HB + 1.5)}
    for k, p in pos.items():
        badge(d, proj(p), k)
    items = [
        ("1", "Hub + grub screw", "The wheel's hub slides over the flat-sided motor shaft. A small screw presses on the flat so the wheel cannot slip."),
        ("2", "Pocket wheel", "Seen from the side. The wheel is held in the middle of the housing with 0.7 mm to spare all around so it spins freely."),
        ("3", "Bearing cap + pin", "Closes the housing and carries a pin that fits in a hole in the wheel, so the wheel is supported on both sides."),
        ("4", "Motor shaft", "A 5 mm shaft with one flat side (a 'D' shaft)."),
        ("5", "Motor mount posts", "Four posts hold the motor plate 14 mm from the housing, just enough room to reach the grub screw."),
        ("6", "Stepper motor (NEMA 17)", "Turns exactly 1.8 degrees per electrical pulse, so the controller can count out precise amounts. Bought part."),
        ("7", "Magnet + reed switch", "A small magnet in the wheel closes a tiny sealed switch once per turn: this tells the controller where the wheel is."),
        ("8", "ESP32 controller", "The brain: knows the time, runs the schedule and tells the motor driver how many steps to turn."),
        ("9", "Clock + motor driver", "The DS3231 clock keeps time even when the power is off. The A4988 driver converts the ESP32's signals into motor current."),
        ("10", "Button + 2 LEDs", "Hold the button for 1 second to feed right now. Green LED = alive, red LED = hopper nearly empty."),
        ("11", "Sealed enclosure", "All electronics are boxed in on the outside of the pen where the rabbit cannot reach or chew the wires."),
        ("12", "Cable glands", "Rubber-lined holes where the power cable and the sensor cable enter the box."),
    ]
    compose(img, "Inside the motor and electronics box",
            "Cut in half, seen from the side. Bought parts are shown in their real colours.", items, out="fig_electronics.png")


# ----------------------------------------------------------------------------- FIGURE 4: exploded
EXPLODE = {
    "02_hopper_lid": (0, 0, 190), "01_hopper_body": (0, 0, 95), "03_wheel_housing": (0, 0, 0),
    "04_pocket_wheel": (0, 75, 0), "03b_bearing_cap": (0, 140, 0),
    "05_motor_mount": (0, -65, 0), "07_enclosure": (0, -135, 0), "07b_enclosure_lid": (0, -230, 0),
    "06_chute": (-60, 0, -40), "06b_chute_flap_TPU": (-60, 0, -95),
    "10_wall_bracket": (120, 0, 70), "08_bowl": (95, 0, 70), "09_bowl_base": (0, 0, -60),
}
NUMBER = {"01_hopper_body": "1", "02_hopper_lid": "2", "03_wheel_housing": "3", "03b_bearing_cap": "3b",
          "04_pocket_wheel": "4", "05_motor_mount": "5", "06_chute": "6", "06b_chute_flap_TPU": "6b",
          "07_enclosure": "7", "07b_enclosure_lid": "7b", "08_bowl": "8", "09_bowl_base": "9", "10_wall_bracket": "10"}
ROLE = {
    "01_hopper_body": ("Hopper body", "Food store and funnel. Print upright."),
    "02_hopper_lid": ("Hopper lid", "Twist-on lid with gasket groove."),
    "03_wheel_housing": ("Wheel housing", "Case around the wheel with the top and bottom openings."),
    "03b_bearing_cap": ("Bearing cap", "Closes the housing, carries the wheel pin."),
    "04_pocket_wheel": ("Pocket wheel", "6 pockets, measures the food."),
    "05_motor_mount": ("Motor mount", "Plate and 4 posts that hold the motor."),
    "06_chute": ("Chute", "Slide from the wheel to the bowl."),
    "06b_chute_flap_TPU": ("Chute flap (flexible)", "Soft one-way door, printed in TPU."),
    "07_enclosure": ("Electronics enclosure", "Box for the motor and electronics."),
    "07b_enclosure_lid": ("Enclosure lid", "Back cover with button and LED holes."),
    "08_bowl": ("Bowl", "Food dish for the rabbit."),
    "09_bowl_base": ("Bowl base", "Heavy base, holds the steel plate."),
    "10_wall_bracket": ("Wall bracket", "Plate that closes the hole in the pen wall."),
}


def fig_exploded(parts):
    meshes, centers = [], {}
    for n, s in parts.items():
        off = EXPLODE[n]
        sh = s.translate(V(*off))
        meshes.append(mesh(sh, b.COLORS[n], 0.3, 0.3))
        bb = sh.BoundingBox()
        centers[n] = ((bb.xmin + bb.xmax) / 2, (bb.ymin + bb.ymax) / 2, (bb.zmin + bb.zmax) / 2)
    img, proj = b.render_view(meshes, az=-50, el=22, width=1250, return_proj=True)
    d = ImageDraw.Draw(img)
    for n, c in centers.items():
        badge(d, proj(c), NUMBER[n])
    items = [(NUMBER[n], ROLE[n][0], ROLE[n][1]) for n in parts]
    compose(img, "All printed parts - exploded view",
            "Pulled apart so every part is visible. Part numbers match the print list.", items, out="fig_exploded.png")


# ----------------------------------------------------------------------------- FIGURE 5: print sheet
MATERIAL = {"06b_chute_flap_TPU": "TPU"}


def fig_printparts(parts):
    tiles = []
    for n, s in parts.items():
        ps = f.to_print(n, s)
        bb = ps.BoundingBox()
        im = b.render_view([mesh(ps, b.COLORS[n], 0.35, 0.35)], az=-35, el=28, width=460, ss=2)
        tiles.append((n, im, (bb.xlen, bb.ylen, bb.zlen)))
    cols = 4
    cw, ch = 520, 470
    rows_n = math.ceil(len(tiles) / cols)
    canvas = Image.new("RGB", (cols * cw, rows_n * ch + 100), BG)
    d = ImageDraw.Draw(canvas)
    d.text((24, 16), "Printed parts - shown the way they sit on the print bed", fill=INK, font=font(34, True))
    d.text((24, 60), "Print them exactly like this (no supports needed). PETG unless stated.", fill=(90, 90, 100), font=font(20))
    for i, (n, im, ext) in enumerate(tiles):
        x, y = (i % cols) * cw + 20, (i // cols) * ch + 100
        d.rectangle([x, y, x + cw - 40, y + ch - 20], fill=(255, 255, 255), outline=(200, 205, 212))
        im.thumbnail((cw - 60, ch - 120))
        canvas.paste(im, (x + (cw - 40 - im.width) // 2, y + 10))
        badge(d, (x + 26, y + 26), NUMBER[n], r=17)
        mat = MATERIAL.get(n, "PETG")
        d.text((x + 14, y + ch - 98), ROLE[n][0] + f"  [{mat}]", fill=INK, font=font(21, True))
        d.text((x + 14, y + ch - 70), f"{ext[0]:.0f} x {ext[1]:.0f} x {ext[2]:.0f} mm", fill=(80, 80, 90), font=font(18))
    canvas.save(os.path.join(DOC, "fig_printparts.png"))
    print("wrote fig_printparts.png", canvas.size)


# ----------------------------------------------------------------------------- FIGURE 6: wiring
def fig_wiring():
    W, H = 1700, 1050
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((24, 16), "Electronics - what is connected to what", fill=INK, font=font(34, True))
    d.text((24, 60), "Red = 12 V power, orange = 5 V power, black = ground / signal wires. Pin numbers are ESP32 GPIO numbers.", fill=(90, 90, 100), font=font(20))

    def blk(x, y, w, h, title, sub, col):
        d.rounded_rectangle([x, y, x + w, y + h], 14, fill=col, outline=(30, 30, 40), width=3)
        d.text((x + 14, y + 10), title, fill=(255, 255, 255) if sum(col) < 450 else INK, font=font(24, True))
        for i, ln in enumerate(sub):
            d.text((x + 14, y + 46 + 24 * i), ln, fill=(255, 255, 255) if sum(col) < 450 else (50, 50, 60), font=font(18))

    def line(pts, col, w=5):
        d.line(pts, fill=col, width=w, joint="curve")

    RED, ORG, BLK, BLU, GRN = (200, 40, 40), (230, 140, 30), (40, 40, 50), (50, 100, 200), (40, 150, 80)
    blk(40, 150, 300, 120, "12 V power adapter", ["2 A, plugs into the wall", "(optional: battery backup)"], (200, 90, 90))
    blk(40, 400, 300, 120, "Buck converter", ["12 V  ->  5 V", "(e.g. LM2596)"], (230, 160, 70))
    blk(520, 380, 380, 300, "ESP32 controller", ["The brain.", "Knows the time, runs the", "schedule, counts motor steps.", "", "Has Wi-Fi to set the clock", "(optional)"], (50, 90, 160))
    blk(520, 120, 380, 190, "Stepper driver (A4988)", ["Turns ESP32 signals into", "motor current. Set to 1/16 step.", "+100 uF capacitor on 12 V."], (190, 60, 60))
    blk(1100, 120, 320, 190, "Stepper motor NEMA 17", ["Turns the pocket wheel", "exactly 1.8 deg per pulse"], (70, 70, 85))
    blk(1100, 400, 320, 130, "DS3231 clock (RTC)", ["Keeps the time with a coin", "cell if the power goes out"], (60, 110, 190))
    blk(1100, 570, 320, 110, "Reed switch + magnet", ["Tells the ESP32 where the", "wheel is (home position)"], (230, 230, 236))
    blk(1100, 710, 320, 110, "Push button", ["Hold 1 s = feed right now"], (235, 210, 90))
    blk(520, 760, 380, 110, "2 LEDs (+330 ohm each)", ["Green = alive, red = hopper low"], (190, 235, 200))
    blk(1100, 850, 320, 130, "Low-food sensor (optional)", ["Reads the pellet level at", "the bottom of the hopper"], (230, 230, 236))
    # power
    line([(190, 270), (190, 400)], RED)
    d.text((200, 320), "12 V", fill=RED, font=font(20, True))
    line([(340, 210), (430, 210), (430, 150), (520, 150)], RED)
    d.text((372, 160), "12 V", fill=RED, font=font(20, True))
    line([(340, 460), (520, 460)], ORG)
    d.text((395, 430), "5 V", fill=ORG, font=font(20, True))
    # driver <-> esp32
    line([(640, 310), (640, 380)], BLK)
    d.text((650, 330), "GPIO 25 STEP, 26 DIR, 27 EN", fill=INK, font=font(18))
    line([(900, 215), (1100, 215)], RED)
    d.text((915, 185), "motor wires", fill=INK, font=font(18))
    # i2c
    line([(900, 465), (1100, 465)], BLU)
    d.text((915, 436), "I2C: GPIO 21, 22", fill=BLU, font=font(18, True))
    # reed
    line([(900, 625), (1100, 625)], BLK)
    d.text((915, 596), "GPIO 32 to GND", fill=INK, font=font(18))
    # button
    line([(900, 600), (1010, 600), (1010, 765), (1100, 765)], BLK)
    d.text((915, 735), "GPIO 33 to GND", fill=INK, font=font(18))
    # LEDs
    line([(710, 680), (710, 760)], BLK)
    d.text((720, 710), "GPIO 2 and 4", fill=INK, font=font(18))
    # low food
    line([(900, 650), (960, 650), (960, 915), (1100, 915)], GRN)
    d.text((915, 890), "GPIO 35", fill=GRN, font=font(18, True))
    # legend
    d.text((40, 600), "Everything sits in the sealed enclosure on the", fill=INK, font=font(22, True))
    d.text((40, 630), "OUTSIDE of the pen. Only the motor wires, the", fill=INK, font=font(22, True))
    d.text((40, 660), "reed and the sensor leave the box, inside the", fill=INK, font=font(22, True))
    d.text((40, 690), "housing, through cable glands.", fill=INK, font=font(22, True))
    im.save(os.path.join(DOC, "fig_wiring.png"))
    print("wrote fig_wiring.png", im.size)


def main():
    parts = f.build_all()
    which = set(sys.argv[1:]) or {"inside", "mechanism", "electronics", "exploded", "printparts", "wiring"}
    if "inside" in which:
        fig_inside(parts)
    if "mechanism" in which:
        fig_mechanism(parts)
    if "electronics" in which:
        fig_electronics(parts)
    if "exploded" in which:
        fig_exploded(parts)
    if "printparts" in which:
        fig_printparts(parts)
    if "wiring" in which:
        fig_wiring()


if __name__ == "__main__":
    main()
