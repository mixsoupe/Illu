//in vec4 finalColor;

void main()        
{
    float depth = (gl_FragCoord.z/gl_FragCoord.w)/255;
    
    gl_FragColor = vec4(depth, 1.0, 1.0, 1.0);
}