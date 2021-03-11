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
    
    vec4 this_pixel = texture(Sampler, vTexCoord).rgba;
    vec4 east_pixel = texture(Sampler, east_uv).rgba;
    vec4 west_pixel = texture(Sampler, west_uv).rgba;  

    /* Remap to 8bits */
    float this_pixel_remap = this_pixel.b + this_pixel.a/255;
    float east_pixel_remap = east_pixel.b + east_pixel.a/255;
    float west_pixel_remap = west_pixel.b + west_pixel.a/255;

    /* SDF */
    float A = this_pixel_remap;                    
    float e = Beta + east_pixel_remap;
    float w = Beta + west_pixel_remap;
    float B = min(min(A, e), w);    

    /* Remap to 16bits */
    float B_int = floor(B*255);
    float B_decimale = B*255 - B_int;        
    B_int /= 255; 
    
    gl_FragColor = vec4(this_pixel.r, this_pixel.g, B_int, B_decimale);

}