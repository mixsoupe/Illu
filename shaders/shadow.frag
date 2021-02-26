in vec4 ShadowCoord;
in vec4 finalColor;

uniform sampler2D Sampler;
uniform float Scale;

void main()        
{
    float bias = 0.005;
    
    float shadow = 1.0;
    //Choisir le sampler en fonction du z
    float light_depthmap = texture(Sampler, ShadowCoord.xy).r + 1 - texture(Sampler, ShadowCoord.xy).a;
    float light_z = ShadowCoord.z-bias;

    float distance = 0.0;

    if ( light_depthmap < light_z){
        distance =  light_z - light_depthmap;
        distance *= Scale/5;
        //distance *= distance;
        shadow = 0.0;
    }

    gl_FragColor = vec4(shadow, distance, finalColor.b, finalColor.a);

}
