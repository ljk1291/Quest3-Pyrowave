// Default-off selection for JMS1717's haar32 / CDF 5/3 Decoder V2 port.
#pragma once
#include <cstring>
#include <cstddef>

// Byte address of a decoded R8 sample in the library's scalar/quad/dual/present
// layouts. Used only after GPU readback, outside the timing interval.
inline size_t decoder_sample_offset(int plane, int x, int y, int frame_width, int stored_width,
                                    bool packed_luma, bool dual_chroma, bool present) {
    if (plane == 0 && packed_luma)
        return (size_t(y / 2) * stored_width + x / 2) * 4 + (x & 1) + 2 * (y & 1);
    if (present)
        return (size_t(y) * stored_width + frame_width / 2 + x) * 4 + plane - 1;
    if (dual_chroma && plane != 0)
        return (size_t(y) * stored_width + x) * 2 + plane - 1;
    return size_t(y) * stored_width + x;
}

inline int parse_decoder_mode(const char *value) {
    return value && value[0] >= '0' && value[0] <= '5' && !value[1] ? value[0] - '0' : 0;
}

inline int parse_packed_levels(const char *value) {
    return value && !std::strcmp(value, "2") ? 2 : 4;
}

struct DecoderModeChoice {
    int requested = 0;
    int active = 0;
    const char *reason = "disabled";
};

// The library validates precision, geometry and competing kernels. Only an accepted
// mode may determine the output allocation. A rejected setter leaves it unchanged.
template <typename Accept>
DecoderModeChoice choose_decoder_mode(const char *value, bool wavelet, bool fragment,
                                     bool full_range, Accept accept) {
    DecoderModeChoice choice;
    choice.requested = parse_decoder_mode(value);
    if (!choice.requested) return choice;
    if (!wavelet) { choice.reason = "wavelet"; return choice; }
    if (fragment) { choice.reason = "fragment"; return choice; }
    const int limit = !full_range && choice.requested == 5 ? 4 : choice.requested;
    for (int mode = limit; mode > 0; --mode) {
        if (accept(mode)) {
            choice.active = mode;
            choice.reason = mode == choice.requested ? "enabled" :
                            limit != choice.requested && mode == limit ? "limited_range" : "decoder_precondition";
            return choice;
        }
    }
    choice.reason = "decoder_precondition";
    return choice;
}
