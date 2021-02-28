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
from mathutils import Matrix, Vector, Euler

from . shader_utils import *

#FIX Prévoir un overscan
def generate_images(obj, image_name, light, scale, angle, shadow_size, soft_shadow, self_shading):
    T = time.time()
    dim_x, dim_y =  get_resolution()

    base_buffer = gpu.types.GPUOffScreen(dim_x, dim_y)
    shadow_buffer = gpu.types.GPUOffScreen(dim_x, dim_y)

    #Creation du modele        
    vertices, indices, colors = build_model(obj)
    
    #Shadow Buffer
    shadow_objs = get_shadow_objects(exclude = obj)
    if len(shadow_objs) > 0:
        vertices_shadow, indices_shadow, shadow_colors = build_model(shadow_objs) 
        bgl_shadow(shadow_buffer, vertices, indices, colors, vertices_shadow, indices_shadow, light, shadow_size, soft_shadow) 
        bgl_filter_sss(shadow_buffer, samples = 50, radius = 50) #FIX améliorer la diffusion des ombres
    
    #Base buffer  
    if self_shading:
        #Base render
        bgl_base_render(base_buffer, vertices, indices, colors)        
        bgl_filter_sss(base_buffer, samples = 50, radius = 50)

        #Distance field buffer
        #bgl_filter_distance_field(base_buffer)

        #Decal        
        bgl_filter_decal(base_buffer, light, scale, angle)
        #bgl_filter_sss(base_buffer, samples = 60, radius = 20)
        
        if len(shadow_objs) > 0:
            merge_buffers(base_buffer, shadow_buffer)
    else:
        copy_buffer(shadow_buffer, base_buffer)

    #Lecture du buffer    
    with base_buffer.bind():        
        buffer = bgl.Buffer(bgl.GL_FLOAT, dim_x * dim_y * 4)        
        bgl.glReadBuffer(bgl.GL_BACK)        
        bgl.glReadPixels(0, 0, dim_x, dim_y, bgl.GL_RGBA, bgl.GL_FLOAT, buffer)
    
    #Suppression des buffers
    shadow_buffer.free()
    base_buffer.free()
    
    #Enregistrement des images
    buffer_to_image( image_name, buffer )
    #print((time.time() - T)*1000)


def bgl_shadow(shadow_buffer, vertices, indices, colors,
    vertices_shadow, indices_shadow, light, shadow_size, soft_shadow):
    
    dim_x, dim_y =  get_resolution()

    #CSM 
    """CREER 3 buffers"""
    depth_buffer = gpu.types.GPUOffScreen(shadow_size, shadow_size)
    shadowmap_buffer = gpu.types.GPUOffScreen(dim_x, dim_y)

    #Camera matrix
    camera = bpy.context.scene.camera
    depsgraph = bpy.context.evaluated_depsgraph_get()    
    view_matrix = camera.matrix_world.inverted()
    projection_matrix = camera.calc_matrix_camera(
        depsgraph, x=dim_x, y=dim_y)
    
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
    batch_post = batch2d(shader_post)

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
                gpu.matrix.load_projection_matrix(projection_matrix_2d())                  
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
    dim_x, dim_y =  get_resolution()

    camera = bpy.context.scene.camera
    depsgraph = bpy.context.evaluated_depsgraph_get()
    
    view_matrix = camera.matrix_world.inverted()
    projection_matrix = camera.calc_matrix_camera(
        depsgraph, x=dim_x, y=dim_y)

    shader =  compile_shader("base.vert", "base.frag")
    batch = batch_for_shader(shader, 'TRIS', {"pos": vertices, "color": colors}, indices=indices)  

    with offscreen.bind():
        
        bgl.glClear(bgl.GL_COLOR_BUFFER_BIT)
        
        with gpu.matrix.push_pop():
                           
            #coords = [(1, 0, 0), (0, 0, 0), (0, 1, 0)]
            shader.bind()
            shader.uniform_float("modelMatrix", view_matrix)
            shader.uniform_float("viewProjectionMatrix", projection_matrix)
            
            bgl.glClearDepth(1000000);
            bgl.glClearColor(0.0, 0.0, 0.0, 0.0);
            bgl.glClear(bgl.GL_COLOR_BUFFER_BIT | bgl.GL_DEPTH_BUFFER_BIT)
                      
            bgl.glEnable(bgl.GL_DEPTH_TEST)
            
            batch.draw(shader)
                            
            bgl.glDisable(bgl.GL_DEPTH_TEST)  

            
