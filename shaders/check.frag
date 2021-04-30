in vec2 vTexCoord;
uniform sampler2D Sampler;
uniform vec2 offset;
uniform int iteration;

void main()    
{   
    int step = int(iteration/10);
    float g = texture(Sampler, vTexCoord).g;

    for (int i = 1; i < step; i++) {
        float next = texture(Sampler, vTexCoord + (offset/step) * i).g;        
        g = max(g, next);

    }
    
    gl_FragColor = vec4(1.0, g*10, 1.0, 1.0);
}