in vec2 vTexCoord;

uniform sampler2D Sampler;
uniform float scale;

void main()    
{  
    vec4 color = texture(Sampler, ((vTexCoord-0.5)*scale)+0.5);
    gl_FragColor = color;
}