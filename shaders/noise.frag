in vec2 vTexCoord;
uniform sampler2D Sampler;
uniform sampler2D Noise;
uniform float amplitude;

void main()    
{  
    vec4 color = texture(Sampler, vTexCoord);
    vec2 noise = texture(Noise, vTexCoord).xy;    
    
    float offset_x = mix(-amplitude, amplitude, noise.x+0.25);
    float offset_y = mix(-amplitude, amplitude, noise.y+0.25);

    vec2 offset = vec2(offset_x, offset_y);
    offset *= color.g;

    vec4 final_color = texture(Sampler, vTexCoord + offset);

    gl_FragColor = final_color;   


}