# Q3 cropped PyroWave frame-bank runner

`tools/xrbench/pyro_q3_framebank.py` freezes and runs the five offline Q3a
PyroWave rows against the native C420 crop: Haar/1000, CDF 5/3 at 800 and
1000, and CDF 9/7 at 800 and 1000 Mbps. It accepts only the 90-frame,
5248x2776 stereo, full-range source contract. Each cell is a 2624x2776 per-eye
encode at 90 Hz.

The plan records the source hash and per-frame identities, crop offsets,
tool-package provenance, shader/dependency provenance from the verified native
bundle, and hashes of the runner, frame-bank, and fence modules. The private
result retains actual PyroWave container bytes and every per-frame payload size,
the confirmed requested wavelet from both CLI logs, decoded-frame identities,
and the shared Q3 score result with both 1–90 and 10–89 windows. It records no
optical FPS or latency claim.

Use `plan` with the reviewed full Metro parent (`--full-source`) to freeze its
original fixed-crop coordinates and HVS calibration, plus the native cropped
source (`--source`) that the codec actually receives. The plan records both
hashes and explicitly identifies the no-resampling crop derivation. Run only
with `run --supervised` while an owner-attested `frame_bank_pc` lease is active.
The runner performs the HVS GPU sanity gate before an encode. It stops on the
first failed cell, writes private progress, and keeps interrupted artifacts.
`--resume` accepts only a matching already-complete result; it never replayes a
completed or partially encoded cell.

Each Q3a encode requires the native encoder's
`<cell>/pyrowave-encode-timing.jsonl`, created with `--timing-jsonl`. Its 90
zero-based records have schema version, frame id, packetized payload bytes,
CPU command-record-submit milliseconds, and submit-to-observed-fence
milliseconds. The fence field is completion latency, not GPU execution. The
runner does not divide aggregate wall time by 90.

When a telemetry rebuild supplies a new encode/decode bundle, pass its metadata
as `--tools-metadata` and the retained qualified HVS bundle as
`--scorer-tools-metadata`. Both bundles are independently verified; the runner
requires equal scorer source, shader, and source-lock records before it mixes
the new codec pair with the retained scorer.

The eight Q3b hooks are frozen only as non-runnable rows. They fail closed until
WO-8 provides a proven reduced-plane encode plus expanded-space scoring path;
the runner cannot substitute blur-only processing for that transform.
