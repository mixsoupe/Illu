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
import math
import random
import mathutils
import bgl
import gpu
import time
import bpy_extras
from mathutils import Matrix, Vector, Euler

from . shader_utils import *

def generate_images(obj, image_name, light, scale, smoothness, angle, texture_size, shadow_size, soft_shadow, self_shading, bake_to_uvs, line_scale, line_detection, noise_scale, noise_diffusion):
    T = time.time()
    global dim_x
    global dim_y
    dim_x, dim_y =  get_resolution()
    ratio = dim_x / dim_y
    obj = [obj,]
    
    if ratio > 1:        
        dim_x = texture_size
        dim_y = int(dim_x / ratio)
    else:
        dim_y = texture_size
        dim_x = int(dim_y * ratio)
    
    base_buffer = gpu.types.GPUOffScreen(dim_x, dim_y)
    depth_buffer = gpu.types.GPUOffScreen(dim_x, dim_y)
    sdf_buffer = gpu.types.GPUOffScreen(dim_x, dim_y)
    erosion_buffer = gpu.types.GPUOffScreen(dim_x, dim_y)
    shadow_buffer = gpu.types.GPUOffScreen(dim_x, dim_y)
    line_buffer = gpu.types.GPUOffScreen(dim_x, dim_y)
    noise_buffer = gpu.types.GPUOffScreen(dim_x, dim_y)
    
    #Creation du modele        
    vertices, indices, colors, uvs, uv_indices, loop_indices, orco = build_model(obj, get_uv = True)

    #Shadow Buffer
    shadow_objs = get_shadow_objects(exclude = obj)
    if len(shadow_objs) > 0:
        vertices_shadow, indices_shadow, shadow_colors = build_model(shadow_objs) 
        bgl_shadow(shadow_buffer, vertices, indices, colors, vertices_shadow, indices_shadow, light, shadow_size, soft_shadow)         
    
    #Base render
    bgl_base_render(base_buffer, vertices, indices, colors, orco)
    copy_buffer(base_buffer, noise_buffer, dim_x, dim_y)
    bgl_filter_custom(base_buffer, "white", 1)
    bgl_depth_render(depth_buffer, vertices, indices, colors)
    

    if self_shading:
        bgl_filter_expand(base_buffer, dim_x, dim_y, 3)    
    bgl_filter_sss(base_buffer, depth_buffer, samples = 20, radius = 10, depth_precision = 1, channel = (1,0,0,0))
    
    #Distance field buffer (transparence)
    
    copy_buffer(base_buffer, sdf_buffer, dim_x, dim_y)
        
    bgl_filter_distance_field(sdf_buffer, depth_buffer, scale)
    
    bgl_filter_sss(sdf_buffer, depth_buffer, samples = 20, radius = 20)
    #bgl_filter_expand(sdf_buffer, dim_x, dim_y, int(-4*scale))        
    #bgl_filter_sss(sdf_buffer, depth_buffer, samples = 20, radius = 1, depth_precision = 1) 
    
    merge_buffers(base_buffer, sdf_buffer, "merge_SDF_post", dim_x, dim_y)  
    
    #Decal (shading)
    if self_shading:   
        bgl_filter_decal(base_buffer, depth_buffer, light, scale, smoothness/5, angle)
        bgl_filter_sss(base_buffer, depth_buffer, samples = int(60*scale), radius = 20*scale, channel = (1,0,0,0))
    
    #Ajouter le trait
    bgl_filter_line(base_buffer, depth_buffer, line_detection, False)
    bgl_filter_sss(base_buffer, depth_buffer, samples = 10, radius = line_scale, channel = (0,0,1,0))
    bgl_filter_custom(base_buffer, "line_filter", line_scale)
    
    #Merge Shadow             
    if len(shadow_objs) > 0:
        if self_shading:
            merge_buffers(base_buffer, shadow_buffer, "merge_shadow", dim_x, dim_y)
        else:
            merge_buffers(base_buffer, shadow_buffer, "merge_shadow_simple", dim_x, dim_y)
    
    #Noise            
    copy_buffer(base_buffer, erosion_buffer, dim_x, dim_y)
    bgl_filter_noise(erosion_buffer, noise_scale, noise_diffusion/200)
    
    if self_shading:   
        merge_buffers(base_buffer, erosion_buffer, "merge_noise", dim_x, dim_y)
    else:
        merge_buffers(base_buffer, erosion_buffer, "merge_noise_simple", dim_x, dim_y)
    
    #Noise2
    #bgl_filter_noise2(base_buffer)
    #bgl_filter_sss(base_buffer, depth_buffer, samples = 20, radius = 3, depth_precision = 1, channel = (1,0,0,0))

    #Bake    
    if bake_to_uvs:
        bake_buffer = gpu.types.GPUOffScreen(texture_size, texture_size)           
        bake_to_texture(base_buffer, bake_buffer, vertices, uvs, uv_indices, loop_indices)
        bgl_filter_expand(bake_buffer, texture_size, texture_size, 3)            
        #Lecture du buffer 
        with bake_buffer.bind():        
            buffer = bgl.Buffer(bgl.GL_FLOAT, texture_size * texture_size * 4)        
            bgl.glReadBuffer(bgl.GL_BACK)        
            bgl.glReadPixels(0, 0, texture_size, texture_size, bgl.GL_RGBA, bgl.GL_FLOAT, buffer)
        bake_buffer.free()
        dim_x = texture_size
        dim_y = texture_size
        
    else:
        bgl_filter_scale(base_buffer, upscale_factor())
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
    buffer_to_image( image_name, buffer, dim_x, dim_y)

    #print ((time.time()-T)*1000)
    

