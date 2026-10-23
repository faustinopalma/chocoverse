"""Build original Chocoverse geometry using the local BlenderMCP archive's bpy helpers."""

import math
from pathlib import Path
import runpy
import sys

import bpy


root = Path(__file__).resolve().parents[2]
archive = Path(sys.argv[sys.argv.index("--") + 1])
output = root / ".local" / "chocoverse-art"
output.mkdir(parents=True, exist_ok=True)
bpy.context.scene["blender_mcp_lab"] = "disposable-test"
helpers = runpy.run_path(str(archive / "scripts" / "gallery_common.py"))
box = helpers["box"]
ball = helpers["ball"]
cylinder = helpers["cylinder"]
cone = helpers["cone"]
beam = helpers["beam"]
line = helpers["line"]
ring = helpers["ring"]
mat = helpers["mat"]
scene = bpy.context.scene
camera = scene.camera

cream = mat("Warm porcelain", (0.83, 0.78, 0.65), rough=0.65)
cocoa = mat("Dark chocolate", (0.105, 0.040, 0.027), rough=0.32)
milk = mat("Milk chocolate", (0.30, 0.13, 0.065), rough=0.38)
rose = mat("Giandoria rose", (0.48, 0.035, 0.095), rough=0.42)
brick = mat("Terracotta", (0.49, 0.20, 0.12), rough=0.7)
gold = mat("Brushed brass", (0.72, 0.43, 0.13), metal=0.65)
leaf = mat("Sage foliage", (0.19, 0.30, 0.16), rough=0.8)
light_leaf = mat("Olive foliage", (0.34, 0.42, 0.21), rough=0.8)
glass = mat("Smoked windows", (0.075, 0.14, 0.15), metal=0.25, rough=0.23)
silver = mat("Steel", (0.53, 0.57, 0.56), metal=0.7)
white = mat("Ivory lettering", (0.97, 0.93, 0.82), rough=0.5)
road = mat("Graphite roads", (0.13, 0.12, 0.11), rough=0.85)
signal = mat("Rose data signals", (0.95, 0.23, 0.32), emission=0.4)


def sign(text, position, size, material=white):
    data = bpy.data.curves.new(text, "FONT")
    data.body = text
    data.align_x = "CENTER"
    data.align_y = "CENTER"
    data.size = size
    data.extrude = 0.003
    obj = bpy.data.objects.new(text, data)
    bpy.context.collection.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (math.pi / 2, 0, 0)
    data.materials.append(material)
    return obj


def tree(x, y, scale=1.0):
    cylinder("Tree trunk", (x, y, 0.55 + scale * 0.45), 0.075, scale * 0.9, cocoa, 10)
    for z, radius in [(1.2, 0.55), (1.65, 0.43), (2.0, 0.30)]:
        cone("Territory cypress", (x, y, 0.5 + z * scale), radius * scale,
             0.02, 0.9 * scale, leaf, 10)


def chocolate(x, y, z, scale=1.0):
    box("Chocolate bar base", (x, y, z), (1.3 * scale, 0.7 * scale, 0.11 * scale), cocoa, 0.04)
    for i in range(3):
        for j in range(2):
            box("Chocolate square", (x + (i - 1) * 0.40 * scale,
                                     y + (j - 0.5) * 0.32 * scale, z + 0.09 * scale),
                (0.37 * scale, 0.29 * scale, 0.12 * scale), milk, 0.045 * scale)


def truck(x, y):
    box("Delivery truck chassis", (x, y, 0.86), (2.05, 0.87, 0.22), cocoa)
    box("Giandoria delivery box", (x - 0.29, y, 1.44), (1.45, 0.86, 0.94), rose)
    box("Delivery cab", (x + 0.78, y, 1.23), (0.68, 0.82, 0.68), cream)
    box("Cab windscreen", (x + 0.84, y - 0.424, 1.40), (0.40, 0.025, 0.29), glass, 0.02)
    for xx in (x - 0.65, x + 0.72):
        for yy in (y - 0.46, y + 0.46):
            wheel = cylinder("Truck tyre", (xx, yy, 0.74), 0.24, 0.13, road, 16)
            wheel.rotation_euler[0] = math.pi / 2
    sign("G", (x - 0.28, y - 0.442, 1.47), 0.53)


