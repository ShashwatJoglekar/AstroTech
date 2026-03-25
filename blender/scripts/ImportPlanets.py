import bpy
import sys
import os
import importlib
import math
import csv
import random
import array

# Import other scripts
blend_dir = os.path.dirname(bpy.data.filepath)
scripts_dir = os.path.join(blend_dir, "scripts")
if scripts_dir not in sys.path:
    sys.path.append(scripts_dir)

import SolarSystemOrbits
importlib.reload(SolarSystemOrbits)
from SolarSystemOrbits import add_planet, add_sun, add_moon, frames_for_day, spin_dir, ensure_follow_path, make_planet_material


# =========================
# HELPER FUNCTIONS
# =========================
def clear_scene():
    """
    Deletes all objects, collections, and orphaned data blocks from the scene.
    """
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    # Remove all non-master collections
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)

    # Clear unused data blocks (meshes, curves, materials, images)
    for block in list(bpy.data.meshes):
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in list(bpy.data.curves):
        if block.users == 0:
            bpy.data.curves.remove(block)
    for block in list(bpy.data.materials):
        if block.users == 0:
            bpy.data.materials.remove(block)
    for block in list(bpy.data.images):
        if block.users == 0:
            bpy.data.images.remove(block)


# =========================
# GLOBAL SETTINGS
# =========================
FPS = 60
EARTH_DAY_FRAMES  = 180 # 1 Earth day = 120 frames (3s @ 60fps)
EARTH_YEAR_FRAMES = 1800 # 1 Earth year = 1200 frames (30s @ 60fps)
SYSTEM_SCALE = 1.0
RING_ALPHA   = 0.55

# Control how many Gaia objects to load (set to 0 to skip, or up to 30000)
NUM_GAIA_OBJECTS = 30000 #154741  # Change this value to load more/fewer objects

BASE_DIR = bpy.path.abspath("//")
TEX_DIR = os.path.join(BASE_DIR, "assets", "textures")
MODELS_DIR = os.path.join(BASE_DIR, "assets", "models")

# Try multiple locations for the CSV file
csv_locations = [
    os.path.join(scripts_dir, "gaia_solar_system_xyz_150kobjects.csv"),  # scripts directory
    os.path.join(BASE_DIR, "gaia_solar_system_xyz_150kobjects.csv"),     # blender directory  
    os.path.join(os.path.dirname(BASE_DIR), "gaia_solar_system_xyz_150kobjects.csv"),  # project root
]

GAIA_CSV = None
for csv_path in csv_locations:
    if os.path.exists(csv_path):
        GAIA_CSV = csv_path
        print(f"[GAIA] Found CSV at: {GAIA_CSV}")
        break

if GAIA_CSV is None:
    print("[GAIA] WARNING: CSV not found! Searched:")
    for loc in csv_locations:
        print(f"  - {loc} (exists: {os.path.exists(loc)})")
    GAIA_CSV = csv_locations[0]

TEX_DIR = os.path.normpath(TEX_DIR)
print(f"[GAIA] Will attempt to load {NUM_GAIA_OBJECTS} objects")

clear_scene()


class AstroObject:
    def __init__(self,
                 name,
                 location=(0,0,0),
                 radius=1.0,
                 rotating_velocity=0.0,
                 orbit_radius=0.0,
                 orbit_velocity=0.0,
                 mass=0.0,
                 texture=None,
                 tilt_deg=0.0,
                 flattening=0.0,
                 rotating_hours=24.0,
                 spin_dir=1,
                 with_rings=False,
                 rings_inner=1.2,
                 rings_outer=2.2):
        self.name = name
        self.location = location
        self.radius = radius
        self.rotating_velocity = rotating_velocity
        self.orbit_radius = orbit_radius
        self.orbit_velocity = orbit_velocity
        self.mass = mass
        self.texture = texture
        self.tilt_deg = tilt_deg
        self.flattening = flattening
        self.rotating_hours = rotating_hours
        self.spin_dir = spin_dir
        self.with_rings = with_rings
        self.rings_inner = rings_inner
        self.rings_outer = rings_outer



# =========================
# SCALE FACTORS
# =========================
RADIUS_SCALE = 1e-6
ORBIT_SCALE  = 20


