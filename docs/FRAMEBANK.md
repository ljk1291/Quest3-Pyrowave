# WO-1 frame-bank owner runbook

The owner creates one lossless **90-frame** Metro encoder-input dump at the agreed fixed checkpoint. This is a supervised capture, separate from a rate capture. Record the matching build identity, exact render and encode geometry, color-range setting, checkpoint, and the measured centre projection density in a private capture record.

Set the existing encoder dump controls only for the supervised capture:

```text
ALVR_PYROWAVE_DUMP=<private results/local destination>
ALVR_PYROWAVE_DUMP_TRIGGER=<owner-selected trigger>
ALVR_PYROWAVE_DUMP_COUNT=90
ALVR_PYROWAVE_DUMP_EVERY=1
```

The resulting Y4M must be 6144Ã—3232, an `F72:1` or `F90:1` header, an 8-bit native `C420jpeg` or `C444` format, and its recorded `XCOLORRANGE`. Do not use a compositor screenshot, a scaled output, a partial dump, a different checkpoint, or a capture made while Metro is not presenting.

`framebank plan` requires an explicit `--crops` JSON array (or `@JSON-file`) selected against this checkpoint. Use safe lowercase labels that describe what is actually visible, such as `rails`, `fog`, or `ui`; do not reuse a generic foliage label for an indoor tunnel. It freezes both the reviewed normalized coordinates and their resolved C420-aligned pixel rectangles, alongside the dump SHA-256, frame hashes, native-chroma offline matrix, projection evidence (horizontal and vertical density, with vertical used by HVS), and scorer calibration. Production planning never falls back to example crops. It performs no codec work. The owner then authorizes the PC workload through WO-0 with `frame_bank_pc`; `framebank run` checks the read-only WO-0 lease before and while every encoder, decoder, and scorer process runs. It refuses an expired, revoked, paused, stale-monitor, competing-GPU, or restoring window.

The runner writes raw Y4M, packet, decoded-frame hashes, and private PNG grids under `results/local/`. Its recorded resize filter is Pillow Lanczos3; it streams one frame at a time and deletes large intermediates by default. The sanitized report is valid only when every frozen source/tool hash remains unchanged and every metric, including the separate `pyrowave-psnr-hvs-m` scorer-adapter result, is present. The pinned upstream tool only emits its fixed 1.00–2.875 sweep. `patches/README-hvs-ppd-scorer.md` documents the isolated opt-in scorer patch that accepts measured vertical pixels/degree, derives one factor from each actual scored image height, and logs both values. The runner passes this explicit value and rejects a missing or mismatched emitted calibration. It never substitutes an isotropic average for the vertical projection density. It is an offline codec-quality result, not a Quest performance or optical-latency claim.
