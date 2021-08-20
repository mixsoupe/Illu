in vec2 vTexCoord;
uniform sampler2D Sampler;
uniform sampler2D Noise;
uniform float amplitude;

void main()    
{  
    vec4 color = texture(Sampler, vTexCoord);
    float noise_x = texture(Noise, vTexCoord).r;    
    
    float offset_x = mix(-amplitude, amplitude, noise_x);
    float offset_y = mix(-amplitude, amplitude, noise_x);

    vec2 offset = vec2(offset_x, offset_y);

    vec4 final_color = texture(Sampler, vTexCoord + offset);

    gl_FragColor = final_color;

    


}