# =========================
# GAIA DATA LOADER
# =========================
# DEPRECATED — replaced by add_gaia_fast(). Kept for reference.
def load_gaia_objects(csv_path, num_objects=100):
    """
    Load Gaia solar system objects from CSV using Python's built-in csv module.
    s
    Args:
        csv_path: Path to the gaia_solar_system_xyz_30kobjects.csv file
        num_objects: Number of objects to load (0 to skip, max 30000)
    
    Returns:
        Dictionary of objects in SolarSystem format
    """
    if num_objects <= 0:
        print("Skipping Gaia objects (NUM_GAIA_OBJECTS = 0)")
        return {}
    
    if not os.path.exists(csv_path):
        print(f"Warning: Gaia CSV not found at {csv_path}")
        return {}
    
    print(f"Loading {num_objects} Gaia objects from CSV...")
    
    gaia_objects = {}

    model_files = [
        os.path.join(MODELS_DIR, f)
        for f in os.listdir(MODELS_DIR)
        if f.lower().endswith('.obj')
    ] if os.path.isdir(MODELS_DIR) else []
    if not model_files:
        print(f"[GAIA] WARNING: No .obj models found in {MODELS_DIR}")

    try:
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            for idx, row in enumerate(reader):
                if idx >= num_objects:
                    break
                
                name = row['denomination']
                
                # Parse numeric values from CSV
                x_au = float(row['X_AU'])
                y_au = float(row['Y_AU'])
                z_au = float(row['Z_AU'])
                
                # Use semi_major_axis if available, otherwise use distance
                orbit_radius_au = float(row.get('semi_major_axis_AU', row['distance_AU']))
                
                # Scale orbit radius to scene units (similar to planets)
                orbit_radius = ORBIT_SCALE * orbit_radius_au
                
                # Small radius for asteroids/minor objects (much smaller than planets)
                obj_radius = 0.05  # Small visual size for asteroids
                
                # Get orbital elements
                eccentricity = float(row.get('eccentricity', 0.0))
                inclination = float(row.get('inclination_deg', 0.0))
                mean_anomaly = float(row.get('mean_anomaly', 0.0))
                
                # Estimate orbital period using Kepler's third law (T² ∝ a³)
                # Period in Earth years = a^1.5 (where a is in AU)
                period_years = orbit_radius_au ** 1.5
                year_frames = max(60, int(EARTH_YEAR_FRAMES * period_years / 3))
                
                # Create object configuration
                gaia_objects[name] = dict(
                    name=name,
                    radius=obj_radius,
                    color=(0.7, 0.7, 0.7, 1),  # Gray color for asteroids
                    texture=os.path.join(TEX_DIR, "Generic_Celestia_asteroid_texture.jpg"),
                    model_path=random.choice(model_files) if model_files else None,
                    tilt_deg=0.0,  # Default tilt
                    flattening=0.0,  # Spherical
                    year_frames=year_frames,
                    day_frames=frames_for_day(10.0),  # Arbitrary rotation
                    spin_dir=1,
                    orbit_radius=orbit_radius,
                    ecc=eccentricity,
                    inc=inclination,
                    asc=0.0,  # Longitude of ascending node (not in CSV, default to 0)
                    peri=mean_anomaly,  # Use mean anomaly as argument of periapsis approximation
                )
        
        print(f"Successfully loaded {len(gaia_objects)} Gaia objects")
        
    except Exception as e:
        print(f"Error loading Gaia objects: {e}")
        return {}
    
    return gaia_objects


# =========================
# FAST GAIA LOADER (geometry instancing via linked mesh copies)
# =========================

def _find_layer_collection(layer_coll, name):
    """Recursively find a LayerCollection by its collection name."""
    if layer_coll.collection.name == name:
        return layer_coll
    for child in layer_coll.children:
        result = _find_layer_collection(child, name)
        if result:
            return result
    return None


def _import_asteroid_prototypes():
    """
    Import asteroid_1.obj–asteroid_5.obj exactly once.
    Returns a list of bpy.types.Object (prototype meshes).
    Each prototype is hidden from viewport/render — only its mesh data is reused.
    """
    prototypes = []
    for i in range(1, 6):
        path = os.path.join(MODELS_DIR, f"asteroid_{i}.obj")
        if not os.path.exists(path):
            print(f"[GAIA] WARNING: {path} not found, skipping prototype {i}")
            continue

        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.wm.obj_import(filepath=path)
        imported = list(bpy.context.selected_objects)
        if not imported:
            print(f"[GAIA] WARNING: OBJ import returned nothing for asteroid_{i}.obj")
            continue

        if len(imported) > 1:
            bpy.context.view_layer.objects.active = imported[0]
            for o in imported:
                o.select_set(True)
            bpy.ops.object.join()

        proto = bpy.context.active_object
        proto.name = f"AsteroidProto_{i}"

        # Scale to 0.1 Blender units (small relative to planets)
        max_dim = max(proto.dimensions)
        if max_dim > 0:
            sf = 0.1 / max_dim
            proto.scale = (sf, sf, sf)
            bpy.ops.object.transform_apply(scale=True)

        # Generate UV map if the OBJ didn't include one (needed for texturing)
        bpy.context.view_layer.objects.active = proto
        if proto.data.uv_layers:
            proto.data.uv_layers[0].active_render = True
        else:
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.02)
            bpy.ops.object.mode_set(mode='OBJECT')
            if proto.data.uv_layers:
                proto.data.uv_layers[0].active_render = True

        # Assign the shared asteroid material so GN ObjectInfo instances carry it.
        mat = _make_shared_asteroid_material()
        proto.data.materials.clear()
        proto.data.materials.append(mat)

        # Move far off-screen so they don't clutter the viewport.
        # Do NOT use hide_set(True) — that removes the object from the depsgraph
        # and makes GeometryNodeObjectInfo return empty geometry.
        proto.location = (0, 0, -9999)
        proto.hide_render = True

        prototypes.append(proto)
        print(f"[GAIA] Imported prototype: {proto.name}")

    return prototypes


