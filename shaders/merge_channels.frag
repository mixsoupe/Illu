in vec2 vTexCoord;
uniform sampler2D Sampler0;
uniform sampler2D Sampler1;
uniform vec4 channel;


void main()    
{  
    vec4 color0 = texture(Sampler0, vTexCoord);
    vec4 color1 = texture(Sampler1, vTexCoord);

    float colorR = mix(color0.r, color1.r, channel.r);
    float colorG = mix(color0.g, color1.g, channel.g);
    float colorB = mix(color0.b, color1.b, channel.b);
    float colorA = mix(color0.a, color1.a, channel.a);

    gl_FragColor = vec4(colorR, colorG, colorB, colorA);
}