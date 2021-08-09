in vec2 vTexCoord;
uniform sampler2D Sampler;

void main()    
{
    vec2 color = texture(Sampler, vTexCoord).ba;
    float color8bits = color.x + color.y/255;
    gl_FragColor = vec4(0.0, color8bits, 0.0, color8bits);
}