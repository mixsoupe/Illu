# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import bpy
import bgl
import gpu
import time

from . utils import *
from . shaders import *
from . geometry import *

def render(all = False, node = None):
    T = time.time()
    rendered = []
    failed = []

    #Get 2d_shade nodes
    if node:
        nodes = [node,]
    else :
        nodes = []
        scene_materials = []     
        if all:
            objs = bpy.context.scene.objects
        else:        
            objs = bpy.context.selected_objects
        
        for obj in objs:        
            for slot in obj.material_slots:
                material = slot.material
                if material:
                    scene_materials.append(material)

        for material in bpy.data.materials:
            if material in scene_materials:
                if material.node_tree is not None:
                    for node_tree in traverse_node_tree(material.node_tree):
                        for node in node_tree.nodes:
                            if node.bl_idname == 'ILLU_2DShade':
                                if node.objects is not None:
                                    nodes.append (node)

    #Build scene geometry
    geo_objects = []
    already_done = {}
    shadow_objects = []

    #Geo
    for node in nodes:        
        geometry = Geometry(node.objects, node)
        geo_objects.append(geometry)
        already_done[node.objects] = geometry

    
    #Shadow    
    for obj in bpy.context.scene.objects:
        if obj.illu.cast_shadow and obj.type == 'MESH' and obj.hide_render is False:  
            if obj in already_done.keys():                
                geometry = already_done[obj]
            else :            
                geometry = Geometry(obj)
            
            shadow_objects.append(geometry)
    
    #Render nodes                    
    for geo_object in geo_objects:
        result = render_node(geo_object, shadow_objects)
        if result:
            rendered.append(geo_object.object.name)
        else:
            failed.append(geo_object.object.name)
    
    #print ((time.time()- T)*1000)
   
    return rendered, failed


