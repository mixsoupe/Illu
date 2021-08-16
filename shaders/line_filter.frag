in vec2 vTexCoord;
uniform sampler2D Sampler;
uniform int value;

void main()    
{
    vec4 color = texture(Sampler, vTexCoord).rgba;
    float b = color.b;
    if (b >0.1){
        b *=value*1.5;
    }
    else {
        b = 0;
    }

    gl_FragColor = vec4(color.r, color.g, b, color.a);
}