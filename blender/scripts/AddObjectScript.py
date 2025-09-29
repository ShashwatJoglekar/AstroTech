import bpy

def create_uv_sphere(location, radius, segments=32, rings=16, name="MySphere", color=(1, 1, 1, 1)):
    """
    Creates a UV sphere in Blender.

    Args:
        location (tuple): The (x, y, z) coordinates for the sphere's center.
        radius (float): The radius of the sphere.
        segments (int): The number of segments (vertical divisions) of the sphere.
        rings (int): The number of rings (horizontal divisions) of the sphere.
        name (str): The name to assign to the new sphere object and its mesh.
    """
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments,
        ring_count=rings,
        radius=radius,
        location=location
    )
    
    # rename the new sphere and its mesh
    new_sphere = bpy.context.selected_objects[0]
    new_sphere.name = name
    new_sphere.data.name = name + "_Mesh"
    
    # add material
    mat = bpy.data.materials.new(name + "_Material")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs[0].default_value = color

    new_sphere.data.materials.clear()
    new_sphere.data.materials.append(mat)


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
