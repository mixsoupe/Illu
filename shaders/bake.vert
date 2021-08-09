uniform mat4 ModelViewProjectionMatrix;

uniform mat4 view_matrix;
uniform mat4 projection_matrix;

in vec3 texCoord;
in vec2 pos;

out vec2 vTexCoord;

void main()
{
    gl_Position = ModelViewProjectionMatrix * vec4(pos.xy, 0.0f, 1.0f);
    
    vec4 coord = projection_matrix * view_matrix * vec4(texCoord, 1.0f);
    vTexCoord = (coord.xy/coord.w + 1)/2;
}