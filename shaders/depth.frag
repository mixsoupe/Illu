//in vec4 finalColor;

void main()        
{
    float depth = (gl_FragCoord.z/gl_FragCoord.w);

    float depth_A = floor(depth)/255;    
    float depth_B = floor(fract(depth)*255)/255;
    float depth_C = fract(fract(depth)*255);
    
    gl_FragColor = vec4(depth_A, depth_B, depth_C, 1.0);
}