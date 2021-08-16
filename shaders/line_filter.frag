in vec2 vTexCoord;
uniform sampler2D Sampler;
uniform int value;

void main()    
{
    vec4 color = texture(Sampler, vTexCoord).rgba;
    float b = color.b;
    if (b >0){
        b *=value*value;
    }
    else {
        b = 0;
    }

    gl_FragColor = vec4(color.r, color.g, b, color.a);
}