// Default-off policy shared by the Android client and standalone harness.
#pragma once
#include <cstring>

struct Fast53Choice {
    int requested;
    bool active;
    int variant;
    const char *reason;
};

inline Fast53Choice choose_fast53(const char *property, bool cdf53, bool fragment) {
    const int requested = !property ? 0 : !strcmp(property, "1") ? 1 :
                          !strcmp(property, "2") ? 2 : !strcmp(property, "3") ? 3 : 0;
    const bool active = requested && cdf53 && !fragment;
    return {requested, active, active ? requested : 0,
            !requested ? "disabled" : !cdf53 ? "wavelet" : fragment ? "fragment" : "enabled"};
}
