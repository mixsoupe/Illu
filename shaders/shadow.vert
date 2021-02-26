in vec3 pos;
in vec4 color;

out vec4 ShadowCoord;
out vec4 finalColor;

uniform mat4 depthBiasMVP;
uniform mat4 MVP;

void main()
{            
    gl_Position = MVP * vec4(pos, 1.0f);
    ShadowCoord = depthBiasMVP * vec4(pos, 1.0f);
    finalColor = color;
}