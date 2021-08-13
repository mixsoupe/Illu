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

def batch2d(shader, dim_x, dim_y):
    #dim_x, dim_y =  get_resolution()
    batch = batch_for_shader(
        shader, 'TRI_FAN',
        {
            "pos": ((0, 0), (dim_x, 0), (dim_x, dim_y), (0, dim_y)),
            "texCoord": ((0, 0), (1, 0), (1, 1), (0, 1)),
        },
    )
    return(batch)

def projection_matrix_2d(dim_x, dim_y):
    #dim_x, dim_y =  get_resolution()
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

def buffer_to_image(image_name, buffer, dim_x, dim_y):
    
    if not image_name in bpy.data.images:
        bpy.data.images.new(image_name, dim_x, dim_y)

    image = bpy.data.images[image_name]
    image.scale(dim_x, dim_y)
    
    image.pixels.foreach_set(buffer)

def calc_proj_matrix(fov = 50, ortho = 0, clip_start = 6, clip_end = 100, dim_x = 2000, dim_y = 2000):
    #Calcul viewplane
    field = math.radians(fov)
    if ortho == 0:
        pixsize = 2 * clip_start * math.tan(field / 2)  
    else:
        pixsize = ortho

    if dim_x >= dim_y:
        viewfac_x = dim_x / dim_y
        viewfac_y = 1

    else:        
        viewfac_x = 1
        viewfac_y = dim_y / dim_x

    left = -0.5 * pixsize / viewfac_y
    bottom = -0.5 * pixsize / viewfac_x
    right =  0.5 * pixsize / viewfac_y
    top =  0.5 * pixsize / viewfac_x
    
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


def build_model(objects, get_uv = False):
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

    bmesh.ops.triangulate(bm, faces=bm.faces[:])
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
    
    if get_uv:
        # uvs = coordonnée de chaque uv point
        # uv_indices = les index des uv point pour chaque loop
        # uv_vertices = l'indice du vertex correspondant à l'uv

        #FIX convert to numpy
        uvs = []
        uv_indices = []
        loop_indices = []

        for uv_layer in mesh.uv_layers:
            if uv_layer.active_render:
                break

        for face in mesh.polygons:        
            for vert_idx, loop_idx in zip(face.vertices, face.loop_indices):
                uv_coords = uv_layer.data[loop_idx].uv
                uvs.append(uv_coords)                
                loop_indices.append(vert_idx)
            uv_indices.append(list(face.loop_indices))

          
        uvs = np.asarray(uvs)
        uv_indices = np.asarray(uv_indices, dtype = np.int32)
        loop_indices = np.asarray(loop_indices, dtype = np.int32) 

    camera_loc = camera.location  

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
        weights = np.ones(len(mesh.vertices))

    #Calcul des normales
    camera_vector = camera.matrix_world.to_quaternion() @ Vector((0.0, 0.0, 1.0))
    normals_to_camera = np.dot(normales, camera_vector)

    #final color
    color_rgba = np.c_[np.ones(len(mesh.vertices)), weights, normals_to_camera, np.ones(len(mesh.vertices)) ]
    #np.random.seed(2021)
    #color_rgba = np.c_[np.random.rand(len(mesh.vertices)), weights, normals_to_camera, np.ones(len(mesh.vertices)) ]
    color_rgba = color_rgba.tolist()
        
    #Nettoyage
    bpy.data.meshes.remove(mesh)
    
    if get_uv:
        return vertices, indices, color_rgba, uvs, uv_indices, loop_indices
    else:
        return vertices, indices, color_rgba


def get_shadow_objects(exclude):
     #Récupérer tous les objets de la scène qui ont un option "Cast Shadow" activée, mais pas l'objet
    shadow_objs = []

    for obj in bpy.context.scene.objects:
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

def copy_buffer(source, target, dim_x, dim_y):
    shader = compile_shader("image2d.vert", "copy_buffer.frag")
    batch = batch2d(shader, dim_x, dim_y)

    with gpu.matrix.push_pop():
        gpu.matrix.load_projection_matrix(projection_matrix_2d(dim_x, dim_y))

    with target.bind():                   
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, source.color_texture)            
            shader.bind()
            shader.uniform_int("Sampler", 0)
            batch.draw(shader)

