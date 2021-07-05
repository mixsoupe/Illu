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

#FIX Prévoir un overscan
def generate_images(obj, image_name, light, scale, depth_precision, angle, texture_size, shadow_size, soft_shadow, self_shading, bake_to_uvs, line_scale, noise_scale, noise_diffusion):
    T = time.time()
    global dim_x
    global dim_y
    dim_x, dim_y =  get_resolution()
    ratio = dim_x / dim_y
    
    if ratio > 1:        
        dim_x = texture_size
        dim_y = int(dim_x / ratio)
    else:
        dim_y = texture_size
        dim_x = int(dim_y * ratio)
    
    for i in range(10):
        base_buffer = gpu.types.GPUOffScreen(dim_x, dim_y)
        base_buffer_copy = gpu.types.GPUOffScreen(dim_x, dim_y)
        erosion_buffer = gpu.types.GPUOffScreen(dim_x, dim_y)
        shadow_buffer = gpu.types.GPUOffScreen(dim_x, dim_y)

        #Creation du modele        
        vertices, indices, colors, uvs, uv_indices, loop_indices = build_model(obj, get_uv = True)
        
        #Shadow Buffer
        shadow_objs = get_shadow_objects(exclude = obj)
        if len(shadow_objs) > 0:
            vertices_shadow, indices_shadow, shadow_colors = build_model(shadow_objs) 
            bgl_shadow(shadow_buffer, vertices, indices, colors, vertices_shadow, indices_shadow, light, shadow_size, soft_shadow)         
        
        #Base buffer  
        if self_shading:
            #Base render
            bgl_base_render(base_buffer, vertices, indices, colors)
            
            bgl_filter_expand(base_buffer, dim_x, dim_y, 3)
            bgl_filter_sss(base_buffer, samples = 20, radius = 10, simple = True, channel = 1)
            
            copy_buffer(base_buffer, base_buffer_copy, dim_x, dim_y)
            
            #Distance field buffer (transparence)                
            bgl_filter_distance_field(base_buffer_copy, scale)
            bgl_filter_sss(base_buffer_copy, samples = 20, radius = 10, simple = True)
            bgl_filter_expand(base_buffer_copy, dim_x, dim_y, -4)        
            merge_buffers(base_buffer_copy, base_buffer, "merge_a1toa0", dim_x, dim_y)
            bgl_filter_sss(base_buffer_copy, samples = 20, radius = 2, simple = True) 

            merge_buffers(base_buffer, base_buffer_copy, "merge_r1tog0", dim_x, dim_y)  
            
            #Decal (shading)    
            bgl_filter_decal(base_buffer, light, scale, depth_precision, angle)
            bgl_filter_sss(base_buffer, samples = max(20, 30*int(scale)), radius = max(8, 10*int(scale)), mask = False)

            #Merge Shadow             
            if len(shadow_objs) > 0:
                merge_buffers(base_buffer, shadow_buffer, "merge_r0dotr1", dim_x, dim_y)
                
            #Ajouter le trait
            bgl_filter_line(base_buffer, line_scale)

            #Noise
                      
            copy_buffer(base_buffer, erosion_buffer, dim_x, dim_y)
            bgl_filter_noise(erosion_buffer, noise_scale, noise_diffusion/100)       
            merge_buffers(base_buffer, erosion_buffer, "merge_noise", dim_x, dim_y)
            
            
        elif len(shadow_objs) == 0:            
                bgl_base_render(base_buffer, vertices, indices, colors)

        else:                    
            copy_buffer(shadow_buffer, base_buffer, dim_x, dim_y)
            bgl_filter_sss(base_buffer, samples = int(10 * soft_shadow), radius = int(3 * soft_shadow))
            bgl_filter_noise(base_buffer, noise_scale, noise_diffusion/100) 
        
        #Check
        valid = valid_check(base_buffer)

        if valid:
            break

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
    base_buffer_copy.free()
    erosion_buffer.free()
    base_buffer.free()

    #Enregistrement des images
    buffer_to_image( image_name, buffer, dim_x, dim_y)

    #print((time.time() - T)*1000)

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
        light_matrix = light.matrix_world.inverted()

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

    
def bgl_base_render(offscreen, vertices, indices, colors):

    camera = bpy.context.scene.camera
    depsgraph = bpy.context.evaluated_depsgraph_get()
    
    view_matrix = camera.matrix_world.inverted()
    projection_matrix = change_camera_matrix(camera, dim_x, dim_y)

    shader =  compile_shader("base.vert", "base.frag")
    batch = batch_for_shader(shader, 'TRIS', {"pos": vertices, "color": colors}, indices=indices)  

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

            
def bgl_filter_decal(offscreen_A, light, scale, depth_precision, angle):
    camera = bpy.context.scene.camera
    light_angle = get_light_angle(light, camera) - angle

    offscreen_B = gpu.types.GPUOffScreen(dim_x, dim_y)
            
    shader = compile_shader("image2d.vert", "decal.frag")                        
    batch = batch2d(shader, dim_x, dim_y)

    with gpu.matrix.push_pop():
        gpu.matrix.load_projection_matrix(projection_matrix_2d(dim_x, dim_y))
    
    rad = math.radians(light_angle)
    with offscreen_B.bind():                   
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_A.color_texture)            
            shader.bind()
            shader.uniform_int("Sampler", 0)
            shader.uniform_float("scale", scale)
            shader.uniform_float("depth_precision", depth_precision)
            shader.uniform_float("angle", rad)
            shader.uniform_float("dim_x", dim_x)
            shader.uniform_float("dim_y", dim_y)
            shader.uniform_int("inverse", 1) 
            batch.draw(shader)

    rad = math.radians(light_angle + 180)
    with offscreen_A.bind():                   
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_B.color_texture)            
            shader.bind()
            shader.uniform_int("Sampler", 0)
            shader.uniform_float("scale", scale)
            shader.uniform_float("depth_precision", depth_precision)
            shader.uniform_float("angle", rad)
            shader.uniform_float("dim_x", dim_x)
            shader.uniform_float("dim_y", dim_y)
            shader.uniform_int("inverse", 0) 
            batch.draw(shader)

    offscreen_B.free()
            

