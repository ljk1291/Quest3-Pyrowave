"""Show labelled eyes and orientation markers through SteamVR for Quest screenshot checks.

Run with: python -m tools.quest3.stereo_scene --out <private-output-dir> --seconds 30
Requires: pip install numpy opencv-python openvr glfw PyOpenGL
"""
import argparse
import json
import time
from pathlib import Path


NEUTRAL_RGB_CODES = (0, 16, 32, 64, 128, 192, 235, 255)
REFERENCE_CANVAS_EYE = (2080, 2208)
QUALITY_ORIGIN = (-650, -760)
QUALITY_LINE_BOX = (740, 55, 411, 361)
QUALITY_STRIPE_BOX = (40, 490, 1200, 117)


def quality_regions(width, height, projection, normalized=True):
    """Eye-local pixel boxes from the same geometry as the quality chart.

    Caller must supply the projection of the captured coordinate domain. Packed
    foveation is nonlinear: these rectangles cannot simply be scaled into it.
    """
    import math
    left, right, top, bottom = projection
    if not all(math.isfinite(v) for v in projection) or not (left < 0 < right and top < 0 < bottom):
        raise ValueError('chart projection must straddle the optical axis')
    rw, rh = REFERENCE_CANVAS_EYE if normalized else (width, height)
    cx, cy = int(rw * -left / (right-left)), int(rh * -top / (bottom-top))
    x0, y0 = cx + QUALITY_ORIGIN[0], cy + QUALITY_ORIGIN[1]
    result = {}
    for name, (x, y, w, h) in [('chart_lines', QUALITY_LINE_BOX), ('chart_stripes', QUALITY_STRIPE_BOX)]:
        a, b, c, d = round((x0+x)*width/rw), round((y0+y)*height/rh), round((x0+x+w)*width/rw), round((y0+y+h)*height/rh)
        if not (0 <= a < c <= width and 0 <= b < d <= height):
            raise ValueError(f'{name} falls outside captured eye; provide mapped crops')
        result[name] = (a, b, c-a, d-b)
    return result


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
        x0,y0=cx+QUALITY_ORIGIN[0],cy+QUALITY_ORIGIN[1]
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
        x0, y0 = cx + QUALITY_ORIGIN[0], cy + QUALITY_ORIGIN[1]
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
        'projections': projections,
    }


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
        textures = []
        pulse_textures = []
        projections = []
        for eye, label, color in [(openvr.Eye_Left, 'LEFT', (32, 32, 200)),
                                  (openvr.Eye_Right, 'RIGHT', (200, 64, 32))]:
            projection = system.getProjectionRaw(eye); projections.append(projection)
            if args.flat is not None:
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
            vr_texture = openvr.Texture_t()
            vr_texture.handle = int(texture)
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
        ready = scene_metadata(args, width, height, projections)
        ready['started_unix_ns'] = started_unix_ns
        (root / 'ready.json').write_text(json.dumps(ready), encoding='utf-8')
        while time.monotonic() - start < args.seconds and not (args.stop_file and args.stop_file.exists()):
            compositor.waitGetPoses(poses, None)
            if args.pulse:
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
