in vec2 vTexCoord;

uniform sampler2D Sampler;
uniform sampler2D Depth;
uniform float scale;
uniform float depth_precision;
uniform float angle;
uniform float dim_x;
uniform float dim_y;
uniform int inverse;

//32bits converion
float convert32 (vec3 input) {
    return (input.x+ (input.y + input.z/255)/255)*255;
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
        
        float sample_a = texture(Sampler, vTexCoord + direction * scale * i).a;

        float current_z = convert32(texture(Depth, vTexCoord).rgb);

        float sample_z = convert32(texture(Depth, vTexCoord + direction * scale * i).rgb);
        
        float delta_z = sample_z - current_z;

        if (sample_a == 0 &&  end == 0) {
            value = 1.0 - (float(i)/iteration);
            end = 1;              
        }
        //normaliser en fonction de la distance de la caméra
        if (delta_z > depth_precision &&  end == 0) {
            value = 1.0 - (float(i)/iteration);
            end = 1;              
        }

    }   
    //value = abs(inverse - value);
    //value += inverse/100000;
    if (inverse == 1) {
        value = colorBase.r * (value + 1)/2;
    }
    else {
        value = colorBase.r - value/2;
    }
                
    gl_FragColor = vec4(value, colorBase.g, colorBase.b, colorBase.a);

}