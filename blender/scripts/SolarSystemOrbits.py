import bpy
import os
import math
from bpy_extras import anim_utils
import importlib
import AddObjectScript

importlib.reload(AddObjectScript)
from AddObjectScript import add_uv_sphere

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

    out = nt.nodes.new("ShaderNodeOutputMaterial"); 
    out.location = (400,0)
    
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); 
    bsdf.location = (100,0)
    
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
            
            tex = nt.nodes.new("ShaderNodeTexImage") 
            tex.location = (-250, 0)
            tex.image = img 
            tex.interpolation = 'Smart'

            
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])


        except:
            print(f"[WARN] Could not load texture: {texture_path}")

    return mat

def make_transparent_sun_material(texture_path=None, strength=8.0, tint=(1.0, 0.9, 0.6, 1.0)):
    # Dynamic name based on tint
    mat_name = f"SunMat_{int(tint[0]*100)}_{int(tint[1]*100)}"
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    
    # Set to Opaque as we removed the Transparent node
    mat.blend_method = 'OPAQUE' 
    
    nt = mat.node_tree
    nt.nodes.clear()

    # 1. Create Core Nodes from your screenshot
    node_out  = nt.nodes.new("ShaderNodeOutputMaterial")
    node_emi  = nt.nodes.new("ShaderNodeEmission")
    node_bw   = nt.nodes.new("ShaderNodeRGBToBW")
    
    # The Multiply node (Mix node set to Multiply)
    node_mult = nt.nodes.new("ShaderNodeMix")
    node_mult.data_type = 'RGBA'
    node_mult.blend_type = 'MULTIPLY'
    node_mult.inputs["Factor"].default_value = 1.0
    
    # 2. Fresnel/Facing Logic (Layer Weight -> Color Ramp)
    node_fres = nt.nodes.new("ShaderNodeLayerWeight")
    node_ramp = nt.nodes.new("ShaderNodeValToRGB") 
    
    # Match your screenshot values (Blend 0.700)
    node_fres.inputs["Blend"].default_value = 0.700
    node_ramp.color_ramp.elements[0].position = 0.0
    node_ramp.color_ramp.elements[1].position = 1.0
    
    # 3. Handling the Texture -> BW -> Mix Slot A
    if texture_path and os.path.exists(texture_path):
        node_tex = nt.nodes.new("ShaderNodeTexImage")
        node_tex.image = bpy.data.images.load(texture_path)
        
        # Link Texture to RGB to BW
        nt.links.new(node_tex.outputs["Color"], node_bw.inputs["Color"])
        # Link BW Result to Mix Slot A (Index 6)
        nt.links.new(node_bw.outputs["Val"], node_mult.inputs[6])
    else:
        # Fallback: if no texture, keep Slot A white so tint shows fully
        node_mult.inputs[6].default_value = (1.0, 1.0, 1.0, 1.0)

    # 4. FEEDING THE TINT INTO THE COLOR MIXER (Slot B / Index 7)
    node_mult.inputs[7].default_value = tint

    # 5. Emission and Final Output
    node_emi.inputs["Strength"].default_value = strength

    # Connect the Multiplied (Tinted) result to Emission Color
    nt.links.new(node_mult.outputs[2], node_emi.inputs["Color"])
    
    # Connect the Facing to Color Ramp (Following your screenshot's logic)
    nt.links.new(node_fres.outputs["Facing"], node_ramp.inputs["Fac"])

    # Output to Surface
    nt.links.new(node_emi.outputs["Emission"], node_out.inputs["Surface"])

    return mat


def make_ring_material(name, alpha_val):
    mat_name = f"Material-Rings-{name}"
    mat = bpy.data.materials.get(mat_name) or bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    
    
    if hasattr(mat, "transparent_method"):
        mat.transparent_method = 'HASHED'

    
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    node_out = nodes.new("ShaderNodeOutputMaterial")
    node_bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    
    node_bsdf.inputs['Alpha'].default_value = alpha_val
    node_bsdf.inputs['Roughness'].default_value = 0.5

    links.new(node_bsdf.outputs["BSDF"], node_out.inputs["Surface"])
    
    return mat

# =========================
# GEOMETRY
# =========================
def add_sphere(name, location=(0,0,0), radius=1.0):
 
    return add_uv_sphere(name, location, radius)

