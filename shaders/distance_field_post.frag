in vec2 vTexCoord;
uniform sampler2D Sampler;

void main()    
{
    
    
    vec4 color = texture(Sampler, vTexCoord).rgba;
    
    //float value = color.b * (1-color.g);//ajouter de la dynamique
    float value = color.b;
    gl_FragColor = vec4(color.r, value, color.b, 1.0);

}