def _make_orbit_curve_data(name, semi_major_axis, eccentricity, inclination, arg_periapsis, long_asc_node):
    """
    Create an elliptical orbit curve via bpy.data (no bpy.ops).
    Mirrors add_orbit_curve() from SolarSystemOrbits exactly:
      - builds a circular bezier (radius = semi_major_axis)
      - squashes Y via scale[1] = b / semi_major_axis  to form the ellipse
      - applies orbital orientation rotations in the same Z-X-Z order
    Returns the curve Object (not yet linked to any collection).
    """
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.use_path = True
    cu.bevel_depth = 0.0
    cu.path_duration = EARTH_YEAR_FRAMES  # overridden later by animate_orbit_with_eval_time

    sp = cu.splines.new('BEZIER')
    sp.bezier_points.add(3)  # adds 3 more → 4 total
    sp.use_cyclic_u = True

    r = semi_major_axis
    H = 0.5522847498  # handle length constant for a bezier circle approximation

    # 4 control points for a unit circle of radius r (counterclockwise)
    # Tuple layout: (co, handle_left, handle_right)
    circle_pts = [
        ((r,  0, 0), (r,  -H*r, 0), (r,   H*r, 0)),
        ((0,  r, 0), (H*r,  r,  0), (-H*r, r,  0)),
        ((-r, 0, 0), (-r,  H*r, 0), (-r, -H*r, 0)),
        ((0, -r, 0), (-H*r, -r, 0), (H*r, -r,  0)),
    ]
    for i, (co, hl, hr) in enumerate(circle_pts):
        bp = sp.bezier_points[i]
        bp.co = co
        bp.handle_left = hl
        bp.handle_right = hr
        bp.handle_left_type = 'FREE'
        bp.handle_right_type = 'FREE'

    curve_obj = bpy.data.objects.new(name, cu)

    # Squash Y to form the ellipse — identical to add_orbit_curve's scale[1] line
    b = semi_major_axis * math.sqrt(max(0.0, 1.0 - eccentricity ** 2))
    curve_obj.scale[1] = b / semi_major_axis

    # Apply orbital orientation (same Z-X-Z order as add_orbit_curve)
    curve_obj.rotation_mode = 'XYZ'
    curve_obj.rotation_euler.rotate_axis('Z', math.radians(long_asc_node))
    curve_obj.rotation_euler.rotate_axis('X', math.radians(inclination))
    curve_obj.rotation_euler.rotate_axis('Z', math.radians(arg_periapsis))

    return curve_obj


def _animate_orbit_fast(path_obj, frames_per_revolution, start_frame=1):
    """
    Like animate_orbit_with_eval_time() but avoids frame_set().
    frame_set() forces a full depsgraph evaluation of every object already in the
    scene, making a loop over N asteroids O(N²). Using keyframe_insert(frame=...)
    inserts at the target frame without triggering that evaluation.
    """
    from bpy_extras import anim_utils

    cu = path_obj.data
    cu.use_path = True
    cu.path_duration = max(2, int(frames_per_revolution))

    cu.eval_time = 0.0
    cu.keyframe_insert(data_path="eval_time", frame=start_frame)
    cu.eval_time = float(frames_per_revolution)
    cu.keyframe_insert(data_path="eval_time", frame=start_frame + int(frames_per_revolution))

    if cu.animation_data:
        channelbag = anim_utils.action_get_channelbag_for_slot(
            cu.animation_data.action, cu.animation_data.action_slot
        )
        for fc in channelbag.fcurves:
            if fc.data_path == "eval_time":
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
                mod = fc.modifiers.new(type='CYCLES')
                mod.mode_before = 'REPEAT'
                mod.mode_after  = 'REPEAT'


def _make_shared_asteroid_material():
    """Create (or retrieve) a single shared material for all GAIA asteroids."""
    mat = bpy.data.materials.get("Material-Asteroid-Shared")
    if mat:
        return mat
    tex_path = os.path.join(TEX_DIR, "Generic_Celestia_asteroid_texture.jpg")
    return make_planet_material(
        "Asteroid-Shared",
        color=(0.7, 0.7, 0.7, 1.0),
        texture_path=tex_path if os.path.exists(tex_path) else None,
    )