def bgl_filter_distance_field(offscreen_A, scale,  factor = True):    

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
            shader.bind()
            shader.uniform_int("Sampler", 0)
            shader.uniform_float("Beta", beta)
            shader.uniform_float("Offset", offset)
            shader.uniform_int("factor", factor)
            batch.draw(shader)
        with offscreen_A.bind():                   
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_B.color_texture)            
            shader.bind()
            shader.uniform_int("Sampler", 0)
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
            shader.bind()
            shader.uniform_int("Sampler", 0)
            shader.uniform_float("Beta", beta)
            shader.uniform_float("Offset", offset)
            shader.uniform_int("factor", factor)
            batch.draw(shader)
        with offscreen_A.bind():                   
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_B.color_texture)            
            shader.bind()
            shader.uniform_int("Sampler", 0)
            shader.uniform_float("Beta", beta)
            shader.uniform_float("Offset", offset)
            shader.uniform_int("factor", factor)
            batch.draw(shader)
     
    offscreen_B.free()


def bgl_filter_sss(offscreen_A, samples = 60, radius = 20, mask = False, simple = False, channel = 0):
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
                shader.bind()                
                shader.uniform_int("Sampler", 0)
                shader.uniform_float("step", step)
                shader.uniform_int("mask", mask)
                shader.uniform_int("simple", simple)
                shader.uniform_int("channel", channel)
                batch.draw(shader)
                step = (0 / dim_x * radius,1 / dim_y * radius)
                
        step = (1 / dim_x * radius , 0)        
        with offscreen_A.bind():                   
                bgl.glActiveTexture(bgl.GL_TEXTURE0)            
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_B.color_texture)            
                shader.bind()
                shader.uniform_int("Sampler", 0)
                shader.uniform_float("step", step)
                shader.uniform_int("mask", mask)
                shader.uniform_int("simple", simple)
                shader.uniform_int("channel", channel)
                batch.draw(shader)

    offscreen_B.free()
          


def bgl_filter_line(offscreen_A, line_scale):     
    offscreen_B = gpu.types.GPUOffScreen(dim_x, dim_y)
            
    shader = compile_shader("image2d.vert", "line.frag")                        
    batch = batch2d(shader, dim_x, dim_y)

    with gpu.matrix.push_pop():
        gpu.matrix.load_projection_matrix(projection_matrix_2d(dim_x, dim_y))
    
    with offscreen_B.bind():                   
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_A.color_texture)            
            shader.bind()
            shader.uniform_int("Sampler", 0)
            shader.uniform_int("line_scale", line_scale)
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

def valid_check(offscreen_A):
    offscreen_B = gpu.types.GPUOffScreen(dim_x, dim_y)
    offscreen_C = gpu.types.GPUOffScreen(dim_x, dim_y)

    shader = compile_shader("image2d.vert", "check.frag")                    
    batch = batch2d(shader, dim_x, dim_y)

    with gpu.matrix.push_pop():
        gpu.matrix.load_projection_matrix(projection_matrix_2d(dim_x, dim_y))  

    with offscreen_B.bind():            
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_A.color_texture)
            shader.bind()
            shader.uniform_int("Sampler", 0)
            shader.uniform_float("offset", (1, 0))
            shader.uniform_int("iteration", dim_x)
            batch.draw(shader)
    
    with offscreen_C.bind():            
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_B.color_texture)
            shader.bind()
            shader.uniform_int("Sampler", 0)
            shader.uniform_float("offset", (0, 1))
            shader.uniform_int("iteration", dim_y)
            batch.draw(shader)
            
            buffer = bgl.Buffer(bgl.GL_BYTE, dim_x * dim_y)        
            bgl.glReadBuffer(bgl.GL_BACK)        
            bgl.glReadPixels(0, 0, dim_x, dim_y, bgl.GL_GREEN, bgl.GL_BYTE, buffer)        

    #copy_buffer(offscreen_C, offscreen_A, dim_x, dim_y)

    offscreen_B.free()
    offscreen_C.free()

    value = buffer[0]

    if value > 0:
        return True
    else:
        return False

