import bpy
import os
import math

# =========================
# GLOBAL SETTINGS
# =========================
FPS = 30
EARTH_DAY_FRAMES  = 120 # 1 Earth day = 120 frames (4s @ 30fps)
EARTH_YEAR_FRAMES = 1200 # 1 Earth year = 1200 frames (40s @ 30fps)
SYSTEM_SCALE = 1.0 # scales all orbit radii visually
RING_ALPHA   = 0.55

BASE_DIR = os.path.dirname(bpy.data.filepath) + os.sep
TEX_DIR  = os.path.join(BASE_DIR, "textures")

# =========================
# CLEANUP & UTIL
# =========================
def delete_grouped(prefixes=("Planet-", "Orbit-", "SpinCtrl-", "OrbitCtrl-", "Rings-", "Moon-", "Sun")):
    bpy.ops.object.select_all(action='DESELECT')
    for p in prefixes:
        bpy.ops.object.select_pattern(pattern=f"{p}*")
    sel = list(bpy.context.selected_objects)
    if sel:
        bpy.ops.object.delete()
    print(f"Deleted {len(sel)} objects with prefixes {prefixes}")

def delete_unused_materials():
    i = 0
    for m in list(bpy.data.materials):
        if m.users == 0:
            bpy.data.materials.remove(m, do_unlink=True); i += 1
    print(f"Deleted {i} unused materials")

def delete_unused_images():
    i = 0
    for im in list(bpy.data.images):
        if im.users == 0:
            bpy.data.images.remove(im, do_unlink=True); i += 1
    print(f"Deleted {i} unused images")

def ensure_collection(name="Solar System"):
    coll = bpy.data.collections.get(name)
    if not coll:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll

def link_to_collection(obj, coll_name="Solar System"):
    coll = ensure_collection(coll_name)
    for c in obj.users_collection:
        c.objects.unlink(obj)
    coll.objects.link(obj)

# =========================
# MATERIALS
# =========================
def make_planet_material(name, color=(0.8,0.8,0.8,1.0), texture_path=None, roughness=0.6, specular=0.3):
    matname = f"Material-{name}"
    mat = bpy.data.materials.get(matname) or bpy.data.materials.new(matname)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (400,0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (100,0)
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value  = roughness
    for key in ("Specular", "Specular IOR Level"):
        if key in bsdf.inputs:
            bsdf.inputs[key].default_value = specular
            break
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    if texture_path:
        try:
            img = bpy.data.images.load(texture_path)
            tex = nt.nodes.new("ShaderNodeTexImage"); tex.location = (-250, 0)
            tex.image = img; tex.interpolation = 'Smart'

            tcoord = nt.nodes.new("ShaderNodeTexCoord"); tcoord.location = (-650, 0)
            mapping = nt.nodes.new("ShaderNodeMapping"); mapping.location = (-450, 0)

            # Link texture mapping
            nt.links.new(tcoord.outputs["Generated"], mapping.inputs["Vector"])
            nt.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])

            # Rotate texture -90° around Z
            import math
            mapping.inputs['Rotation'].default_value[2] = math.radians(-90)

        except:
            print(f"[WARN] Could not load texture: {texture_path}")

    return mat

def make_emissive_sun_material(strength=8.0, tint=(1.0, 0.9, 0.6, 1.0)):
    mat = bpy.data.materials.get("Material-Sun") or bpy.data.materials.new("Material-Sun")
    mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (300,0)
    emi = nt.nodes.new("ShaderNodeEmission"); emi.location = (80,0)
    emi.inputs["Color"].default_value    = tint
    emi.inputs["Strength"].default_value = strength
    nt.links.new(emi.outputs["Emission"], out.inputs["Surface"])
    return mat

