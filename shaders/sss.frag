in vec2 vTexCoord;

uniform sampler2D Sampler;
uniform vec2 step;
uniform int mask;
uniform int simple;
uniform int channel;

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
    vec2 colorM = texture(Sampler, vTexCoord).rg;
    float depthM = texture(Sampler, vTexCoord).b + texture(Sampler, vTexCoord).a;

    //float depthM = (gl_FragCoord.z / gl_FragCoord.w);
    
    // Accumulate center sample, multiplying it with its gaussian weight
    vec2 colorBlurred = colorM;
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
        vec2 color = texture(Sampler, offset).rg;
        float depth = texture(Sampler, offset).b + texture(Sampler, offset).a;
        float intensity = texture(Sampler, offset).g;
        
        float correction = 12;

        if (mask == 1){
            //Sur le contour, le flou ne tient pas compte de la profondeur
            correction *= (1 + intensity - texture(Sampler, offset).a);
        }

        if (simple == 1){
            // simple blur. FIX Optimiser en mettant la condition en amont
            correction = 1; 
        }


        // If the difference in depth is huge, we lerp color back to "colorM":
        float s = min(correction * abs(depthM - depth), 1.0);        

        color = mix(color, colorM, s);

        // Accumulate:
        colorBlurred += w[i] * color;
    }
    
    if (channel == 0){
    gl_FragColor = vec4(colorBlurred.x, colorBase.g, colorBase.b, colorBase.a);
    }
    if (channel == 1){
    gl_FragColor = vec4(colorBase.r, colorBlurred.y, colorBase.b, colorBase.a);
    }
}