def bgl_shadow(shadow_buffer, vertices, indices, colors,
    vertices_shadow, indices_shadow, light, shadow_size, soft_shadow):

    #CSM 
    """CREER 3 buffers"""
    depth_buffer = gpu.types.GPUOffScreen(shadow_size, shadow_size)
    shadowmap_buffer = gpu.types.GPUOffScreen(dim_x, dim_y)

    #Camera matrix
    camera = bpy.context.scene.camera 
    view_matrix = camera.matrix_world.inverted()
    projection_matrix = change_camera_matrix(camera, dim_x, dim_y)
    
    MVP = projection_matrix @ view_matrix

    #CSM
    """AJUSTER LE CLIPPING PLANE SUR L'OBJET PUIS DECOUPER LE FRUSTRUM
    EVITER LES CSMs POUR LES PETITS OBJETS ?"""
    test = Vector((1, 1, 1))
    new = MVP.inverted() @ test

    #Shaders creation
    shader_depth =  compile_shader("shadow_depth.vert", "shadow_depth.frag")
    batch_depth = batch_for_shader(shader_depth, 'TRIS', {"pos": vertices_shadow,}, indices=indices_shadow)

    shader =  compile_shader("shadow.vert", "shadow.frag")
    batch = batch_for_shader(shader, 'TRIS', {"pos": vertices, "color": colors}, indices=indices)
    
    shader_post = compile_shader("image2d.vert", "shadow_post.frag")                        
    batch_post = batch2d(shader_post,dim_x, dim_y)

    #Soft shadow samples
    rotation_matrices = soft_shadow_pattern(soft_shadow)
    for i, mat in enumerate(rotation_matrices):
        #Light matrix
        if light:
            light_matrix = light.matrix_world.inverted()
        else:
            light_matrix = Matrix.Identity(4)

        #Light jittering matrix
        light_jitter_matrix = mat @ light_matrix

        #CSM 
        """FOR LOOP"""
        #Center light to object
        #CSM 
        """REMPLACER LES VERTICES PAR LES COORDONNEES DES FRUSTRUMS"""
        object_frustrum = calc_frustrum(light_jitter_matrix, vertices) 
        all_vertices = np.concatenate((vertices, vertices_shadow), axis=0)
        shadow_frustrum = calc_frustrum(light_jitter_matrix, all_vertices)

        offset = Matrix((
            (1.0, 0.0, 0.0, object_frustrum[5]), 
            (0.0, 1.0, 0.0, object_frustrum[6]), 
            (0.0, 0.0, 1.0, shadow_frustrum[7]), 
            (0.0, 0.0, 0.0, 1.0)
            ))  

        light_view_matrix = offset @ light_jitter_matrix
        
        #Create projection matrix
        final_frustrum = calc_frustrum(light_view_matrix, vertices)
        
        size_x = final_frustrum[0]
        size_y = final_frustrum[1]
        size_z = shadow_frustrum[2]
        light_clip_end = final_frustrum[4]

        light_proj_matrix = calc_proj_matrix(ortho = max(size_x, size_y), clip_start = 0.001, 
            clip_end = light_clip_end, dim_x = shadow_size, dim_y = shadow_size)

        #Matrix for depth map pass
        depthMVP = light_proj_matrix @ light_view_matrix

        #Matrix for final pass
        biasMatrix = Matrix((
            (0.5, 0.0, 0.0, 0.5), 
            (0.0, 0.5, 0.0, 0.5), 
            (0.0, 0.0, 0.5, 0.5), 
            (0.0, 0.0, 0.0, 1.0)
            ))    
        depthBiasMVP = biasMatrix @ depthMVP
        
        #Shadowmap pass (from light POV)
        with depth_buffer.bind():
            
            bgl.glClear(bgl.GL_COLOR_BUFFER_BIT)
            
            with gpu.matrix.push_pop():
                            
                shader_depth.bind()
                shader_depth.uniform_float("depthMVP", depthMVP)
                
                bgl.glDepthMask(bgl.GL_TRUE)
                bgl.glClearDepth(1000000);
                bgl.glClearColor(0.0, 0.0, 0.0, 0.0);
                bgl.glClear(bgl.GL_COLOR_BUFFER_BIT | bgl.GL_DEPTH_BUFFER_BIT)
                        
                bgl.glEnable(bgl.GL_DEPTH_TEST)
                
                batch_depth.draw(shader_depth)
                                
                bgl.glDisable(bgl.GL_DEPTH_TEST)
        #CSM 
        """END LOOP"""

        #Render pass (from camera POV)  
        with shadowmap_buffer.bind():

            bgl.glClear(bgl.GL_COLOR_BUFFER_BIT)
            
            with gpu.matrix.push_pop():                           
                #CSM 
                """CHARGER 3 BUFFERS"""
                bgl.glActiveTexture(bgl.GL_TEXTURE0)            
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, depth_buffer.color_texture)              
                shader.bind()
                shader.uniform_int("Sampler", 0)
                shader.uniform_float("MVP", MVP)
                shader.uniform_float("Scale", light_clip_end)
                shader.uniform_float("depthBiasMVP", depthBiasMVP)
                
                bgl.glClearDepth(1000000);
                bgl.glClearColor(0.0, 0.0, 0.0, 0.0);
                bgl.glClear(bgl.GL_COLOR_BUFFER_BIT | bgl.GL_DEPTH_BUFFER_BIT)
                        
                bgl.glEnable(bgl.GL_DEPTH_TEST)
                
                batch.draw(shader)
                                
                bgl.glDisable(bgl.GL_DEPTH_TEST)

        with shadow_buffer.bind():
            with gpu.matrix.push_pop():
                gpu.matrix.load_projection_matrix(projection_matrix_2d(dim_x, dim_y))                  
                bgl.glActiveTexture(bgl.GL_TEXTURE0)            
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, shadow_buffer.color_texture)
                bgl.glActiveTexture(bgl.GL_TEXTURE1)            
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, shadowmap_buffer.color_texture)              
                shader_post.bind()
                shader_post.uniform_int("Sampler0", 0)
                shader_post.uniform_int("Sampler1", 1)
                shader_post.uniform_int("Iteration", len(rotation_matrices))
                batch_post.draw(shader_post)
             
    depth_buffer.free()
    shadowmap_buffer.free()

    
