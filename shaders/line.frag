in vec2 vTexCoord;                
        
uniform sampler2D Sampler;       

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

void main()
{
    vec3 diffuse = texture(Sampler, vTexCoord.st).rgb;
    float alpha = texture(Sampler, vTexCoord.st).a;              
    int thickness = 1;

    mat3 I;
    for (int i=0; i<3; i++) {
        for (int j=0; j<3; j++) {
            vec4 sample  = texelFetch(Sampler, ivec2(gl_FragCoord) + ivec2(i-1,j-1)*thickness, 0 ).rgba;
            if (sample.a == 0) {
                I[i][j] = diffuse.b;
            } 
            else {
            I[i][j] = sample.b;
            }
            //I[i][j] = sample.b;
    }
    
}

float gx = dot(sx[0], I[0]) + dot(sx[1], I[1]) + dot(sx[2], I[2]); 
float gy = dot(sy[0], I[0]) + dot(sy[1], I[1]) + dot(sy[2], I[2]);



float g = sqrt(pow(gx, 2.0)+pow(gy, 2.0));

// Try different values and see what happens
g = smoothstep(0.1, 0.4, g);

gl_FragColor = vec4(diffuse.r, diffuse.g, g, alpha);

} 