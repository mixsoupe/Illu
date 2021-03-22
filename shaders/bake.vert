uniform mat4 ModelViewProjectionMatrix;
uniform mat4 CameraMatrix;

in vec3 texCoord;
in vec2 pos;

out vec2 vTexCoord;

void main()
{
    gl_Position = ModelViewProjectionMatrix * vec4(pos.xy, 0.0f, 1.0f);
    //gl_Position.z = 1.0;
    vec4 viewCoord = CameraMatrix * vec4(texCoord, 1.0f);
    vTexCoord = viewCoord.xy;
}