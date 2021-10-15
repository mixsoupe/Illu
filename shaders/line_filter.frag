in vec2 vTexCoord;
uniform sampler2D Sampler;
uniform float value;

void main()    
{
    vec4 color = texture(Sampler, vTexCoord).rgba;
    float b = color.b;
    if (b > 0.5/value){
        b = b*(value);
        //b=1.0;
    }
    else {
        b = 0;
    }

    gl_FragColor = vec4(color.r, color.g, b, color.a);
}