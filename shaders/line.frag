in vec2 vTexCoord;                
        
uniform sampler2D Sampler;
uniform sampler2D Depth_buffer;
uniform int line_scale;
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

    float alpha = texture(Depth_buffer, vTexCoord.st).a;              
    // Line from depth
    mat3 I;
    for (int i=0; i<3; i++) {
        for (int j=0; j<3; j++) {
            vec4 sample  = texelFetch(Depth_buffer, ivec2(gl_FragCoord) + ivec2(i-1,j-1)*line_scale*1, 0 ).rgba;          
            float sample_depth = convert32(sample.rgb);
            
            if (sample.a == 0.0){
                if (border == 0){
                    I[i][j] = center_depth;
                }
                else {
                    I[i][j] = sample_depth;
                }
            }
            else if (sample_depth < center_depth){
                I[i][j] = center_depth;
            }            
            else {
                I[i][j] = sample_depth;
            } 
        }    
    }
    float dx = dot(sx[0], I[0]) + dot(sx[1], I[1]) + dot(sx[2], I[2]); 
    float dy = dot(sy[0], I[0]) + dot(sy[1], I[1]) + dot(sy[2], I[2]);
    float d = sqrt(pow(dx, 2.0)+pow(dy, 2.0));

    // Line from normals
    mat3 J;
    for (int i=0; i<3; i++) {
        for (int j=0; j<3; j++) {
            vec4 sample  = texelFetch(Sampler, ivec2(gl_FragCoord) + ivec2(i-1,j-1)*line_scale*1, 0 ).rgba;          
            float sample_normal = sample.b;
            
            if (sample.a == 0.0){
                J[i][j] = center_normal;
            }
            else if (sample_normal < center_normal){
                J[i][j] = center_normal;
            }            
            else {
                J[i][j] = sample_normal;
            } 
        }    
    }
    float nx = dot(sx[0], J[0]) + dot(sx[1], J[1]) + dot(sx[2], J[2]); 
    float ny = dot(sy[0], J[0]) + dot(sy[1], J[1]) + dot(sy[2], J[2]);
    float n = sqrt(pow(nx, 2.0)+pow(ny, 2.0));


    // Try different values and see what happens
    //g = smoothstep(0.2, 0.3, g*2000); // DEFAULT 0.1, 0.4
    n = smoothstep(0.0, 1.0, n); // DEFAULT 0.1, 0.4

    d *= 500 * max((1-center_depth*30), 0.05);
    d *= n*5;
    

    gl_FragColor = vec4(base_center.r, base_center.g, d, alpha);

} 