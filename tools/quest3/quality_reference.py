"""CPU reference for opt-in area downscale and ordered R8 quantization.

These checks establish filter arithmetic, not headset quality or shader execution.
"""
import math

BAYER4 = (0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5)


def axis_weights(centre, footprint, lower_pixel, upper_pixel):
    """Area overlap with texel cells, clamped to one submitted eye crop."""
    if not all(math.isfinite(v) for v in (centre, footprint)) or not 1 <= footprint <= 4:
        raise ValueError('finite footprint in [1,4] required')
    if lower_pixel > upper_pixel:
        raise ValueError('empty eye bounds')
    lo, hi = centre - footprint / 2, centre + footprint / 2
    first = math.floor(lo)
    weights = {}
    for at in range(first, first + 5):
        w = max(0.0, min(hi, at + 1) - max(lo, at))
        if w:
            pixel = min(max(at, lower_pixel), upper_pixel)
            weights[pixel] = weights.get(pixel, 0) + w / footprint
    return weights


def area_box(image, centre, footprint, bounds):
    """Linear-light scalar sample; x/y weights form a separable area box."""
    min_x, min_y, max_x, max_y = bounds
    xs = axis_weights(centre[0], footprint[0], min_x, max_x)
    ys = axis_weights(centre[1], footprint[1], min_y, max_y)
    return sum(image[y][x] * wy * wx for y, wy in ys.items() for x, wx in xs.items())


def dither_offset(x, y):
    return ((BAYER4[(y % 4) * 4 + x % 4] + .5) / 16 - .5) / 255


def quantize_r8(value, x=0, y=0, dither=False):
    if not math.isfinite(value):
        raise ValueError('finite plane value required')
    value += dither_offset(x, y) if dither else 0
    return math.floor(min(1, max(0, value)) * 255 + .5)
