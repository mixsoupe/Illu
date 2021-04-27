in vec2 vTexCoord;
uniform sampler2D Sampler;

void main()    
{   
    vec4 color = textureLod(Sampler, vTexCoord, 0).rgba;
    
    gl_FragColor = color;
}