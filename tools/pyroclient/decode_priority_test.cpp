// Host-only property and device-create retry tests. No Android/Vulkan/GPU work.
#include "decode_priority.h"
#include <cstdio>
#include <vector>

static int failures = 0;
static void expect(bool value, const char *name) {
    if (!value) { std::printf("FAIL: %s\n", name); ++failures; }
}
static bool same(const char *a, const char *b) { return !std::strcmp(a, b); }

struct Attempt { DecodeQueuePriority priority; const char *extension; };
struct MockCreate {
    std::vector<Attempt> attempts;
    std::vector<int32_t> results;
    int32_t operator()(DecodeQueuePriority priority, const char *extension) {
        attempts.push_back({priority, extension});
        return results.at(attempts.size() - 1);
    }
};

int main() {
    using P = DecodeQueuePriority;
    for (const char *value : {static_cast<const char *>(nullptr), "", "default"}) {
        const auto request = parse_decode_priority(value);
        expect(request.valid && request.priority == P::Default, "unset/default keeps original priority");
    }
    for (const char *value : {"LOW", "low ", " low", "low\n", "0", "auto", "realtime", "junk"}) {
        const auto request = parse_decode_priority(value);
        expect(!request.valid && request.priority == P::Default && same(request.name, "invalid"),
               "malformed property cannot enable priority");
    }
    expect(same(parse_decode_priority(nullptr).name, "unset"), "unset marker");
    expect(same(decode_priority_extension(true, true), "VK_KHR_global_priority"), "prefer KHR");
    expect(same(decode_priority_extension(false, true), "VK_EXT_global_priority"), "EXT fallback");
    expect(decode_priority_extension(false, false) == nullptr, "extension absent");

    for (const char *value : {"low", "medium", "high"}) {
        for (const char *extension : {"VK_KHR_global_priority", "VK_EXT_global_priority"}) {
            const auto request = parse_decode_priority(value);
            MockCreate create{{}, {0}};
            const auto result = create_decode_priority_device(request, extension,
                [&](P p, const char *e) { return create(p, e); });
            expect(request.valid && create.attempts.size() == 1 && result.applied && result.result == 0 &&
                   same(result.effective, value) && same(result.extension, extension) && same(result.fallback, "none"),
                   "explicit requested level accepted and logged");
            expect(create.attempts[0].priority == request.priority && create.attempts[0].extension == extension,
                   "exact request reaches device creation");

            // Permission denial and other create failures both retry at the unmodified default.
            for (int32_t rejected : {-1000174001, -3}) {
                MockCreate retry{{}, {rejected, 0}};
                const auto fallback = create_decode_priority_device(request, extension,
                    [&](P p, const char *e) { return retry(p, e); });
                expect(retry.attempts.size() == 2 && retry.attempts[1].priority == P::Default &&
                       retry.attempts[1].extension == nullptr, "retry removes priority and extension");
                expect(!fallback.applied && fallback.result == 0 && fallback.first_result == rejected &&
                       same(fallback.effective, "medium") && same(fallback.extension, "none") &&
                       same(fallback.fallback, "device_rejected"), "fallback reports default, not rejected priority");
            }
        }
        MockCreate create{{}, {0}};
        const auto absent = create_decode_priority_device(parse_decode_priority(value), nullptr,
            [&](P p, const char *e) { return create(p, e); });
        expect(create.attempts.size() == 1 && create.attempts[0].priority == P::Default &&
               !absent.applied && same(absent.fallback, "extension_unavailable") &&
               same(absent.effective, "medium"), "no extension keeps decoding at default");
    }
    for (const char *value : {"", "default", "bogus"}) {
        MockCreate create{{}, {-3}};
        const auto result = create_decode_priority_device(parse_decode_priority(value), "VK_KHR_global_priority",
            [&](P p, const char *e) { return create(p, e); });
        expect(create.attempts.size() == 1 && create.attempts[0].extension == nullptr &&
               result.result == -3 && !result.applied && same(result.effective, "unavailable"),
               "ordinary failure is preserved without retry or effective claim");
        expect(same(result.fallback, same(value, "bogus") ? "invalid_property" : "none"), "invalid marker");
    }
    MockCreate failed_retry{{}, {-1000174001, -4}};
    const auto failure = create_decode_priority_device(parse_decode_priority("low"), "VK_KHR_global_priority",
        [&](P p, const char *e) { return failed_retry(p, e); });
    expect(failed_retry.attempts.size() == 2 && failure.result == -4 && !failure.applied &&
           same(failure.effective, "unavailable") && same(failure.extension, "none"),
           "failed fallback propagates error and never claims a granted queue");
    if (failures) return 1;
    std::puts("decode_priority_test: all passed");
    return 0;
}
