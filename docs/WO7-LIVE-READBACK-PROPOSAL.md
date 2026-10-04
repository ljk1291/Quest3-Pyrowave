# WO-7 live RDO readback proposal

This is a review-only proposal for proving the actual RDO density used by a
live PyroWave encoder. It requires a newly built matching pair and therefore
cannot prove the setting in the verified `80a1635` pair.

The PyroWave overlay `patches/pyrowave-rdo-live-readback.patch` is pinned by
`sources.lock.json` at SHA-256
`2a8c8e151689204d05c8f8ebd480ea297a76bd3ece2c6c81997ee15d1f370f96`.
It adds `pyrowave_encoder_get_rdo_density()` in `pyrowave.h` and implements it
in `pyrowave_c.cpp`. The getter reads the `Encoder::Impl::rdo_density` retained
by `Encoder::init()` in `pyrowave_encoder.cpp`; it returns effective px/deg,
Nyquist cycles/deg, and the legacy-equivalent flag.

The ALVR overlay `patches/alvr-pyrowave-rdo-live-readback.patch` is pinned at
SHA-256 `d32a96c6456f13ace911db9298800f1c7da9ebf9f75296b3b3c668489a2bb94d`.
In `alvr/server_openvr/cpp/platform/win32/VideoEncoderPyroWave.cpp`, it calls
the getter immediately after `pyrowave_encoder_create()` and emits a `Warn()`
marker to `vrserver.txt`. That avoids PyroWave's intentionally installed
`NullLogger`, which suppresses the native `LOGI` emitted during initialization.

The patch does not change `PYROWAVE_RDO_PX_PER_DEG` parsing, RDO arithmetic,
encoder inputs, defaults, or the bitstream path. With the variable unset, the
existing legacy 96-DPI-at-one-metre calculation remains in effect.

Focused source/lock checks and the standalone RDO report-parity test validate
the proposal. A native build must still verify the exported DLL symbol, and an
initialized live Vulkan encoder must still produce and retain the `Warn()`
marker. Those are deferred until an owner approves replacing the current
verified pair.
