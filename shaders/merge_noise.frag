in vec2 vTexCoord;
uniform sampler2D Sampler0;
uniform sampler2D Sampler1;

void main()    
{  
    vec4 color0 = texture(Sampler0, vTexCoord);
    vec4 color1 = texture(Sampler1, vTexCoord);


    float mergeB = (color1.b * 1.2 * color1.a + color1.a)/2;

    // mergeB *= 0.0000001; //debug
    // mergeB += color0.b; //debug


    gl_FragColor = vec4(color0.r, color0.g, mergeB, color0.a);
    //gl_FragColor = vec4(color0.r, color0.g, merge, color0.a); //Le noise est désactivé dans le shading et dans le distance field
}