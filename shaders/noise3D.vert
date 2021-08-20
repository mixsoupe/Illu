uniform mat4 modelMatrix;
uniform mat4 viewProjectionMatrix;

in vec3 pos;
in vec4 color;
in vec3 orco;

out vec4 finalColor;
out vec3 orcofrag;

void main()
{            
    gl_Position = viewProjectionMatrix * modelMatrix * vec4(pos, 1.0f);
    finalColor = color;
    orcofrag = orco;
}