// Host-only checks for the terminal GPU submission policy. No Vulkan or Android runtime needed.
#include "gpu_failure_policy.h"
#include <cstdio>

static int failures = 0;
static void expect(bool value, const char *name) {
    if (!value) { std::printf("FAIL: %s\n", name); ++failures; }
}

int main() {
    GpuSubmissionState completed;
    expect(completed.can_submit(), "new instance accepts work");
    completed.submitted();
    expect(!completed.can_submit(), "pending submission cannot be reused");
    completed.completed();
    expect(completed.can_submit(), "completed submission can be reused");
    expect(!completed.retain_resources(), "completed instance cleans up normally");

    GpuSubmissionState timeout;
    timeout.submitted();
    timeout.terminal_failure();
    expect(!timeout.can_submit(), "timeout blocks reuse");
    expect(timeout.retain_resources(), "timeout retains pending resources");

    GpuSubmissionState device_lost;
    device_lost.terminal_failure();
    expect(!device_lost.can_submit(), "device loss blocks reuse");
    expect(device_lost.retain_resources(), "device loss retains resources");
    if (failures) return 1;
    std::puts("gpu_failure_policy_test: all passed");
    return 0;
}