def bgl_filter_decal(offscreen_A, light, scale, angle):
    camera = bpy.context.scene.camera
    light_angle = get_light_angle(light, camera) - angle

    dim_x, dim_y =  get_resolution()
    offscreen_B = gpu.types.GPUOffScreen(dim_x, dim_y)
            
    shader = compile_shader("image2d.vert", "decal.frag")                        
    batch = batch2d(shader)

    with gpu.matrix.push_pop():
        gpu.matrix.load_projection_matrix(projection_matrix_2d())
    
    rad = math.radians(light_angle)
    with offscreen_B.bind():                   
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_A.color_texture)            
            shader.bind()
            shader.uniform_int("Sampler", 0)
            shader.uniform_float("scale", scale)
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
            shader.uniform_float("angle", rad)
            shader.uniform_float("dim_x", dim_x)
            shader.uniform_float("dim_y", dim_y)
            shader.uniform_int("inverse", 0) 
            batch.draw(shader)

    #copy_buffer(offscreen_B, offscreen_A)
            

def bgl_filter_distance_field(offscreen_A):    

    dim_x, dim_y =  get_resolution()
    offscreen_B = gpu.types.GPUOffScreen(dim_x, dim_y)
    
    shader_PRE = compile_shader("image2d.vert", "distance_field_pre.frag")
    batch_PRE = batch2d(shader_PRE)

    shader = compile_shader("image2d.vert", "distance_field.frag")                    
    batch = batch2d(shader)
    
    shader_POST = compile_shader("image2d.vert", "distance_field_post.frag")
    batch_POST = batch2d(shader_POST)
    
    with gpu.matrix.push_pop():
        gpu.matrix.load_projection_matrix(projection_matrix_2d())

    #PRE
    with offscreen_B.bind():                   
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_A.color_texture)            
            shader_PRE.bind()
            shader_PRE.uniform_int("Sampler", 0)
            batch_PRE.draw(shader_PRE)
    
    div = 10000
    step = 2
    start = 20
    #LOOP HORIZONTAL
    beta = start / div
    offset = (step / dim_x, 0)
    for i in range(500):
        beta += 1 / div
        with offscreen_A.bind():                   
                bgl.glActiveTexture(bgl.GL_TEXTURE0)            
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_B.color_texture)            
                shader.bind()
                shader.uniform_int("Sampler", 0)
                shader.uniform_float("Beta", beta)
                shader.uniform_float("Offset", offset)
                batch.draw(shader)
        beta += 1 / div
        with offscreen_B.bind():                   
                bgl.glActiveTexture(bgl.GL_TEXTURE0)            
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_A.color_texture)            
                shader.bind()
                shader.uniform_int("Sampler", 0)
                shader.uniform_float("Beta", beta)
                shader.uniform_float("Offset", offset)
                batch.draw(shader)
                
    #LOOP VERTICAL
    beta = start / div
    offset = (0, step / dim_y)     
    for i in range(500):
        beta += 1 / div
        with offscreen_A.bind():                   
                bgl.glActiveTexture(bgl.GL_TEXTURE0)            
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_B.color_texture)            
                shader.bind()
                shader.uniform_int("Sampler", 0)
                shader.uniform_float("Beta", beta)
                shader.uniform_float("Offset", offset)
                batch.draw(shader)
        beta += 1 / div
        with offscreen_B.bind():                   
                bgl.glActiveTexture(bgl.GL_TEXTURE0)            
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_A.color_texture)            
                shader.bind()
                shader.uniform_int("Sampler", 0)
                shader.uniform_float("Beta", beta)
                shader.uniform_float("Offset", offset)
                batch.draw(shader)
    #POST
    with offscreen_A.bind():                   
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_B.color_texture)            
            shader_POST.bind()
            shader_POST.uniform_int("Sampler", 0)
            batch_POST.draw(shader_POST)

    offscreen_B.free()


def bgl_filter_sss(offscreen_A, samples = 60, radius = 20):
    """
    Flou en tenant compte de la couche de profondeur
    R = Valeur d'entrée
    G = Intensité
    B = Z depth
    A = Alpha
    """
    dim_x, dim_y =  get_resolution()

    offscreen_B = gpu.types.GPUOffScreen(dim_x, dim_y)
      
    shader = compile_shader("image2d.vert", "sss.frag")                        
    batch = batch2d(shader)
    
    with gpu.matrix.push_pop():
            gpu.matrix.load_projection_matrix(projection_matrix_2d())

    for i in range (samples):
        radius -= radius/samples
        
        step = (0 , 1 / dim_y * radius)
        with offscreen_B.bind():                   
                bgl.glActiveTexture(bgl.GL_TEXTURE0)            
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_A.color_texture)            
                shader.bind()
                shader.uniform_int("Sampler", 0)
                shader.uniform_float("step", step)
                batch.draw(shader)
                step = (0 / dim_x * radius,1 / dim_y * radius)
                
        step = (1 / dim_x * radius , 0)        
        with offscreen_A.bind():                   
                bgl.glActiveTexture(bgl.GL_TEXTURE0)            
                bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_B.color_texture)            
                shader.bind()
                shader.uniform_int("Sampler", 0)
                shader.uniform_float("step", step)
                batch.draw(shader)

    offscreen_B.free()
          


    