def add_orbit_curve(
        name, 
        semi_major_axis,
        center=(0,0,0), 
        eccentricity=1.0,
        inclination=0.0,
        arg_periapsis=0.0,
        long_asc_node=0.0
        ):
    """
    Create an orbit path. 
    """
    bpy.ops.curve.primitive_bezier_circle_add(
        radius=semi_major_axis, 
        location=center
    )
    curve = bpy.context.object
    curve.name = name

    cu = curve.data
    # keep as a thin guide path
    cu.bevel_depth = 0.0
    cu.use_path = True  # REQUIRED for eval_time animation
    cu.path_duration = EARTH_YEAR_FRAMES

    b = semi_major_axis * math.sqrt(1 - eccentricity**2)

    # Scale Y
    curve.scale[1] = b / semi_major_axis  


    # Orbital Orientation
    asc = math.radians(long_asc_node)
    inc = math.radians(inclination)
    peri = math.radians(arg_periapsis)

    curve.rotation_mode = "XYZ"
    curve.rotation_euler = (0.0, 0.0, 0.0)

    curve.rotation_euler.rotate_axis('Z', asc)

    curve.rotation_euler.rotate_axis('X', inc)

    curve.rotation_euler.rotate_axis('Z', peri)

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
    if spin_ctrl.animation_data:
        
        channelbag = anim_utils.action_get_channelbag_for_slot(spin_ctrl.animation_data.action, spin_ctrl.animation_data.action_slot)
        for fc in channelbag.fcurves:
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
    if cu.animation_data:
        
        channelbag = anim_utils.action_get_channelbag_for_slot(cu.animation_data.action, cu.animation_data.action_slot)
        for fc in channelbag.fcurves:
            if fc.data_path == "eval_time":
                _linear_and_cycle(fc)

# =========================
# BUILDERS (with hierarchy)
# =========================
def import_obj_as_planet(name, obj_path, target_radius):
    """Import an OBJ file, scale it to target_radius, and return the Blender object."""
    bpy.ops.object.select_all(action='DESELECT')

    bpy.ops.wm.obj_import(filepath=obj_path)

    imported = list(bpy.context.selected_objects)
    if not imported:
        print(f"[WARN] OBJ import returned no objects for {obj_path}, falling back to UV sphere")
        return add_uv_sphere(name, (0, 0, 0), target_radius)

    # Join multiple meshes into one if needed
    bpy.ops.object.select_all(action='DESELECT')
    for o in imported:
        o.select_set(True)
    bpy.context.view_layer.objects.active = imported[0]
    if len(imported) > 1:
        bpy.ops.object.join()

    obj = bpy.context.active_object
    obj.name = name
    obj.location = (0, 0, 0)

    # Scale to match target_radius based on bounding box
    dims = obj.dimensions
    max_dim = max(dims.x, dims.y, dims.z)
    if max_dim > 0:
        scale_factor = (target_radius * 2) / max_dim
        obj.scale = (scale_factor, scale_factor, scale_factor)
        bpy.ops.object.transform_apply(scale=True)

    # Ensure a UV map exists and is active for texture rendering
    bpy.context.view_layer.objects.active = obj
    if obj.data.uv_layers:
        uv = obj.data.uv_layers[0]
        obj.data.uv_layers.active = uv
        uv.active_render = True
    else:
        # No UV map from OBJ — generate one via Smart UV Project
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.02)
        bpy.ops.object.mode_set(mode='OBJECT')
        if obj.data.uv_layers:
            obj.data.uv_layers[0].active_render = True

    return obj


