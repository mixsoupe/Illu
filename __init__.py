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
    "version" : (1, 4, 1),
    "location" : "View3D",
    "warning" : "",
    "category" : "",
}
import bpy
from . import addon_updater_ops
from . illu import *
from bpy.app.handlers import persistent
from nodeitems_utils import NodeItem, register_node_categories, unregister_node_categories
from nodeitems_builtins import ShaderNodeCategory, CompositorNodeCategory

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
        column = layout.column()

        addon_updater_ops.update_settings_ui(self,context)

#PROPS
class ILLU_Object_Properties(bpy.types.PropertyGroup):
    cast_shadow: bpy.props.BoolProperty(
        name="Cast Shadow",
        default = False,
        override={'LIBRARY_OVERRIDABLE'},
        )

#PANELS
class ILLU_PT_view3d_ui(bpy.types.Panel):
    bl_label = "Illu"
    bl_idname = "ILLU_PT_view3d_ui"
    bl_space_type = "VIEW_3D"   
    bl_region_type = "UI"
    bl_category = "Illu"

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
        layout.prop(context.scene, "illu_playback")
        layout.prop(context.scene, "illu_render")
        layout.operator("illu.update_all")
        layout.operator("illu.update_selected")

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

#CUSTOM NODE    
class ILLU_2DShade(bpy.types.ShaderNodeCustomGroup, NodeHelper):

    bl_name = 'ILLU_2DShade'
    bl_label = '2D Shade'
    bl_description = "Testing node with unique nodetree"

    image_name: bpy.props.StringProperty(
        name="Image Name",
        )    
    objects: bpy.props.PointerProperty(
        name="Object",
        type=bpy.types.Object,
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
        default = False
        )
    bake_to_uvs: bpy.props.BoolProperty(
        name="Bake to UVs",
        default = False
        )
    override: bpy.props.BoolProperty(
        name="Override",
        default = False
        )

    def _new_node_tree(self):
        nt_name= '.' + self.bl_name + '_nodetree'
        self.node_tree=bpy.data.node_groups.new(nt_name, 'ShaderNodeTree')
        self.addNodes([('NodeGroupInput', {'name':'Group Input'}),
                    ('NodeGroupOutput', {'name':'Group Output'}),
                    ('ShaderNodeTexImage', {'name':'Image'}),
                    ('ShaderNodeSeparateRGB', {'name':'Separate'}),
                    ('ShaderNodeMapRange', {'name':'Line'}),
                    ('ShaderNodeMapRange', {'name':'Border'}),                    
                    ])
        self.addInputs([
                    ('NodeSocketObject', {'name':'Light'}),
                    ('NodeSocketFloat', {'name':'Scale','default_value':1.0, 'min_value':0, 'max_value':10}),
                    ('NodeSocketFloat', {'name':'Smoothness','default_value':0.1, 'min_value':0, 'max_value':1}),
                    ('NodeSocketFloat', {'name':'Angle Compensation', 'default_value':0.0, 'min_value':-180, 'max_value':180}),
                    ('NodeSocketFloat', {'name':'Soft Shadow', 'default_value':1.0, 'min_value':0, 'max_value':20}),                    
                    ('NodeSocketFloat', {'name':'Noise Scale', 'default_value':2000, 'min_value':0, 'max_value':10000}),
                    ('NodeSocketFloat', {'name':'Noise Diffusion', 'default_value':0.1, 'min_value':0, 'max_value':2}),
                    ('NodeSocketFloat', {'name':'Line Scale', 'default_value':1.0, 'min_value':0, 'max_value':100}),
                    ('NodeSocketFloat', {'name':'Line Detection', 'default_value':1.0, 'min_value':0, 'max_value':10}),
                    ('NodeSocketVector', {'name':'Vector', 'default_value':(0.0, 0.0, 0.0)}),
                        
                    ])
        self.addOutputs([('NodeSocketFloat', {'name':'Shade'}),
                    ('NodeSocketFloat', {'name':'Distance Field'}),
                    ('NodeSocketFloat', {'name':'Border'}),
                    ('NodeSocketFloat', {'name':'Line'}),
                    ('NodeSocketFloat', {'name':'Alpha'}),
                    ])
        self.addLinks([('nodes["Image"].outputs[0]', 'nodes["Separate"].inputs[0]'),
                    ('inputs["Vector"]', 'nodes["Image"].inputs[0]'),
                    ('nodes["Separate"].outputs[0]', 'outputs[0]'),
                    ('nodes["Separate"].outputs[1]', 'outputs[1]'),
                    ('nodes["Separate"].outputs[2]', 'nodes["Line"].inputs[0]'),
                    ('nodes["Separate"].outputs[2]', 'nodes["Border"].inputs[0]'),
                    ('nodes["Border"].outputs[0]', 'outputs[2]'),
                    ('nodes["Line"].outputs[0]', 'outputs[3]'),
                    ('nodes["Image"].outputs[1]', 'outputs[4]'),
                    ])
        self.node_tree.inputs["Vector"].hide_value = True
        self.node_tree.nodes['Line'].inputs[1].default_value = 0.5
        self.node_tree.nodes['Line'].inputs[2].default_value = 1.0
        self.node_tree.nodes['Border'].inputs[2].default_value = 0.212
        self.node_tree.nodes['Border'].inputs[3].default_value = 1.0
        self.node_tree.nodes['Border'].inputs[4].default_value = 0.0

    def new_image(self):
        if self.node_tree.name in bpy.data.images:
            bpy.data.images.remove(bpy.data.images[self.node_tree.name])
        
        image = bpy.data.images.new(self.node_tree.name, 2048, 2048) #FIX RESOLUTION

        self.node_tree.nodes['Image'].image = image
        self.node_tree.nodes['Image'].extension = "CLIP"

    def draw_buttons(self, context, layout):        
        layout.prop(self, 'objects')
        layout.prop(self, 'texture_size')
        layout.prop(self, 'shadow_size')
        layout.prop(self, 'self_shading')
        layout.prop(self, 'bake_to_uvs')
        layout.operator("illu.update")        

    def init(self, context):
        self._new_node_tree()
        self.new_image()

    def copy(self, node):        
        if node.node_tree:
            self.node_tree=node.node_tree.copy()
            self.new_image()
        else:
            self._new_node_tree()
            self.new_image()

    def free(self):
        bpy.data.images.remove(bpy.data.images[self.node_tree.name])        
        bpy.data.node_groups.remove(self.node_tree, do_unlink=True)

            
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
        return node.bl_idname == 'ILLU_2DShade'
    
    def execute(self, context):        
        node = context.active_node
           
        rendered, failed =  render(all = False, node = node)
        material_name = context.material.name

        if rendered:            
            self.report({'INFO'}, '{} rendered'.format(rendered))
        if failed:
            self.report({'WARNING'}, '{} render failed'.format(failed))  
        return {'FINISHED'}


