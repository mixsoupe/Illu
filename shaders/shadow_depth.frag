void main()        
{
    float value = gl_FragCoord.z;

    gl_FragColor = vec4(value, value, value, 1.0);
}