in vec2 vTexCoord;

uniform sampler2D Sampler;
uniform sampler2D Depth;
uniform vec2 step;
uniform float depth_precision;
uniform vec3 channel;

//32bits converion
float convert32 (vec3 input) {
    return (input.x+ (input.y + input.z/255)/255)*255;
}   

//generate noise
float random (vec2 st) {
        return fract(sin(dot(st.xy, vec2(12.9898,78.233))) * 43758.5453123);
}     
        
// Gaussian weights for the six samples around the current pixel    
float w[6] = float[]( 0.006,   0.061,   0.242,  0.242,  0.061, 0.006 );
float o[6] = float[](  -1.0, -0.6667, -0.3333, 0.3333, 0.6667,   1.0 );

    
void main()    
{
    //get random value
    vec2 st = gl_FragCoord.xy;
    float rand = random(st);
    
    // Fetch color and linear depth for current pixel
    vec4 colorBase = texture(Sampler, vTexCoord).rgba;    
    vec3 colorM = texture(Sampler, vTexCoord).rgb;
    float depthM = convert32(texture(Depth, vTexCoord).rgb); //+ texture(Sampler, vTexCoord).a;

    
    // Accumulate center sample, multiplying it with its gaussian weight
    vec3 colorBlurred = colorM;
    colorBlurred *= 0.382;
    
    // Calculate the step that we will use to fetch the surrounding pixels,
    // where "step" is:
    //     step = sssStrength * gaussianWidth * pixelSize * dir
    // The closer the pixel, the stronger the effect needs to be, hence
    // the factor 1.0 / depthM.        
    
    vec2 finalStep = texture(Sampler, vTexCoord).a * step; // TODO / depthM;

    // Accumulate the other samples:
    for (int i = 0; i < 6; i++) {
        // Fetch color and depth for current sample:
        vec2 offset = vTexCoord + o[i] * finalStep;
        vec3 color = texture(Sampler, offset).rgb;
        float depth = convert32(texture(Depth, offset).rgb);
        
        // If the difference in depth is huge, we lerp color back to "colorM":
        float s = min(depth_precision * abs(depthM - depth), 1.0);        

        color = mix(color, colorM, s);

        // Accumulate:
        colorBlurred += w[i] * color;
    }

    float colorR = mix(colorBase.r, colorBlurred.r, channel.r);
    float colorG = mix(colorBase.g, colorBlurred.g, channel.g);
    float colorB = mix(colorBase.b, colorBlurred.b, channel.b);

    gl_FragColor = vec4(colorR, colorG, colorB, colorBase.a);


}