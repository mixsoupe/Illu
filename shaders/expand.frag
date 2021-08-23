in vec2 vTexCoord;

uniform sampler2D Sampler;
uniform vec2 step;
uniform int expand;
//uniform int normal;

void main()    
{   
    
    vec4 color = texture(Sampler, vTexCoord).rgba;

    vec4 sampleA = texture(Sampler, vTexCoord + step).rgba;
    vec4 sampleB = texture(Sampler, vTexCoord - step).rgba; 

    if (expand == 1){
        if (color.a < 0.1){
            color = sampleA;
        }
        if (color.a < 0.1){
            color = sampleB;
        }
    }
    else{
        if (sampleA.a < 0.1){
            color.a *= 0;
        }
        if (sampleB.a < 0.1){
            color.a *= 0;
        }
    }


    gl_FragColor = color;


}