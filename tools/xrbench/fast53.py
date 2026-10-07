"""CPU proof of idwt.comp's gather/apron and barrier-free 2x2-pair variant.

Extends WO-6 (codex/wo6-fused-inverse) to literal 2D gather addressing,
FP32/FP16 arithmetic, all shared stores, partial tiles and DCShift. No GPU claim.
Coordinates below are transposed shader coordinates unless labelled native.
"""
import struct


def rounded(value, half=False):
    fmt = 'e' if half else 'f'
    return struct.unpack(fmt, struct.pack(fmt, value))[0]


class Arithmetic:
    def __init__(self, precision):
        self.precision = precision

    def math(self, value):
        return rounded(value, self.precision == 0)

    def store(self, value):
        return rounded(value, self.precision != 2)

    def update(self, low, left, right):
        return self.math(low - self.math(.25 * self.math(left + right)))

    def predict(self, high, left, right):
        return self.math(high + self.math(.5 * self.math(left + right)))


def mirror(index, size):
    index %= 2 * size
    return min(index, 2 * size - 1 - index)


def gather_coordinates(coord, resolution, low):
    """Literal generate_mirror_uv, textureGather, .wxzy; in transposed axes."""
    adjusted = []
    for c, size, even in zip(coord, resolution, low):
        c -= int(even and c < 0)
        c += 1
        c += int(not even and c >= size)
        adjusted.append(c)
    u, v = adjusted
    # Native gather order: (x0,y1), (x1,y1), (x1,y0), (x0,y0).
    native = [(v - 1, u), (v, u), (v, u - 1), (v - 1, u - 1)]
    return [(mirror(native[i][1], resolution[0]), mirror(native[i][0], resolution[1]))
            for i in (3, 0, 2, 1)]


def fast_address(c, size, low):
    if 0 <= c < size:
        return c
    origin = c & ~1
    return mirror(c - int(low and origin < 0) + int(not low and origin + 1 >= size), size)


def apron_tile(bands, group=(0, 0), precision=1, dc=False, extent=None):
    """Literal 20x20-pair gather, first-axis apron lift, transpose, second lift.

    Bands are [layer][native y][native x]. Return native (x,y)->float output.
    The 8x2 and 4x2 kept spans have identical update/predict dependencies.
    """
    a = Arithmetic(precision)
    res = (len(bands[0]), len(bands[0][0]))
    extent = extent or (2 * res[1], 2 * res[0])
    base = (16 * group[0] - 2, 16 * group[1] - 2)
    tile = [[None] * 40 for _ in range(40)]
    for v in range(0, 20, 2):
        for u in range(0, 20, 2):
            for layer in range(4):
                coords = gather_coordinates((base[0] + u, base[1] + v), res,
                                             (layer < 2, layer % 2 == 0))
                for (du, dv), (sy, sx) in zip(((0, 0), (1, 0), (0, 1), (1, 1)), coords):
                    tile[2 * (v + dv) + layer % 2][2 * (u + du) + layer // 2] = a.store(
                        a.math(bands[layer][sy][sx]))

    def lift(line):
        out = []
        for start in range(0, 32, 8):
            values = line[start:start + 16].copy()
            for i in range(2, 15, 2):
                values[i] = a.update(values[i], values[i - 1], values[i + 1])
            for i in range(3, 14, 2):
                values[i] = a.predict(values[i], values[i - 1], values[i + 1])
            out.extend(a.store(v) for v in values[4:12])
        return out

    first = [lift(row) for row in tile]
    out = {}
    for y in range(32):
        column = lift([first[x][y] for x in range(40)])
        for x, value in enumerate(column):
            native = (32 * group[1] + x, 32 * group[0] + y)
            if native[0] < extent[0] and native[1] < extent[1]:
                out[native] = a.math(value + .5) if dc else value
    return out


def fast_tile(bands, group=(0, 0), precision=1, dc=False, extent=None):
    """Independent scalar transcription of fast53_column / inverse_53_pairs."""
    a = Arithmetic(precision)
    res = (len(bands[0]), len(bands[0][0]))
    extent = extent or (2 * res[1], 2 * res[0])

    def fetch(u, v, layer):
        u = fast_address(u, res[0], layer < 2)
        v = fast_address(v, res[1], layer % 2 == 0)
        return a.store(a.math(bands[layer][u][v]))

    def column(u, v, band):
        low = [fetch(u + i, v, band) for i in range(3)]
        high = [fetch(u + i, v, band + 2) for i in range(-1, 3)]
        even = [a.update(low[i], high[i], high[i + 1]) for i in range(3)]
        return [a.store(value) for i in range(2) for value in
                (even[i], a.predict(high[i + 1], even[i], even[i + 1]))]

    out = {}
    for lane in range(64):
        # unswizzle8x8, followed by the shader's 2x2 coefficient blocking.
        u = 16 * group[0] + 2 * (((lane >> 1) & 3) | ((lane >> 5) << 2))
        v = 16 * group[1] + 2 * ((lane & 1) | (((lane >> 3) & 3) << 1))
        if u >= res[0] or v >= res[1]:
            continue
        lows = [column(u, v + i, 0) for i in range(3)]
        highs = [column(u, v + i, 1) for i in range(-1, 3)]
        for y in range(4):
            even = [a.update(lows[i][y], highs[i][y], highs[i + 1][y]) for i in range(3)]
            for i in range(2):
                for dx, value in enumerate((even[i], a.predict(highs[i + 1][y], even[i], even[i + 1]))):
                    pixel = (2 * v + 2 * i + dx, 2 * u + y)
                    if pixel[0] < extent[0] and pixel[1] < extent[1]:
                        assert pixel not in out, 'overlapping invocation output'
                        value = a.store(value)
                        out[pixel] = a.math(value + .5) if dc else value
    return out