def add_gaia_fast(csv_path, num_objects):
    """
    Fast GAIA asteroid loader. Replaces load_gaia_objects() + per-asteroid add_planet().

    Key speedups vs the old approach:
      - Imports 5 OBJ prototypes ONCE (vs once per asteroid)
      - Creates linked mesh copies via bpy.data.objects.new() — zero re-import cost
      - Creates orbit curves via bpy.data (no bpy.ops context overhead)
      - Drops SpinCtrl per asteroid (no axial tilt / self-rotation needed)
      - Uses a single shared material for all 30k asteroids

    Per-asteroid Keplerian orbit animation is preserved via ensure_follow_path
    + animate_orbit_with_eval_time (same as planets).
    """
    if num_objects <= 0 or not os.path.exists(csv_path):
        return

    print(f"[GAIA] Building {num_objects} asteroids (fast path)...")

    # --- 1. Import 5 OBJ prototypes once ---
    prototypes = _import_asteroid_prototypes()
    if not prototypes:
        print("[GAIA] No prototypes imported — aborting fast loader")
        return

    mat = _make_shared_asteroid_material()

    # --- 2. Move prototypes into a hidden collection ---
    proto_coll = bpy.data.collections.new("AsteroidPrototypes")
    bpy.context.scene.collection.children.link(proto_coll)
    for p in prototypes:
        for c in list(p.users_collection):
            c.objects.unlink(p)
        proto_coll.objects.link(p)
    lc = _find_layer_collection(bpy.context.view_layer.layer_collection, "AsteroidPrototypes")
    if lc:
        lc.exclude = True

    # --- 3. Collection for all GAIA asteroid objects ---
    gaia_coll = bpy.data.collections.new("GAIA Asteroids")
    bpy.context.scene.collection.children.link(gaia_coll)

    # --- 4. Per-asteroid: orbit curve + OrbitCtrl empty + linked mesh ---
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            if idx >= num_objects:
                break

            name = row['denomination']

            # Orbital parameters
            sma_str = row.get('semi_major_axis_AU', '').strip()
            orbit_radius_au = float(sma_str) if sma_str else float(row['distance_AU'])
            orbit_radius    = ORBIT_SCALE * orbit_radius_au
            ecc  = float(row.get('eccentricity', 0.0) or 0.0)
            inc  = float(row.get('inclination_deg', 0.0) or 0.0)
            peri = float(row.get('mean_anomaly', 0.0) or 0.0)
            period_years = orbit_radius_au ** 1.5
            year_frames  = max(60, int(EARTH_YEAR_FRAMES * period_years / 3))

            # Orbit curve via bpy.data
            orbit_curve = _make_orbit_curve_data(
                f"Orbit-{name}", orbit_radius, ecc, inc, peri, long_asc_node=0.0
            )
            gaia_coll.objects.link(orbit_curve)

            # OrbitCtrl empty via bpy.data
            orbit_ctrl = bpy.data.objects.new(f"OrbitCtrl-{name}", None)
            orbit_ctrl.empty_display_type = 'PLAIN_AXES'
            gaia_coll.objects.link(orbit_ctrl)
            ensure_follow_path(orbit_ctrl, orbit_curve)
            _animate_orbit_fast(orbit_curve, frames_per_revolution=year_frames, start_frame=1)

            # Asteroid mesh — linked copy of prototype (shares mesh data, no OBJ import)
            proto = prototypes[idx % len(prototypes)]
            asteroid = bpy.data.objects.new(f"Planet-{name}", proto.data)
            asteroid.parent = orbit_ctrl
            gaia_coll.objects.link(asteroid)
            asteroid.data.materials.clear()
            asteroid.data.materials.append(mat)

            if idx % 500 == 0:
                print(f"[GAIA] {idx}/{num_objects} asteroids created...")

    print(f"[GAIA] Done — {min(num_objects, idx + 1)} asteroids in 'GAIA Asteroids' collection.")