def add_planet(cfg):
    """
    Hierarchy:
      OrbitCtrl-Name  [Follow Path to Orbit-Name curve]  <-- revolution
          └─ SpinCtrl-Name  [axial tilt on X, spin on Z] <-- self-rotation
                └─ Planet-Name (mesh)                    <-- materials, flattening
    """
    name = cfg['name']

    # Orbit path
    orbit_curve = add_orbit_curve(
        f"Orbit-{name}",
        semi_major_axis=cfg["orbit_radius"],
        center=cfg.get("center", (0, 0, 0)),
        eccentricity=cfg.get("ecc", 1.0),
        inclination=cfg.get("inc", 0.0),
        arg_periapsis=cfg.get("peri", 0.0),
        long_asc_node=cfg.get("asc", 0.0)
    )
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
    
    # Apply Z spin first before tilting
    spin_ctrl.rotation_mode = 'ZXY'
    
    # Apply axial tilt on X so Z becomes the tilted axis
    spin_ctrl.rotation_euler = (math.radians(cfg.get("tilt_deg", 0.0)), 0.0, 0.0)
    animate_spin(spin_ctrl, frames_per_rotation=cfg["day_frames"], start_frame=1, direction=cfg.get("spin_dir", 1))

    # Planet mesh
    model_path = cfg.get("model_path")
    if model_path:
        planet = import_obj_as_planet(f"Planet-{name}", model_path, cfg["radius"])
    else:
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
    import bmesh
    

    name_clean = parent_spin_ctrl.name.replace('SpinCtrl-', '')
    mesh = bpy.data.meshes.new(f"Mesh-Rings-{name_clean}")
    ring = bpy.data.objects.new(f"Rings-{name_clean}", mesh)
    
    bpy.context.collection.objects.link(ring)
    ring.parent = parent_spin_ctrl
    ring.location = (0, 0, 0)
    ring.rotation_euler = (0, 0, 0)

    bm = bmesh.new()
    

    bmesh.ops.create_circle(bm, cap_ends=False, radius=inner, segments=128)
    bmesh.ops.create_circle(bm, cap_ends=False, radius=outer, segments=128)
    
    
    bm.edges.ensure_lookup_table()
    bmesh.ops.bridge_loops(bm, edges=bm.edges)


    uv_layer = bm.loops.layers.uv.new("UVMap")
    for face in bm.faces:
        for loop in face.loops:
            vert_coords = loop.vert.co
            
            dist = vert_coords.length
            u = (dist - inner) / (outer - inner)
            loop[uv_layer].uv = (u, 0.5)

    bm.to_mesh(mesh)
    bm.free()

    ring.data.materials.clear()
    ring.data.materials.append(make_ring_material(name_clean, alpha))
    
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
    mat = make_transparent_sun_material(
        texture_path = cfg.get("texture"),
        strength = strength,
        tint = cfg.get("color", (1.0, 0.9, 0.6, 1.0))
    )
    
    sun.data.materials.clear()
    sun.data.materials.append(mat)
    link_to_collection(sun)
    
    
    light_data = bpy.data.lights.new(name="SunInnerLight", type='POINT')
    light_data.energy = strength * 10000.0  
    light_data.color = cfg.get("color", (1.0, 0.9, 0.6))[:3]
    
    light_data.use_shadow = False
    
    
    light_obj = bpy.data.objects.new(name="SunInnerLight", object_data=light_data)
    light_obj.location = cfg.get("location", (0, 0, 0))
    bpy.context.scene.collection.objects.link(light_obj)
    link_to_collection(light_obj)
    

    return sun

def add_moon(
    earth_bundle, 
    name="Moon", 
    radius=0.27, 
    orbit_radius=1.8, 
    day_frames=120, 
    year_frames=300, 
    texture_path=None
):
    # 1. Get Earth's Orbit Controller (The empty moving around the Sun)
    earth_ctrl = earth_bundle["orbit"]

    # 2. CREATE MOON ORBIT CURVE
    # We parent this to Earth's controller so the "center" of the circle is Earth.
    moon_curve = add_orbit_curve(f"Orbit-{name}", radius=orbit_radius, center=(0,0,0))
    moon_curve.parent = earth_ctrl
    moon_curve.matrix_parent_inverse.identity()
    moon_curve.location = (0, 0, 0) # Snap curve center to Earth center

    # 3. CREATE MOON ORBIT CONTROLLER (The Empty that moves on the curve)
    # This is the "middle man" that handles the revolution around Earth.
    moon_orbit_ctrl = bpy.data.objects.new(f"OrbitCtrl-{name}", None)
    moon_orbit_ctrl.empty_display_type = 'PLAIN_AXES'
    bpy.context.scene.collection.objects.link(moon_orbit_ctrl)
    
    # Parent the controller to the Earth controller
    moon_orbit_ctrl.parent = earth_ctrl
    moon_orbit_ctrl.matrix_parent_inverse.identity()
    moon_orbit_ctrl.location = (0, 0, 0) # Snap to Earth center

    # 4. ATTACH & ANIMATE USING YOUR FUNCTIONS
    # This empty now follows the Moon's local circle around Earth
    ensure_follow_path(moon_orbit_ctrl, moon_curve)
    animate_orbit_with_eval_time(moon_curve, frames_per_revolution=year_frames)

    # 5. CREATE MOON MESH
    # Parent the mesh to the Moon's controller, NOT the Earth's.
    moon_mesh = add_sphere(f"Moon-{name}", location=(0,0,0), radius=radius)
    moon_mesh.parent = moon_orbit_ctrl
    moon_mesh.matrix_parent_inverse.identity()
    moon_mesh.location = (0,0,0) # Must be (0,0,0) to stay on the path

    # 6. SPIN & MATERIAL
    # We can create a spin controller if needed, but for simplicity, we spin the mesh
    animate_spin(moon_mesh, frames_per_rotation=day_frames)
    
    mat = make_planet_material(name, color=(0.7, 0.7, 0.7, 1.0), texture_path=texture_path)
    moon_mesh.data.materials.append(mat)

    return {"mesh": moon_mesh, "orbit": moon_orbit_ctrl}

