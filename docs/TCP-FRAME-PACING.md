# TCP frame-pacing probe

`python -m tools.quest3.network --transport tcp` is an opt-in, network-only
section-6 tool. It does not modify ALVR, router, Wi-Fi, headset settings, or a
streaming session. It must be run only in an authorized supervised test.

It sends one synthetic TCP frame at each requested refresh deadline. Each frame is
exactly `floor(Mbps * 1,000,000 / 8 / Hz)` bytes, matching the live fixed-rate
payload budget. A delayed frame skips subsequent missed deadlines instead of making
a catch-up burst.

`tcpframerecv-android` ACKs only after it has read the complete frame. The report
therefore gives ACK-delivery p50/p99/p99.9, late-frame share against the selected
period, and longest ACK-delivery stall. These values include the ACK return path
and receiver scheduling. They do not claim one-way latency, decoder completion,
fresh submissions, display FPS, or optical latency.

Writes and ACK reads run concurrently with at most three outstanding frames.
A late ACK is retained rather than terminating the test at one frame period.
Socket I/O and the final ACK drain are bounded to one second by default. An
incomplete write terminates that TCP stream because its framing cannot safely
continue. Every scheduled slot remains in the late-share denominator; partial
writes, skipped slots and unacknowledged frames are separate fields. The reported
longest completed ACK delay excludes missing ACKs, whose censored lower bound is
reported separately. Receiver/protocol errors or sender/receiver count mismatches
make the run incomplete rather than producing a passing delivery result.

Before and after each TCP rate, the tool reads `cmd wifi status` and `dumpsys wifi`.
It keeps only link rate, band, channel and channel width; SSID, BSSID and IP data
are discarded. A missing field remains unknown.

The live-cell event summary now publishes keyed `video_packet_bytes` p50/p99/max
and sample count. It rejects unkeyed GraphStatistics as frame-size samples so a
sampled aggregate cannot be mistaken for per-frame H.264 variability.