def _build_gn_orbital_tree(ng, prototypes):
    """
    Populate a GeometryNodeTree with a first-order Keplerian orbit solver.

    Per-point FLOAT attributes consumed:
      semi_major_axis  — scene units (AU × ORBIT_SCALE)
      eccentricity     — 0–1
      inclination      — radians
      arg_periapsis    — radians
      mean_anomaly     — radians at frame 0
      period_frames    — frames per full orbit
    Per-point INT attribute consumed:
      model_index      — 0–4, selects which prototype to instance

    Math used (first-order Kepler, error ≈ O(e²)):
      M(t)  = M₀ + (frame / T) · 2π
      E     ≈ M + e·sin(M)
      ν     ≈ E + 2e·sin(E)
      r     = a·(1 − e·cos(E))
      x_orb = r·cos(ν),  y_orb = r·sin(ν)
      x₁    = x_orb·cos(ω) − y_orb·sin(ω)   (rotate by arg_periapsis ω)
      y₁    = x_orb·sin(ω) + y_orb·cos(ω)
      x_w   = x₁,  y_w = y₁·cos(i),  z_w = y₁·sin(i)
    """
    nodes = ng.nodes
    links = ng.links
    TAU   = 2.0 * math.pi

    def mth(op, x, y, v0=None, v1=None):
        n = nodes.new('ShaderNodeMath')
        n.operation = op
        n.location   = (x, y)
        if v0 is not None: n.inputs[0].default_value = float(v0)
        if v1 is not None: n.inputs[1].default_value = float(v1)
        return n

    def fa(name, x, y):   # float named attribute
        n = nodes.new('GeometryNodeInputNamedAttribute')
        n.data_type = 'FLOAT'
        n.inputs[0].default_value = name
        n.location = (x, y)
        return n

    def ia(name, x, y):   # int named attribute
        n = nodes.new('GeometryNodeInputNamedAttribute')
        n.data_type = 'INT'
        n.inputs[0].default_value = name
        n.location = (x, y)
        return n

    # ── I/O ───────────────────────────────────────────────────────────────
    n_in  = nodes.new('NodeGroupInput');  n_in.location  = (-2400,    0)
    n_out = nodes.new('NodeGroupOutput'); n_out.location = ( 2200,    0)

    # ── Scene time & attributes ───────────────────────────────────────────
    n_t   = nodes.new('GeometryNodeInputSceneTime'); n_t.location = (-2200, 800)
    n_a   = fa('semi_major_axis', -2200,  600)
    n_e   = fa('eccentricity',    -2200,  400)
    n_inc = fa('inclination',     -2200,  200)
    n_per = fa('arg_periapsis',   -2200,    0)
    n_asc = fa('long_asc_node',   -2200, -200)
    n_m0  = fa('mean_anomaly',    -2200, -400)
    n_T   = fa('period_frames',   -2200, -600)
    n_mi  = ia('model_index',     -2200, -800)

    # ── M = M₀ + (frame / T) · 2π ────────────────────────────────────────
    dT   = mth('DIVIDE',   -1900, 600)
    links.new(n_t.outputs['Frame'],       dT.inputs[0])
    links.new(n_T.outputs['Attribute'],   dT.inputs[1])
    mTAU = mth('MULTIPLY', -1700, 600, v1=TAU)
    links.new(dT.outputs['Value'],        mTAU.inputs[0])
    M    = mth('ADD',      -1500, 600)
    links.new(n_m0.outputs['Attribute'],  M.inputs[0])
    links.new(mTAU.outputs['Value'],      M.inputs[1])

    # ── E ≈ M + e·sin(M) ─────────────────────────────────────────────────
    sM   = mth('SINE',     -1300,  400);  links.new(M.outputs['Value'],         sM.inputs[0])
    esM  = mth('MULTIPLY', -1100,  400);  links.new(n_e.outputs['Attribute'],  esM.inputs[0]); links.new(sM.outputs['Value'],   esM.inputs[1])
    E    = mth('ADD',       -900,  500);  links.new(M.outputs['Value'],          E.inputs[0]); links.new(esM.outputs['Value'],    E.inputs[1])

    # ── ν ≈ E + 2e·sin(E) ────────────────────────────────────────────────
    sE   = mth('SINE',      -700,  300);  links.new(E.outputs['Value'],         sE.inputs[0])
    esE  = mth('MULTIPLY',  -500,  300);  links.new(n_e.outputs['Attribute'],  esE.inputs[0]); links.new(sE.outputs['Value'],   esE.inputs[1])
    twesE= mth('MULTIPLY',  -300,  300, v0=2.0);                                               links.new(esE.outputs['Value'], twesE.inputs[1])
    nu   = mth('ADD',       -100,  400);  links.new(E.outputs['Value'],         nu.inputs[0]); links.new(twesE.outputs['Value'], nu.inputs[1])

    # ── r = a·(1 − e·cos(E)) ─────────────────────────────────────────────
    cE   = mth('COSINE',    -700,  100);  links.new(E.outputs['Value'],         cE.inputs[0])
    ecE  = mth('MULTIPLY',  -500,  100);  links.new(n_e.outputs['Attribute'],  ecE.inputs[0]); links.new(cE.outputs['Value'],   ecE.inputs[1])
    s1   = mth('SUBTRACT',  -300,  100, v0=1.0);                                               links.new(ecE.outputs['Value'],   s1.inputs[1])
    r    = mth('MULTIPLY',  -100,  200);  links.new(n_a.outputs['Attribute'],    r.inputs[0]); links.new(s1.outputs['Value'],     r.inputs[1])

    # ── Orbital-plane position ────────────────────────────────────────────
    cNu  = mth('COSINE',     100,  400);  links.new(nu.outputs['Value'],       cNu.inputs[0])
    xO   = mth('MULTIPLY',   300,  400);  links.new(r.outputs['Value'],         xO.inputs[0]); links.new(cNu.outputs['Value'],   xO.inputs[1])
    sNu  = mth('SINE',       100,  200);  links.new(nu.outputs['Value'],       sNu.inputs[0])
    yO   = mth('MULTIPLY',   300,  200);  links.new(r.outputs['Value'],         yO.inputs[0]); links.new(sNu.outputs['Value'],   yO.inputs[1])

    # ── Rotate by arg_periapsis ω ─────────────────────────────────────────
    cP   = mth('COSINE',     100, -200);  links.new(n_per.outputs['Attribute'], cP.inputs[0])
    sP   = mth('SINE',       100, -400);  links.new(n_per.outputs['Attribute'], sP.inputs[0])
    xcP  = mth('MULTIPLY',   500,  400);  links.new(xO.outputs['Value'],       xcP.inputs[0]); links.new(cP.outputs['Value'],  xcP.inputs[1])
    ysP  = mth('MULTIPLY',   500,  200);  links.new(yO.outputs['Value'],       ysP.inputs[0]); links.new(sP.outputs['Value'],  ysP.inputs[1])
    x1   = mth('SUBTRACT',   700,  300);  links.new(xcP.outputs['Value'],       x1.inputs[0]); links.new(ysP.outputs['Value'],  x1.inputs[1])
    xsP  = mth('MULTIPLY',   500, -200);  links.new(xO.outputs['Value'],       xsP.inputs[0]); links.new(sP.outputs['Value'],  xsP.inputs[1])
    ycP  = mth('MULTIPLY',   500, -400);  links.new(yO.outputs['Value'],       ycP.inputs[0]); links.new(cP.outputs['Value'],  ycP.inputs[1])
    y1   = mth('ADD',        700, -300);  links.new(xsP.outputs['Value'],       y1.inputs[0]); links.new(ycP.outputs['Value'],  y1.inputs[1])

    # ── Apply inclination i ───────────────────────────────────────────────
    cI   = mth('COSINE',     100, -600);  links.new(n_inc.outputs['Attribute'], cI.inputs[0])
    sI   = mth('SINE',       100, -800);  links.new(n_inc.outputs['Attribute'], sI.inputs[0])
    yW   = mth('MULTIPLY',   900, -300);  links.new(y1.outputs['Value'],        yW.inputs[0]); links.new(cI.outputs['Value'],   yW.inputs[1])
    zW   = mth('MULTIPLY',   900, -500);  links.new(y1.outputs['Value'],        zW.inputs[0]); links.new(sI.outputs['Value'],   zW.inputs[1])

    # ── Rotate by long_asc_node Ω (Z-axis rotation) ──────────────────────
    # x_final = x1·cos(Ω) − yW·sin(Ω)
    # y_final = x1·sin(Ω) + yW·cos(Ω)
    cAsc = mth('COSINE',   1100, -700);  links.new(n_asc.outputs['Attribute'], cAsc.inputs[0])
    sAsc = mth('SINE',     1100, -900);  links.new(n_asc.outputs['Attribute'], sAsc.inputs[0])
    x1cA = mth('MULTIPLY', 1300, -700);  links.new(x1.outputs['Value'],  x1cA.inputs[0]); links.new(cAsc.outputs['Value'], x1cA.inputs[1])
    yWsA = mth('MULTIPLY', 1300, -900);  links.new(yW.outputs['Value'],  yWsA.inputs[0]); links.new(sAsc.outputs['Value'], yWsA.inputs[1])
    xF   = mth('SUBTRACT', 1500, -700);  links.new(x1cA.outputs['Value'],  xF.inputs[0]); links.new(yWsA.outputs['Value'],   xF.inputs[1])
    x1sA = mth('MULTIPLY', 1500, -900);  links.new(x1.outputs['Value'],  x1sA.inputs[0]); links.new(sAsc.outputs['Value'], x1sA.inputs[1])
    yWcA = mth('MULTIPLY', 1500,-1100);  links.new(yW.outputs['Value'],  yWcA.inputs[0]); links.new(cAsc.outputs['Value'], yWcA.inputs[1])
    yF   = mth('ADD',      1700, -900);  links.new(x1sA.outputs['Value'],  yF.inputs[0]); links.new(yWcA.outputs['Value'],   yF.inputs[1])

    # ── Combine → Set Position ────────────────────────────────────────────
    cXYZ = nodes.new('ShaderNodeCombineXYZ'); cXYZ.location = (1900, -100)
    links.new(xF.outputs['Value'],  cXYZ.inputs['X'])
    links.new(yF.outputs['Value'],  cXYZ.inputs['Y'])
    links.new(zW.outputs['Value'],  cXYZ.inputs['Z'])

    spos = nodes.new('GeometryNodeSetPosition'); spos.location = (2100, 200)
    links.new(n_in.outputs['Geometry'], spos.inputs['Geometry'])
    links.new(cXYZ.outputs['Vector'],   spos.inputs['Position'])

    # ── Instance on Points ────────────────────────────────────────────────
    # One InstanceOnPoints per prototype, gated by (model_index == k).
    # Avoids GeometryToInstance + Pick Instance ordering issues.
    iop_outputs = []
    for k, proto in enumerate(prototypes):
        oi = nodes.new('GeometryNodeObjectInfo')
        oi.transform_space = 'ORIGINAL'
        oi.inputs['Object'].default_value = proto
        oi.location = (1300, 900 - k * 220)

        # model_index == k  (FunctionNodeCompare, INT mode)
        cmp = nodes.new('FunctionNodeCompare')
        cmp.data_type = 'INT'
        cmp.operation = 'EQUAL'
        cmp.location  = (1500, 900 - k * 220)
        links.new(n_mi.outputs['Attribute'], cmp.inputs[2])  # INT A
        cmp.inputs[3].default_value = k                      # INT B (constant)

        iop_k = nodes.new('GeometryNodeInstanceOnPoints')
        iop_k.location = (1700, 900 - k * 220)
        links.new(spos.outputs['Geometry'], iop_k.inputs['Points'])
        links.new(oi.outputs['Geometry'],   iop_k.inputs['Instance'])
        links.new(cmp.outputs['Result'],    iop_k.inputs['Selection'])
        iop_outputs.append(iop_k)

    n_join_out = nodes.new('GeometryNodeJoinGeometry'); n_join_out.location = (1950, 400)
    for iop_k in iop_outputs:
        links.new(iop_k.outputs['Instances'], n_join_out.inputs['Geometry'])

    links.new(n_join_out.outputs['Geometry'], n_out.inputs['Geometry'])


