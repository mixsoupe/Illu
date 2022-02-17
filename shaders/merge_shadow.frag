in vec2 vTexCoord;
uniform sampler2D Sampler0;
uniform sampler2D Sampler1;
uniform float Variable;

void main()    
{  
    vec4 color0 = texture(Sampler0, vTexCoord);
    vec4 color1 = texture(Sampler1, vTexCoord);

    float r = color0.r * min((color1.r + 1 - Variable), 1.0);

    gl_FragColor = vec4(r, color0.g, color0.b, color0.a);
}