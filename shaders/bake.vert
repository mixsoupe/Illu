uniform mat4 ModelViewProjectionMatrix;

in vec2 texCoord;
in vec2 pos;

out vec2 vTexCoord;

void main()
{
    gl_Position = ModelViewProjectionMatrix * vec4(pos.xy, 0.0f, 1.0f);
    gl_Position.z = 1.0;
    vTexCoord = texCoord;
}