in vec3 pos;

uniform mat4 depthMVP;

void main()
{            
    gl_Position = depthMVP * vec4(pos, 1.0f);
}