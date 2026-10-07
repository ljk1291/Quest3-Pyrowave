// Default-off policy shared by the Android client and standalone harness.
#pragma once
#include <cstring>

struct Fast53Choice {
    bool requested;
    bool active;
    const char *reason;
};

inline Fast53Choice choose_fast53(const char *property, bool cdf53, bool fragment) {
    const bool requested = property && !strcmp(property, "1");
    return {requested, requested && cdf53 && !fragment,
            !requested ? "disabled" : !cdf53 ? "wavelet" : fragment ? "fragment" : "enabled"};
}
