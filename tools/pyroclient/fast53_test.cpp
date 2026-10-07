#include "fast53.h"
#include <cstdio>
#include <initializer_list>

int main() {
    const struct { const char *value; bool requested; } cases[] = {
        {nullptr, false}, {"", false}, {"0", false}, {"1", true},
        {"true", false}, {"01", false}, {"1 ", false}, {"-1", false}
    };
    const bool enabled[2][2] = {{false, false}, {true, false}};
    const char *reasons[2][2] = {{"wavelet", "wavelet"}, {"enabled", "fragment"}};
    for (const auto &test : cases) {
        for (bool cdf53 : {false, true}) {
            for (bool fragment : {false, true}) {
                const auto c = choose_fast53(test.value, cdf53, fragment);
                const char *reason = test.requested ? reasons[cdf53][fragment] : "disabled";
                const bool active = test.requested ? enabled[cdf53][fragment] : false;
                if (c.requested != test.requested || c.active != active ||
                    strcmp(c.reason, reason)) return 1;
            }
        }
    }
    puts("fast53 selection: all 32 combinations passed");
    return 0;
}