def make_ring_material(name, alpha=RING_ALPHA):
    mat = bpy.data.materials.get(f"Rings-{name}") or bpy.data.materials.new(f"Rings-{name}")
    mat.use_nodes = True
    nt = mat.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (300,0)
    mix = nt.nodes.new("ShaderNodeMixShader"); mix.location = (100,0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (-150,80)
    tr   = nt.nodes.new("ShaderNodeBsdfTransparent"); tr.location = (-150,-120)
    fac  = nt.nodes.new("ShaderNodeValue"); fac.location = (-350, -20); fac.outputs[0].default_value = 1.0 - alpha
    bsdf.inputs["Roughness"].default_value = 0.25
    nt.links.new(fac.outputs[0], mix.inputs[0])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(bsdf.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat

# =========================
# GEOMETRY
# =========================
def add_sphere(name, location=(0,0,0), radius=1.0):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, radius=radius, location=location)
    obj = bpy.context.object; obj.name = name
    bpy.ops.object.shade_smooth()
    return obj

def add_orbit_curve(name, radius=5.0, center=(0,0,0)):
    bpy.ops.curve.primitive_bezier_circle_add(radius=radius, location=center)
    curve = bpy.context.object; curve.name = name
    cu = curve.data
    # No fill_mode='NONE' in Blender 4.5; bevel=0 already makes it a thin guide
    cu.bevel_depth = 0.0
    cu.use_path = True # REQUIRED for eval_time animation
    cu.path_duration = EARTH_YEAR_FRAMES
    return curve

def set_oblateness(obj, flattening=0.0):
    f = max(0.0, min(flattening, 0.25))
    if f > 0:
        obj.scale[2] *= (1.0 - f)

# =========================
# ANIMATION HELPERS
# =========================
def _linear_and_cycle(fc):
    for kp in fc.keyframe_points:
        kp.interpolation = 'LINEAR'
    mod = fc.modifiers.new(type='CYCLES')
    mod.mode_before = 'REPEAT'
    mod.mode_after  = 'REPEAT'

def animate_spin(spin_ctrl, frames_per_rotation=120, start_frame=1, direction=1):
    """Animate Z rotation on SpinCtrl (tilted local Z)."""
    sc = bpy.context.scene
    sc.frame_set(start_frame)
    spin_ctrl.keyframe_insert(data_path="rotation_euler", index=2)
    sc.frame_set(start_frame + int(abs(frames_per_rotation)))
    spin_ctrl.rotation_euler[2] += direction * 2.0 * math.pi
    spin_ctrl.keyframe_insert(data_path="rotation_euler", index=2)
    if spin_ctrl.animation_data and spin_ctrl.animation_data.action:
        for fc in spin_ctrl.animation_data.action.fcurves:
            if fc.data_path == "rotation_euler" and fc.array_index == 2:
                _linear_and_cycle(fc)

def ensure_follow_path(obj, path_obj):
    con = None
    for c in obj.constraints:
        if c.type == 'FOLLOW_PATH' and c.target == path_obj:
            con = c; break
    if con is None:
        con = obj.constraints.new(type='FOLLOW_PATH')
        con.target = path_obj
    # 4.5 LTS: drive motion with curve.eval_time
    con.use_fixed_location = False
    con.use_curve_follow   = False
    con.forward_axis = 'FORWARD_Y'
    con.up_axis      = 'UP_Z'
    return con

def animate_orbit_with_eval_time(path_obj, frames_per_revolution=EARTH_YEAR_FRAMES, start_frame=1):
    """Animate curve.data.eval_time: 0 -> frames_per_revolution (loops)."""
    cu = path_obj.data
    cu.use_path = True
    cu.path_duration = max(2, int(frames_per_revolution))
    sc = bpy.context.scene
    sc.frame_set(start_frame)
    cu.eval_time = 0.0
    cu.keyframe_insert(data_path="eval_time")
    sc.frame_set(start_frame + int(frames_per_revolution))
    cu.eval_time = float(frames_per_revolution)
    cu.keyframe_insert(data_path="eval_time")
    if cu.animation_data and cu.animation_data.action:
        for fc in cu.animation_data.action.fcurves:
            if fc.data_path == "eval_time":
                _linear_and_cycle(fc)

# =========================
# BUILDERS (with hierarchy)
# =========================
def add_planet(cfg):
    """
    Hierarchy:
      OrbitCtrl-Name  [Follow Path to Orbit-Name curve]  <-- revolution
          └─ SpinCtrl-Name  [axial tilt on X, spin on Z] <-- self-rotation
                └─ Planet-Name (mesh)                    <-- materials, flattening
    """
    name = cfg['name']

    # Orbit path
    orbit_curve = add_orbit_curve(f"Orbit-{name}", radius=cfg["orbit_radius"])
    link_to_collection(orbit_curve)

    # Orbit controller (follows the path)
    orbit_ctrl = bpy.data.objects.new(f"OrbitCtrl-{name}", None)
    orbit_ctrl.empty_display_type = 'PLAIN_AXES'
    orbit_ctrl.location = (0,0,0)
    bpy.context.scene.collection.objects.link(orbit_ctrl)
    link_to_collection(orbit_ctrl)
    ensure_follow_path(orbit_ctrl, orbit_curve)
    animate_orbit_with_eval_time(orbit_curve, frames_per_revolution=cfg["year_frames"], start_frame=1)

    # Spin controller (tilt + spin), child of orbit ctrl
    spin_ctrl = bpy.data.objects.new(f"SpinCtrl-{name}", None)
    spin_ctrl.empty_display_type = 'SPHERE'
    bpy.context.scene.collection.objects.link(spin_ctrl)
    link_to_collection(spin_ctrl)
    spin_ctrl.parent = orbit_ctrl
    # Apply axial tilt on X so Z becomes the tilted axis
    spin_ctrl.rotation_euler = (math.radians(cfg.get("tilt_deg", 0.0)), 0.0, 0.0)
    animate_spin(spin_ctrl, frames_per_rotation=cfg["day_frames"], start_frame=1, direction=cfg.get("spin_dir", 1))

    # Planet mesh
    planet = add_sphere(f"Planet-{name}", location=(0,0,0), radius=cfg["radius"])
    planet.parent = spin_ctrl
    link_to_collection(planet)

    # Material
    mat = make_planet_material(name, color=cfg["color"], texture_path=cfg.get("texture"))
    planet.data.materials.clear(); planet.data.materials.append(mat)

    # Shape (oblateness) on mesh only (not on controllers)
    set_oblateness(planet, cfg.get("flattening", 0.0))

    # Rings
    if cfg.get("with_rings", False):
        major_inner = cfg.get("rings_inner", 1.2) * cfg["radius"]
        major_outer = cfg.get("rings_outer", 2.2) * cfg["radius"]
        ring = add_rings_for(spin_ctrl, inner=major_inner, outer=major_outer, alpha=RING_ALPHA)
        link_to_collection(ring)

    print(f"Planet '{name}' created with proper tilt/spin.")
    return dict(mesh=planet, spin=spin_ctrl, orbit=orbit_ctrl, curve=orbit_curve)

def add_rings_for(parent_spin_ctrl, inner=1.2, outer=2.2, alpha=RING_ALPHA):
    major = (inner + outer)/2.0
    minor = (outer - inner)/10.0
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
                                     rotation=(math.radians(90),0,0),
                                     location=(0,0,0))
    ring = bpy.context.object
    ring.name = f"Rings-{parent_spin_ctrl.name.replace('SpinCtrl-','')}"
    ring.data.materials.clear()
    ring.data.materials.append(make_ring_material(parent_spin_ctrl.name.replace('SpinCtrl-',''), alpha))
    ring.parent = parent_spin_ctrl
    # align to equator (same tilt already on parent)
    ring.rotation_euler = (0, 0, 0)
    return ring

