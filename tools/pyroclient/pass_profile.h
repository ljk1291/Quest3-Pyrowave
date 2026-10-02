// Host-only parsing and cadence rules for optional Granite pass-profile logs.
#pragma once

#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>

enum class PassProfilePhase {
    None,
    Dequant,
    IDwt,
    IDwtFragment,
};

struct PassProfileSample {
    PassProfilePhase phase = PassProfilePhase::None;
    double milliseconds = 0.0;
};

inline const char *pass_profile_phase_name(PassProfilePhase phase) {
    switch (phase) {
    case PassProfilePhase::Dequant: return "Dequant";
    case PassProfilePhase::IDwt: return "iDWT";
    case PassProfilePhase::IDwtFragment: return "iDWT fragment";
    default: return "";
    }
}

inline bool parse_pass_profile_sample(const char *message, PassProfileSample *sample) {
    if (!message || !sample) return false;
    const char *separator = std::strstr(message, ": ");
    if (!separator) return false;

    const size_t label_size = size_t(separator - message);
    PassProfilePhase phase = PassProfilePhase::None;
    const PassProfilePhase candidates[] = {
        PassProfilePhase::Dequant, PassProfilePhase::IDwt, PassProfilePhase::IDwtFragment,
    };
    for (PassProfilePhase candidate : candidates) {
        const char *name = pass_profile_phase_name(candidate);
        if (std::strlen(name) == label_size && !std::memcmp(message, name, label_size)) {
            phase = candidate;
            break;
        }
    }
    if (phase == PassProfilePhase::None) return false;

    errno = 0;
    char *end = nullptr;
    const double milliseconds = std::strtod(separator + 2, &end);
    while (end && *end == ' ') ++end;
    if (errno == ERANGE || end == separator + 2 || !end || std::strcmp(end, "ms per frame") ||
        !std::isfinite(milliseconds) || milliseconds <= 0.0) {
        return false;
    }

    *sample = {phase, milliseconds};
    return true;
}

class PassProfileCadence {
public:
    static constexpr uint32_t completed_frame_window = 90;

    explicit PassProfileCadence(bool enabled = false) : enabled_(enabled) {}

    void set_enabled(bool enabled) {
        enabled_ = enabled;
        completed_ = 0;
    }

    bool record_completed_frame() {
        if (!enabled_) return false;
        ++completed_;
        if (completed_ != completed_frame_window) return false;
        completed_ = 0;
        return true;
    }

    uint32_t pending_completed_frames() const { return completed_; }

private:
    bool enabled_ = false;
    uint32_t completed_ = 0;
};
