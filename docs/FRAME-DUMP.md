# Lossless live frame pairs (default-off diagnostic)

`patches/frame-dump.patch` is an additive ALVR overlay. It applies after upstream's ALVR stack
(`alvr-20.13.0-server-instrumentation.patch`, `quest3-alvr.patch` and the copied files), the
fork-identity overlay and `fast-abr.patch`, and before `frame-loss-diagnostics.patch`. It touches
no file that fast ABR changes. Nothing changes unless a control below is set: no protocol, setting
or default changes. ALVR, PyroWave and JMS1717 credits are unchanged.

Ported on 2026-10-08 from the ljk1291 fork (`codex/decoder-v2`, based on f6eae38) to upstream
`18d43ce` (`.65`). The port has not been compiled or run: Actions is the compiler, and device
behaviour needs a hardware session.

## Controls

Set them before the encoder or the client stream starts. A running encoder or stream does not
reread them.

```powershell
# Server: in the environment inherited by vrserver, before its next encoder is initialized.
$env:ALVR_Q3PW_FRAME_DUMP = 'C:\private\cell-source:32:1'
# Client: before the next stream starts.
adb -s <serial> shell setprop debug.q3pw.frame_dump 128:1
```

- Format: server `directory:count:interval` (split from the right, so drive letters work),
  client `count:interval`. Count 1-128, interval 1-9000.
- Both limits count capture attempts, including readback failures and writer-busy drops.
- The first new frame and every interval-th new frame are selected.
  - The server counts encoder submissions.
  - The client counts fresh selected decoded timestamps; a repeated presentation is not a new
    frame.
  - These counters are local and never pair frames. Use interval 1 on both sides and a longer
    client window; packet loss, supersession and startup delay leave unmatched frames.
- Off: an absent or empty server variable, `debug.q3pw.frame_dump=0` or an absent property.
- HDR swapchains log `[Q3PW_FRAME_DUMP] disabled reason=HDR_unsupported`.

Each encoder or stream writes to its own `server-<time>` or `client-<time>` directory. The client
root is `/sdcard/Android/data/<package>/files/q3pw-dumps/`. The package is the client process's
name, so fork and upstream application ids both work (`io.github.ljk1291.quest3pyrowave` is the
fallback). Collection changes no device setting and removes no device file.

## Files and stages

Each record is `<transported_timestamp_ns>-<stage>.raw` plus `.json`. The `.raw` is uncompressed
and exact at its stage. The sidecar is written only after the raw bytes, and it is the completion
record: `schema=1`, `complete=true`, `timestamp_ns`, local zero-based `frame_index`, `stage`,
`width`, `height`, `format`, `range`, `matrix=bt709`, `row_order`, `bytes`. Rows have no padding.
Pair identity is the transported timestamp (`Duration` on the client, `targetTimestampNs` on the
server), never the XR-clamped display time, discovery order or a nearest timestamp.

| Stage | Side | What it holds |
|---|---|---|
| `encoder_input` | server | The encoder's actual input, read just before `VideoEncoder::Transmit`. PyroWave: its three R8 planes concatenated Y, U, V (`yuv420p` or `yuv444p`, full or limited range). Stock SDR codecs: the texture handed to the encoder (`rgba8` or `bgra8`), before NVENC's own conversion. Rows top-down. Other formats log `readback_failed`. |
| `post_decode` | client | The decoder output the eye pass samples, read before this frame's eye pass imports it. See below. |
| `post_decode_packed` | client | PyroWave modes 5 and 6 only: the packed buffer's raw texels. |
| `presented_left`, `presented_right` | client | The acquired OpenXR eye images after ALVR's eye pass (FFE expansion, YCbCr conversion, gamma, colour correction, upscaling), read before release. Raw GL rows are `bottom_up`. They exclude the runtime's layer filtering, timewarp and optics. |

### What `post_decode` holds

The decoded buffer is read at its own extent, texel for texel: an external-image draw with nearest
filtering at texel centres into an RGBA8 target, then `glReadPixels`. There is no range, gamma, FFE
or YCbCr conversion and no resampling. The AHardwareBuffer gets no CPU-read flags, no lock and no
change to its lease. Rows are in buffer order (texture v = 0 first), `row_order=top_down`.

The client tells the layouts apart the way the eye pass does (`present_ycbcr_layout`): by the
buffer's extent against the decoded size per eye.

- **RGBA buffers** (PyroWave modes 0-4, every MediaCodec frame): `post_decode` is `rgba8` at the
  buffer's extent. MediaCodec's EGL YUV-to-RGB conversion is part of this stage.
- **Packed YCbCr** (PyroWave mode 5, the default for Haar and CDF 5/3 since 2026-10-07, and
  opt-in mode 6): the raw buffer is written as `post_decode_packed`. The writer thread then
  rearranges the same bytes into `post_decode` as `yuv420p`, full range, at the frame's size (both
  eyes). The log says which layout it saw once per change:
  `[Q3PW_FRAME_DUMP] decoded_layout=mode5 buffer=4160x1104 frame=4160x2208`.

### Packed layout (`format=q3pw_ycbcr420_packed`)

The sidecar adds `packing` (`mode5` or `mode6`), `frame_width` and `frame_height`. `width` and
`height` are the buffer's texels. For a frame of W x H pixels (W and H multiples of 4), the buffer
is H/2 rows of RGBA8 texels, as `resources/present_ycbcr.glsl` reads it:

