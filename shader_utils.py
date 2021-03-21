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
import gpu
import os
import math
import bmesh
import numpy as np
import time
import bgl
from gpu_extras.batch import batch_for_shader
from mathutils import Matrix, Vector
import mathutils

def load_shader(file):
    addon_path = os.path.realpath(__file__).split("shader_utils.py")[0]
    shaders_path = os.path.join(addon_path,"shaders", file)

    f = open(shaders_path, 'r')
    content = f.read()
    f.close()
    return(content)

def get_resolution():
    dim_x = bpy.context.scene.render.resolution_x
    dim_y = bpy.context.scene.render.resolution_y
    return (dim_x, dim_y)

def compile_shader(vertex, fragment):
    vertex_shader = load_shader(vertex)    
    fragment_shader = load_shader(fragment)            
    shader = gpu.types.GPUShader(vertex_shader, fragment_shader)
    return (shader)

def batch2d(shader):
    dim_x, dim_y =  get_resolution()
    batch = batch_for_shader(
        shader, 'TRI_FAN',
        {
            "pos": ((0, 0), (dim_x, 0), (dim_x, dim_y), (0, dim_y)),
            "texCoord": ((0, 0), (1, 0), (1, 1), (0, 1)),
        },
    )
    return(batch)

def projection_matrix_2d():
    dim_x, dim_y =  get_resolution()
    projection_matrix = Matrix.Diagonal( (2.0 / dim_x, 2.0 / dim_y, 1.0) )
    projection_matrix = Matrix.Translation( (-1.0, -1.0, 0.0) ) @ projection_matrix.to_4x4()
    return(projection_matrix)

def np_matrix_multiplication(matrix, coords):
    vlen = coords.shape[0]
    coords_4x4 = np.empty((vlen, 4), 'f')
    coords_4x4[::4] = 1.0
    coords_4x4[:,:-1] = coords
    coords_4x4 = np.dot(coords_4x4, matrix)
    coords = coords_4x4[:,:-1]
    
    return coords

def buffer_to_image(image_name, buffer):
    dim_x, dim_y =  get_resolution()
    
    if not image_name in bpy.data.images:
        bpy.data.images.new(image_name, dim_x, dim_y)

    image = bpy.data.images[image_name]
    image.scale(dim_x, dim_y)
    
    image.pixels.foreach_set(buffer)

def calc_proj_matrix(fov = 50, ortho = 0, clip_start = 6, clip_end = 100, dim_x = 2000, dim_y = 2000):
    #Calcul viewplane
    field = math.radians(fov)
    viewfac = dim_x / dim_y #C'est plus compliqué que ça
    
    if ortho == 0:
        pixsize = 2 * clip_start * math.tan(field / 2)  
    else:
        pixsize = ortho

    left = -0.5 * pixsize
    bottom = -0.5 * pixsize / viewfac
    right =  0.5 * pixsize
    top =  0.5 * pixsize / viewfac
    
    #Matrix
    Xdelta = right - left
    Ydelta = top - bottom
    Zdelta = clip_end - clip_start

    mat = [[0]*4 for i in range(4)]
    
    if ortho == 0:
        mat[0][0] = clip_start * 2 / Xdelta
        mat[1][1] = clip_start * 2 / Ydelta
        mat[2][2] = -(clip_end + clip_start) / Zdelta
        mat[2][3] = (-2 * clip_start * clip_end) / Zdelta
        mat[3][2] = -1

    else :
        mat[0][0] = 2 / Xdelta
        mat[1][1] = 2 / Ydelta
        mat[2][2] = -2 / Zdelta
        mat[2][3] = -(clip_end + clip_start) / Zdelta
        mat[3][3] = 1

    return Matrix(mat)


def build_model(objects):
    camera = bpy.context.scene.camera
    depsgraph = bpy.context.evaluated_depsgraph_get()

    #Préparation du mesh 
    mesh = bpy.data.meshes.new("temp_mesh")
    bm = bmesh.new()

    for o in objects: #Astuce pour fusionner plusieurs objets
        bm_temp = bmesh.new()            
        bm_temp.from_object(object=o, depsgraph=depsgraph, deform=True)
        bm_temp.transform(o.matrix_world)
        bm_temp.to_mesh(mesh)
        bm_temp.free()
        bm.from_mesh(mesh)
        obj = o

    bm.to_mesh(mesh)
    bm.free()

    mesh.calc_loop_triangles()
    
    vlen = len(mesh.vertices)
    tlen = len(mesh.loop_triangles)
    
    #Récupération des données
    indices = np.empty((tlen, 3), 'i')    
    mesh.loop_triangles.foreach_get(
        "vertices", np.reshape(indices, tlen * 3))

    vertices = np.empty((vlen, 3), 'f')
    mesh.vertices.foreach_get(
        "co", np.reshape(vertices, vlen * 3))
      
    normales = np.empty((vlen, 3), 'f')
    mesh.vertices.foreach_get(
        "normal", np.reshape(normales, vlen * 3))

    uvs = np.empty((vlen, 3), 'f')


    dim_x, dim_y =  get_resolution()

    camera_loc = camera.location
    view_matrix = camera.matrix_world.inverted()
    projection_matrix = camera.calc_matrix_camera(
            depsgraph, x=dim_x, y=dim_y)    

    #Calcul et normalisation zdepth    
    distances = np.linalg.norm(vertices - camera_loc, ord=2, axis=1.)
    distances = np.interp(distances, (distances.min(), distances.max()), (0, 1))
    
    depth = distances.reshape(vlen, 1)
    
    #Check et récupération de l'épaisseur
    thick_eval = False  
    vgroups = obj.vertex_groups

    for vg in vgroups:
        if vg.name == "Thickness":
            thick_eval = True
            break
    if thick_eval:
        weight_list = []
        for i in range(len(mesh.vertices)):
            weight_list.append(vg.weight(i))
        weights = np.asarray(weight_list)
    else:
        weights = np.zeros(len(mesh.vertices))

    color_rgba = np.c_[np.ones(len(mesh.vertices)), weights, depth, np.ones(len(mesh.vertices)) ]
    color_rgba = color_rgba.tolist()
        
    #Nettoyage
    bpy.data.meshes.remove(mesh)
    
    return vertices, indices, color_rgba, uvs


