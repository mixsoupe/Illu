in vec2 vTexCoord;

uniform sampler2D Sampler;
uniform sampler2D Depth;
uniform float scale;
uniform float smoothness;
uniform float angle;
uniform float dim_x;
uniform float dim_y;
uniform int inverse;

//32bits converion
float convert32 (vec3 input) {
    return (input.x+ (input.y + input.z/255)/255)*100;
}   

float random (vec2 st) {
        return fract(sin(dot(st.xy, vec2(12.9898,78.233))) * 43758.5453123);
    }
    
void main()    
{
    vec2 st = gl_FragCoord.xy;
    float rand = random(st);        

    vec4 colorBase = texture(Sampler, vTexCoord).rgba;       
    
    int end = 0;        
    float value = 0.0;
    int iteration = 100;

    for (int i = 1; i < iteration; i++) {        
        float rand = (random(vTexCoord) * 2 - 1) / 2;
        float rand_angle = angle + (rand*1.0);
                
        vec2 direction = vec2(cos(rand_angle)/dim_x, sin(rand_angle)/dim_y);
        float current_z = convert32(texture(Depth, vTexCoord).rgb);
        
        
        float distance = scale * max((1-current_z/10), 0.1);

        float sample_a = texture(Sampler, vTexCoord + direction * distance * i).a;
        float sample_z = convert32(texture(Depth, vTexCoord + direction * distance * i).rgb);
        
        float delta_z = sample_z - current_z;

        if (sample_a == 0 &&  end == 0) {
            value = 1.0 - (float(i)/iteration);
            end = 1;              
        }
        //normaliser en fonction de la distance de la caméra
        if (delta_z > smoothness &&  end == 0) {
            value = 1.0 - (float(i)/iteration);
            end = 1;              
        }

    }   

    if (inverse == 1) {
        value = colorBase.r * (value + 1)/2;
    }
    else {
        value = colorBase.r - value/2;
    }
                
    gl_FragColor = vec4(value, colorBase.g, colorBase.b, colorBase.a);

}