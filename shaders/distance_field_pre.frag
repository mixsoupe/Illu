in vec2 vTexCoord;
uniform sampler2D Sampler;

void main()  
{    
    float alpha = texture(Sampler, vTexCoord).a;            
    gl_FragColor = vec4(0.0, 0.0, alpha, alpha);
    
}