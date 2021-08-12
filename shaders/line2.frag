in vec2 vTexCoord;                
        
uniform sampler2D Sampler;
uniform sampler2D Depth_buffer;
uniform int line_scale;          

mat3 sx = mat3( 
    1.0, 2.0, 1.0, 
    0.0, 0.0, 0.0, 
    -1.0, -2.0, -1.0 
);
mat3 sy = mat3( 
    1.0, 0.0, -1.0, 
    2.0, 0.0, -2.0, 
    1.0, 0.0, -1.0 
);


float convert32 (vec3 input) {
    return input.x+ (input.y + input.z/255)/255;
}


void main()
{
    vec4 diffuse = texture(Sampler, vTexCoord.st).rgba;

    vec3 center = texture(Depth_buffer, vTexCoord.st).rgb;
    float center_depth = convert32(center);

    float alpha = texture(Depth_buffer, vTexCoord.st).a;              

    mat3 I;
    for (int i=0; i<3; i++) {
        for (int j=0; j<3; j++) {
            vec3 sample  = texelFetch(Depth_buffer, ivec2(gl_FragCoord) + ivec2(i-1,j-1)*line_scale*1, 0 ).rgb;
            float sample_depth = convert32(sample);

            if (sample.g < center_depth){
                I[i][j] = center_depth;
            }            
            else {
                I[i][j] = sample_depth;
            }
            I[i][j] = sample_depth;
    }    
}

float gx = dot(sx[0], I[0]) + dot(sx[1], I[1]) + dot(sx[2], I[2]); 
float gy = dot(sy[0], I[0]) + dot(sy[1], I[1]) + dot(sy[2], I[2]);



float g = sqrt(pow(gx, 2.0)+pow(gy, 2.0));

// Try different values and see what happens
//g = smoothstep(0.1, 0.4, g*255); // DEFAULT 0.1, 0.4
g = g*2055;

gl_FragColor = vec4(diffuse.r, diffuse.g, g, alpha);

} 