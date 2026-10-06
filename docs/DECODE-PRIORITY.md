# Opt-in decode queue priority (T3 candidate)

This fork preserves the existing default decode queue. `debug.q3pw.decode_priority`
is read once inside native `pyroclient::create_device`, for both the ALVR decoder
and standalone probe. Changing it requires recreating the decoder/client. No
refresh-rate or chroma policy automatically enables LOW.

| Exact property value | Request |
| --- | --- |
| unset/empty, `default` | Original create info, no priority extension or queue pNext |
| `low` | `VK_QUEUE_GLOBAL_PRIORITY_LOW_KHR` (128) |
| `medium` | Explicit `VK_QUEUE_GLOBAL_PRIORITY_MEDIUM_KHR` (256) |
| `high` | Explicit `VK_QUEUE_GLOBAL_PRIORITY_HIGH_KHR` (512); experimental, not the T3 A/B arm |
| other, including whitespace/case variants | Original create info; `fallback=invalid_property` |

The original per-device float queue priority remains `1.0`. This is different
from system-wide global priority. The first graphics-capable queue family and
queue index zero remain unchanged; decode and RGBA conversion still share that
queue. No LPAC family, conversion, shader, synchronization, buffer ownership,
ABI, dependency pin, protocol, signing or preset change is included.

For explicit requests, enumerate device extensions, preferring
`VK_KHR_global_priority` over `VK_EXT_global_priority`. Enable only that extension
and attach `VkDeviceQueueGlobalPriorityCreateInfoKHR` to
`VkDeviceQueueCreateInfo::pNext`. KHR/EXT use equivalent structure/enumeration
aliases in the pinned Vulkan headers. Without either extension, create the
original device and report `extension_unavailable`. Failed extension enumeration
also uses the original device, reporting `extension_query_failed`.

On any failed priority-bearing `vkCreateDevice`, remove both the priority pNext
and added extension and retry once with the original configuration. Retain the
first and final Vulkan results. A failed ordinary/default creation is not
retried; a failed fallback still fails initialization. Create-info storage and
the extension list remain alive for the borrowed PyroWave device.

Successful initialization emits, for example:

```text
[Q3PW_DECODE_PRIORITY] requested=low effective=low extension=VK_KHR_global_priority fallback=none applied=1 family=0 queue_index=0 local_priority=1.0 first_result=0 result=0 proof=vkCreateDevice
[Q3PW_DECODE_PRIORITY] requested=low effective=medium extension=none fallback=device_rejected applied=0 family=0 queue_index=0 local_priority=1.0 first_result=-1000174001 result=0 proof=vkCreateDevice
[Q3PW_DECODE_PRIORITY] requested=unset effective=medium extension=none fallback=none applied=0 family=0 queue_index=0 local_priority=1.0 first_result=0 result=0 proof=vkCreateDevice
```

