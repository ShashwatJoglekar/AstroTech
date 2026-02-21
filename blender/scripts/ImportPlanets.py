import bpy
import sys
import os
import importlib
import math

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
EARTH_DAY_FRAMES  = 180 # 1 Earth day = 120 frames (3s @ 60fps)
EARTH_YEAR_FRAMES = 1800 # 1 Earth year = 1200 frames (30s @ 60fps)
SYSTEM_SCALE = 1.0
RING_ALPHA   = 0.55

BASE_DIR = bpy.path.abspath("//")
TEX_DIR = os.path.join(BASE_DIR, "assets", "textures")

TEX_DIR = os.path.normpath(TEX_DIR)
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
# CREATE PLANETS
# =========================


bundles = {}

for name, obj in SolarSystem.items():
    if name == "Sun":
        add_sun(obj)
    else:
        print(f"add obj: {name}")
        bundles[name] = add_planet(obj)
        
    
 

bpy.context.scene.frame_set(1)

bpy.context.scene.render.fps = 60

bpy.context.view_layer.update()

