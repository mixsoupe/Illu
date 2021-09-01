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
import bmesh
import numpy as np
import time
from mathutils import Vector
from . utils import *


class Geometry:
    def __init__(self, object, node = None):
        self.object = object        
        self.node = node

        self.bake_to_uvs = None
        if node:
            self.node = node
            self.image_name = node.node_tree.nodes['Image'].image.name
            self.texture_size = int(node.texture_size)
            self.shadow_size = int(node.shadow_size)
            self.self_shading = node.self_shading
            self.bake_to_uvs = node.bake_to_uvs
            self.light = get_socket_value(node, "Light")
            self.scale = get_socket_value(node, "Scale")
            self.smoothness = get_socket_value(node, "Smoothness")
            self.angle = get_socket_value(node, "Angle Compensation")
            self.soft_shadow = get_socket_value(node, "Soft Shadow")
            self.line_scale = get_socket_value(node, "Line Scale")
            self.line_detection = get_socket_value(node, "Line Detection")    
            self.noise_scale = get_socket_value(node, "Noise Scale")
            self.noise_diffusion = get_socket_value(node, "Noise Diffusion")

        self.build_model(object)



    def build_model(self, obj, get_uv = False):
        camera = bpy.context.scene.camera

        #Préparation du mesh 
        mesh = bpy.data.meshes.new("temp_mesh")
        bm = bmesh.new()

        object_state = {}

        bm_temp = bmesh.new()
        subsurfs = {}

        #Disable subsurf
        for modifier in obj.modifiers:
            if modifier.type == "SUBSURF":
                subsurfs[modifier.name] = (modifier.show_viewport, modifier.show_render)
                modifier.show_viewport = False
                modifier.show_render = False
        object_state[obj.name] = subsurfs
        depsgraph = bpy.context.evaluated_depsgraph_get()          
        bm_temp.from_object(object=obj, depsgraph=depsgraph, deform=True)
        bm_temp.transform(obj.matrix_world)
        bm_temp.to_mesh(mesh)
        bm_temp.free()
        bm.from_mesh(mesh)

        bmesh.ops.triangulate(bm, faces=bm.faces[:]) #SLOW
        
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

        #Orco coordinates
        bm = bmesh.new()

        mesh_orco = bpy.data.meshes.new("temp_mesh_orco")

        bm_temp = bmesh.new()            
        bm_temp.from_object(object=obj, depsgraph=depsgraph, deform=False)
        bm_temp.to_mesh(mesh_orco)
        bm_temp.free()
        bm.from_mesh(mesh_orco)
        
        bmesh.ops.triangulate(bm, faces=bm.faces[:]) 
        
        bm.to_mesh(mesh)
        bm.free()
        
        mesh_orco.calc_loop_triangles()
        
        vlen_orco = len(mesh_orco.vertices)
        
        #Récupération des données
        orco = np.empty((vlen_orco, 3), 'f')
        mesh_orco.vertices.foreach_get(
            "co", np.reshape(orco, vlen_orco * 3))

        t = time.time()
        if self.bake_to_uvs:
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
        #print ((time.time()-t)*1000) 
        camera_loc = camera.location  

        #Calcul et normalisation zdepth    
        distances = np.linalg.norm(vertices - camera_loc, ord=2, axis=1.)
        distance_average = np.average(distances)
        
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
        color_rgba = color_rgba.tolist()
            
        #Nettoyage
        bpy.data.meshes.remove(mesh)
        
        #REnable subsurf
        

        for modifier in obj.modifiers:
            if modifier.type == "SUBSURF":
                modifier.show_viewport = object_state[obj.name][modifier.name][0]
                modifier.show_render = object_state[obj.name][modifier.name][1]
        

        self.vertices = vertices
        self.indices = indices
        self.colors = color_rgba
        if self.bake_to_uvs:
            self.uvs = uvs
            self.uv_indices = uv_indices
            self.loop_indices = loop_indices
        self.orco = orco
        self.distance = distance_average



