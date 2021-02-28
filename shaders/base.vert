uniform mat4 modelMatrix;
uniform mat4 viewProjectionMatrix;

in vec3 pos;
in vec4 color;

out vec4 finalColor;

void main()
{            
    gl_Position = viewProjectionMatrix * modelMatrix * vec4(pos, 1.0f);
    finalColor = color;
    //float depth = (gl_Position.z*gl_Position.z*gl_Position.z)/1000;
    //finalColor = vec4(color.r, color.g, depth, color.a);
}