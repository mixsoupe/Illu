in vec2 vTexCoord;
uniform sampler2D Sampler;

uniform float Beta;
uniform vec2 Offset;
uniform int factor;


void main()    
{        
    
    vec2 east_uv = vTexCoord + Offset;
    vec2 west_uv = vTexCoord - Offset;
    
    /* Out of view samples. */
    if (any(lessThan(east_uv, vec2(0.0))) || any(greaterThan(east_uv, vec2(1.0)))) {
        east_uv = vTexCoord;
    }
    
    if (any(lessThan(west_uv, vec2(0.0))) || any(greaterThan(west_uv, vec2(1.0)))) {
        west_uv = vTexCoord;
    }
    vec4 base = texture(Sampler, vTexCoord).rgba;
    
    float new_beta = Beta;

    if (factor == 1){
        float influence = 12;

        new_beta = Beta * (influence - base.g*(influence-1));

        if (base.g < 0.01){
            new_beta = 1;
        }
    }

    /* SDF */
    float A = texture(Sampler, vTexCoord).r;                    
    float e = new_beta + texture(Sampler, east_uv).r;
    float w = new_beta + texture(Sampler, west_uv).r;
    float B = min(min(A, e), w);  

    gl_FragColor = vec4(B, base.g, base.b, base.a);

}