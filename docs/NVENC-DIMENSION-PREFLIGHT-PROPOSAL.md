# Proposal: NVENC dimension preflight

Status: **not active, not merged, and not included in any build pair.** This is a literal
source-change proposal for review after an owner-approved, read-only capability receipt exists.
It does not authorize a local GPU query.

## Placement

Add a fail-closed `ValidateEncodeDimensions()` method to
`server_openvr/cpp/platform/win32/NvEncoder.{h,cpp}`. Invoke it in
`VideoEncoderNVENC::Initialize()` after `FillEncodeConfig()` and before
`m_NvNecoder->CreateEncoder(&initializeParams)`. The `NvEncoderD3D11` constructor has already
opened the NVENC session at that point, so `nvEncGetEncodeCaps` is available, while no encoder has
been initialized and no frame resources have been registered.

The preflight must map only these existing codec GUIDs:

| ALVR codec | NVENC GUID | caps queried |
| --- | --- | --- |
| H.264 | `NV_ENC_CODEC_H264_GUID` | `NV_ENC_CAPS_WIDTH_MAX`, `NV_ENC_CAPS_HEIGHT_MAX` |
| HEVC | `NV_ENC_CODEC_HEVC_GUID` | `NV_ENC_CAPS_WIDTH_MAX`, `NV_ENC_CAPS_HEIGHT_MAX` |
| AV1 | `NV_ENC_CODEC_AV1_GUID` | `NV_ENC_CAPS_WIDTH_MAX`, `NV_ENC_CAPS_HEIGHT_MAX` |

The checked geometry is exactly `NV_ENC_INITIALIZE_PARAMS::encodeWidth` by
`encodeHeight`, after ALVR's existing `FillEncodeConfig()` has selected it. This covers normal
stock streams and H264Fit without inventing a separate resolution rule.

## Proposed shape

```cpp
// NvEncoder.h: private or protected; returns false on every query or identity failure.
bool TryGetCapabilityValue(GUID codec, NV_ENC_CAPS cap, int* value) const;
bool ValidateEncodeDimensions(const NV_ENC_INITIALIZE_PARAMS& params, std::string* reason) const;

// VideoEncoderNVENC.cpp, after FillEncodeConfig and before CreateEncoder.
std::string dimension_reason;
if (!m_NvNecoder->ValidateEncodeDimensions(initializeParams, &dimension_reason)) {
    throw MakeException("NVENC geometry preflight failed: %s", dimension_reason.c_str());
}
m_NvNecoder->CreateEncoder(&initializeParams);
```

`TryGetCapabilityValue` must initialize its output and return false unless the session handle,
the function pointer and the `nvEncGetEncodeCaps` return status are all valid. It must not reuse
the existing `GetCapabilityValue()` helper because that helper returns an uninitialized local if
the driver call fails. `ValidateEncodeDimensions` must reject a zero requested geometry, an
unknown GUID, absent/zero/negative cap values, and either maximum below the request. Its reason
must include codec, requested width/height and the two observed caps; it must never report a
supported result from an absent receipt.

No adapter is selected or created by this check. The normal ALVR D3D/NVENC session remains the
single source of adapter identity. Before activation, the controller must compare its already
captured adapter LUID/name and probe receipt with the ALVR process log, then retain the receipt
with its source/tool hashes and command.

## CPU-only test proposal

Extract the GUID-to-label mapping and maximum comparison into a header-only pure helper (for
example `NvencDimensionPolicy.h`) with no D3D or NVENC calls. Test it with a fake capability
reader:

1. H.264, HEVC and AV1 each accept a requested dimension equal to their caps.
2. Each codec rejects width and height independently when one cap is too small.
3. A missing function, failed query, duplicate/unknown codec or zero cap fails closed.
4. The known H264Fit request `3968x2080` is accepted only with H.264 caps at least that large.
5. The policy result includes no claim about frame rate, throughput, encode latency or quality.

Run that pure C++ test in the CPU CI job. Do not run a GPU capability probe as part of the test.

## Activation prerequisites

1. Root runs the minimal read-only probe under the owner-approved scope and supplies its receipt.
2. The receipt validates exact adapter identity, source hash, tool hash, command and all three
   codec cap pairs.
3. A reviewer accepts the literal patch and CPU test, then a separately built signed pair carries
   its own provenance. The verified `80a1635` pair remains unchanged.