The family above is illustrative; the marker prints the selected family.
`effective` identifies the global priority of the successfully created queue,
including implicit MEDIUM on the original path. If creation ultimately fails it
is `unavailable`, never a claimed grant. `extension` describes the final device,
not an extension rejected on the first attempt. There is no Vulkan post-creation
queue-priority getter: the proof is successful creation with that exact queue
create info, not OS scheduler readback or measured preemption. See the Khronos
[queue priority structure](https://docs.vulkan.org/refpages/latest/refpages/source/VkDeviceQueueGlobalPriorityCreateInfo.html)
and [extension contract](https://docs.vulkan.org/refpages/latest/refpages/source/VK_KHR_global_priority.html).
Android property readback alone proves a request. The capture tools now snapshot
the property, label it as requested, and include it in explicit experiment reset;
they do not infer a successful grant from that readback.

## Upstream source and evidence

The request/retry mechanism is adapted from JMS1717/Quest3-Pyrowave
[`tools/pyroclient/pyroclient.cpp` at `8fb4656c3949b9538b22286a9a2068b98fa0ed75`](https://github.com/JMS1717/Quest3-Pyrowave/blob/8fb4656c3949b9538b22286a9a2068b98fa0ed75/tools/pyroclient/pyroclient.cpp)
(.33). Its MIT copyright is retained in the helper and packaged `NOTICE`;
existing ALVR, PyroWave and Granite credits remain intact.
The complete review reference is upstream/main
`2de8ad13973ed9c3a8e72f4c85a79e1e7e5d085a`.

Upstream .33 reads the property on the Rust TCP-decoder side and passes a boolean
through `pyroclient_create_prioritized`. `low` always requests LOW; `default`
forces the original path; other values choose LOW for 4:2:0 with positive refresh
rate at most 120.5 Hz. Native code enables KHR, else EXT, on the first graphics
family (family 0 on the measured Quest), attaches the LOW structure, retries a
rejected device creation at default, and logs `[Q3PW_PRIORITY]` policy plus
requested/applied/extension. Its inherited PyroWave borrowed-device/queue-type
support carries those create infos into Granite; no queue-priority codec/shader
change is needed. Our starting fork has that borrowing support and local float
priority `1.0`, but no equivalent global-priority request, property or marker.
This port reads natively and keeps the API unchanged, with no automatic LOW rule.

Upstream's [recorded priority A/B](https://github.com/JMS1717/Quest3-Pyrowave/blob/2de8ad13973ed9c3a8e72f4c85a79e1e7e5d085a/results/DECODE-PRIORITY-AB-2026-10-04.json)
used a stationary chart at 2080x2208/eye, USB/TCP, 1000 Mbps, 4:2:0,
5 seconds excluded settle and 20 seconds measured per restart, interleaved blocks.
At 120 Hz .32 displayed-target proxy rates rose 114.3 to 117.7/s (5/5 adjacent
pairs), and .33 110.6 to 115.7/s (4/5). Eye-copy CPU p90 fell about 7.4-7.5 to
1.8-1.9 ms; GPU decode p90 increased about 1 ms. At 144 Hz LOW regressed 135.0
to 124.7/s (3/3 pairs); that session stopped early on a reconnect problem.
These were short unworn-headset screens, not gameplay, optical FPS or sustained
thermal acceptance. Upstream's later timestamp correction also qualifies
displayed-target/lost-target proxies: tracking IDs are not encoded-frame IDs.
They are not our Godlike/90-Hz/Wi-Fi primary fresh-output measure.

## Selection wait comparison (no changes)

Our reconstructed `alvr/client_openxr/src/stream.rs` uses the policy in
`patches/quest3-alvr.patch`; subsequent baseline overlays do not change it:

| Detail | This fork at 6ee1ba5 | Upstream .31-.33 bounded half-frame wait |
| --- | --- | --- |
| Default / malformed property | 0 us | 4000 us |
| Numeric property cap | 1000 us | 4000 us |
| Display-period cap | one eighth | one half |
| At 90 Hz | at most 1000 us; default 0 | default 4000 us |
| Read cadence | once at StreamContext creation | about once per second |
| Starts after | empty post-xrWaitFrame selection with eye copy ready, Quest3 PyroWave | same eligibility, plus a complete frame decoding |
| Continues while | no ready frame and before deadline, regardless of input/decode state | decode in flight and before deadline; final poll handles publication clearing the flag |
| Polling | sleep 50 us, retry `get_frame` | sleep 50 us, retry `get_frame` |
| Evidence | `[Q3PW_FRAME_WAIT]` budget/waits/hits/mean/max | wait evidence plus freshness/in-flight diagnostics |

Thus we have the bounded-wait mechanism, but not the 4-ms default, half-frame
budget or decode-in-flight gate. Our wait may spend its entire optional budget
even when no packet is available. Both retain buffer leases and immediately use
an already available frame. Sleep scheduling can overshoot the nominal budget.

At the reviewed upstream head, explicit requests 4001-6000 us additionally reserve
2000 us for the eye copy instead of using the half-frame cap. Default remains
4000 us. Default-off packet grace permits up to 1000 us for input to arrive
inside the same total budget; measured upstream grace did not justify enabling
it. There is also an opt-in condition-variable publication wait. None is ported.

Our `debug.q3pw.pre_wait_poll=1` is a separate default-off, nonblocking ready-frame
selection before `xrWaitFrame`, requiring `debug.xrwired.early_poll != 0`.
It can hold a leased, older frame across the runtime wait and skip later selection
when one is held; `[Q3PW_PRE_WAIT]` counts polls/hits/consumption and hold time.
It introduces no selection sleep and is not equivalent to the half-frame wait.
Keep pre-wait and frame-wait settings identical across T3 arms.

## Later opt-in candidates (not ported)

The following review reflects upstream's
[ADRENO-740](https://github.com/JMS1717/Quest3-Pyrowave/blob/2de8ad13973ed9c3a8e72f4c85a79e1e7e5d085a/docs/ADRENO-740.md)
and [XR2-GEN2-SOC](https://github.com/JMS1717/Quest3-Pyrowave/blob/2de8ad13973ed9c3a8e72f4c85a79e1e7e5d085a/docs/XR2-GEN2-SOC.md)
documents and code. All three are built/default-off upstream, with **no recorded
hardware experiment for the feature** at that reference.

| Feature | Mechanism / gate | Fit for our workload |
| --- | --- | --- |
| LPAC `debug.q3pw.lpac=1` | A LOW compute-only family for decode and compute RGBA conversion, alongside the graphics family Granite needs. Requires a usable family, timestamps and LOW support/extension; logs `[Q3PW_LPAC]` and falls back on absence/rejection. Forces fragment reconstruction/conversion to compute. Intended to run concurrently with graphics through Adreno's second command processor. | Most relevant later scheduling experiment: could reduce graphics preemption/serialization in our ~2.5 ms completion gap. Exposed family and an actual win are unproved on our firmware. Compare exact readbacks to compute-conversion control, then default/compute-convert/LPAC/default to separate conversion cost from queue effects. Concurrent work may contend for memory or increase tails. |
| Eye invalidate `debug.q3pw.eye_invalidate=1` | `glInvalidateFramebuffer` before full-eye copy tells the tiler it need not load old eye contents into GMEM. Full coverage is required. `[Q3PW_EYE_INVALIDATE]` plus an eye-copy GPU probe proves activation/cost. | Lower priority unless eye-copy profiling shows a material GMEM/load cost. It may help competing graphics, but may save nothing on a direct-to-memory pass; it does not directly shorten wavelet decode. Needs eye output/correctness gates. |
| XR hints `debug.q3pw.thread_hints=1` | Enable `XR_KHR_android_thread_settings` at instance creation; declare frame loop RENDERER_MAIN, decode RENDERER_WORKER, socket/handoff/tracking APPLICATION_WORKER. `[Q3PW_THREAD_HINTS]` logs result and scheduler policy/RT priority/nice/CPU affinity before/after. | Lower priority for mean decode-to-fence throughput. Could improve CPU wake-up and selection/fence-observation tails; cannot establish shorter GPU execution. First verify runtime scheduling changes; otherwise drop per upstream proposal. |

The earlier trace's ~1.2 ms preemption is evidence motivating LPAC, not a measured
LPAC gain. These three options have no equivalent in this fork and remain outside T3.

## Next owner-supervised A/B

This is a protocol proposal, not permission for unattended or hardware work.
After full matching CI/artifact verification, confirm owner readiness and take
the existing settings/property/VD snapshots before any session interruption.
Use the same signed APK/server pair for all arms and preserve the active install.

1. Freeze scene/checkpoint, 3072x3232/eye, accepted runtime 90 Hz, TCP Wi-Fi,
   wavelet/chroma/bitrate, allocation, worker count, render path, frame/pre-wait
   settings, overlays and diagnostics. Keep clocks/thermal state comparable.
2. Run **off/on/off**: original default (`default` or empty) / `low` / original
   default. Recreate the client/decoder each arm. Exclude 5 seconds settling and
   measure 20 seconds per arm; repeat the sequence before interpreting a small win.
3. Require the native marker for every decoder/worker: off `effective=medium`,
   `extension=none`, `result=0`; on `requested=low effective=low applied=1`,
   KHR or EXT, `fallback=none`, `result=0`. A fallback is a diagnostic cell, not ON.
4. Lead with fresh selected **post-render/release submissions per wall second**
   and matching decode-to-fence **p50/p95**. Also retain completion counts,
   superseded/repeated frames, eye-copy times, CPU record/submit/wait splits,
   estimated pipeline latency, thermals and faults. Do not substitute tracking
   timestamp uniqueness, displayed-target proxies or GPU-only decode ms.
5. Reject image errors, terminal faults, pacing/latency regression, thermal or
   settings drift. Restore exact properties/settings and verify VD state.
   Longer gameplay/endurance and in-headset sign-off are separate gates.

LOW may worsen the main bottleneck: upstream traded extra decode/preemption time
for shorter eye-copy waits. Our ~83-84 fresh/s relationship to decode-to-fence
completion makes that risk concrete. No gain, standalone <=11.11 ms budget,
sustained 90 fresh/s or default promotion is claimed. Runtime acceptance of 90 Hz,
standalone completion budget and sustained live fresh output stay separate.

## Software validation

`decode_priority_test.cpp` covers exact/invalid/unset parsing, KHR preference/EXT
fallback, all three accepted priorities, missing extension, permission and other
creation rejection, removal of request/extension on retry, ordinary failure and
failed fallback. The production retry helper is used directly by those CPU tests.
Python contracts check native wiring, build integration and mocked snapshot/reset
evidence. No test invokes ADB or a GPU.

The `Quest3-Pyrowave` workflow (`.github/workflows/ci.yml`) runs the host test with
g++ under `tests`. A manual dispatch of this branch with `cpu_only=false` must
pass `tests`, `client`, `streamer`, and `matching-pair`. `client` reconstructs the
locked source stack and builds this native client through the existing
`tools/build_alvr_2013.sh` -> `tools/pyroclient/build.sh` path. No new patch/pin or
shader regeneration is needed because this decoder shim is repo-owned source.

Local 2026-10-06 software checks: 111/112 unittest checks passed; the native C++
policy check skipped because neither g++ nor clang++ is on PATH. Pin, metadata and
build-script pytest checks: 33 passed, four external-source/layout checks skipped.
Additional legacy Markdown/dashboard tests retain four unrelated failures: 22
bad links in unchanged `docs/UPSTREAM-README.md` and three README expectations for
the old upstream dashboard/4:4:4 preset. Their inputs match 6ee1ba5 exactly.
Changed Markdown links and `git diff --check` pass. Native CPU execution,
Android compilation and full CI remain pending; no hardware action or performance
validation was performed. [Source check record](../results/t3-decode-priority-source-2026-10-06.json).
