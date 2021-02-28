in vec2 vTexCoord;
uniform sampler2D Sampler;

void main()    
{
    
    
    vec4 color = texture(Sampler, vTexCoord).rgba;
    
    float value = color.b * (1-color.g)*20;//ajouter de la dynamique
    gl_FragColor = vec4(color.r, color.g, value, 1.0);

}