## =========================
## DATA (temporary)
## =========================
#Y = {  # orbital periods in Earth years
#    "Mercury": 0.2408467, "Venus": 0.61519726, "Earth": 1.0, "Mars": 1.8808158,
#    "Jupiter": 11.862615, "Saturn": 29.447498, "Uranus": 84.016846, "Neptune": 164.79132
#}
#TILT = {  # axial tilts (deg)
#    "Mercury": 0.03, "Venus": 177.4, "Earth": 23.44, "Mars": 25.19,
#    "Jupiter": 3.13, "Saturn": 26.73, "Uranus": 97.77, "Neptune": 28.32
#}
#ROT_H = {  # sidereal rotation hours; negative = retrograde (Venus, Uranus)
#    "Mercury": 1407.5, "Venus": -5832.5, "Earth": 23.934, "Mars": 24.623,
#    "Jupiter": 9.925,  "Saturn": 10.656,  "Uranus": -17.24,  "Neptune": 16.11
#}
#FLAT = {  # flattening (approx)
#    "Mercury": 0.00006, "Venus": 0.0001, "Earth": 1/298.257, "Mars": 0.00589,
#    "Jupiter": 0.06487, "Saturn": 0.09796, "Uranus": 0.0229,  "Neptune": 0.0171
#}
#R = {  # display radii (artistic scale; Earth=1)
#    "Mercury": 0.30, "Venus": 0.95, "Earth": 1.00, "Mars": 0.53,
#    "Jupiter": 2.80, "Saturn": 2.40, "Uranus": 1.80, "Neptune": 1.70
#}
#A = {  # orbit radii (scene units)
#    "Mercury": 8.0, "Venus": 12.0, "Earth": 16.0, "Mars": 20.0,
#    "Jupiter": 28.0, "Saturn": 36.0, "Uranus": 44.0, "Neptune": 52.0
#}

def frames_for_day(hours):   # map real hours to frames
   return max(10, int(EARTH_DAY_FRAMES * (abs(hours)/24.0)))
def spin_dir(hours):         # retrograde sign
   return -1 if hours < 0 else 1

## =========================
## MAIN
## =========================
#if __name__ == "__main__":
#    # scene
#    bpy.context.scene.render.fps = FPS
#    bpy.context.scene.frame_start = 1
#    bpy.context.scene.frame_end   = 4000

#    # cleanup
#    delete_grouped()
#    delete_unused_materials()
#    delete_unused_images()


#    # Planets
#    bundles = {}
#    order = ["Mercury","Venus","Earth","Mars","Jupiter","Saturn","Uranus","Neptune"]

#    for name in order:
#        cfg = dict(
#            name=name,
#            radius=R[name],
#            color=(1, 1, 1, 1),
#            texture=os.path.join(
#                TEX_DIR, f"{name.lower()}.jpg"
#            ) if os.path.exists(os.path.join(TEX_DIR, f"{name.lower()}.jpg")) else None,
#            tilt_deg=TILT[name],
#            flattening=FLAT[name],
#            orbit_radius=A[name] * SYSTEM_SCALE,
#            year_frames=max(60, int(EARTH_YEAR_FRAMES * Y[name])),
#            day_frames=frames_for_day(ROT_H[name]),
#            spin_dir=spin_dir(ROT_H[name]),
#            with_rings=(name == "Saturn"),
#            rings_inner=1.2,
#            rings_outer=2.2,
#            # elliptical orbits: >1.0 = stretched along X
#            ellipse_factor=1.2
#        )
#        bundles[name] = add_planet(cfg)

#    # Moons
#    if "Earth" in bundles:
#        add_moon(bundles["Earth"], name="Moon",
#                 radius=0.27, orbit_radius=1.8,
#                 day_frames=frames_for_day(655.7 / 24.0),
#                 year_frames=int(EARTH_YEAR_FRAMES * 0.0748))
#                 
#    # Sun
#    add_sun(cfg, strength=8.0)

#    bpy.context.scene.frame_set(1)
#    bpy.context.view_layer.update()
