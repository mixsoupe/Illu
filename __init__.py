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

bl_info = {
    "name" : "Illu",
    "author" : "Paul",
    "description" : "",
    "blender" : (2, 80, 0),
    "version" : (0, 0, 3),
    "location" : "View3D",
    "warning" : "",
    "category" : "",
}
import bpy
from . import addon_updater_ops
from . illu import *
from bpy.app.handlers import persistent

#PREFERENCES
class ILLU_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    #ADDON UPDATER PREFERENCES
    auto_check_update : bpy.props.BoolProperty(
    name = "Auto-check for Update",
    description = "If enabled, auto-check for updates using an interval",
    default = False,
    )

    updater_intrval_months : bpy.props.IntProperty(
        name='Months',
        description = "Number of months between checking for updates",
        default=0,
        min=0
    )
    updater_intrval_days : bpy.props.IntProperty(
        name='Days',
        description = "Number of days between checking for updates",
        default=7,
        min=0,
    )
    updater_intrval_hours : bpy.props.IntProperty(
        name='Hours',
        description = "Number of hours between checking for updates",
        default=0,
        min=0,
        max=23
    )
    updater_intrval_minutes : bpy.props.IntProperty(
        name='Minutes',
        description = "Number of minutes between checking for updates",
        default=0,
        min=0,
        max=59
    )


    def draw(self, context):
        layout = self.layout
        #column = layout.column()

        addon_updater_ops.update_settings_ui(self,context)


#PROPS
class ILLUNodeProperties(bpy.types.PropertyGroup):

    image_name: bpy.props.StringProperty(
        name="Image Name",
        )    
    objects: bpy.props.StringProperty(
        name="Object",
        )
    light: bpy.props.StringProperty(
        name="Light",
        )
    scale: bpy.props.FloatProperty(
        name = "Scale",
        default = 1.0,
        )      
    depth_precision: bpy.props.FloatProperty(
        name = "Volume Depth Precision",
        default = 0.08,
        )    
    angle: bpy.props.FloatProperty(
        name = "Angle Compensation",
        default = 0.0,
        )
    soft_shadow: bpy.props.FloatProperty(
        name = "Soft Shadow",
        default = 1.0,
        )
    texture_size: bpy.props.EnumProperty(
        name="Texture Size",
        items=[ ('1024', '1024', ""),
                ('2048', '2048', ""),
                ('4096', '4096', ""),
               ],
        default = '2048',
        )
    shadow_size: bpy.props.EnumProperty(
        name="Shadow Size",
        items=[ ('1024', '1024', ""),
                ('2048', '2048', ""),
                ('4096', '4096', ""),
               ],
        default = '2048',
        )
    self_shading: bpy.props.BoolProperty(
        name="Self Shading",
        default = True
        )
class ILLUObjectProperties(bpy.types.PropertyGroup):
    cast_shadow: bpy.props.BoolProperty(
        name="Cast Shadow",
        default = False,
        override={'LIBRARY_OVERRIDABLE'},
        )

#PANELS
class ILLU_PT_node_ui(bpy.types.Panel):
    bl_label = "Illu"
    bl_idname = "ILLU_PT_node_ui"
    bl_space_type = "NODE_EDITOR"   
    bl_region_type = "UI"
    bl_category = "WorkFlow"
    bl_context = "objectmode"

    @classmethod
    def poll(self,context):
        node = context.active_node
        if node is None:
            return False
        return node.bl_idname == 'ShaderNodeTexImage'
        
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        illu = context.active_node.illu

        layout.prop(illu, "image_name")
        layout.prop_search(illu, "objects", bpy.data, "objects")
        layout.prop_search(illu, "light", bpy.data, "objects")
        layout.prop(illu, "scale")
        layout.prop(illu, "depth_precision")
        layout.prop(illu, "angle")               
        layout.prop(illu, "soft_shadow")
        layout.prop(illu, "texture_size") 
        layout.prop(illu, "shadow_size")
        layout.prop(illu, "self_shading")        
        layout.operator("illu.update")
        layout.separator()