def bgl_base_render(offscreen, vertices, indices, colors, orco):

    camera = bpy.context.scene.camera
    depsgraph = bpy.context.evaluated_depsgraph_get()
    
    view_matrix = camera.matrix_world.inverted()
    projection_matrix = change_camera_matrix(camera, dim_x, dim_y)

    shader =  compile_shader("base.vert", "base.frag")
    batch = batch_for_shader(shader, 'TRIS', {"pos": vertices, "color": colors, "orco": orco}, indices=indices)  

    with offscreen.bind():
        
        bgl.glClear(bgl.GL_COLOR_BUFFER_BIT)
        
        with gpu.matrix.push_pop():
                           
            shader.bind()
            shader.uniform_float("modelMatrix", view_matrix)
            shader.uniform_float("viewProjectionMatrix", projection_matrix)
            
            bgl.glDepthMask(bgl.GL_TRUE)
            bgl.glClearDepth(1000000);
            bgl.glClearColor(0.0, 0.0, 0.0, 0.0);
            bgl.glClear(bgl.GL_COLOR_BUFFER_BIT | bgl.GL_DEPTH_BUFFER_BIT)
                      
            bgl.glEnable(bgl.GL_DEPTH_TEST)
            
            batch.draw(shader)
                            
            bgl.glDisable(bgl.GL_DEPTH_TEST)