def agent(x, y):
    box("Decision agent body", (x, y, 0.99), (0.42, 0.37, 0.52), rose, 0.09)
    box("Decision agent head", (x, y, 1.48), (0.62, 0.48, 0.42), cream, 0.12)
    box("Agent face", (x, y - 0.25, 1.49), (0.44, 0.025, 0.20), glass, 0.04)
    for side in (-1, 1):
        ball("Agent eye", (x + side * 0.12, y - 0.28, 1.5), 0.04, signal)
        box("Agent boot", (x + side * 0.14, y - 0.02, 0.62), (0.19, 0.30, 0.19), cocoa)
        beam("Agent arm", (x + side * 0.26, y, 1.13),
             (x + side * 0.35, y - 0.13, 0.88), 0.06, gold)
    beam("Agent antenna", (x, y, 1.69), (x, y, 1.9), 0.025, gold)
    ball("Agent beacon", (x, y, 1.92), 0.06, signal)


cylinder("Chocolate world foundation", (0, 0, 0), 8.15, 0.55, cocoa, 96)
cylinder("Porcelain business island", (0, 0, 0.33), 7.98, 0.16, cream, 96)
for i in range(48):
    angle = i * math.tau / 48
    bar = box("Chocolate foundation segments", (8.05 * math.cos(angle), 8.05 * math.sin(angle), 0.0),
              (0.29, 0.46, 0.43), milk, 0.04)
    bar.rotation_euler[2] = angle

box("Delivery avenue", (0, -4.6, 0.44), (12.4, 1.45, 0.06), road, 0.3)
for i in range(18):
    box("Road centre marking", (-5.8 + i * 0.68, -4.6, 0.48), (0.31, 0.035, 0.012), cream, 0.005)
truck(-3.9, -4.6)
truck(3.6, -4.6)

box("Factory plinth", (-0.5, 0.8, 0.57), (6.5, 4.5, 0.26), milk)
box("Giandoria factory", (-0.5, 1.2, 1.72), (6.1, 3.4, 2.3), brick)
for xx in (-2.9, -1.7, -0.5, 0.7, 1.9):
    box("Factory front windows", (xx, -0.53, 1.66), (0.78, 0.065, 1.1), glass, 0.045)
    box("Factory window mullion", (xx, -0.58, 1.66), (0.035, 0.04, 1.12), gold, 0.005)
for i in range(4):
    xx = -2.8 + i * 1.55
    roof = box("Sawtooth roof", (xx, 1.2, 3.21), (1.7, 3.65, 0.12), cream, 0.025)
    roof.rotation_euler[1] = -0.30
    box("Clerestory glazing", (xx + 0.78, 1.2, 3.18), (0.06, 3.30, 0.48), glass, 0.015)
box("Giandoria nameplate", (-0.5, -0.62, 2.78), (4.7, 0.14, 0.60), rose)
sign("GIANDORIA", (-0.5, -0.706, 2.78), 0.46)
for xx in (-4.55, -5.65):
    cylinder("Ingredient silo", (xx, 0.9, 1.71), 0.48, 2.45, silver, 32)
    cone("Silo crown", (xx, 0.9, 3.04), 0.49, 0.12, 0.30, silver, 32)
    line("Ingredient pipe", [(xx, 0.9, 2.8), (xx, 1.6, 3.35), (-3.1, 1.6, 3.2)], 0.075, gold)

box("Chocolate conveyor", (-0.5, -2.1, 1.02), (5.6, 0.95, 0.25), silver)
box("Conveyor belt", (-0.5, -2.1, 1.17), (5.5, 0.76, 0.06), cocoa)
for xx in (-2.8, -1.6, -0.4, 0.8, 1.9):
    chocolate(xx, -2.1, 1.25, 0.65)
for xx in (-2.6, 1.6):
    for yy in (-2.44, -1.76):
        box("Conveyor legs", (xx, yy, 0.74), (0.13, 0.13, 0.6), silver, 0.02)
agent(-2.9, -3.0)
agent(1.1, -3.1)

