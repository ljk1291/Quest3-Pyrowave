#pragma once

// Small, platform-independent ownership policy for the Vulkan submission in pyroclient.
// The safety invariant is intentionally conservative: once submission might be pending after
// a wait failure, this decoder instance must be abandoned instead of recycling its resources.
class GpuSubmissionState {
public:
    bool can_submit() const { return !fatal_ && !pending_; }
    void submitted() { pending_ = true; }
    void completed() { pending_ = false; }
    void terminal_failure() { fatal_ = true; }
    bool retain_resources() const { return fatal_ || pending_; }

private:
    bool pending_ = false;
    bool fatal_ = false;
};
