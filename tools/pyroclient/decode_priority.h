// SPDX-License-Identifier: MIT
// Queue request/retry mechanism adapted from JMS1717/Quest3-Pyrowave,
// tools/pyroclient/pyroclient.cpp at 8fb4656c3949b9538b22286a9a2068b98fa0ed75.
// Copyright (c) 2026 JMS1717 - Quest3-Pyrowave changes
// Fork policy: explicit opt-in only; no refresh/chroma-based automatic LOW.
#pragma once
#include <cstdint>
#include <cstring>

enum class DecodeQueuePriority { Default, Low, Medium, High };

struct DecodePriorityRequest {
    DecodeQueuePriority priority;
    const char *name;
    bool valid;
};

inline DecodePriorityRequest parse_decode_priority(const char *property) {
    if (!property || !*property) return {DecodeQueuePriority::Default, "unset", true};
    if (!std::strcmp(property, "default")) return {DecodeQueuePriority::Default, "default", true};
    if (!std::strcmp(property, "low")) return {DecodeQueuePriority::Low, "low", true};
    if (!std::strcmp(property, "medium")) return {DecodeQueuePriority::Medium, "medium", true};
    if (!std::strcmp(property, "high")) return {DecodeQueuePriority::High, "high", true};
    return {DecodeQueuePriority::Default, "invalid", false};
}

inline const char *decode_priority_extension(bool khr, bool ext) {
    return khr ? "VK_KHR_global_priority" : ext ? "VK_EXT_global_priority" : nullptr;
}

inline const char *decode_priority_name(DecodeQueuePriority priority) {
    switch (priority) {
    case DecodeQueuePriority::Low: return "low";
    case DecodeQueuePriority::High: return "high";
    case DecodeQueuePriority::Default:
    case DecodeQueuePriority::Medium: return "medium";
    }
    return "unknown";
}

struct DecodePriorityResult {
    const char *effective; // "unavailable" on final device creation failure
    const char *extension; // extension on the successfully created device, or "none"
    const char *fallback;
    int32_t first_result;
    int32_t result;
    bool applied;
};

// No Vulkan/Android dependency: CPU tests exercise the same retry path used by the client.
// create(priority, extension) MUST replace the queue pNext and enabled-extension list on
// each attempt. Default means the original create info with no global-priority extension.
// VkResult success is zero. Do not retry a failed ordinary/default device creation.
template <typename Create>
DecodePriorityResult create_decode_priority_device(DecodePriorityRequest requested,
                                                   const char *extension, Create create) {
    const bool explicit_priority = requested.priority != DecodeQueuePriority::Default;
    const bool attempt_priority = explicit_priority && extension;
    const char *fallback = !requested.valid ? "invalid_property" :
        explicit_priority && !extension ? "extension_unavailable" : "none";
    const int32_t first = create(attempt_priority ? requested.priority : DecodeQueuePriority::Default,
                                 attempt_priority ? extension : nullptr);
    int32_t result = first;
    bool applied = attempt_priority && first == 0;
    if (first != 0 && attempt_priority) {
        fallback = "device_rejected";
        result = create(DecodeQueuePriority::Default, nullptr);
    }
    return {result != 0 ? "unavailable" : applied ? decode_priority_name(requested.priority) : "medium",
            applied ? extension : "none", fallback, first, result, applied};
}
