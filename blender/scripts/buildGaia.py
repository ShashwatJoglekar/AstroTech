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
SYSTEM_SCALE = 1.0
RING_ALPHA   = 0.55

# Control how many Gaia objects to load (set to 0 to skip, or up to 30000)
NUM_GAIA_OBJECTS = 100  # Change this value to load more/fewer objects

BASE_DIR = bpy.path.abspath("//")
TEX_DIR = os.path.join(BASE_DIR, "assets", "textures")
MODELS_DIR = os.path.join(BASE_DIR, "assets", "models")

# Try multiple locations for the CSV file
# fix
csv_locations = [
    os.path.join(scripts_dir, "gaia_solar_system_xyz_30kobjects.csv"),  # scripts directory
    os.path.join(BASE_DIR, "gaia_solar_system_xyz_30kobjects.csv"),     # blender directory  
    os.path.join(os.path.dirname(BASE_DIR), "gaia_solar_system_xyz_30kobjects.csv"),  # project root
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