class ILLU_PT_view3d_ui(bpy.types.Panel):
    bl_label = "Illu"
    bl_idname = "ILLU_PT_view3d_ui"
    bl_space_type = "VIEW_3D"   
    bl_region_type = "UI"
    bl_category = "WorkFlow"

    def draw(self, context):
        layout = self.layout
        #Check for update

        addon_updater_ops.check_for_update_background()
        if addon_updater_ops.updater.update_ready == True:
            layout.label(text = "New addon version available", icon="INFO")

        obj = context.active_object
        
        if obj is not None:            
            obj_type = obj.type
            illu = obj.illu
            is_geometry = (obj_type in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'VOLUME', 'HAIR', 'POINTCLOUD'})
            if is_geometry: 
                layout.prop(illu, "cast_shadow")
        layout.prop(context.scene, "playback")
        layout.operator("illu.update_all")

class ILLU_PT_object_ui(bpy.types.Panel):
    bl_label = "Illu"
    bl_idname = "ILLU_PT_object_ui"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'    
    bl_context = "object"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls,context):
        obj = context.active_object
        obj_type = obj.type
        is_geometry = (obj_type in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'VOLUME', 'HAIR', 'POINTCLOUD'})
        
        return is_geometry

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        illu = obj.illu

        layout.prop(illu, "cast_shadow") 

   
#OPERATORS
class ILLU_OT_update(bpy.types.Operator):
    """Update image"""
    bl_idname = "illu.update"
    bl_label = "Update Image"

    @classmethod
    def poll(cls, context):
        if bpy.context.area.type != 'NODE_EDITOR':
            return False
        node = context.active_node
        if node is None:
            return False
        return node.bl_idname == 'ShaderNodeTexImage'

    def execute(self, context):
        node = context.active_node
        illu = node.illu

        if illu.image_name is not '' and illu.objects is not '' and illu.light is not '':    
            update_image(illu)
            image = bpy.data.images[illu.image_name]
            node.image = image
        else:
            self.report({"WARNING"}, "Missing properties")
            return {'CANCELLED'} 
        return {'FINISHED'}

class ILLU_OT_update_all(bpy.types.Operator):
    """Update all images"""
    bl_idname = "illu.update_all"
    bl_label = "Update All"

    def execute(self, context):
        update_all()
        return {'FINISHED'}

#FUNCTIONS
def update_image(illu):
    obj = [bpy.data.objects[illu.objects] ,] 
    image_name = illu.image_name
    light = bpy.data.objects[illu.light]
    scale = illu.scale
    depth_precision = illu.depth_precision
    angle = illu.angle
    texture_size = int(illu.texture_size)
    shadow_size = int(illu.shadow_size)
    soft_shadow = illu.soft_shadow
    self_shading = illu.self_shading    

    generate_images(obj, image_name, light, scale, depth_precision, angle, texture_size, shadow_size, soft_shadow, self_shading)

def update_all():
    
    for material in bpy.data.materials:
            if material.node_tree is not None:
                for node in material.node_tree.nodes:
                    if node.bl_idname == 'ShaderNodeTexImage':
                        illu = node.illu
                        if illu.image_name is not '' and illu.objects is not '' and illu.light is not '':    
                            update_image(illu)

@persistent
def update_handler(dummy):
    if bpy.context.scene.playback:
        update_all()

#REGISTER UNREGISTER
classes = (
    ILLU_Preferences,
    ILLUNodeProperties, 
    ILLUObjectProperties,
    ILLU_PT_node_ui, 
    ILLU_PT_view3d_ui,
    ILLU_PT_object_ui,
    ILLU_OT_update, 
    ILLU_OT_update_all,
    )

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)

    if not hasattr( bpy.types.ShaderNodeTexImage, 'illu'):
        bpy.types.ShaderNodeTexImage.illu = bpy.props.PointerProperty(type=ILLUNodeProperties)
    if not hasattr( bpy.types.Object, 'illu'):
        bpy.types.Object.illu = bpy.props.PointerProperty(type=ILLUObjectProperties, override={'LIBRARY_OVERRIDABLE'}) #FIX Simplifier, supprimer le group de propriété
    if not hasattr( bpy.types.Scene, 'playback'):
        bpy.types.Scene.playback = bpy.props.BoolProperty(name="Update on Playback", default=False)

    bpy.app.handlers.frame_change_post.append(update_handler)


def unregister():
    addon_updater_ops.register(bl_info)

    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)
    del bpy.types.ShaderNodeTexImage.illu
    del bpy.types.Object.illu
    del bpy.types.Scene.playback


    bpy.app.handlers.frame_change_post.remove(update_handler)
