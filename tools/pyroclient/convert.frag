#version 450
layout(set = 0, binding = 0) uniform sampler2D planeY;
layout(set = 0, binding = 1) uniform sampler2D planeCb;
layout(set = 0, binding = 2) uniform sampler2D planeCr;
layout(push_constant) uniform Params { int limitedRange; } params;
layout(location = 0) out vec4 color;
// JMS1717 haar32 / Decoder V2 packed output layouts.
layout(constant_id = 0) const bool PACKED_LUMA = false;
layout(constant_id = 1) const bool DUAL_CHROMA = false;

void main() {
    ivec2 coord = ivec2(gl_FragCoord.xy);
    vec2 uv = (vec2(coord) + 0.5) / vec2(textureSize(planeY, 0) * (PACKED_LUMA ? 2 : 1));
    float Y = PACKED_LUMA ? texelFetch(planeY, coord >> 1, 0)[(coord.x & 1) | ((coord.y & 1) << 1)]
                          : texelFetch(planeY, coord, 0).r;
    float Cb = textureLod(planeCb, uv, 0.0).r;
    float Cr = DUAL_CHROMA ? textureLod(planeCb, uv, 0.0).g : textureLod(planeCr, uv, 0.0).r;
    if (params.limitedRange != 0) {
        Y = (Y - 16.0 / 255.0) * (255.0 / 219.0);
        Cb = (Cb - 128.0 / 255.0) * (255.0 / 224.0);
        Cr = (Cr - 128.0 / 255.0) * (255.0 / 224.0);
    } else { Cb -= 0.5; Cr -= 0.5; }
    color = vec4(clamp(vec3(Y + 1.5748 * Cr, Y - 0.1873 * Cb - 0.4681 * Cr,
                            Y + 1.8556 * Cb), 0.0, 1.0), 1.0);
}
