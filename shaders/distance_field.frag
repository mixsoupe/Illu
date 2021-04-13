in vec2 vTexCoord;
uniform sampler2D Sampler;

uniform float Beta;
uniform vec2 Offset;


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
    /* SDF */
    float A = texture(Sampler, vTexCoord).r;                    
    float e = Beta + texture(Sampler, east_uv).r;
    float w = Beta + texture(Sampler, west_uv).r;
    float B = min(min(A, e), w);  

    gl_FragColor = vec4(B, base.g, base.b, base.a);

}