for index, yy in enumerate((0.0, 2.4)):
    xx = 4.8
    box("Giandoria shop", (xx, yy, 1.16), (1.9, 1.65, 1.45), cream)
    roof = box("Shop terracotta canopy", (xx, yy, 2.0), (2.1, 1.9, 0.16), rose)
    box("Shop display", (xx, yy - 0.84, 1.12), (1.35, 0.04, 0.80), glass, 0.02)
    for i in range(6):
        box("Striped shop awning", (xx - 0.79 + i * 0.31, yy - 1.03, 1.81),
            (0.30, 0.57, 0.1), white if i % 2 else rose, 0.015)
    sign("BOTTEGA", (xx, yy - 0.85, 1.68), 0.20, cocoa)
    for k in range(3):
        box("Shop chocolate display", (xx - 0.4 + k * 0.4, yy - 0.88, 0.91),
            (0.19, 0.07, 0.3), gold, 0.015)
agent(4.8, -2.1)

for xx, yy, size in [(-5.1, 3.7, 1.0), (-3.5, 4.6, 0.8), (-1.8, 5.1, 1.0),
                     (-6.2, -1.2, 0.8), (6.7, 0.5, 0.65), (6.2, 3.8, 0.8)]:
    tree(xx, yy, size)
for xx, yy in [(-5.8, 3.4), (-4.1, 4.1), (-2.6, 4.8)]:
    ball("Piedmont landscape", (xx, yy, 0.55), 1, light_leaf, (1.0, 0.8, 0.45))

cylinder("Fabric data pedestal", (1.8, 4.7, 0.64), 1.20, 0.43, rose, 48)
ring("Connected data halo", (1.8, 4.7, 2.04), 1.02, 0.055, gold)
for i in range(3):
    cube = box("Connected business data", (1.8, 4.7, 1.18 + i * 0.57),
               (0.78, 0.78, 0.40), cream)
    cube.rotation_euler[2] = i * 0.36
sign("FABRIC", (1.8, 3.48, 1.05), 0.29, cocoa)
for name, points in [
    ("Factory records", [(-1, 2.4, 3.8), (-0.5, 3.9, 4.7), (1.8, 4.7, 3.1)]),
    ("Channel records", [(4.8, 2.4, 2.3), (4.5, 4.7, 3.7), (1.8, 4.7, 3.1)]),
    ("Planning records", [(-4.8, 3.8, 2.0), (-2, 5.4, 4.4), (1.8, 4.7, 3.1)]),
]:
    line(name, points, 0.028, signal)
    for point in (points[0], points[-1]):
        ball("Data connection", point, 0.075, gold)

box("Chocoverse entrance sign", (0, -6.60, 0.94), (6.7, 0.14, 1.03), rose, 0.10)
sign("CHOCOVERSE", (0, -6.69, 1.12), 0.68, white)
sign("A CONNECTED CHOCOLATE WORLD", (0, -6.70, 0.66), 0.18, white)

camera.location = (13, -20, 16)
helpers["point_at"](camera, (0, 0, 0.8))
camera.data.ortho_scale = 22
scene.render.resolution_x = 1500
scene.render.resolution_y = 1000
scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.65, 0.60, 0.52, 1)
for obj in scene.objects:
    if obj.type == "LIGHT":
        obj.data.color = (1.0, 0.90, 0.76)
scene.render.filepath = str(output / "chocoverse-preview.png")
bpy.ops.wm.save_as_mainfile(filepath=str(output / "chocoverse.blend"))
bpy.ops.render.render(write_still=True)

bpy.ops.object.select_all(action="DESELECT")
for obj in list(scene.objects):
    if obj.type in {"MESH", "CURVE", "FONT"}:
        obj.select_set(True)
bpy.context.view_layer.objects.active = next(obj for obj in scene.objects if obj.select_get())
bpy.ops.object.convert(target="MESH")
destination = root / "site" / "art" / "chocoverse.glb"
bpy.ops.export_scene.gltf(filepath=str(destination), export_format="GLB", use_selection=True,
                          export_cameras=False, export_lights=False, export_animations=False)
print(f"CHOCOVERSE_GLB={destination} bytes={destination.stat().st_size}")
