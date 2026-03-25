import bpy
import sys
import os
import importlib
import math
import csv
import random

# Import other scripts
blend_dir = os.path.dirname(bpy.data.filepath)
scripts_dir = os.path.join(blend_dir, "scripts")
if scripts_dir not in sys.path:
    sys.path.append(scripts_dir)

import SolarSystemOrbits
importlib.reload(SolarSystemOrbits)
from SolarSystemOrbits import add_planet, add_sun, add_moon, frames_for_day, spin_dir


# =========================
# HELPER FUNCTIONS
# =========================
def clear_scene():
    """
    Deletes all objects from the current Blender scene.
    """
    bpy.ops.object.select_all(action='SELECT') # select all objects
    bpy.ops.object.delete(use_global=False) # delete selected objects

    # clear unused data blocks (meshes, materials)
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)


# =========================
# GLOBAL SETTINGS
# =========================
FPS = 60
# EARTH_DAY_FRAMES  = 180 # 1 Earth day = 120 frames (3s @ 60fps)
# EARTH_YEAR_FRAMES = 1800 # 1 Earth year = 1200 frames (30s @ 60fps)
SYSTEM_SCALE = 1
RING_ALPHA   = 0.55

# Control how many Gaia objects to load (set to 0 to skip, or up to 30000)
NUM_GAIA_OBJECTS = 2500  # Change this value to load more/fewer objects

BASE_DIR = bpy.path.abspath("//")
TEX_DIR = os.path.join(BASE_DIR, "assets", "textures")

# Try multiple locations for the CSV file
# fix
csv_locations = [
    os.path.join(scripts_dir, "gaia_stars_10k.csv"),  # scripts directory
    os.path.join(BASE_DIR, "gaia_stars_10k.csv"),     # blender directory  
    os.path.join(os.path.dirname(BASE_DIR), "gaia_stars_10k.csv"),  # project root
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
ORBIT_SCALE  = 100

def get_star_color(bp_rp_str):
    """
    Interpolates between high-detail anchor points to provide a 
    unique, varied tint for any BP-RP value.
    """
    try:
        val = float(bp_rp_str)
    except (ValueError, TypeError):
        return (1.0, 1.0, 1.0, 1.0)

    # Anchor points: (BP-RP Value, (R, G, B, A))
    # These are calibrated to be "Blender-safe" (Saturated enough to survive Emission)
    anchors = [
        (-0.5, (0.5, 0.7, 1.0, 1.0)),  # Class O: Deep Blue
        (0.0,  (0.7, 0.85, 1.0, 1.0)), # Class B: Light Blue
        (0.3,  (0.9, 0.95, 1.0, 1.0)), # Class A: Blue-White
        (0.6,  (1.0, 1.0, 0.9, 1.0)),  # Class F: Pure White
        (0.9,  (1.0, 0.9, 0.5, 1.0)),  # Class G: Sun-like Yellow
        (1.5,  (1.0, 0.5, 0.1, 1.0)),  # Class K: Deep Orange
        (2.5,  (1.0, 0.2, 0.05, 1.0)), # Class M: Deep Red
        (4.0,  (0.8, 0.1, 0.0, 1.0))   # Class M (Late): Dark Blood Red
    ]

    # Handle values outside our anchor range
    if val <= anchors[0][0]: return anchors[0][1]
    if val >= anchors[-1][0]: return anchors[-1][1]

    # Find the two anchors to interpolate between
    for i in range(len(anchors) - 1):
        v1, c1 = anchors[i]
        v2, c2 = anchors[i+1]
        
        if v1 <= val <= v2:
            # Calculate the interpolation factor (0.0 to 1.0)
            fac = (val - v1) / (v2 - v1)
            
            # Linearly interpolate each channel (R, G, B)
            return (
                c1[0] + (c2[0] - c1[0]) * fac,
                c1[1] + (c2[1] - c1[1]) * fac,
                c1[2] + (c2[2] - c1[2]) * fac,
                1.0
            )

    return (1.0, 1.0, 1.0, 1.0)

# =========================
# GAIA DATA LOADER
# =========================
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

    try:
        total_rows_estimate = 100000 
        step = max(1, total_rows_estimate // num_objects)

        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            for idx, row in enumerate(reader):
                # ONLY process every 'step' rows
                if idx % step != 0:
                    continue
                    
                if len(gaia_objects) >= num_objects:
                    break
                
                name = row['source_id']  

                dist = 0.0
                if row.get('distance_pc'):
                    dist = float(row['distance_pc'])
                elif row.get('parallax') and float(row['parallax']) > 0:
                    dist = 1000.0 / float(row['parallax'])              
                
                if dist <= 0:
                    continue

                ra_rad = math.radians(float(row['ra']))
                dec_rad = math.radians(float(row['dec']))
                
                x = dist * math.cos(dec_rad) * math.cos(ra_rad)
                y = dist * math.cos(dec_rad) * math.sin(ra_rad)
                z = dist * math.sin(dec_rad)
                
                location = (round(x, 4), round(y, 4), round(z, 4))

                # This now uses your detailed interpolation tint function
                color = get_star_color(row.get('bp_rp'))

                gaia_objects[name] = dict(
                    name=name,
                    radius=1.0,
                    location=location,
                    tilt_deg=0.0,
                    texture=os.path.join(TEX_DIR, "8k_sun.jpg"),
                    color=color
                )

        print(f"Successfully loaded {len(gaia_objects)} Gaia objects")
        
    except Exception as e:
        print(f"Error loading Gaia objects: {e}")
        return {}
    
    return gaia_objects


# =========================
# SOLAR SYSTEM DEFINITION
# =========================
SolarSystem = {}


# =========================
# LOAD GAIA OBJECTS INTO SOLAR SYSTEM
# =========================
# Load Gaia objects and append them to SolarSystem dictionary
if NUM_GAIA_OBJECTS > 0:
    gaia_objects = load_gaia_objects(GAIA_CSV, NUM_GAIA_OBJECTS)
    SolarSystem.update(gaia_objects)
    print(f"Total objects in SolarSystem: {len(SolarSystem)}")
else:
    print("Gaia objects loading skipped")


# =========================
# CREATE PLANETS & OBJECTS
# =========================
bundles = {}

for name, obj in SolarSystem.items():
    add_sun(obj)


bpy.context.scene.frame_set(1)

bpy.context.scene.render.fps = 60

bpy.context.view_layer.update()