def bgl_depth_render(offscreen, vertices, indices, colors):

    camera = bpy.context.scene.camera
    depsgraph = bpy.context.evaluated_depsgraph_get()
    
    view_matrix = camera.matrix_world.inverted()
    projection_matrix = change_camera_matrix(camera, dim_x, dim_y)

    shader =  compile_shader("depth.vert", "depth.frag")
    batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)   

    with offscreen.bind():
        
        bgl.glClear(bgl.GL_COLOR_BUFFER_BIT)
        
        with gpu.matrix.push_pop():
                           
            shader.bind()
            shader.uniform_float("modelMatrix", view_matrix)
            shader.uniform_float("viewProjectionMatrix", projection_matrix)
            
            bgl.glDepthMask(bgl.GL_TRUE)
            bgl.glClearDepth(1000000);
            bgl.glClearColor(0.0, 0.0, 0.0, 0.0);
            bgl.glClear(bgl.GL_COLOR_BUFFER_BIT | bgl.GL_DEPTH_BUFFER_BIT)
                      
            bgl.glEnable(bgl.GL_DEPTH_TEST)
            
            batch.draw(shader)
                            
            bgl.glDisable(bgl.GL_DEPTH_TEST)

            
def bgl_filter_decal(offscreen_A, depth_buffer, light, scale, smoothness, angle):
    camera = bpy.context.scene.camera
    if light is not None:
        light_angle = get_light_angle(light, camera) - angle
    else:
        light_angle = 90 - angle

    offscreen_B = gpu.types.GPUOffScreen(dim_x, dim_y)
            
    shader = compile_shader("image2d.vert", "decal.frag")                        
    batch = batch2d(shader, dim_x, dim_y)

    with gpu.matrix.push_pop():
        gpu.matrix.load_projection_matrix(projection_matrix_2d(dim_x, dim_y))
    
    rad = math.radians(light_angle)
    with offscreen_B.bind():                   
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_A.color_texture)
            bgl.glActiveTexture(bgl.GL_TEXTURE1)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, depth_buffer.color_texture)          
            shader.bind()
            shader.uniform_int("Sampler", 0)
            shader.uniform_int("Depth", 1)
            shader.uniform_float("scale", scale)
            shader.uniform_float("smoothness", smoothness)
            shader.uniform_float("angle", rad)
            shader.uniform_float("dim_x", dim_x)
            shader.uniform_float("dim_y", dim_y)
            shader.uniform_int("inverse", 1) 
            batch.draw(shader)

    rad = math.radians(light_angle + 180)
    with offscreen_A.bind():                   
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_B.color_texture)
            bgl.glActiveTexture(bgl.GL_TEXTURE1)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, depth_buffer.color_texture)              
            shader.bind()
            shader.uniform_int("Sampler", 0)
            shader.uniform_int("Depth", 1)
            shader.uniform_float("scale", scale)
            shader.uniform_float("smoothness", smoothness)
            shader.uniform_float("angle", rad)
            shader.uniform_float("dim_x", dim_x)
            shader.uniform_float("dim_y", dim_y)
            shader.uniform_int("inverse", 0) 
            batch.draw(shader)

    offscreen_B.free()
            

