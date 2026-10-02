// Host-only checks for optional Granite pass-profile parsing and cadence.
#include "pass_profile.h"

#include <cstdio>

static int failures = 0;
static void expect(bool value, const char *name) {
    if (!value) { std::printf("FAIL: %s\n", name); ++failures; }
}

int main() {
    PassProfileSample sample;
    expect(parse_pass_profile_sample("Dequant: 2.500 ms per frame", &sample) &&
           sample.phase == PassProfilePhase::Dequant && sample.milliseconds == 2.5,
           "accepts valid Dequant sample");
    expect(parse_pass_profile_sample("iDWT fragment: 1.125 ms per frame", &sample) &&
           sample.phase == PassProfilePhase::IDwtFragment,
           "accepts valid fragment sample");
    const char *invalid_samples[] = {
        "Unknown: 1.0 ms per frame", "Dequant: 0 ms per frame", "Dequant: nan ms per frame",
        "Dequant: inf ms per frame", "Dequant: 1.0 milliseconds",
    };
    for (const char *invalid : invalid_samples) {
        expect(!parse_pass_profile_sample(invalid, &sample), "rejects invalid timestamp sample");
    }

    PassProfileCadence off;
    for (uint32_t i = 0; i < PassProfileCadence::completed_frame_window; ++i)
        expect(!off.record_completed_frame(), "off cadence never advances");
    expect(off.pending_completed_frames() == 0, "off cadence retains no count");

    PassProfileCadence on(true);
    for (uint32_t i = 1; i < PassProfileCadence::completed_frame_window; ++i)
        expect(!on.record_completed_frame(), "cadence waits for 90 completions");
    expect(on.pending_completed_frames() == PassProfileCadence::completed_frame_window - 1,
           "cadence counts completed frames");
    expect(on.record_completed_frame(), "cadence fires at 90 completions");
    expect(on.pending_completed_frames() == 0, "cadence resets at 90 completions");
    expect(!on.record_completed_frame(), "next window starts after reset");
    on.set_enabled(false);
    expect(on.pending_completed_frames() == 0 && !on.record_completed_frame(),
           "disabling resets and stops cadence");
    if (failures) return 1;
    std::puts("pass_profile_test: all passed");
    return 0;
}