def add_sun(cfg, strength=8.0):
    import math
    sun = add_sphere(cfg.get("name", "Sun"),
                     location=cfg.get("location", (0, 0, 0)),
                     radius=cfg.get("radius", 3.0))

    # Apply tilt if provided
    tilt = cfg.get("tilt_deg", 0.0)
    if tilt != 0.0:
        sun.rotation_euler[0] = math.radians(tilt)

    # Create emissive material
    mat = make_emissive_sun_material(strength=strength)

    # Add texture
    if "texture" in cfg and cfg["texture"]:
        try:
            img = bpy.data.images.load(cfg["texture"])
            tex_node = mat.node_tree.nodes.new("ShaderNodeTexImage")
            tex_node.image = img
            bsdf = mat.node_tree.nodes.get("Emission")
            if bsdf:
                mat.node_tree.links.new(tex_node.outputs["Color"], bsdf.inputs["Color"])
        except:
            print(f"[WARN] Could not load Sun texture: {cfg['texture']}")

    sun.data.materials.clear()
    sun.data.materials.append(mat)
    link_to_collection(sun)

    # Optional directional light
    if not any(hasattr(o, "data") and isinstance(o.data, bpy.types.Light) for o in bpy.data.objects):
        bpy.ops.object.light_add(type='SUN', location=(0, 0, 50))
        bpy.context.object.data.energy = 3.0

    return sun

