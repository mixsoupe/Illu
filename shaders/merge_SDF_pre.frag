in vec2 vTexCoord;
uniform sampler2D Sampler0;
uniform sampler2D Sampler1;

void main()    
{  
    vec4 color0 = texture(Sampler0, vTexCoord);
    vec4 color1 = texture(Sampler1, vTexCoord);

    gl_FragColor = vec4(color0.r, color0.g, color0.b, color1.a);
}