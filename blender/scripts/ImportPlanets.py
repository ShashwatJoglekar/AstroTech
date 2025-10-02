import bpy
import sys
import os
import importlib

# Code to be able to import other scripts
blend_dir = os.path.dirname(bpy.data.filepath)
scripts_dir = os.path.join(blend_dir, "scripts")
if scripts_dir not in sys.path:
    sys.path.append(scripts_dir)

import AddObjectScript
importlib.reload(AddObjectScript)
from AddObjectScript import create_uv_sphere, clear_scene

clear_scene()

class AstroObject:
    def __init__(self, name, location, radius, rotating_velocity, orbit_radius, orbit_velocity, mass, texture=None):
        self.name = name
        self.location = location
        self.radius = radius
        self.rotating_velocity = rotating_velocity
        self.orbit_radius = orbit_radius
        self.orbit_velocity = orbit_velocity
        self.mass = mass
        self.texture = texture

# Hard coded for now
SolarSystem = {
    "Earth": AstroObject(
        name="Earth",
        location=(0,0,0), # TODO: update with true value
        radius=6.371e6,                  # meters
        rotating_velocity=444.444,       # m/s
        orbit_radius=149.6e9,            # meters
        orbit_velocity=29.8e3,           # m/s
        mass=5.972e24,                   # kg
        texture="//assets/textures/8k_earth_daymap.jpg"
    ),
    "Mars": AstroObject(
        name="Mars",
        radius=3.389e6,
        location=(10,0,0),
        rotating_velocity=241.17,
        orbit_radius=227.9e9,
        orbit_velocity=24.1e3,
        mass=6.39e23,
        texture="//assets/textures/8k_mars.jpg"
    )
}


# Create UV spheres for each object
for obj, info in SolarSystem.items():
    create_uv_sphere(
        location=info.location,
        radius=info.radius / 1e6,
        name=info.name,
        texture_path=bpy.path.abspath(info.texture)
    )