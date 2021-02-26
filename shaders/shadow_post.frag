in vec2 vTexCoord;
uniform sampler2D Sampler0;
uniform sampler2D Sampler1;
uniform int Iteration;

void main()    
{   
    vec4 color0 = texture(Sampler0, vTexCoord).rgba;
    vec4 color1 = texture(Sampler1, vTexCoord).rgba;
    vec4 color_accum = color0 + color1/Iteration;
    
    gl_FragColor = vec4(color_accum.r, color_accum.g, color1.b, color1.a);
}