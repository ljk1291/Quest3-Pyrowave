#include "decoder_modes.h"
#include <cassert>
#include <cstdio>
#include <vector>

int main() {
    const char *invalid[] = {nullptr, "", "00", "01", "6", "-1", "5 ", " 5", "true", "2x"};
    for (const char *value : invalid) {
        assert(parse_decoder_mode(value) == 0);
        assert(parse_packed_levels(value) == 4);
    }
    assert(parse_packed_levels("2") == 2);
    assert(parse_packed_levels("4") == 4);
    for (int request = 0; request <= 5; ++request) {
        const char value[] = {char('0' + request), 0};
        for (int accepted = 0; accepted <= 5; ++accepted) {
            for (bool wavelet : {false, true}) for (bool fragment : {false, true}) {
                for (bool full_range : {false, true}) {
                    std::vector<int> attempts;
                    const auto choice = choose_decoder_mode(value, wavelet, fragment, full_range,
                        [&](int mode) { attempts.push_back(mode); return mode <= accepted; });
                    const int limit = request == 5 && !full_range ? 4 : request;
                    const int expected = wavelet && !fragment ? (limit < accepted ? limit : accepted) : 0;
                    assert(choice.requested == request && choice.active == expected);
                    if (!wavelet || fragment || !request) assert(attempts.empty());
                    else {
                        assert(attempts.front() == limit);
                        assert(attempts.back() == (expected ? expected : 1));
                        for (size_t i = 1; i < attempts.size(); ++i) assert(attempts[i] == attempts[i - 1] - 1);
                    }
                    if (!request) assert(!std::strcmp(choice.reason, "disabled"));
                    else if (!wavelet) assert(!std::strcmp(choice.reason, "wavelet"));
                    else if (fragment) assert(!std::strcmp(choice.reason, "fragment"));
                    else if (expected == request) assert(!std::strcmp(choice.reason, "enabled"));
                    else assert(std::strcmp(choice.reason, "enabled"));
                }
            }
        }
    }
    // All four lanes and both chroma components, including last texels and the
    // real crop. Luma and chroma must occupy disjoint halves of mode-5 storage.
    for (int width : {64, 5248}) for (int height : {32, 2752}) {
        for (int y : {0, 1, height - 2, height - 1}) for (int x : {0, 1, width - 2, width - 1}) {
            const size_t quad = size_t(y / 2) * (width / 2) + x / 2;
            const size_t lane = (y % 2) * 2 + x % 2;
            assert(decoder_sample_offset(0, x, y, width, width / 2, true, false, false) == quad * 4 + lane);
            const size_t offset = decoder_sample_offset(0, x, y, width, width, true, true, true);
            assert(offset / 4 % width < size_t(width / 2));
            assert(offset < size_t(width) * height * 2);
        }
        for (int c : {1, 2}) for (int y : {0, height / 2 - 1}) for (int x : {0, width / 2 - 1}) {
            const size_t offset = decoder_sample_offset(c, x, y, width, width, true, true, true);
            assert(offset / 4 % width >= size_t(width / 2));
            assert(offset < size_t(width) * height * 2);
            assert(offset % 4 == size_t(c - 1));
            assert(decoder_sample_offset(c, x, y, width, width / 2, true, true, false) ==
                   (size_t(y) * (width / 2) + x) * 2 + c - 1);
        }
    }
    puts("decoder mode parsing and descending precondition fallback passed");
}
