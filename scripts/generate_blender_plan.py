#!/usr/bin/env python3
"""
Generate a DockMind 3D loading plan render and GLB from plan JSON.

Run:
/Applications/Blender.app/Contents/MacOS/Blender --background --python scripts/generate_blender_plan.py -- data/sample-plan.json assets/blender-preview.png assets/dockmind-load-plan.glb
"""

from __future__ import annotations

import json
import math
import pathlib
import sys

import bpy
from mathutils import Vector


TRUCKS = {
    "smallVan": {"name": "Small van", "length": 320, "width": 170, "height": 160},
    "fourTon": {"name": "4-ton truck", "length": 620, "width": 220, "height": 230},
    "reefer": {"name": "Refrigerated truck", "length": 560, "width": 210, "height": 220},
}

COLORS = [
    (0.12, 0.43, 0.92, 1),
    (0.09, 0.54, 0.29, 1),
    (0.71, 0.42, 0.0, 1),
    (0.02, 0.45, 0.51, 1),
    (0.42, 0.31, 1.0, 1),
    (0.7, 0.14, 0.09, 1),
]


def parse_args() -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    plan_path = pathlib.Path(args[0]) if len(args) > 0 else pathlib.Path("data/sample-plan.json")
    png_path = pathlib.Path(args[1]) if len(args) > 1 else pathlib.Path("assets/blender-preview.png")
    glb_path = pathlib.Path(args[2]) if len(args) > 2 else pathlib.Path("assets/dockmind-load-plan.glb")
    return plan_path, png_path, glb_path


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def material(name: str, color: tuple[float, float, float, float]) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    principled = mat.node_tree.nodes.get("Principled BSDF")
    if principled:
        principled.inputs["Base Color"].default_value = color
        principled.inputs["Roughness"].default_value = 0.56
    return mat


def cube(name: str, loc: tuple[float, float, float], scale: tuple[float, float, float], mat: bpy.types.Material) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    return obj


def plan_layout(cargo: list[dict], truck: dict) -> list[dict]:
    route = ["Osaka", "Kyoto", "Nagoya"]

    def rank(item: dict) -> tuple[int, int, float]:
        stop_index = route.index(item.get("stop", "Osaka")) if item.get("stop") in route else 0
        tags = item.get("tags", [])
        return (-stop_index, -int("heavy" in tags), -float(item.get("weight", 0)))

    items = sorted(cargo, key=rank)
    placements = []
    cursor_x = 12
    cursor_y = 12
    shelf_depth = 0
    for item in items:
        length = max(36, float(item["length"]))
        width = max(32, float(item["width"]))
        if cursor_y + width > truck["width"] - 12:
            cursor_y = 12
            cursor_x += shelf_depth + 10
            shelf_depth = 0
        placements.append({**item, "x": cursor_x, "y": cursor_y, "z": 0, "placedLength": length, "placedWidth": width})
        cursor_y += width + 8
        shelf_depth = max(shelf_depth, length)
    return placements


def add_label(text: str, loc: tuple[float, float, float], size: float = 0.18) -> None:
    bpy.ops.object.text_add(location=loc, rotation=(math.radians(75), 0, 0))
    obj = bpy.context.object
    obj.name = f"label-{text}"
    obj.data.body = text
    obj.data.align_x = "CENTER"
    obj.data.size = size
    mat = material(f"label-{text}", (0.05, 0.07, 0.11, 1))
    obj.data.materials.append(mat)


def main() -> None:
    plan_path, png_path, glb_path = parse_args()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    truck = TRUCKS[plan.get("truck", "fourTon")]
    placements = plan_layout(plan["cargo"], truck)

    clear_scene()
    png_path.parent.mkdir(parents=True, exist_ok=True)
    glb_path.parent.mkdir(parents=True, exist_ok=True)

    truck_mat = material("truck-shell", (0.86, 0.9, 0.95, 1))
    floor_mat = material("dock-floor", (0.64, 0.7, 0.78, 1))
    rail_mat = material("truck-rails", (0.1, 0.14, 0.2, 1))
    rear_mat = material("rear-zone", (0.12, 0.43, 0.92, 1))

    scale = 0.018
    length = truck["length"] * scale
    width = truck["width"] * scale
    height = truck["height"] * scale

    cube("dock-floor", (length / 2, width / 2, -0.08), (length + 2.4, width + 2.2, 0.08), floor_mat)
    cube("truck-floor", (length / 2, width / 2, 0), (length, width, 0.08), truck_mat)
    rail_height = 0.14
    cube("front-rail", (0, width / 2, rail_height), (0.12, width, rail_height), rail_mat)
    cube("left-rail", (length / 2, 0, rail_height), (length, 0.12, rail_height), rail_mat)
    cube("right-rail", (length / 2, width, rail_height), (length, 0.12, rail_height), rail_mat)
    cube("rear-loading-zone", (length, width / 2, rail_height), (0.18, width, rail_height), rear_mat)

    for index, item in enumerate(placements):
        mat = material(f"cargo-{item['id']}", COLORS[index % len(COLORS)])
        lx = item["placedLength"] * scale
        wy = item["placedWidth"] * scale
        hz = max(28, float(item["height"])) * scale
        x = (item["x"] * scale) + lx / 2
        y = (item["y"] * scale) + wy / 2
        z = hz / 2 + 0.05
        cube(item["id"], (x, y, z), (lx, wy, hz), mat)
        add_label(item["id"], (x, y, z + hz / 2 + 0.04))

    bpy.ops.object.light_add(type="AREA", location=(length / 2, -width * 0.35, height + 6))
    light = bpy.context.object
    light.name = "softbox"
    light.data.energy = 780
    light.data.size = 7

    bpy.ops.object.camera_add(location=(length * 0.72, -width * 0.95, height * 1.95), rotation=(math.radians(62), 0, math.radians(38)))
    camera = bpy.context.object
    bpy.context.scene.camera = camera
    direction = Vector((length / 2, width / 2, height / 5)) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    camera.data.lens = 28

    bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [item.identifier for item in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
    bpy.context.scene.view_settings.view_transform = "Standard"
    bpy.context.scene.view_settings.look = "Medium High Contrast"
    bpy.context.scene.world.color = (0.78, 0.82, 0.87)
    bpy.context.scene.render.resolution_x = 1600
    bpy.context.scene.render.resolution_y = 1000
    bpy.context.scene.render.filepath = str(png_path)
    bpy.ops.render.render(write_still=True)

    bpy.ops.export_scene.gltf(filepath=str(glb_path), export_format="GLB")
    print(f"DockMind render: {png_path}")
    print(f"DockMind model: {glb_path}")


if __name__ == "__main__":
    main()
