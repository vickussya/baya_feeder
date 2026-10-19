# Bill of materials

## Printed parts (`stl/`, already in print orientation)

| # | File | Qty | Material | Notes |
|---|------|-----|----------|-------|
| 1 | 01_hopper_body.stl | 1 | PETG | outlet flange on the bed, 3 perimeters min |
| 2 | 02_hopper_lid.stl | 1 | PETG | plug up, finger-dish side on the bed |
| 3 | 03_wheel_housing.stl | 1 | PETG | motor-side wall on the bed, 4 perimeters |
| 3b | 03b_bearing_cap.stl | 1 | PETG | pin up |
| 4 | 04_pocket_wheel.stl | 1 | PETG | hub up; pocket ceilings are bridges up to ~36 mm |
| 5 | 05_motor_mount.stl | 1 | PETG | posts up |
| 6 | 06_chute.stl | 1 | PETG | **4+ walls, 100 % perimeters**, flange on the bed, leans 30 deg from vertical (no supports) |
| 6b | 06b_chute_flap_TPU.stl | 1 | TPU 95A | stretch-fit sleeve + living-hinge flap |
| 7 | 07_enclosure.stl | 1 | PETG | |
| 7b | 07b_enclosure_lid.stl | 1 | PETG | |
| 8 | 08_bowl.stl | 1 | food-safe PETG | **4+ walls, 100 % perimeters** |
| 9 | 09_bowl_base.stl | 1 | PETG | |
| 10 | 10_wall_bracket.stl | 1 | PETG | optional, only if you use the pen-wall interface |

## Purchased parts

| Qty | Item | Use |
|-----|------|-----|
| 1 | NEMA 17 stepper, 40 mm body, 5 mm D-shaft (>= 0.4 Nm) | wheel drive |
| 1 | ESP32 DevKit (30-pin) | controller |
| 1 | DS3231 RTC module + CR2032 | schedule survives power loss |
| 1 | A4988 or DRV8825 driver + 100 uF capacitor | stepper driver (set 1/16 microstep) |
| 1 | 12 V 2 A DC adapter + DC barrel jack/pigtail | power |
| 1 | LM2596 (or similar) buck converter 12 V to 5 V | ESP32 supply |
| 1 | Optional battery backup: 3 x AA holder or 18650 + diode-OR | power-failure backup |
| 1 | Reed switch (glass, 2.7 x 14 mm) | wheel home |
| 1 | Neodymium disc magnet 6 x 3 mm | glued into the wheel face |
| 1 | 12 mm momentary push button (panel mount) | feed now |
| 2 | 5 mm LED + 330 ohm resistors | status / low food |
| 1 | Optional capacitive or IR level sensor (e.g. XKC-Y25-style), 3.3 V logic | low-food sensor, pocket on hopper |
| 1 | 70 x 50 mm perfboard + pin headers | carries the electronics |
| 2 | PG7 cable glands (6.3 mm hole) + 4.6 mm hole grommet | enclosure |
| 1 | Steel plate, 106 mm dia x 3.2 mm (about 222 g) | bowl base weight (laser-cut / ordered; mild steel, clear-coated or stainless) |
| 3 | M4 countersunk screws x 16 mm | bowl, weight plate and base |
| 3 | M4 heat-set inserts (M4 x 5.7) | bowl foot |
| 24 | M3 heat-set inserts (M3 x 5.7) | housing: top, bottom, cap, box, posts, bracket (4 each) |
| 8 | M3 x 12 screws | hopper and chute flanges |
| 4 | M3 x 12 screws | bearing cap |
| 4 | M3 x 20 screws | motor mount posts |
| 4 | M3 x 8 screws | NEMA 17 to the motor plate |
| 4 | M3 x 16 screws (long-reach driver) | enclosure frame to housing |
| 4 | M3 x 10 self-tapping screws | enclosure lid |
| 4 | M3 x 12 screws | bracket plate to housing |
| 1 | M3 x 6 grub screw (or M3 x 8 cap screw) | wheel hub on the D-shaft |
| 2 m | 2 mm silicone cord or foam strip | lid and enclosure gaskets |
| 1 | Clear PETG or acrylic strip 1 x 14 x 94 mm | fill-level window |
| - | Food-safe epoxy / cyanoacrylate | magnet, window strip |
