in vec2 vTexCoord;
uniform sampler2D Sampler;

void main()    
{
    
    
    vec4 color = texture(Sampler, vTexCoord).rgba;
    
    gl_FragColor = vec4(color.r, color.b, color.b, color.a);

}