#include "NvencDimensionPolicy.h"

#include <cassert>
#include <string>

using alvr_nvenc_dimension::Caps;
using alvr_nvenc_dimension::Codec;

static Caps caps(int width, int height) { return {true, width, true, height}; }

int main() {
    std::string reason;
    assert(alvr_nvenc_dimension::Validate(Codec::H264, 3968, 2080, caps(4096, 4096), &reason));
    assert(alvr_nvenc_dimension::Validate(Codec::HEVC, 8192, 8192, caps(8192, 8192), &reason));
    assert(alvr_nvenc_dimension::Validate(Codec::AV1, 8192, 8192, caps(8192, 8192), &reason));
    assert(!alvr_nvenc_dimension::Validate(Codec::H264, 4097, 2080, caps(4096, 4096), &reason));
    assert(reason.find("width") != std::string::npos);
    assert(!alvr_nvenc_dimension::Validate(Codec::H264, 3968, 4097, caps(4096, 4096), &reason));
    assert(reason.find("height") != std::string::npos);
    assert(!alvr_nvenc_dimension::Validate(Codec::Unknown, 1, 1, caps(1, 1), &reason));
    assert(!alvr_nvenc_dimension::Validate(Codec::H264, 0, 2080, caps(4096, 4096), &reason));
    assert(!alvr_nvenc_dimension::Validate(Codec::H264, 3968, 2080, {false, 0, true, 4096}, &reason));
    assert(!alvr_nvenc_dimension::Validate(Codec::H264, 3968, 2080, {true, 4096, false, 0}, &reason));
    assert(!alvr_nvenc_dimension::Validate(Codec::H264, 3968, 2080, caps(0, 4096), &reason));
    return 0;
}