def add_moon(earth_bundle, name="Moon", radius=0.27, orbit_radius=1.8, day_frames=120, year_frames=300):
    """Moon orbits Earth: parent its orbit curve to Earth's ORBIT CTRL."""
    earth_orbit_ctrl = earth_bundle["orbit"]
    # orbit curve
    curve = add_orbit_curve(f"Orbit-{name}", radius=orbit_radius, center=(0,0,0))
    curve.parent = earth_orbit_ctrl
    curve.matrix_parent_inverse.identity()
    link_to_collection(curve)

    # orbit controller (empty) for the moon
    orbit_ctrl = bpy.data.objects.new(f"OrbitCtrl-{name}", None)
    orbit_ctrl.empty_display_type = 'PLAIN_AXES'
    bpy.context.scene.collection.objects.link(orbit_ctrl)
    orbit_ctrl.parent = earth_orbit_ctrl
    link_to_collection(orbit_ctrl)
    ensure_follow_path(orbit_ctrl, curve)
    animate_orbit_with_eval_time(curve, frames_per_revolution=year_frames, start_frame=1)

    # spin controller for the moon
    spin_ctrl = bpy.data.objects.new(f"SpinCtrl-{name}", None)
    spin_ctrl.empty_display_type = 'SPHERE'
    bpy.context.scene.collection.objects.link(spin_ctrl)
    spin_ctrl.parent = orbit_ctrl
    link_to_collection(spin_ctrl)
    animate_spin(spin_ctrl, frames_per_rotation=day_frames, start_frame=1, direction=1)

    # moon mesh
    moon = add_sphere(f"Moon-{name}", location=(0,0,0), radius=radius)
    moon.parent = spin_ctrl
    link_to_collection(moon)
    mat = make_planet_material(name, color=(0.7,0.7,0.7,1.0), texture_path=None, roughness=0.9, specular=0.1)
    moon.data.materials.clear(); moon.data.materials.append(mat)
    print(f"Moon '{name}' added.")
    return dict(mesh=moon, spin=spin_ctrl, orbit=orbit_ctrl, curve=curve)

# =========================
# DATA (temporary)
# =========================
Y = {  # orbital periods in Earth years
    "Mercury": 0.2408467, "Venus": 0.61519726, "Earth": 1.0, "Mars": 1.8808158,
    "Jupiter": 11.862615, "Saturn": 29.447498, "Uranus": 84.016846, "Neptune": 164.79132
}
TILT = {  # axial tilts (deg)
    "Mercury": 0.03, "Venus": 177.4, "Earth": 23.44, "Mars": 25.19,
    "Jupiter": 3.13, "Saturn": 26.73, "Uranus": 97.77, "Neptune": 28.32
}
ROT_H = {  # sidereal rotation hours; negative = retrograde (Venus, Uranus)
    "Mercury": 1407.5, "Venus": -5832.5, "Earth": 23.934, "Mars": 24.623,
    "Jupiter": 9.925,  "Saturn": 10.656,  "Uranus": -17.24,  "Neptune": 16.11
}
FLAT = {  # flattening (approx)
    "Mercury": 0.00006, "Venus": 0.0001, "Earth": 1/298.257, "Mars": 0.00589,
    "Jupiter": 0.06487, "Saturn": 0.09796, "Uranus": 0.0229,  "Neptune": 0.0171
}
R = {  # display radii (artistic scale; Earth=1)
    "Mercury": 0.30, "Venus": 0.95, "Earth": 1.00, "Mars": 0.53,
    "Jupiter": 2.80, "Saturn": 2.40, "Uranus": 1.80, "Neptune": 1.70
}
A = {  # orbit radii (scene units)
    "Mercury": 4.0, "Venus": 6.0, "Earth": 8.0, "Mars": 10.0,
    "Jupiter": 14.0, "Saturn": 18.0, "Uranus": 22.0, "Neptune": 26.0
}

def frames_for_day(hours):   # map real hours to frames
    return max(10, int(EARTH_DAY_FRAMES * (abs(hours)/24.0)))
def spin_dir(hours):         # retrograde sign
    return -1 if hours < 0 else 1

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    # scene
    bpy.context.scene.render.fps = FPS
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end   = 4000

    # cleanup
    delete_grouped()
    delete_unused_materials()
    delete_unused_images()

    # Sun
    add_sun(radius=3.0, strength=8.0)

    # Planets
    bundles = {}
    order = ["Mercury","Venus","Earth","Mars","Jupiter","Saturn","Uranus","Neptune"]
    for name in order:
        cfg = dict(
            name=name,
            radius=R[name],
            color=(1,1,1,1),
            texture=os.path.join(TEX_DIR, f"{name.lower()}.jpg") if os.path.exists(os.path.join(TEX_DIR, f"{name.lower()}.jpg")) else None,
            tilt_deg=TILT[name],
            flattening=FLAT[name],
            orbit_radius=A[name] * SYSTEM_SCALE,
            year_frames=max(60, int(EARTH_YEAR_FRAMES * Y[name])),
            day_frames=frames_for_day(ROT_H[name]),
            spin_dir=spin_dir(ROT_H[name]),
            with_rings=(name == "Saturn"),
            rings_inner=1.2,
            rings_outer=2.2
        )
        bundles[name] = add_planet(cfg)

    # Moons
    if "Earth" in bundles:
        add_moon(bundles["Earth"], name="Moon",
                 radius=0.27, orbit_radius=1.8,
                 day_frames=frames_for_day(655.7/24.0),
                 year_frames=int(EARTH_YEAR_FRAMES * 0.0748))

    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()     