def render_node(geo, shadow_objects):
    
    dim_x, dim_y =  get_resolution()
    ratio = dim_x / dim_y
    
    if ratio > 1:        
        dim_x = geo.texture_size
        dim_y = int(dim_x / ratio)
    else:
        dim_y = geo.texture_size
        dim_x = int(dim_y * ratio)

    #Create buffers    
    base_buffer = gpu.types.GPUOffScreen(dim_x, dim_y)
    depth_buffer = gpu.types.GPUOffScreen(dim_x, dim_y)
    sdf_buffer = gpu.types.GPUOffScreen(dim_x, dim_y)
    erosion_buffer = gpu.types.GPUOffScreen(dim_x, dim_y)
    shadow_buffer = gpu.types.GPUOffScreen(dim_x, dim_y)
    line_buffer = gpu.types.GPUOffScreen(dim_x, dim_y)
    noise_buffer = gpu.types.GPUOffScreen(dim_x, dim_y)
    
    #Creation du modele     
    depth_precision = geo.distance * geo.smoothness /10
    
    #Shadow Buffer
    if shadow_objects:        
        vertices_shadow, indices_shadow = build_shadow(shadow_objects, geo)
        bgl_shadow(shadow_buffer, dim_x, dim_y, geo.vertices, geo.indices, geo.colors, vertices_shadow, indices_shadow, geo.light, geo.shadow_size, geo.soft_shadow)         


    #Base render
    bgl_base_render(base_buffer, dim_x, dim_y, geo.vertices, geo.indices, geo.colors)
    
    bgl_base_noise(noise_buffer, dim_x, dim_y, geo.vertices, geo.indices, geo.colors, geo.orco, geo.noise_scale/8)
    bgl_filter_sss(noise_buffer, depth_buffer, dim_x, dim_y, samples = 20, radius = 3)
    bgl_depth_render(depth_buffer, dim_x, dim_y, geo.vertices, geo.indices, geo.colors)    

    if geo.self_shading:
        bgl_filter_expand(base_buffer, dim_x, dim_y, 3, channel = (1,1,1))    
    #bgl_filter_sss(base_buffer, depth_buffer, dim_x, dim_y, samples = 20, radius = 10, channel = (1,0,0,0))    
    
    #Distance field buffer (transparence)    
    copy_buffer(base_buffer, sdf_buffer, dim_x, dim_y)        
    bgl_filter_distance_field(sdf_buffer, dim_x, dim_y, geo.scale)    
    bgl_filter_sss(sdf_buffer, depth_buffer, dim_x, dim_y, samples = 20, radius = 20, depth_precision = depth_precision)
    merge_buffers(base_buffer, sdf_buffer, "merge_SDF_post", dim_x, dim_y)  
    
    #Decal (shading)
    if geo.self_shading:   
        bgl_filter_decal(base_buffer, depth_buffer, dim_x, dim_y, geo.light, geo.scale, depth_precision, geo.angle)
        bgl_filter_sss(base_buffer, depth_buffer, dim_x, dim_y, samples = int(60*geo.scale), radius = 20*geo.scale, depth_precision = depth_precision, channel = (1,0,0,0))
    
    #Ajouter le trait
    bgl_filter_line(base_buffer, depth_buffer, dim_x, dim_y, geo.line_detection, False, depth_precision)
    bgl_filter_sss(base_buffer, depth_buffer, dim_x, dim_y, samples = 10, radius = geo.line_scale, depth_precision = depth_precision, channel = (0,0,1,0))
    bgl_filter_custom(base_buffer, dim_x, dim_y, "line_filter", geo.line_scale)
    
    #Merge Shadow
          
    if shadow_objects:
        if geo.self_shading:
            merge_buffers(base_buffer, shadow_buffer, "merge_shadow", dim_x, dim_y)
        else:
            merge_buffers(base_buffer, shadow_buffer, "merge_shadow_simple", dim_x, dim_y)
      
    #Noise    
    border= geo.noise_diffusion*20    
    copy_buffer(base_buffer, erosion_buffer, dim_x, dim_y)
    bgl_filter_noise(erosion_buffer, noise_buffer, dim_x, dim_y, geo.noise_diffusion/30)
    bgl_filter_expand(erosion_buffer, dim_x, dim_y, -border)  
    bgl_filter_sss(erosion_buffer, depth_buffer, dim_x, dim_y, samples = 30, radius = max(geo.noise_diffusion*100, 7), channel = (0,0,0,1))
    
    if geo.self_shading:   
        merge_buffers(base_buffer, erosion_buffer, "merge_noise", dim_x, dim_y)
    else:
        merge_buffers(base_buffer, erosion_buffer, "merge_noise_simple", dim_x, dim_y)
    
    #Bake    
    if geo.bake_to_uvs:
        bake_buffer = gpu.types.GPUOffScreen(geo.texture_size, geo.texture_size)
        #bgl_filter_expand(base_buffer, dim_x, dim_y, 3, channel = (1,0,0))             
        bake_to_texture(base_buffer, bake_buffer, dim_x, dim_y, geo.vertices, geo.uvs, geo.uv_indices, geo.loop_indices)
        bgl_filter_expand(bake_buffer, geo.texture_size, geo.texture_size, 3)            
        #Lecture du buffer 
        with bake_buffer.bind():        
            buffer = bgl.Buffer(bgl.GL_FLOAT, geo.texture_size * geo.texture_size * 4)        
            bgl.glReadBuffer(bgl.GL_BACK)        
            bgl.glReadPixels(0, 0, geo.texture_size, geo.texture_size, bgl.GL_RGBA, bgl.GL_FLOAT, buffer)
        bake_buffer.free()
        dim_x = geo.texture_size
        dim_y = geo.texture_size
        
    else:
        bgl_filter_scale(base_buffer, dim_x, dim_y, upscale_factor())
        with base_buffer.bind():        
            buffer = bgl.Buffer(bgl.GL_FLOAT, dim_x * dim_y * 4)        
            bgl.glReadBuffer(bgl.GL_BACK)        
            bgl.glReadPixels(0, 0, dim_x, dim_y, bgl.GL_RGBA, bgl.GL_FLOAT, buffer)  
    
    #Suppression des buffers
    shadow_buffer.free()               
    sdf_buffer.free()
    erosion_buffer.free()
    base_buffer.free()
    depth_buffer.free()
    line_buffer.free()
    noise_buffer.free()

    #Enregistrement des images
    buffer_to_image( geo.image_name, buffer, dim_x, dim_y)
    
    return True