import bpy
import os
import bmesh
import math



def add_uv_sphere(name, 
                location, 
                radius, 
                u_segments=64, 
                v_segments=32):
                    
    mesh = bpy.data.meshes.new(name + "_Mesh")
    obj = bpy.data.objects.new(name, mesh);
    bpy.context.collection.objects.link(obj)
    obj.location = location
    
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=u_segments, v_segments=v_segments, radius=radius)
    
    uv_layer = bm.loops.layers.uv.new("UVMap")
    
    for face in bm.faces:
        for loop in face.loops:
            
            co = loop.vert.co
            mag = co.length
            
            if mag > 0:
                x, y, z = co / mag
                u = 0.5 + (math.atan2(y, x) / (2 * math.pi))
                v = 0.5 + (math.asin(z) / math.pi)
                loop[uv_layer].uv = (u, v)
            
            
    bm.to_mesh(mesh)
    bm.free()
    
    mesh.update()
    

    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    

    bpy.ops.mesh.select_all(action='SELECT')
    
    
    bpy.ops.uv.sphere_project(
        direction='ALIGN_TO_OBJECT', 
        align='POLAR_ZX', 
        correct_aspect=True, 
        clip_to_bounds=True, 
        scale_to_bounds=True
    )

    bpy.ops.object.mode_set(mode='OBJECT')
    
    for poly in mesh.polygons:
        poly.use_smooth = True
        
    if not mesh.uv_layers:
        print(f"FAILED to create UV layers for {name}")
    else:
        mesh.uv_layers.active = mesh.uv_layers["UVMap"]
        mesh.uv_layers["UVMap"].active_render = True

    return obj
    