class ILLU_OT_update_all(bpy.types.Operator):
    """Update all images"""
    bl_idname = "illu.update_all"
    bl_label = "Update All"
    
    def execute(self, context):
        rendered, failed = render(all = True)
        
        if rendered:
            self.report({'INFO'}, '{} rendered'.format(rendered))
        if failed:
            self.report({'WARNING'}, '{} render failed'.format(failed))  

        return {'FINISHED'}

class ILLU_OT_update_selected(bpy.types.Operator):
    """Update selected"""
    bl_idname = "illu.update_selected"
    bl_label = "Update Selected"
    
    def execute(self, context):
        rendered, failed = render(all = False)
        
        print (failed)
        if rendered:
            self.report({'INFO'}, '{} rendered'.format(rendered))
        if failed:
            self.report({'WARNING'}, '{} render failed'.format(failed))  

        return {'FINISHED'}

#FUNCTIONS

@persistent
def update_handler(dummy):
    if bpy.context.scene.illu_playback:            
        render(all = True)
        
@persistent
def render_handler(dummy):
    if bpy.context.scene.illu_render:    
        render(all = True)


#REGISTER UNREGISTER
classes = (
    ILLU_Preferences,
    ILLU_Object_Properties,
    ILLU_PT_view3d_ui,
    ILLU_PT_object_ui,
    ILLU_OT_update, 
    ILLU_OT_update_all,
    ILLU_OT_update_selected,
    ILLU_2DShade,
    )

shcat = [ShaderNodeCategory("ILLU_NODES", "Illu", items=[NodeItem("ILLU_2DShade")]),]

def register():
    from bpy.utils import register_class
    for cls in classes:
        register_class(cls)
  
    if not hasattr( bpy.types.Object, 'illu'):
        bpy.types.Object.illu = bpy.props.PointerProperty(type=ILLU_Object_Properties, override={'LIBRARY_OVERRIDABLE'}) #FIX Simplifier, supprimer le group de propriété
    if not hasattr( bpy.types.Scene, 'illu_playback'):
        bpy.types.Scene.illu_playback = bpy.props.BoolProperty(name="Update on Playback", default=False)
    if not hasattr( bpy.types.Scene, 'illu_render'):
        bpy.types.Scene.illu_render = bpy.props.BoolProperty(name="Update on Render", default=True)

    bpy.app.handlers.frame_change_post.append(update_handler)
    bpy.app.handlers.render_pre.append(render_handler)
    
    register_node_categories("ILLU_NODES", shcat)

def unregister():
    addon_updater_ops.register(bl_info)

    from bpy.utils import unregister_class
    for cls in reversed(classes):
        unregister_class(cls)
    del bpy.types.Object.illu
    del bpy.types.Scene.illu_playback
    del bpy.types.Scene.illu_render

    bpy.app.handlers.frame_change_post.remove(update_handler)
    bpy.app.handlers.render_pre.remove(render_handler)

    unregister_node_categories("ILLU_NODES")