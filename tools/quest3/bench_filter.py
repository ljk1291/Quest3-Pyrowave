"""Opt-in backdrop cubic sampler. CPU counterpart: OpenCV INTER_CUBIC, A=-.75.

Uses the existing explicit rounded area mips and code-value RGBA8 targets.
GL parity is covered structurally with mocks, not hardware-validated.
"""
VERTEX = '''#version 130
void main() {
    gl_Position = ftransform();
    gl_TexCoord[0] = gl_MultiTexCoord0;
}
'''
FRAGMENT = '''#version 130
uniform sampler2D image;
uniform int lastLevel;
float cubic(float x) {
    x = abs(x);
    if (x <= 1.0) return (1.25*x-2.25)*x*x+1.0;
    if (x < 2.0) return ((-0.75*x+3.75)*x-6.0)*x+3.0;
    return 0.0;
}
vec3 sampleLevel(vec2 uv, int level) {
    ivec2 dimensions = textureSize(image, level);
    vec2 p = uv*vec2(dimensions)-0.5;
    ivec2 base = ivec2(floor(p));
    vec2 fraction = p-vec2(base);
    vec3 sum = vec3(0.0);
    for (int y=-1; y<=2; ++y)
        for (int x=-1; x<=2; ++x) {
            ivec2 pixel = clamp(base+ivec2(x,y), ivec2(0), dimensions-ivec2(1));
            sum += texelFetch(image, pixel, level).rgb * cubic(float(x)-fraction.x) * cubic(float(y)-fraction.y);
        }
    return sum;
}
void main() {
    vec2 uv = gl_TexCoord[0].xy;
    vec2 p = uv*vec2(textureSize(image, 0));
    float lod = clamp(log2(max(max(length(dFdx(p)), length(dFdy(p))), 1.0)), 0.0, float(lastLevel));
    int low = int(floor(lod));
    vec3 value = mix(sampleLevel(uv, low), sampleLevel(uv, min(low+1,lastLevel)), fract(lod));
    gl_FragColor = vec4(value, 1.0);
}
'''


def program(GL, levels):
    shaders = []
    handle = GL.glCreateProgram()
    try:
        for kind, source in ((GL.GL_VERTEX_SHADER, VERTEX), (GL.GL_FRAGMENT_SHADER, FRAGMENT)):
            shader = GL.glCreateShader(kind); shaders.append(shader)
            GL.glShaderSource(shader, source)
            GL.glCompileShader(shader)
            if not GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS):
                raise RuntimeError(f'Bench cubic shader compile failed: {GL.glGetShaderInfoLog(shader)}')
            GL.glAttachShader(handle, shader)
        GL.glLinkProgram(handle)
        if not GL.glGetProgramiv(handle, GL.GL_LINK_STATUS):
            raise RuntimeError(f'Bench cubic shader link failed: {GL.glGetProgramInfoLog(handle)}')
        GL.glUseProgram(handle)
        GL.glUniform1i(GL.glGetUniformLocation(handle, 'image'), 0)
        GL.glUniform1i(GL.glGetUniformLocation(handle, 'lastLevel'), levels-1)
        GL.glUseProgram(0)
        return handle
    except Exception:
        GL.glDeleteProgram(handle)
        raise
    finally:
        for shader in shaders:
            GL.glDeleteShader(shader)