def add_gaia_geometry_nodes_animated(csv_path, num_objects):
    """
    O(1) import path for GAIA asteroids using Geometry Nodes orbital animation.

    Architecture:
      - 1 mesh object  — one vertex per asteroid (initial XYZ from CSV)
      - 7 named float/int attributes per vertex — orbital elements
      - 1 GN modifier  — computes Keplerian positions from attributes + scene time,
                          instances one of 5 prototype meshes at each position

    vs. add_gaia_fast (3 objects × N): creation cost is constant regardless of N.
    vs. Follow Path constraints: GN runs as compiled C++ per frame, not N Python
    constraint evaluations.
    """
    import array as _array

    if num_objects <= 0 or not os.path.exists(csv_path):
        return

    print(f"[GAIA] Building GN animated belt ({num_objects} asteroids)...")

    # ── 1. Read CSV into flat Python lists ───────────────────────────────
    sma_l, ecc_l, inc_l, per_l, asc_l, m0_l, T_l, mi_l, pos_l = [], [], [], [], [], [], [], [], []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader):
            if idx >= num_objects:
                break
            sma_str = row.get('semi_major_axis_AU', '').strip()
            sma_au  = float(sma_str) if sma_str else float(row['distance_AU'])
            sma     = ORBIT_SCALE * sma_au
            ecc     = min(float(row.get('eccentricity',    0.0) or 0.0), 0.99)
            inc_deg = float(row.get('inclination_deg', 0.0) or 0.0)
            m0_rad  = float(row.get('mean_anomaly',    0.0) or 0.0)  # already in radians
            per_rad = float(row.get('arg_perihelion',  0.0) or 0.0)  # radians; 0 if absent (30k CSV)
            asc_rad = float(row.get('long_asc_node',   0.0) or 0.0)  # radians; 0 if absent (30k CSV)
            T_fr    = max(60.0, EARTH_YEAR_FRAMES * (sma_au ** 1.5) / 3.0)

            sma_l.append(sma)
            ecc_l.append(ecc)
            inc_l.append(math.radians(inc_deg))
            per_l.append(per_rad)
            asc_l.append(asc_rad)
            m0_l.append(m0_rad)
            T_l.append(T_fr)
            mi_l.append(idx % 5)
            pos_l.append((
                float(row['X_AU']) * ORBIT_SCALE,
                float(row['Y_AU']) * ORBIT_SCALE,
                float(row['Z_AU']) * ORBIT_SCALE,
            ))

    n = len(pos_l)
    print(f"[GAIA] Read {n} rows")

    # ── 2. Import prototypes (5 OBJ imports total, regardless of N) ───────
    prototypes = _import_asteroid_prototypes()
    if not prototypes:
        print("[GAIA] No prototypes, aborting")
        return

    # Move prototypes into a separate collection.
    # Do NOT exclude it from the view layer — GN Object Info needs depsgraph access.
    # The objects are hidden via hide_set(True)/hide_render=True in _import_asteroid_prototypes().
    proto_coll = bpy.data.collections.new("AsteroidPrototypes")
    bpy.context.scene.collection.children.link(proto_coll)
    for p in prototypes:
        for c in list(p.users_collection): c.objects.unlink(p)
        proto_coll.objects.link(p)

    # ── 3. Build point-cloud mesh (from_pydata is a single C call) ────────
    mesh = bpy.data.meshes.new("GaiaAsteroidPoints")
    mesh.from_pydata(pos_l, [], [])
    mesh.update()

    # ── 4. Write orbital attributes via foreach_set (one C call each) ─────
    def fa(name, vals):
        a = mesh.attributes.new(name, 'FLOAT', 'POINT')
        a.data.foreach_set('value', _array.array('f', vals))
    def ia(name, vals):
        a = mesh.attributes.new(name, 'INT', 'POINT')
        a.data.foreach_set('value', _array.array('i', vals))

    fa('semi_major_axis', sma_l)
    fa('eccentricity',    ecc_l)
    fa('inclination',     inc_l)
    fa('arg_periapsis',   per_l)
    fa('long_asc_node',   asc_l)
    fa('mean_anomaly',    m0_l)
    fa('period_frames',   T_l)
    ia('model_index',     mi_l)
    mesh.update()

    # ── 5. Create object ───────────────────────────────────────────────────
    belt_obj = bpy.data.objects.new("GaiaAsteroidBelt", mesh)
    gaia_coll = bpy.data.collections.new("GAIA Asteroids")
    bpy.context.scene.collection.children.link(gaia_coll)
    gaia_coll.objects.link(belt_obj)

    # ── 6. Build and attach Geometry Nodes modifier ────────────────────────
    ng = bpy.data.node_groups.new("GaiaOrbitalGN", 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT',  socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    _build_gn_orbital_tree(ng, prototypes)

    mod = belt_obj.modifiers.new("OrbitalInstancer", 'NODES')
    mod.node_group = ng

    print(f"[GAIA] Done — {n} asteroids, 1 GN object, {len(prototypes)} prototypes")
    return belt_obj


# =========================
# SOLAR SYSTEM DEFINITION
# =========================
SolarSystem = {
    "Sun": dict(
        name="Sun",
        radius=3.0,
        location=(0, 0, 0),
        tilt_deg=7.25,
        texture=os.path.join(TEX_DIR, "8k_sun.jpg"),
        color=(1, 0.9, 0.6, 1.0)
    ),
    "Mercury": dict(
        name="Mercury",

        radius=0.30,
        color=(1, 1, 1, 1),
        texture=os.path.join(TEX_DIR, "8k_mercury.jpg"),
        tilt_deg=0.03,
        flattening=0.00006,
        year_frames=max(60, int(EARTH_YEAR_FRAMES * 0.2408467 / 3)),
        day_frames=frames_for_day(1407.5),
        spin_dir=spin_dir(1407.5),

        orbit_radius= ORBIT_SCALE * 0.387,
        ecc=0.21,
        inc=7.004,
        asc=48.33,
        peri=77.45,
    ),
    "Venus": dict(
        name="Venus",
        radius=0.95,
        color=(1, 1, 1, 1),
        texture=os.path.join(TEX_DIR, "8k_venus.jpg"),
        tilt_deg=177.4,
        flattening=0.0001,
        
        year_frames=max(60, int(EARTH_YEAR_FRAMES * 0.61519726 / 3)),
        day_frames=frames_for_day(-5832.5),
        spin_dir=spin_dir(-5832.5),

        orbit_radius= ORBIT_SCALE * 0.723,
        ecc=0.007,
        inc=3.394,
        asc=76.68,
        peri=131.5637,
        
    ),
    "Earth": dict(
        name="Earth",
        radius=1.0,
        color=(1, 1, 1, 1),
        texture=os.path.join(TEX_DIR, "8k_earth_daymap.jpg"),
        tilt_deg=23.44,
        flattening=1/298.257,
        year_frames=int(EARTH_YEAR_FRAMES / 3),
        day_frames=frames_for_day(23.934),
        spin_dir=spin_dir(23.934),

        orbit_radius= ORBIT_SCALE * 1,
        ecc=0.0167,
        inc=0,
        asc=0,
        peri=102.9374,
    ),
    "Mars": dict(
        name="Mars",
        radius=0.53,
        color=(1, 1, 1, 1),
        texture=os.path.join(TEX_DIR, "8k_mars.jpg"),
        tilt_deg=25.19,
        flattening=0.00589,
        orbit_radius= ORBIT_SCALE * 1.524,
        year_frames=max(60, int(EARTH_YEAR_FRAMES * 1.8808158 / 3)),
        day_frames=frames_for_day(24.623),
        spin_dir=spin_dir(24.623),

        ecc=0.0934,
        inc=1.8497,
        asc=49.558,
        peri=336.60,
    ),
    "Jupiter": dict(
        name="Jupiter",
        radius=2.0,
        color=(1, 1, 1, 1),
        texture=os.path.join(TEX_DIR, "8k_jupiter.jpg"),
        tilt_deg=3.13,
        flattening=0.06487,
        orbit_radius= ORBIT_SCALE * 5.2027,
        year_frames=max(60, int(EARTH_YEAR_FRAMES * 11.862 / 3)),
        day_frames=frames_for_day(9.925),
        spin_dir=spin_dir(9.925),

        ecc=0.048,
        inc=1.303,
        asc=100.464,
        peri=14.331,
    ),
    "Saturn": dict(
        name="Saturn",
        radius=1.7,
        color=(1, 1, 1, 1),
        texture=os.path.join(TEX_DIR, "8k_saturn.jpg"),
        tilt_deg=26.73,
        flattening=0.09796,
        orbit_radius= ORBIT_SCALE * 9.542,
        year_frames=max(60, int(EARTH_YEAR_FRAMES * 29.457 / 3)),
        day_frames=frames_for_day(10.656),
        spin_dir=spin_dir(10.656),
        with_rings=True,
        rings_inner=2.0,
        rings_outer=3.3,

        ecc=0.055,
        inc=2.488,
        asc=113.666,
        peri=93.057,
    ),
    "Uranus": dict(
        name="Uranus",
        radius=1.4,
        color=(1, 1, 1, 1),
        texture=os.path.join(TEX_DIR, "2k_uranus.jpg"),
        tilt_deg=97.77,
        flattening=0.0229,
        orbit_radius= ORBIT_SCALE * 19.192,
        year_frames=max(60, int(EARTH_YEAR_FRAMES * 84.016846 / 3)),
        day_frames=frames_for_day(-17.24),
        spin_dir=spin_dir(-17.24),

        ecc=0.046,
        inc=0.773,
        asc=74.01,
        peri=173.01,
    ),
    "Neptune": dict(
        name="Neptune",
        radius=1.35,
        color=(1, 1, 1, 1),
        texture=os.path.join(TEX_DIR, "2k_neptune.jpg"),
        tilt_deg=28.32,
        flattening=0.0171,
        orbit_radius= ORBIT_SCALE * 30.068,
        year_frames=max(60, int(EARTH_YEAR_FRAMES * 164.8 / 3)),
        day_frames=frames_for_day(16.11),
        spin_dir=spin_dir(16.11),
        
        ecc=0.008,
        inc=1.770,
        asc=131.78,
        peri=48.12,
    )
}


# =========================
# CREATE PLANETS & OBJECTS
# =========================
bundles = {}

for name, obj in SolarSystem.items():
    if name == "Sun":
        add_sun(obj)
    else:
        print(f"add obj: {name}")
        bundles[name] = add_planet(obj)

# =========================
# GAIA ASTEROID BELT (geometry nodes)
# =========================
if NUM_GAIA_OBJECTS > 0 and os.path.exists(GAIA_CSV):
    add_gaia_geometry_nodes_animated(GAIA_CSV, NUM_GAIA_OBJECTS)
elif NUM_GAIA_OBJECTS > 0:
    print(f"[GAIA] Skipping: CSV not found at {GAIA_CSV}")


        
    
 

bpy.context.scene.frame_set(1)

bpy.context.scene.render.fps = 60

bpy.context.view_layer.update()

