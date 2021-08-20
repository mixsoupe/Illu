in vec2 vTexCoord;
uniform sampler2D Sampler;
uniform int value;

void main()    
{
    vec4 color = texture(Sampler, vTexCoord).rgba;
    gl_FragColor = vec4(color.a*value, color.g, color.b, color.a);
}