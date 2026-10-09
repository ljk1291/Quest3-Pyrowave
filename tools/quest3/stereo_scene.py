"""Show labelled eyes and orientation markers through SteamVR for Quest screenshot checks.

Run with: python -m tools.quest3.stereo_scene --out <private-output-dir> --seconds 30
Requires: pip install numpy opencv-python openvr glfw PyOpenGL
"""
import argparse
import json
import math
import time
from pathlib import Path


NEUTRAL_RGB_CODES = (0, 16, 32, 64, 128, 192, 235, 255)
REFERENCE_CANVAS_EYE = (2080, 2208)


def render_modules():
    """Keep argument/metadata checks runnable without the optional scene dependencies."""
    import cv2
    import numpy as np
    return cv2, np


def eye_pattern(width, height, label, color, projection, quality=False, neutral_patches=False):
    cv2, np = render_modules()
    image = np.full((height, width, 3), 24, dtype=np.uint8)
    for x in range(0, width, 128):
        cv2.line(image, (x, 0), (x, height - 1), (80, 80, 80), 2)
    for y in range(0, height, 128):
        cv2.line(image, (0, y), (width - 1, y), (80, 80, 80), 2)
    left, right, top, bottom = projection
    cx = int(width * -left / (right - left))
    cy = int(height * -top / (bottom - top))
    cv2.rectangle(image, (cx - 450, cy - 250), (cx + 450, cy + 250), color, -1)
    cv2.putText(image, label, (cx - 300, cy + 40), cv2.FONT_HERSHEY_SIMPLEX, 4, (255, 255, 255), 10)
    cv2.putText(image, 'TOP', (cx - 100, cy - 320), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 6)
    cv2.putText(image, 'BOTTOM', (cx - 160, cy + 400), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 6)
    cv2.arrowedLine(image, (cx - 600, cy), (cx - 850, cy), (0, 255, 255), 12)
    cv2.arrowedLine(image, (cx + 600, cy), (cx + 850, cy), (0, 255, 255), 12)
    if quality:
        # Head-locked high-chroma diagnostics above the separate client overlay.
        x0,y0=cx-650,cy-760
        cv2.rectangle(image,(x0,y0),(cx+650,cy-100),(28,28,28),-1)
        colors=[(0,220,255),(255,255,0),(255,0,255),(0,255,80)]
        for i,c in enumerate(colors):
            y=y0+80+i*100
            cv2.putText(image,'HUD 0123456789 AaBb RGB + HP 100%',(x0+40,y),
                        cv2.FONT_HERSHEY_SIMPLEX,.7+i*.15,c,1,cv2.LINE_8)
            cv2.rectangle(image,(x0+40,y+20),(x0+700,y+38),c,1)
            cv2.line(image,(x0+740,y-25),(x0+1150,y+35),c,1)
        # Red/cyan and blue/yellow edge pairs at several source-pixel widths.
        for i,stripe in enumerate((1,2,4,8)):
            top=y0+490+i*32
            for x in range(x0+40,x0+1240,stripe):
                c=(0,0,255) if ((x-x0-40)//stripe)%2==0 else (255,255,0)
                cv2.rectangle(image,(x,top),(x+stripe-1,top+20),c,-1)
    if neutral_patches:
        # The Session 07 range chart: source pixels are neutral full-range RGB codes.
        x0, y0 = cx - 640, cy + 560
        for index, value in enumerate(NEUTRAL_RGB_CODES):
            x = x0 + index * 160
            cv2.rectangle(image, (x, y0), (x + 159, y0 + 180), (value, value, value), -1)
            cv2.putText(image, str(value), (x + 15, y0 - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(image, 'Full-range neutral RGB patches', (x0, y0 + 245),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    return image


def flat_field(width, height, code):
    """A label-free deterministic neutral full field for panel comparison."""
    _, np = render_modules()
    return np.full((height, width, 3), code, dtype=np.uint8)


def normalized_eye_pattern(width, height, label, color, projection, quality=False, neutral_patches=False):
    """Render the legacy chart in a fixed reference canvas, scaled into this eye texture."""
    cv2, np = render_modules()
    reference_width, reference_height = REFERENCE_CANVAS_EYE
    scale_x, scale_y = width / reference_width, height / reference_height
    scale_font = min(scale_x, scale_y)

    def point(x, y):
        return (round(x * scale_x), round(y * scale_y))

    def thickness(value):
        return max(1, round(value * scale_font))

    image = np.full((height, width, 3), 24, dtype=np.uint8)
    for x in range(0, reference_width, 128):
        cv2.line(image, point(x, 0), point(x, reference_height - 1), (80, 80, 80), thickness(2))
    for y in range(0, reference_height, 128):
        cv2.line(image, point(0, y), point(reference_width - 1, y), (80, 80, 80), thickness(2))
    left, right, top, bottom = projection
    cx = int(reference_width * -left / (right - left))
    cy = int(reference_height * -top / (bottom - top))
    cv2.rectangle(image, point(cx - 450, cy - 250), point(cx + 450, cy + 250), color, -1)
    cv2.putText(image, label, point(cx - 300, cy + 40), cv2.FONT_HERSHEY_SIMPLEX,
                4 * scale_font, (255, 255, 255), thickness(10))
    cv2.putText(image, 'TOP', point(cx - 100, cy - 320), cv2.FONT_HERSHEY_SIMPLEX,
                2 * scale_font, (255, 255, 255), thickness(6))
    cv2.putText(image, 'BOTTOM', point(cx - 160, cy + 400), cv2.FONT_HERSHEY_SIMPLEX,
                2 * scale_font, (255, 255, 255), thickness(6))
    cv2.arrowedLine(image, point(cx - 600, cy), point(cx - 850, cy), (0, 255, 255), thickness(12))
    cv2.arrowedLine(image, point(cx + 600, cy), point(cx + 850, cy), (0, 255, 255), thickness(12))
    if quality:
        x0, y0 = cx - 650, cy - 760
        cv2.rectangle(image, point(x0, y0), point(cx + 650, cy - 100), (28, 28, 28), -1)
        colors = [(0, 220, 255), (255, 255, 0), (255, 0, 255), (0, 255, 80)]
        for i, color_value in enumerate(colors):
            y = y0 + 80 + i * 100
            cv2.putText(image, 'HUD 0123456789 AaBb RGB + HP 100%', point(x0 + 40, y),
                        cv2.FONT_HERSHEY_SIMPLEX, (.7 + i * .15) * scale_font,
                        color_value, thickness(1), cv2.LINE_8)
            cv2.rectangle(image, point(x0 + 40, y + 20), point(x0 + 700, y + 38), color_value, thickness(1))
            cv2.line(image, point(x0 + 740, y - 25), point(x0 + 1150, y + 35), color_value, thickness(1))
        for i, stripe in enumerate((1, 2, 4, 8)):
            top = y0 + 490 + i * 32
            for x in range(x0 + 40, x0 + 1240, stripe):
                color_value = (0, 0, 255) if ((x - x0 - 40) // stripe) % 2 == 0 else (255, 255, 0)
                cv2.rectangle(image, point(x, top), point(x + stripe - 1, top + 20), color_value, -1)
    if neutral_patches:
        x0, y0 = cx - 640, cy + 560
        for index, value in enumerate(NEUTRAL_RGB_CODES):
            x = x0 + index * 160
            cv2.rectangle(image, point(x, y0), point(x + 159, y0 + 180), (value, value, value), -1)
            cv2.putText(image, str(value), point(x + 15, y0 - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, scale_font, (255, 255, 255), thickness(2))
        cv2.putText(image, 'Full-range neutral RGB patches', point(x0, y0 + 245),
                    cv2.FONT_HERSHEY_SIMPLEX, scale_font, (255, 255, 255), thickness(2))
    return image


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--seconds', type=float, default=30)
    chart = parser.add_mutually_exclusive_group()
    chart.add_argument('--quality', action='store_true', help='Add fine colored HUD text and saturated edge diagnostics')
    chart.add_argument('--neutral-patches', action='store_true',
                       help='Add labelled full-range neutral RGB patches used for range checks')
    chart.add_argument('--flat', type=int, metavar='RGB_CODE',
                       help='Submit a label-free neutral full field with one 8-bit RGB code (0-255)')
    parser.add_argument('--normalized-chart', action='store_true',
                        help='Scale the legacy 2080x2208 reference canvas into the selected source-eye texture')
    parser.add_argument('--source-eye', type=int, nargs=2, metavar=('WIDTH', 'HEIGHT'),
                        help='Pin source-eye texture geometry instead of querying SteamVR')
    parser.add_argument('--pulse', action='store_true', help='Add a changing 10 Hz counter to detect stale imported pixels; separate from FPS measurement')
    parser.add_argument('--stop-file', type=Path, help='End gracefully when this file appears; duration remains a hard limit')
    parser.add_argument('--sway', type=float, default=0, metavar='PIXELS',
                        help='Move the whole chart smoothly (sub-pixel, bilinear): PIXELS horizontal amplitude over 1.2 s, '
                             'half that vertically over 1.7 s. Gives inter-frame codecs real motion to code.')
    parser.add_argument('--image', nargs='+', type=Path, metavar='PNG',
                        help='Submit this image (one for both eyes, or LEFT RIGHT), area-resized to the source eye, '
                             'instead of the chart; --quality/--normalized-chart/--pulse are then ignored (2026-10-08)')
    parser.add_argument('--jitter', type=float, default=0, metavar='PIXELS',
                        help='Head-tremor-like motion: per-frame AR(1) random sub-pixel translation with this standard '
                             'deviation (correlation 0.9 per frame), so an intra codec re-decides every frame (2026-10-08)')
    parser.add_argument('--seed', type=int, default=1, help='Random seed for --jitter')
    parser.add_argument('--bench', action='store_true', help='Deterministic benchmark; ignores legacy chart/pulse/motion flags')
    parser.add_argument('--bench-seed', type=int, default=1)
    parser.add_argument('--bench-motion', choices=('none', 'mix', 'static', 'tremor', 'jitter', 'pan', 'turn'), default='mix')
    parser.add_argument('--bench-assets', type=Path)
    parser.add_argument('--bench-layout', choices=('cards', 'metro'), default='cards')
    parser.add_argument('--bench-scale', type=float, default=1.)
    parser.add_argument('--bench-backdrop', choices=('metro','mosaic','none'))
    parser.add_argument('--bench-backdrop-asset', type=Path)
    parser.add_argument('--bench-backdrop-fov', type=float, nargs=4)
    parser.add_argument('--bench-panel', choices=('on','off'), default='on')
    parser.add_argument('--bench-backdrop-filter', choices=('default', 'ss4', 'cubic4'), default='default')
    parser.add_argument('--bench-recenter-file', type=Path)
    parser.add_argument('--bench-calibration', choices=('full-eye-5x5-v1',))
    return parser


def validate_args(parser, args):
    if not 1 <= args.seconds <= 600:
        parser.error('Use 1-600 seconds')
    if args.flat is not None and not 0 <= args.flat <= 255:
        parser.error('--flat RGB_CODE must be in the 8-bit range 0-255')
    if args.flat is not None and args.pulse:
        parser.error('--flat and --pulse cannot be combined: a pulse makes the field non-uniform')
    if args.flat is not None and args.normalized_chart:
        parser.error('--flat and --normalized-chart cannot be combined: normalization has no effect on a full field')
    if args.source_eye and any(value <= 0 for value in args.source_eye):
        parser.error('--source-eye WIDTH HEIGHT must both be positive')
    if args.stop_file and args.stop_file.exists():
        parser.error('Stop file already exists; use a fresh path')
    if not 0 <= args.sway <= 512:
        parser.error('--sway must be 0-512 pixels')
    if not 0 <= args.jitter <= 16:
        parser.error('--jitter must be 0-16 pixels')
    if args.image and (len(args.image) > 2 or not all(p.is_file() for p in args.image)):
        parser.error('--image takes one or two existing image files')
    if args.bench and (not math.isfinite(args.bench_scale) or not 0 <= args.bench_scale <= 1):
        parser.error('--bench-scale must be finite in [0,1]')
    if args.bench_calibration and not args.bench:
        parser.error('--bench-calibration requires --bench')
    return args


def scene_metadata(args, width, height, projections):
    return {
        'source_eye_size': [width, height],
        'quality_chart': args.quality,
        'neutral_patch_chart': args.neutral_patches,
        'flat_rgb_code': args.flat,
        'source_neutral_rgb_codes': list(NEUTRAL_RGB_CODES) if args.neutral_patches else
                                    ([args.flat] if args.flat is not None else []),
        'normalized_chart': args.normalized_chart,
        'reference_canvas_eye': list(REFERENCE_CANVAS_EYE) if args.normalized_chart else None,
        'pulse': args.pulse,
        'sway_pixels': args.sway,
        'jitter_pixels': args.jitter,
        'image': [str(p) for p in args.image] if args.image else None,
        'projections': projections,
    }


def bench_pose_step(scene, pose, elapsed, request=None):
    """One live-loop pose: (real_pose, recenter_event) for a valid pose, None to skip the frame.

    A skipped pose resets the pending startup yaw-mismatch timer, so the automatic
    recenter only follows a mismatch that stayed continuous (valid poses throughout).
    """
    if not pose.bPoseIsValid:
        scene.tracking_lost()
        return None
    from tools.quest3.bench_scene import pose_matrix
    real_pose = pose_matrix(pose.mDeviceToAbsoluteTracking.m)
    return real_pose, scene.maybe_recenter(real_pose, elapsed, request)


def run_bench(args, root, system, compositor, width, height, GL, openvr):
    """World-locked planar menu. Only small barcode/pose data changes per frame."""
    from tools.quest3.bench_scene import BenchScene, CalibrationScene, PERIOD, SUPERSAMPLE, SURROUND, pose_matrix, panel_anchor, projection_raw, backdrop_arguments
    _, np = render_modules()
    eyes = (openvr.Eye_Left, openvr.Eye_Right)
    raw = [list(system.getProjectionRaw(eye)) for eye in eyes]
    projections = [projection_raw(p) for p in raw]
    eye_poses = [pose_matrix(system.getEyeToHeadTransform(eye).m) for eye in eyes]
    poses = (openvr.TrackedDevicePose_t * openvr.k_unMaxTrackedDeviceCount)()
    compositor.waitGetPoses(poses, None)
    if not poses[openvr.k_unTrackedDeviceIndex_Hmd].bPoseIsValid:
        raise RuntimeError('Valid initial HMD render pose required to anchor benchmark panel')
    initial = pose_matrix(poses[openvr.k_unTrackedDeviceIndex_Hmd].mDeviceToAbsoluteTracking.m)
    calibration = bool(args.bench_calibration)
    scene_type = CalibrationScene if calibration else BenchScene
    scene = scene_type(args.bench_seed, (width, height), args.bench_motion, args.bench_scale, args.bench_assets,
                       layout=args.bench_layout, projections=projections, eye_to_head=eye_poses, anchor=panel_anchor(initial), **backdrop_arguments(args))
    scene.frame_records[0] = scene.frame_geometry(0, initial)  # startup preview only; frame 0 is logged from its later render pose
    scene.save(root)
    scene.frame_records.clear()
    scene.live = True
    from tools.quest3.bench_scene import write_json
    write_json(root/'bench.json', scene.metadata())
    print('[Q3PW_BENCH] active=1 world_locked=%d seed=%d motion=%s layout=%s period=%d' %
          (int(not calibration), args.bench_seed, scene.motion, scene.layout, PERIOD), flush=True)
    if calibration:
        print(f'[Q3PW_BENCH_CALIBRATION] mode={scene.layout} layout_sha256={scene.layout_hash} head_locked=1', flush=True)
    print(f'[Q3PW_BENCH_BACKDROP] mode={scene.backdrop_kind} panel={scene.panel_mode} mosaic={int(scene.backdrop_kind == "mosaic")}', flush=True)
    print(f'[Q3PW_BENCH_FILTER] mode={scene.backdrop_filter}', flush=True)

    def upload(pixels, size, levels=None):
        texture = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR_MIPMAP_LINEAR if levels else GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        for name in (GL.GL_TEXTURE_WRAP_S, GL.GL_TEXTURE_WRAP_T):
            GL.glTexParameteri(GL.GL_TEXTURE_2D, name, GL.GL_CLAMP_TO_EDGE)
        for level, data in enumerate(levels or [pixels]):
            extent = (data.shape[1], data.shape[0]) if data is not None else size
            GL.glTexImage2D(GL.GL_TEXTURE_2D, level, GL.GL_RGBA8, *extent, 0, GL.GL_RGB, GL.GL_UNSIGNED_BYTE,
                            np.rint(data).astype(np.uint8) if data is not None else None)
        if levels:
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAX_LEVEL, len(levels)-1)
        return texture

    def target(size):
        texture = upload(None, size)
        fbo = GL.glGenFramebuffers(1)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
        GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_TEXTURE_2D, texture, 0)
        if GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER) != GL.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError('Bench framebuffer incomplete')
        return texture, fbo

    panel = None if calibration else upload(scene.panel, scene.panel_size, scene.mips)
    backdrop = upload(scene.backdrop.image,scene.backdrop.size,scene.backdrop.mips) if scene.backdrop else None
    cubic_program = None
    if scene.backdrop_filter == 'cubic4' and scene.backdrop:
        from tools.quest3.bench_filter import program
        cubic_program = program(GL, len(scene.backdrop.mips))
    x, y, bw, bh = scene.barcode_box
    barcode = upload(scene.barcode_patch(0), (bw, bh))
    large = tuple(v*4 if scene.backdrop_filter != 'default' else round(v*SUPERSAMPLE) for v in scene.size)
    render_fbo = None if calibration else target(large)[1]
    half = target(tuple(v*2 for v in scene.size)) if scene.backdrop_filter != 'default' else None
    # Direct source-eye uploads preserve exact CPU pixels. Only the barcode
    # changes per frame; there is no pose transform, mip or FBO resolve here.
    targets = ([(upload(scene.panel_frame(0), scene.size), None) for _ in eyes]
               if calibration else [target(scene.size) for _ in eyes])
    textures = []
    for texture, _ in targets:
        vr = openvr.Texture_t()
        vr.handle, vr.eType, vr.eColorSpace = int(texture), openvr.TextureType_OpenGL, openvr.ColorSpace_Gamma
        textures.append(vr)
    # FBO has conventional GL +Y up. Unlike legacy CPU uploads it needs no flip.
    bounds = openvr.VRTextureBounds_t()
    bounds.uMin, bounds.uMax, bounds.vMin, bounds.vMax = 0, 1, 0, 1
    if calibration:
        bounds.vMin, bounds.vMax = 1, 0  # top-down upload, as in the legacy CPU path
    GL.glEnable(GL.GL_TEXTURE_2D)
    GL.glDisable(GL.GL_BLEND)
    GL.glDisable(GL.GL_DEPTH_TEST)
    GL.glDisable(GL.GL_FRAMEBUFFER_SRGB)
    GL.glClearColor(SURROUND/255, SURROUND/255, SURROUND/255, 1)
    GL.glMatrixMode(GL.GL_MODELVIEW)
    GL.glLoadIdentity()

    def quad(texture, box, size=None, metres=None):
        px, py, pw, ph = box
        w, h = size or scene.panel_size
        mw, mh = metres or scene.panel_metres
        GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
        GL.glBegin(GL.GL_QUADS)
        for u, v in ((0,0), (1,0), (1,1), (0,1)):
            GL.glTexCoord2f(u, v)
            GL.glVertex3f(((px+u*pw)/w-.5)*mw, (.5-(py+v*ph)/h)*mh, 0)
        GL.glEnd()

    ready = scene_metadata(args, width, height, raw)
    ready.update(bench=scene.metadata(), quality_chart=False, normalized_chart=False, pulse=False,
                 sway_pixels=0, jitter_pixels=0, reference_canvas_eye=list(scene.panel_size))
    frames = 0
    start = time.monotonic()
    ready['started_unix_ns'] = time.time_ns()
    (root/'ready.json').write_text(json.dumps(ready), encoding='utf-8')
    log = (root/'frames.ndjson').open('w', encoding='utf-8', buffering=1024*1024)
    try:
        while time.monotonic()-start < args.seconds and not (args.stop_file and args.stop_file.exists()):
            compositor.waitGetPoses(poses, None)
            step = bench_pose_step(scene, poses[openvr.k_unTrackedDeviceIndex_Hmd], time.monotonic()-start, args.bench_recenter_file)
            if step is None:
                continue  # never submit using an old pose
            real_pose, event = step
            geometry = scene.frame_geometry(frames, real_pose)
            if event:
                geometry['recenter'] = event
                print('[Q3PW_BENCH_RECENTER] '+json.dumps(event), flush=True)
            geometry['render_unix_ns'] = time.time_ns()
            GL.glBindTexture(GL.GL_TEXTURE_2D, barcode)
            GL.glTexSubImage2D(GL.GL_TEXTURE_2D, 0, 0, 0, bw, bh, GL.GL_RGB, GL.GL_UNSIGNED_BYTE, scene.barcode_patch(frames))
            for n, eye in enumerate(eyes):
                if calibration:
                    GL.glBindTexture(GL.GL_TEXTURE_2D, targets[n][0])
                    GL.glTexSubImage2D(GL.GL_TEXTURE_2D, 0, x, y, bw, bh, GL.GL_RGB, GL.GL_UNSIGNED_BYTE, scene.barcode_patch(frames))
                    compositor.submit(eye, textures[n], bounds)
                    continue
                GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, render_fbo)
                GL.glViewport(0, 0, *large)
                GL.glClear(GL.GL_COLOR_BUFFER_BIT)
                GL.glMatrixMode(GL.GL_PROJECTION)
                vp = np.array(geometry['eyes'][n]['view_projection'])
                if backdrop is not None:
                    b = scene.backdrop
                    GL.glLoadMatrixf(np.ascontiguousarray((vp @ b.anchor).T,dtype=np.float32))
                    if cubic_program is not None: GL.glUseProgram(cubic_program)
                    quad(backdrop,(0,0,*b.size),b.size,b.metres)
                    if cubic_program is not None: GL.glUseProgram(0)
                matrix = vp @ scene.content_anchor
                GL.glLoadMatrixf(np.ascontiguousarray(matrix.T, dtype=np.float32))
                quad(panel, (0, 0, *scene.panel_size))
                quad(barcode, scene.barcode_box)
                GL.glBindFramebuffer(GL.GL_READ_FRAMEBUFFER, render_fbo)
                if half is not None:
                    GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, half[1])
                    GL.glBlitFramebuffer(0, 0, *large, 0, 0, width*2, height*2, GL.GL_COLOR_BUFFER_BIT, GL.GL_LINEAR)
                    GL.glBindFramebuffer(GL.GL_READ_FRAMEBUFFER, half[1])
                GL.glBindFramebuffer(GL.GL_DRAW_FRAMEBUFFER, targets[n][1])
                GL.glBlitFramebuffer(0, 0, *(tuple(v*2 for v in scene.size) if half is not None else large), 0, 0, width, height, GL.GL_COLOR_BUFFER_BIT, GL.GL_LINEAR)
                GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
                compositor.submit(eye, textures[n], bounds)
            GL.glFlush()
            log.write(json.dumps(geometry, separators=(',', ':'), allow_nan=False)+'\n')
            frames += 1
            if frames % 90 == 0: log.flush()
    finally:
        log.close()
        if cubic_program is not None: GL.glDeleteProgram(cubic_program)
        result = {**ready, 'frames_submitted': frames, 'seconds': time.monotonic()-start,
                  'ended_unix_ns': time.time_ns(), 'pulse_events': [],
                  'stop_reason': 'stop_file' if args.stop_file and args.stop_file.exists() else 'duration',
                  'note': 'Submission count is not decoded or displayed frame rate.'}
        (root/'scene.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result))


def main():
    import glfw
    import openvr
    from OpenGL import GL
    cv2, np = render_modules()
    parser = build_parser()
    args = validate_args(parser, parser.parse_args())
    root = Path(args.out); root.mkdir(parents=True, exist_ok=True)
    window = None
    system = openvr.init(openvr.VRApplication_Scene)
    try:
        if not glfw.init():
            raise RuntimeError('GLFW initialization failed')
        glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
        window = glfw.create_window(64, 64, 'Quest3 PyroWave stereo check', None, None)
        if not window:
            raise RuntimeError('GLFW context creation failed')
        glfw.make_context_current(window)
        compositor = openvr.VRCompositor()
        width, height = args.source_eye or system.getRecommendedRenderTargetSize()
        if args.bench:
            return run_bench(args, root, system, compositor, width, height, GL, openvr)
        textures = []
        pulse_textures = []
        sway_targets = []
        projections = []
        for eye, label, color in [(openvr.Eye_Left, 'LEFT', (32, 32, 200)),
                                  (openvr.Eye_Right, 'RIGHT', (200, 64, 32))]:
            projection = system.getProjectionRaw(eye); projections.append(projection)
            if args.image:
                path = args.image[min(len(textures), len(args.image) - 1)]
                image = cv2.resize(cv2.imread(str(path), cv2.IMREAD_COLOR), (width, height),
                                   interpolation=cv2.INTER_AREA)
            elif args.flat is not None:
                image = flat_field(width, height, args.flat)
            elif args.normalized_chart:
                image = normalized_eye_pattern(width, height, label, color, projection,
                                               args.quality, args.neutral_patches)
            else:
                image = eye_pattern(width, height, label, color, projection,
                                    args.quality, args.neutral_patches)
            cv2.imwrite(str(root / f'{label.lower()}-reference.png'), image)
            texture = GL.glGenTextures(1)
            GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
            GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
            GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, width, height, 0,
                            GL.GL_RGB, GL.GL_UNSIGNED_BYTE, np.ascontiguousarray(image[:, :, ::-1]))
            submitted = texture
            if args.sway or args.jitter:
                # Draw the chart through an FBO with shifted, wrapping texture coordinates each frame.
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_REPEAT)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_REPEAT)
                submitted = GL.glGenTextures(1)
                GL.glBindTexture(GL.GL_TEXTURE_2D, submitted)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
                GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
                GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, width, height, 0,
                                GL.GL_RGB, GL.GL_UNSIGNED_BYTE, None)
                fbo = GL.glGenFramebuffers(1)
                GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
                GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_TEXTURE_2D, submitted, 0)
                if GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER) != GL.GL_FRAMEBUFFER_COMPLETE:
                    raise RuntimeError('Sway framebuffer incomplete')
                GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
                sway_targets.append((texture, fbo))
            vr_texture = openvr.Texture_t()
            vr_texture.handle = int(submitted)
            vr_texture.eType = openvr.TextureType_OpenGL
            vr_texture.eColorSpace = openvr.ColorSpace_Gamma
            textures.append((eye, vr_texture))
            left, right, top, bottom = projection
            cx = int(width * -left / (right - left))
            cy = int(height * -top / (bottom - top))
            pulse_textures.append((texture, max(0, min(width - 512, cx - 256)),
                                   max(0, min(height - 112, cy - 950))))
        GL.glFinish()
        bounds = openvr.VRTextureBounds_t()
        bounds.uMin, bounds.uMax, bounds.vMin, bounds.vMax = 0, 1, 1, 0
        poses = (openvr.TrackedDevicePose_t * openvr.k_unMaxTrackedDeviceCount)()
        frames = 0; start = time.monotonic(); started_unix_ns = time.time_ns()
        pulse_tick = -1; pulse_events = []
        rng = np.random.default_rng(args.seed); jx = jy = 0.0
        ready = scene_metadata(args, width, height, projections)
        ready['started_unix_ns'] = started_unix_ns
        (root / 'ready.json').write_text(json.dumps(ready), encoding='utf-8')
        while time.monotonic() - start < args.seconds and not (args.stop_file and args.stop_file.exists()):
            compositor.waitGetPoses(poses, None)
            if args.pulse and not args.image:
                tick = int((time.monotonic() - start) * 10)
                if tick != pulse_tick:
                    pulse_tick = tick
                    patch = np.full((112, 512, 3), (0, 96, 160 if tick % 20 < 10 else 0), dtype=np.uint8)
                    cv2.putText(patch, f'T{tick:06d}', (20, 78), cv2.FONT_HERSHEY_SIMPLEX,
                                2, (255, 255, 255), 4, cv2.LINE_8)
                    for texture, x, y in pulse_textures:
                        GL.glBindTexture(GL.GL_TEXTURE_2D, texture)
                        GL.glTexSubImage2D(GL.GL_TEXTURE_2D, 0, x, y, 512, 112,
                                          GL.GL_RGB, GL.GL_UNSIGNED_BYTE, patch)
                    pulse_events.append({'tick':tick, 'uploaded_unix_ns':time.time_ns()})
            if sway_targets:
                t = time.monotonic() - start
                du = args.sway * math.sin(2 * math.pi * t / 1.2) / width
                dv = 0.5 * args.sway * math.sin(2 * math.pi * t / 1.7) / height
                if args.jitter:
                    jx = 0.9 * jx + args.jitter * math.sqrt(1 - 0.81) * rng.standard_normal()
                    jy = 0.9 * jy + args.jitter * math.sqrt(1 - 0.81) * rng.standard_normal()
                    du += jx / width; dv += jy / height
                GL.glViewport(0, 0, width, height)
                GL.glEnable(GL.GL_TEXTURE_2D)
                for source, fbo in sway_targets:
                    GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
                    GL.glBindTexture(GL.GL_TEXTURE_2D, source)
                    GL.glBegin(GL.GL_QUADS)
                    for u, v, x, y in ((0, 0, -1, -1), (1, 0, 1, -1), (1, 1, 1, 1), (0, 1, -1, 1)):
                        GL.glTexCoord2f(u + du, v + dv)
                        GL.glVertex2f(x, y)
                    GL.glEnd()
                GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
            for eye, texture in textures:
                compositor.submit(eye, texture, bounds)
            GL.glFlush(); frames += 1
        result = {'frames_submitted': frames, 'seconds': time.monotonic() - start,
                  'started_unix_ns':started_unix_ns,'ended_unix_ns':time.time_ns(),
                  'left_label': None if args.flat is not None else 'LEFT',
                  'right_label': None if args.flat is not None else 'RIGHT',
                  'pulse_events':pulse_events,
                  'stop_reason': 'stop_file' if args.stop_file and args.stop_file.exists() else 'duration',
                  'note': 'Submission count is not decoded or displayed frame rate.'}
        result.update(scene_metadata(args, width, height, projections))
        (root / 'scene.json').write_text(json.dumps(result, indent=2))
        print(json.dumps(result))
    finally:
        openvr.shutdown()
        if window:
            glfw.destroy_window(window)
        glfw.terminate()


if __name__ == '__main__':
    main()