def merge_buffers(offscreen_A, offscreen_B, operation, dim_x, dim_y):
    #dim_x, dim_y =  get_resolution()
    offscreen_C = gpu.types.GPUOffScreen(dim_x, dim_y)
            
    shader = compile_shader("image2d.vert", "{}.frag".format(operation))                        
    batch = batch2d(shader,dim_x, dim_y)

    with gpu.matrix.push_pop():
        gpu.matrix.load_projection_matrix(projection_matrix_2d(dim_x, dim_y))
    
    with offscreen_C.bind():                   
            bgl.glActiveTexture(bgl.GL_TEXTURE0)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_A.color_texture)
            bgl.glActiveTexture(bgl.GL_TEXTURE1)            
            bgl.glBindTexture(bgl.GL_TEXTURE_2D, offscreen_B.color_texture)              
            shader.bind()
            shader.uniform_int("Sampler0", 0)
            shader.uniform_int("Sampler1", 1)              
            batch.draw(shader)

    copy_buffer(offscreen_C, offscreen_A, dim_x, dim_y)
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

def change_camera_matrix(camera, dim_x, dim_y):
    fov = math.degrees(camera.data.angle * 1.2)
    clip_start = camera.data.clip_start
    clip_end = camera.data.clip_end

    projection_matrix = calc_proj_matrix(fov = fov, clip_start = clip_start, 
            clip_end = clip_end, dim_x = dim_x, dim_y = dim_y)

    return projection_matrix

def upscale_factor():
    camera = bpy.context.scene.camera    
    plane = math.tan(camera.data.angle/2)*2
    upscale_plane = math.tan((camera.data.angle * 1.2)/2)*2
    factor = plane/upscale_plane

    return factor

def traverse_node_tree(node_tree):
    yield node_tree
    for node in node_tree.nodes:
        if node.bl_idname =="ShaderNodeGroup":
            if node.node_tree is not None:
                yield from traverse_node_tree(node.node_tree)
                
class NodeHelper():
    def __path_resolve__(self, obj, path):
        if "." in path:
            extrapath, path= path.rsplit(".", 1)
            obj = obj.path_resolve(extrapath)
        return obj, path
            
    def value_set(self, obj, path, val):
        obj, path=self.__path_resolve__(obj, path)
        setattr(obj, path, val)                

    def addNodes(self, nodes):
        for nodeitem in nodes:
            node=self.node_tree.nodes.new(nodeitem[0])
            for attr in nodeitem[1]:
                self.value_set(node, attr, nodeitem[1][attr])

    def addLinks(self, links):
        for link in links:
            if isinstance(link[0], str):
                if link[0].startswith('inputs'):
                    socketFrom=self.node_tree.path_resolve('nodes["Group Input"].outputs' + link[0][link[0].rindex('['):])
                else:
                    socketFrom=self.node_tree.path_resolve(link[0])
            else:
                socketFrom=link[0]
            if isinstance(link[1], str):
                if link[1].startswith('outputs'):
                    socketTo=self.node_tree.path_resolve('nodes["Group Output"].inputs' + link[1][link[1].rindex('['):])
                else:
                    socketTo=self.node_tree.path_resolve(link[1])
            else:
                socketTo=link[1]
            self.node_tree.links.new(socketFrom, socketTo)

    def addInputs(self, inputs):
        for inputitem in inputs:
            name = inputitem[1].pop('name')
            socketInterface=self.node_tree.inputs.new(inputitem[0], name)
            socket=self.path_resolve(socketInterface.path_from_id())
            for attr in inputitem[1]:
                if attr in ['default_value', 'hide', 'hide_value', 'enabled']:
                    self.value_set(socket, attr, inputitem[1][attr])
                else:
                    self.value_set(socketInterface, attr, inputitem[1][attr])
            
    def addOutputs(self, outputs):
        for outputitem in outputs:
            name = outputitem[1].pop('name')
            socketInterface=self.node_tree.outputs.new(outputitem[0], name)
            socket=self.path_resolve(socketInterface.path_from_id())
            for attr in outputitem[1]:
                if attr in ['default_value', 'hide', 'hide_value', 'enabled']:
                    self.value_set(socket, attr, outputitem[1][attr])
                else:   
                    self.value_set(socketInterface, attr, outputitem[1][attr])

def get_socket_value(this_node, input):
    socket = this_node.inputs[input]
    links = socket.links
    if not links:
        return socket.default_value
    else:
        input_name = links[0].from_socket.name       
        if links[0].from_node.bl_idname == "NodeGroupInput":
            for material in bpy.data.materials:
                if material.node_tree is not None:
                    for node in material.node_tree.nodes:
                        if node.bl_idname =="ShaderNodeGroup":
                            if node.node_tree is not None:
                                for node_tree in traverse_node_tree(node.node_tree):                                    
                                    for subnode in node_tree.nodes:                    
                                        if subnode == this_node:
                                            group = node
                                            value = group.inputs[input_name].default_value
                                            return value
                