def bgl_filter_distance_field(offscreen_A, depth_buffer, scale,  factor = True):    

    offscreen_B = gpu.types.GPUOffScreen(dim_x, dim_y)
    
    shader = compile_shader("image2d.vert", "distance_field.frag")                    
    batch = batch2d(shader, dim_x, dim_y)
       
    step = 1
    div = 80 * scale
    iteration = int(div/2) 
    beta = 1 / div
    offset = (step / dim_x, 0)

    with gpu.matrix.push_pop():
        gpu.matrix.load_projection_matrix(projection_matrix_2d(dim_x, dim_y))
        
    #LOOP HORIZONTAL
    for i in range(iteration):        
        with offscreen_B.bind():
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_A.color_texture)
            bgl.glActiveTexture(bgl.GL_TEXTURE1)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, depth_buffer.color_texture)            
            shader.bind()
            shader.uniform_int("Sampler", 0)
            shader.uniform_int("Depth", 1)
            shader.uniform_float("Beta", beta)
            shader.uniform_float("Offset", offset)
            shader.uniform_int("factor", factor)
            batch.draw(shader)
        with offscreen_A.bind():                   
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_B.color_texture)
            bgl.glActiveTexture(bgl.GL_TEXTURE1)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, depth_buffer.color_texture)           
            shader.bind()
            shader.uniform_int("Sampler", 0)
            shader.uniform_int("Depth", 1)
            shader.uniform_float("Beta", beta)
            shader.uniform_float("Offset", offset)
            shader.uniform_int("factor", factor)
            batch.draw(shader)
    #LOOP VERTICAL
    offset = (0, step / dim_y)     
    for i in range(iteration):
        with offscreen_B.bind():                   
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_A.color_texture)
            bgl.glActiveTexture(bgl.GL_TEXTURE1)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, depth_buffer.color_texture)           
            shader.bind()
            shader.uniform_int("Sampler", 0)
            shader.uniform_int("Depth", 1)
            shader.uniform_float("Beta", beta)
            shader.uniform_float("Offset", offset)
            shader.uniform_int("factor", factor)
            batch.draw(shader)
        with offscreen_A.bind():                   
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_B.color_texture)
            bgl.glActiveTexture(bgl.GL_TEXTURE1)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, depth_buffer.color_texture)            
            shader.bind()
            shader.uniform_int("Sampler", 0)
            shader.uniform_int("Depth", 1)
            shader.uniform_float("Beta", beta)
            shader.uniform_float("Offset", offset)
            shader.uniform_int("factor", factor)
            batch.draw(shader)
     
    offscreen_B.free()


