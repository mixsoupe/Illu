in vec2 vTexCoord;

uniform sampler2D Sampler;
uniform vec2 step;

void main()    
{   
    
    vec4 color = texture(Sampler, vTexCoord).rgba;

    vec4 sampleA = texture(Sampler, vTexCoord + step).rgba;
    vec4 sampleB = texture(Sampler, vTexCoord - step).rgba; 

    if (color.a < 0.1){
        color = sampleA;
    }
    if (color.a < 0.1){
        color = sampleB;
    }

    gl_FragColor = color;

}