| Texels | Holds |
|---|---|
| x < W/2 | Luma: texel (x, y) holds pixels (2x, 2y), (2x+1, 2y), (2x, 2y+1), (2x+1, 2y+1) in R, G, B, A. |
| mode 5: W/2 <= x < W | 4:2:0 chroma, one pixel per texel: chroma pixel (c, y) is texel W/2 + c, Cb in R, Cr in G. B and A are unused. |
| mode 6: W/2 <= x < 3W/4 | Two chroma pixels per texel: chroma pixel (c, y) is texel W/2 + c/2, (Cb, Cr) in R, G for even c and in B, A for odd c. |

Unpacking to planes (what the writer thread does, `unpack_packed_ycbcr420` in
`alvr/graphics/src/frame_dump.rs`, with a CPU unit test):

```
Y[2y + j][2x + i]      = raw[y][x][i + 2j]                 for x < W/2, i, j in {0, 1}
mode 5: Cb[y][c], Cr[y][c] = raw[y][W/2 + c][0], [1]
mode 6: Cb[y][c], Cr[y][c] = raw[y][W/2 + c/2][2(c&1)], [2(c&1) + 1]
```

The eye pass converts with full-range BT.709 (`Y + 1.5748 Cr`, `Y - 0.1873 Cb - 0.4681 Cr`,
`Y + 1.8556 Cb`, Cb/Cr centred on 0.5), luma at the nearest pixel (bilinear in light-foveation
bands) and chroma bilinear. Both stored forms keep every byte the eye pass can sample; mode 5's
unused chroma B and A bytes are only in `post_decode_packed`.

### Why the packed buffer, not a converted image or the eye output

- The old fork converted mode 5 to RGB in the dump shader. That repeats the eye pass's arithmetic
  with different rounding, so the dump was not exact with respect to what the eye pass reads.
- The packed buffer is exactly what the eye pass samples, and its planar form is a rearrangement of
  the same bytes, so both are lossless.
- After the eye pass is already captured (`presented_*`). It mixes in FFE expansion, filtering,
  gamma and colour correction, so it cannot replace a decoder-output stage.
- The unpack runs on the writer thread, not the render thread. Our scorer
  (`tools/quest3/frame_score.py` in the fork's scorer tree) and `compare_sheet.py` already read
  `yuv420p` records and skip unknown stages such as `post_decode_packed`, so they need no change.

For packed buffers `post_decode` is codec-domain YCbCr: PSNR-Y now compares decoded Y with the
encoder's Y plane directly. RGBA `post_decode` records still measure BT.709 luma of the RGB
output. Compare cells of the same layout only.

## Repeated tracking timestamps

Consecutive frames can carry the same tracking timestamp when no new tracking arrived (TRANSPORT.md:
about 2 % at 1000 Mbps, 8-15 % at 1250 Mbps and 41-45 % at 1500 Mbps over Wi-Fi). Such a timestamp
identifies neither frame.

- The server holds each capture until the next submission's timestamp is known. If it repeats, the
  held capture is discarded (`duplicate_timestamp=1 discarded=1`) and the repeat is not captured
  (`duplicate_timestamp=1 skipped=1`). The last capture of a run is written as captured.
- The client skips a selected frame whose timestamp equals the previous selection's.
- A client capture whose timestamp the server discarded stays unmatched and is not scored.

## Markers

`[Q3PW_FRAME_DUMP]` on both sides (client logcat tag `q3pw_copy`, which bypasses the mirrored-log
filter):

- `enabled count=.. interval=.. synchronous_gpu_readback=1 async_disk=1`
- `disabled reason=..`, `disabled setup_failed=..`, `disabled worker_failed=..`,
  `invalid ALVR_Q3PW_FRAME_DUMP; disabled`, `setup_failed=..; disabled`
- `timestamp_ns=.. encoder_stall_ms=..` (server); `timestamp_ns=.. phase=decode|presented
  client_stall_ms=..` (client, add the two phases)
- `timestamp_ns=.. dropped=writer_busy`, `readback_failed=..`, `presented_readback_failed=..`,
  `unpack_failed=..`
- `timestamp_ns=.. stage=.. write=Ok(())` (client), `stage=encoder_input timestamp_ns=.. written=1`
  (server), `write_failed=..`
- `decoded_layout=rgba8|mode5|mode6 buffer=WxH frame=WxH` (client, new)
- `timestamp_ns=.. duplicate_timestamp=1 discarded=1|skipped=1` (server, new)

## Cost and limits

Off: no allocation, worker thread, GPU readback, file I/O or per-frame property read; the hot paths
check one `Option`. On: selected frames stall the render or encoder thread for a synchronous GPU
readback. Disk writes and the unpack run on a bounded writer: one job may wait while one is being
written, anything more is dropped and logged. Shutdown drains the writer. Capture cells are
quality diagnostics; use capture-free cells for timing.

Storage per client frame at 2080x2208 per eye: packed 18.4 MB, planar 13.8 MB, eyes 36.7 MB
(about 69 MB; 128 frames is about 8.8 GB). Budget the device's storage.

## Verification

- Generated against upstream's ALVR stack at `18d43ce` plus `fork-identity-alvr.patch` and
  `fast-abr.patch` (codex/ur-fast-abr a5fb33b). The three overlays apply in order to a fresh
  reconstruction, reproduce the generating tree exactly and reverse cleanly; `git diff --check` is
  clean. This patch touches no file those two change.
- Rust tests added: the packed unpack and layout detection (CPU, runs in the Windows CI test step),
  the property parser (`frame_dump_config.rs`), and the software-GLES readback and GL-state
  restoration test (Linux only, needs `LIBGL_ALWAYS_SOFTWARE=1`; upstream CI does not run it).
- Not compiled locally (no Rust or C++ toolchain). Not run on a headset.