def bgl_filter_sss(offscreen_A, depth_buffer, samples = 60, radius = 20, depth_precision = 50, channel = (1, 1, 1, 0)):
    """
    Flou en tenant compte de la couche de profondeur
    R = Valeur d'entrée
    G = Intensité
    B = Z depth
    A = Alpha
    """
    offscreen_B = gpu.types.GPUOffScreen(dim_x, dim_y)
      
    shader = compile_shader("image2d.vert", "sss.frag")                        
    batch = batch2d(shader, dim_x, dim_y)
    with gpu.matrix.push_pop():
            gpu.matrix.load_projection_matrix(projection_matrix_2d(dim_x, dim_y))

    for i in range (samples):
        radius -= radius/samples
        
        step = (0 , 1 / dim_y * radius)
        with offscreen_B.bind():                   
                bgl.glActiveTexture(bgl.GL_TEXTURE0)            
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_A.color_texture)
                bgl.glActiveTexture(bgl.GL_TEXTURE1)            
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, depth_buffer.color_texture)            
                shader.bind()                
                shader.uniform_int("Sampler", 0)
                shader.uniform_int("Depth", 1)
                shader.uniform_float("step", step)
                shader.uniform_float("depth_precision", depth_precision)
                shader.uniform_float("channel", channel)
                batch.draw(shader)
                step = (0 / dim_x * radius,1 / dim_y * radius)
                
        step = (1 / dim_x * radius , 0)        
        with offscreen_A.bind():                   
                bgl.glActiveTexture(bgl.GL_TEXTURE0)            
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_B.color_texture)
                bgl.glActiveTexture(bgl.GL_TEXTURE1)            
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, depth_buffer.color_texture)             
                shader.bind()
                shader.uniform_int("Sampler", 0)
                shader.uniform_int("Depth", 1)
                shader.uniform_float("step", step)
                shader.uniform_float("depth_precision", depth_precision)
                shader.uniform_float("channel", channel)
                batch.draw(shader)

    offscreen_B.free()


def bgl_filter_line(offscreen_A, depth_buffer, line_detection, border):     
    offscreen_B = gpu.types.GPUOffScreen(dim_x, dim_y)
            
    shader = compile_shader("image2d.vert", "line.frag")                        
    batch = batch2d(shader, dim_x, dim_y)

    with gpu.matrix.push_pop():
        gpu.matrix.load_projection_matrix(projection_matrix_2d(dim_x, dim_y))
    
    with offscreen_B.bind():                   
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_A.color_texture)
            bgl.glActiveTexture(bgl.GL_TEXTURE1)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, depth_buffer.color_texture)               
            shader.bind()
            shader.uniform_int("Sampler", 0)
            shader.uniform_int("Depth_buffer", 1)
            shader.uniform_int("border", border)
            shader.uniform_float("line_detection", line_detection)
            batch.draw(shader)

    copy_buffer(offscreen_B, offscreen_A, dim_x, dim_y)

    offscreen_B.free()


def bgl_filter_expand(offscreen_A, dim_x, dim_y, value):
    offscreen_B = gpu.types.GPUOffScreen(dim_x, dim_y)
            
    shader = compile_shader("image2d.vert", "expand.frag")                        
    batch = batch2d(shader, dim_x, dim_y)

    with gpu.matrix.push_pop():
        gpu.matrix.load_projection_matrix(projection_matrix_2d(dim_x, dim_y))
    
    if value > 0:
        expand = 1
    else:
        expand = 0

    iteration = abs(value)
    for i in range (iteration):
        step = (1/dim_x, 0)
        with offscreen_B.bind():                   
                bgl.glActiveTexture(bgl.GL_TEXTURE0)            
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_A.color_texture)            
                shader.bind()
                shader.uniform_int("Sampler", 0)
                shader.uniform_float("step", step)
                shader.uniform_int("expand", expand)
                batch.draw(shader)

        step = (0, 1/dim_y)
        with offscreen_A.bind():                   
                bgl.glActiveTexture(bgl.GL_TEXTURE0)            
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_B.color_texture)            
                shader.bind()
                shader.uniform_int("Sampler", 0)
                shader.uniform_float("step", step)
                shader.uniform_int("expand", expand)
                batch.draw(shader)
   
    offscreen_B.free()


