in vec2 vTexCoord;

uniform sampler2D Sampler;
uniform vec2 step;
uniform int expand;
uniform vec3 channel;
//uniform int normal;

void main()    
{   
    
    vec4 colorBase = texture(Sampler, vTexCoord).rgba;
    vec4 colorExpand = colorBase;

    vec4 sampleA = texture(Sampler, vTexCoord + step).rgba;
    vec4 sampleB = texture(Sampler, vTexCoord - step).rgba; 

    if (expand == 1){
        if (colorExpand.a < 0.1){
            colorExpand = sampleA;
        }
        if (colorExpand.a < 0.1){
            colorExpand = sampleB;
        }
    }
    else{
        if (sampleA.a < 0.1){
            colorExpand.a *= 0;
            colorExpand.b *= 0;
        }
        if (sampleB.a < 0.1){
            colorExpand.a *= 0;
            colorExpand.b *= 0;
        }
    }

    float colorR = mix(colorBase.r, colorExpand.r, channel.r);
    float colorG = mix(colorBase.g, colorExpand.g, channel.g);
    float colorB = mix(colorBase.b, colorExpand.b, channel.b);

    gl_FragColor = vec4(colorR, colorG, colorB, colorExpand.a);



}