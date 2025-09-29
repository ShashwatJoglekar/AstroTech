import bpy
import sys
import os
from AddObjectScript import create_uv_sphere, clear_scene

clear_scene()
create_uv_sphere((0, 0, 0), 1.0, name="Earth", color=(0, 0, 1, 1))
create_uv_sphere((3, 0, 0), 0.5, name="Mars", color=(1, 0.3, 0, 1))
create_uv_sphere((6, 0, 0), 1.2, name="Jupiter", color=(0.8, 0.6, 0.4, 1))