def bake_to_texture(offscreen_A, offscreen_B, vertices, uvs, uv_indices, loop_indices):
    #res = texture_size
    uvs = uvs * (dim_x, dim_y)  
    uvs = uvs.tolist() #FIX Pourquoi ça ne marche pas avec numpy ?

    #Get vertex 2D coords
    loops = np.take(vertices, loop_indices, axis=0)

    camera = bpy.context.scene.camera
    depsgraph = bpy.context.evaluated_depsgraph_get()
    
    view_matrix = camera.matrix_world.inverted()
    projection_matrix = change_camera_matrix(camera, dim_x, dim_y)
    
    shader = compile_shader("bake.vert", "bake.frag")                        
    batch = batch_for_shader(
        shader, 'TRIS',
        {
            "pos": uvs,
            "texCoord": loops,
        },
        indices = uv_indices
    )

    with gpu.matrix.push_pop():
        gpu.matrix.load_projection_matrix(projection_matrix_2d(dim_x, dim_y))

    with offscreen_B.bind():
        bgl.glActiveTexture(bgl.GL_TEXTURE0)            
        bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_A.color_texture)
        shader.uniform_float("view_matrix", view_matrix)
        shader.uniform_float("projection_matrix", projection_matrix)
        shader.uniform_int("Sampler", 0)        
        shader.bind()
        batch.draw(shader)

def bgl_filter_noise(offscreen_A, scale, amplitude):    

    offscreen_B = gpu.types.GPUOffScreen(dim_x, dim_y)
    
    shader = compile_shader("image2d.vert", "noise.frag")                    
    batch = batch2d(shader, dim_x, dim_y)

    with gpu.matrix.push_pop():
        gpu.matrix.load_projection_matrix(projection_matrix_2d(dim_x, dim_y))        
      
    with offscreen_B.bind():
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_A.color_texture)            
            shader.bind()
            shader.uniform_int("Sampler", 0)
            shader.uniform_float("scale", scale)
            shader.uniform_float("amplitude", amplitude)
            shader.uniform_float("u_resolution", (dim_x, dim_y))
            batch.draw(shader)
    
    copy_buffer(offscreen_B, offscreen_A, dim_x, dim_y)

    offscreen_B.free()

def bgl_filter_scale(offscreen_A, scale):    

    offscreen_B = gpu.types.GPUOffScreen(dim_x, dim_y)
    
    shader = compile_shader("image2d.vert", "scale.frag")                    
    batch = batch2d(shader, dim_x, dim_y)

    with gpu.matrix.push_pop():
        gpu.matrix.load_projection_matrix(projection_matrix_2d(dim_x, dim_y))        
      
    with offscreen_B.bind():
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_A.color_texture)            
            shader.bind()
            shader.uniform_int("Sampler", 0)
            shader.uniform_float("scale", scale)
            batch.draw(shader)
    
    copy_buffer(offscreen_B, offscreen_A, dim_x, dim_y)

    offscreen_B.free()


def bgl_filter_custom(offscreen_A, filter, value):    

    offscreen_B = gpu.types.GPUOffScreen(dim_x, dim_y)
    
    shader = compile_shader("image2d.vert", "{}.frag".format(filter))                    
    batch = batch2d(shader, dim_x, dim_y)

    with gpu.matrix.push_pop():
        gpu.matrix.load_projection_matrix(projection_matrix_2d(dim_x, dim_y))        
      
    with offscreen_B.bind():
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_A.color_texture)            
            shader.bind()
            shader.uniform_int("Sampler", 0)
            shader.uniform_int("value", value)
            batch.draw(shader)
    
    copy_buffer(offscreen_B, offscreen_A, dim_x, dim_y)

    offscreen_B.free()

def bgl_filter_noise2(offscreen_A):    

    offscreen_B = gpu.types.GPUOffScreen(dim_x, dim_y)
    
    shader = compile_shader("image2d.vert", "noise2.frag")                    
    batch = batch2d(shader, dim_x, dim_y)

    with gpu.matrix.push_pop():
        gpu.matrix.load_projection_matrix(projection_matrix_2d(dim_x, dim_y))        
      
    with offscreen_B.bind():
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_A.color_texture)            
            shader.bind()
            shader.uniform_int("Sampler", 0)
            #shader.uniform_float("scale", scale)
            #shader.uniform_float("amplitude", amplitude)
            #shader.uniform_float("u_resolution", (dim_x, dim_y))
            batch.draw(shader)
    
    copy_buffer(offscreen_B, offscreen_A, dim_x, dim_y)

    offscreen_B.free()

