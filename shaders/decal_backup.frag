in vec2 vTexCoord;

uniform sampler2D Sampler;
uniform float angle;
uniform float dim_x;
uniform float dim_y;
uniform int inverse;



float random (vec2 st) {
        return fract(sin(dot(st.xy, vec2(12.9898,78.233))) * 43758.5453123);
    }
    
void main()    
{
    vec2 st = gl_FragCoord.xy;
    float rand = random(st);
        

    vec4 colorBase = texture(Sampler, vTexCoord).rgba;
    float dist = colorBase.g;
            
    
    int end = 0;        
    float value = 0.0;
    int iteration = 200 + inverse * 200;
    iteration = 400;


    for (int i = 1; i < iteration; i++) {        
        float rand = (random(vTexCoord) * 2 - 1) / 2;
        float rand_angle = angle + (rand*0.8);
                
        vec2 direction = vec2(cos(rand_angle)/dim_x, sin(rand_angle)/dim_y);
        
        float a = texture(Sampler, vTexCoord + direction * dist * i).a;
        
        if (a == 0 &&  end == 0) {
            value = 1.0 - (float(i)/iteration);
            end = 1;              
        }    
    }   
    //value = abs(inverse - value);
    //value += inverse/100000;
    if (inverse == 1) {
        value = colorBase.r * value + 0.5; // Trouver la formule du gamma
    }
    else {
        value = colorBase.r - value;
    }
    

                
    gl_FragColor = vec4(value, colorBase.g, colorBase.b, colorBase.a);


}