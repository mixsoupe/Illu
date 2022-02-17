in vec2 vTexCoord;                
        
uniform sampler2D Sampler;
uniform sampler2D Depth_buffer;
uniform float line_detection;
uniform float depth_precision;
uniform int border;         

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
    vec4 base_center = texture(Sampler, vTexCoord.st).rgba;
    float center_normal = base_center.b;

    vec4 center = texture(Depth_buffer, vTexCoord.st).rgba;
    float center_depth = convert32(center.rgb);

    float alpha = texture(Sampler, vTexCoord.st).a;              
    // Line from depth
    mat3 I;
    for (int i=0; i<3; i++) {
        for (int j=0; j<3; j++) {
            vec4 sample  = texelFetch(Depth_buffer, ivec2(gl_FragCoord) + ivec2(i-1,j-1), 0 ).rgba;
            vec4 sample2  = texelFetch(Depth_buffer, ivec2(gl_FragCoord) + ivec2(i-1,j-1)*10, 0 ).rgba;         
            float sample_depth = convert32(sample.rgb);
            float delta_z = (sample_depth - center_depth)*line_detection;
            if (sample2.a == 0){
                if (border == 0){
                    I[i][j] = center_depth;
                }
                else {
                    I[i][j] = sample_depth;
                }
            }
            else if (center.a == 0){
                    I[i][j] = center_depth;
            }
            else if (delta_z > 0.00004){ //0.00004
                I[i][j] = sample_depth;
            }            
            else {
                I[i][j] = center_depth;
            } 
        }    
    }
    float dx = dot(sx[0], I[0]) + dot(sx[1], I[1]) + dot(sx[2], I[2]); 
    float dy = dot(sy[0], I[0]) + dot(sy[1], I[1]) + dot(sy[2], I[2]);
    float d = sqrt(pow(dx, 2.0)+pow(dy, 2.0));

    // // Line from normals
    // mat3 J;
    // for (int i=0; i<3; i++) {
    //     for (int j=0; j<3; j++) {
    //         vec4 sample  = texelFetch(Sampler, ivec2(gl_FragCoord) + ivec2(i-1,j-1), 0 ).rgba;         
    //         float sample_normal = sample.b;
            
    //         if (sample.a == 0.0){
    //             J[i][j] = center_normal;
    //         }
    //         else if (sample_normal < center_normal){
    //             J[i][j] = center_normal;
    //         }            
    //         else {
    //             J[i][j] = sample_normal;
    //         } 
    //     }    
    // }
    // float nx = dot(sx[0], J[0]) + dot(sx[1], J[1]) + dot(sx[2], J[2]); 
    // float ny = dot(sy[0], J[0]) + dot(sy[1], J[1]) + dot(sy[2], J[2]);
    // float n = sqrt(pow(nx, 2.0)+pow(ny, 2.0));
    //n = smoothstep(0.0, 1.0, n); // DEFAULT 0.1, 0.4

    d *= max((1-center_depth)/depth_precision, 0.05) * line_detection * 100 ;
    d = smoothstep(0.3, 1.0, d); // DEFAULT 0.1, 0.4
    


    // d *= 0.000000000001;
    // d += n;
    

    gl_FragColor = vec4(base_center.r, base_center.g, d, alpha);

} 