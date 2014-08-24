# -*- coding: utf-8 -*-
# Copyright (c) 2014, Vispy Development Team.
# Distributed under the (new) BSD License. See LICENSE.txt for more info.

""" A Mesh Visual that uses the new shader Function.
"""

from __future__ import division

import numpy as np

#from .visual import Visual
#from ..shader.function import Function, Variable
#from ...import gloo

from vispy.scene.visuals.visual import Visual
from vispy.scene.shaders import ModularProgram, Function, Variable, Varying
from vispy import gloo
from vispy.util.meshdata import MeshData

## Snippet templates (defined as string to force user to create fresh Function)
# Consider these stored in a central location in vispy ...


vertex_template = """

void main() {
   gl_Position = $transform($position);
}
"""

fragment_template = """
void main() {
  gl_FragColor = $color;
}
"""

phong_template = """
vec4 phong_shading(vec4 color) {
    vec3 norm = normalize($normal.xyz);
    vec3 light = normalize($light_dir.xyz);
    float p = dot(light, norm);
    p = (p < 0. ? 0. : p);
    vec4 diffuse = $light_color * p;
    diffuse.a = 1.0;
    p = dot(reflect(light, norm), vec3(0,0,1));
    if (p < 0.0) {
        p = 0.0;
    }
    vec4 specular = $light_color * 5.0 * pow(p, 100.);
    return color * ($ambient + diffuse) + specular;
}
"""

## Functions that can be used as is (don't have template variables)
# Consider these stored in a central location in vispy ...

vec3to4 = Function("""
vec4 vec3to4(vec3 xyz) {
    return vec4(xyz, 1.0);
}
""")



## Actual code


class Mesh(Visual):
    
    def __init__(self, vertices=None, faces=None, vertex_colors=None,
                 face_colors=None, color=(0.5, 0.5, 1, 1), meshdata=None, 
                 shading=None, **kwds):
        Visual.__init__(self, **kwds)
        
        # Create a program
        self._program = ModularProgram(vertex_template, fragment_template)
        
        # Define variables related to color. Only one is in use at all times
        #self._variables = {}
        #self._variables['u_color3'] = Variable('uniform vec3 u_color')
        #self._variables['u_color4'] = Variable('uniform vec4 u_color')
        #self._variables['a_color3'] = Variable('attribute vec3 a_color')
        #self._variables['a_color4'] = Variable('attribute vec4 a_color')

        # Define buffers
        self._vertices = gloo.VertexBuffer(np.zeros((300, 3), dtype=np.float32))
        self._normals = gloo.VertexBuffer(np.zeros((0, 3), dtype=np.float32))
        self._faces = gloo.IndexBuffer()
        self._colors = gloo.VertexBuffer(np.zeros((0, 4), dtype=np.float32))
        
        # Whether to use _faces index
        self._indexed = None
        
        # Uniform color
        self._color = color
        
        # varyings
        self._color_var = Varying('v_color', dtype='vec4')
        self._normal_var = Varying('v_normal', dtype='vec3')
        
        # Init
        self.shading = shading
        self.set_data(vertices=vertices, faces=faces, 
                      vertex_colors=vertex_colors,
                      face_colors=face_colors, meshdata=meshdata)

    def set_data(self, vertices=None, faces=None, vertex_colors=None, 
                 face_colors=None, meshdata=None, color=None):
        """
        """
        
        if meshdata is not None:
            self._meshdata = meshdata
        else:
            self._meshdata = MeshData(vertices=vertices, faces=faces, 
                                      vertex_colors=vertex_colors,
                                      face_colors=face_colors)

        if color is not None:
            self._color = color
        self.mesh_data_changed()
    
    def mesh_data_changed(self):
        self._data_changed = True
        self.update()
        
    def _update_data(self):
        md = self._meshdata
        
        # Update vertex/index buffers
        if self.shading == 'smooth' and not md.has_face_indexed_data():
            self._vertices.set_data(md.vertices())
            self._normals.set_data(md.vertex_normals())
            self._faces.set_data(md.faces())
            self._indexed = True
            if md.has_vertex_color():
                self._colors.set_data(md.vertex_colors())
            if md.has_face_color():
                self._colors.set_data(md.face_colors())
        else:
            v = md.vertices(indexed='faces')
            #self._vertices.set_data(v)  # preferred but buggy (#450)
            self._vertices = gloo.VertexBuffer(v)
            if self.shading == 'smooth':
                self._normals.set_data(md.vertex_normals(indexed='faces'))
            elif self.shading == 'flat':
                self._normals.set_data(md.face_normals(indexed='faces'))
            self._indexed = False
            if md.has_vertex_color():
                self._colors.set_data(md.vertex_colors(indexed='faces'))
            elif md.has_face_color():
                self._colors.set_data(md.face_colors(indexed='faces'))
        
        # Position input handling
        self._program.vert['position'] = vec3to4(self._vertices)
        
        # Color input handling
        if not md.has_vertex_color() and not md.has_face_color():
            # assign uniform to color varying
            color = self._color
        else:
            # assign attribute to color varying
            color = self._colors
        self._program.vert[self._color_var] = color
            
        # Shading
        if self.shading is None:
            self._program.frag['color'] = self._color_var
        else:
            phong = Function(phong_template)
            
            # Normal data comes via vertex shader
            self._program.vert[self._normal_var] = self._normals
            phong['normal'] = self._normal_var
            
            # Additional phong proprties
            phong['light_dir'] = (1.0, 1.0, 1.0)
            phong['light_color'] = (1.0, 1.0, 1.0, 1.0)
            phong['ambient'] = (0.3, 0.3, 0.3, 1.0)
            
            self._program.frag['color'] = phong(self._color_var)
    
    @property
    def shading(self):
        """ The shading method used.
        """
        return self._shading
    
    @shading.setter
    def shading(self, value):
        assert value in (None, 'flat', 'smooth')
        self._shading = value
    
    def draw(self, event):
        gloo.set_state('translucent', depth_test=True, cull_face='front_and_back')
        if self._data_changed:
            self._update_data()
        
        self._program.vert['transform'] = event.render_transform.shader_map()
        
        # Draw
        if self._indexed:
            self._program.draw('triangles', self._faces)
        else:
            self._program.draw('triangles')