def get_shadow_objects(exclude):
     #Récupérer tous les objets de la scène qui ont un option "Cast Shadow" activée, mais pas l'objet
    shadow_objs = []

    
    for obj in bpy.data.objects:
        if obj != exclude[0]:
            if obj.illu.cast_shadow and obj.type == 'MESH' and obj.hide_render is False:
                shadow_objs.append(obj)
                
    return shadow_objs

def calc_frustrum(view_matrix, vertices):

    vertices4 = np.c_[vertices, np.ones(vertices.shape[0])]
    
    vertices_pov = np.dot(view_matrix, vertices4.T).T
    
    min_x = np.min( vertices_pov[:, 0] )
    max_x = np.max( vertices_pov[:, 0] )
    min_y = np.min( vertices_pov[:, 1] )
    max_y = np.max( vertices_pov[:, 1] )
    min_z = np.min( vertices_pov[:, 2] )
    max_z = np.max( vertices_pov[:, 2] )

    size_x = abs(max_x - min_x)
    size_y = abs(max_y - min_y)
    size_z = abs(max_z - min_z)

    offset_x = -(min_x + max_x)/2 
    offset_y = -(min_y + max_y)/2
    offset_z = 0 if max_z < 0 else -max_z
    offset_z = -max_z

    clip_start = 0 if max_z > 0 else abs(max_z) #Invertion de min et max parce que Z est négatif
    clip_end = abs(min_z)


    return (size_x, size_y, size_z, clip_start, clip_end, offset_x, offset_y, offset_z)

def copy_buffer(source, target):
    shader = compile_shader("image2d.vert", "copy_buffer.frag")
    batch = batch2d(shader)

    with target.bind():                   
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, source.color_texture)            
            shader.bind()
            shader.uniform_int("Sampler", 0)
            batch.draw(shader)

def merge_buffers(offscreen_A, offscreen_B, operation):
    dim_x, dim_y =  get_resolution()
    offscreen_C = gpu.types.GPUOffScreen(dim_x, dim_y)
            
    shader = compile_shader("image2d.vert", "{}.frag".format(operation))                        
    batch = batch2d(shader)

    with gpu.matrix.push_pop():
        gpu.matrix.load_projection_matrix(projection_matrix_2d())
    
    with offscreen_C.bind():                   
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_A.color_texture)
            bgl.glActiveTexture(bgl.GL_TEXTURE1)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_B.color_texture)              
            shader.bind()
            shader.uniform_int("Sampler0", 0)
            shader.uniform_int("Sampler1", 1)              
            batch.draw(shader)

    copy_buffer(offscreen_C, offscreen_A)
    offscreen_C.free()


def soft_shadow_pattern(spread):
    vectors = (
        (0.1382, -0.4253, -0.2236), (-0.3618, -0.2629, -0.2236),
        (-0.3618, 0.2629, -0.2236), (0.1382, 0.4253, -0.2236),
        (0.4472, 0.0000, -0.2236), (0.0000, 0.0000, -0.5000),
        (0.4755, -0.1545, 0.0000), (0.4755, 0.1545, 0.0000),
        (0.0000, -0.5000, 0.0000), (0.2939, -0.4045, 0.0000),
        (-0.4755, -0.1545, 0.0000), (-0.2939, -0.4045, 0.0000),
        (-0.2939, 0.4045, 0.0000), (-0.4755, 0.1545, 0.0000),
        (0.2939, 0.4045, 0.0000), (0.0000, 0.5000, 0.0000),
        (0.3441, -0.2500, -0.2629), (-0.1314, -0.4045, -0.2629),
        (-0.4253, 0.0000, -0.2629), (-0.1314, 0.4045, -0.2629),
        (0.3441, 0.2500, -0.2629), (0.0812, -0.2500, -0.4253),
        (0.2629, 0.0000, -0.4253), (-0.2127, -0.1545, -0.4253),
        (-0.2127, 0.1545, -0.4253), (0.0812, 0.2500, -0.4253),
    )
    quaternions = []
    matrices = []
    for v in vectors:
        v = Vector(v)       
        quat = v.rotation_difference((0, 0, 1))
        quaternions.append(quat)

    for quat in quaternions:       
        
        axis, angle = quat.to_axis_angle()
        angle *= spread / 100
        quat = mathutils.Quaternion(axis, angle)

        mat = quat.to_matrix()
        mat = mat.to_4x4()
        matrices.append(mat)

    return matrices

def get_linked_objects(instance):
    depsgraph = bpy.context.evaluated_depsgraph_get()

    collection = instance.instance_collection

    for obj in collection.all_objects:
        bm = bmesh.new()
        bm.from_object(object=obj, depsgraph=depsgraph, deform=True)

def get_light_angle(light, camera):
    z_vector = light.matrix_world.col[2].to_3d()
    view_z_vector = z_vector @ camera.matrix_world
    angle = math.atan2(view_z_vector[1], view_z_vector[0])

    return math.degrees(angle)

    