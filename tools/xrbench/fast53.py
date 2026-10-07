"""CPU proof of idwt.comp's gather/apron and barrier-free pair-local variants.

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


def blocked_tile(bands, group=(0, 0), precision=1, dc=False, extent=None, variant=2, counts=None):
    """4x4-pair v2/v3 model; count texture instructions, including edge overfetch.

    A workgroup now covers 32x32 coefficient pairs. First-axis stored columns
    round before horizontal updates; updated horizontal evens never narrow.
    v3 loads column pairs in the shader's dependency order, using .wxzy lanes.
    """
    if variant not in (2, 3):
        raise ValueError('blocked variant must be 2 or 3')
    a = Arithmetic(precision)
    res = (len(bands[0]), len(bands[0][0]))
    extent = extent or (2 * res[1], 2 * res[0])
    counts = counts if counts is not None else {}

    def fetch(u, v, layer):
        counts['fetch'] = counts.get('fetch', 0) + 1
        u = fast_address(u, res[0], layer < 2)
        v = fast_address(v, res[1], layer % 2 == 0)
        return a.store(a.math(bands[layer][u][v]))

    def gather(u, v, layer):
        counts['gather'] = counts.get('gather', 0) + 1
        coords = gather_coordinates((u, v), res, (layer < 2, layer % 2 == 0))
        return [a.store(a.math(bands[layer][sy][sx])) for sy, sx in coords]

    def column(u, v, band):
        # fast53_column8 + four stateful fast53_next_pair calls.
        previous, high = fetch(u - 1, v, band + 2), fetch(u, v, band + 2)
        even = a.update(fetch(u, v, band), previous, high)
        out = []
        for i in range(1, 5):
            next_high = fetch(u + i, v, band + 2)
            next_even = a.update(fetch(u + i, v, band), high, next_high)
            out.extend((a.store(even), a.store(a.predict(high, even, next_even))))
            high, even = next_high, next_even
        return out

    def gather_columns(u, v, band):
        low01 = gather(u, v, band)
        highm0 = gather(u - 1, v, band + 2)
        high12 = gather(u + 1, v, band + 2)
        low23 = gather(u + 2, v, band)
        high34 = gather(u + 3, v, band + 2)
        low45 = gather(u + 4, v, band)
        out = []
        for lane in (0, 2):  # .xy are first column; .zw are its neighbour
            e0 = a.update(low01[lane], highm0[lane], highm0[lane + 1])
            e1 = a.update(low01[lane + 1], highm0[lane + 1], high12[lane])
            e2 = a.update(low23[lane], high12[lane], high12[lane + 1])
            e3 = a.update(low23[lane + 1], high12[lane + 1], high34[lane])
            e4 = a.update(low45[lane], high34[lane], high34[lane + 1])
            values = (e0, a.predict(highm0[lane + 1], e0, e1),
                      e1, a.predict(high12[lane], e1, e2),
                      e2, a.predict(high12[lane + 1], e2, e3),
                      e3, a.predict(high34[lane], e3, e4))
            out.append([a.store(value) for value in values])
        return out

    output = {}
    for lane in range(64):
        u = 32 * group[0] + 4 * (((lane >> 1) & 3) | ((lane >> 5) << 2))
        v = 32 * group[1] + 4 * ((lane & 1) | (((lane >> 3) & 3) << 1))
        if u >= res[0] or v >= res[1]:
            continue
        counts['invocations'] = counts.get('invocations', 0) + 1
        low, high = {}, {}
        if variant == 3:
            for offset, band in ((0, 0), (-1, 1), (1, 1), (2, 0), (3, 1), (4, 0)):
                cols = gather_columns(u, v + offset, band)
                target = high if band else low
                target[offset], target[offset + 1] = cols
        else:
            high[-1], high[0] = column(u, v - 1, 1), column(u, v, 1)
            low[0] = column(u, v, 0)
        even = [a.update(low[0][y], high[-1][y], high[0][y]) for y in range(8)]
        for x in range(4):
            if variant == 2:
                high[x + 1] = column(u, v + x + 1, 1)
                low[x + 1] = column(u, v + x + 1, 0)
            next_even = [a.update(low[x + 1][y], high[x][y], high[x + 1][y]) for y in range(8)]
            for y in range(8):
                odd = a.predict(high[x][y], even[y], next_even[y])
                for dx, value in enumerate((even[y], odd)):
                    pixel = (2 * v + 2 * x + dx, 2 * u + y)
                    if pixel[0] < extent[0] and pixel[1] < extent[1]:
                        assert pixel not in output, 'overlapping invocation output'
                        value = a.store(value)
                        output[pixel] = a.math(value + .5) if dc else value
            even = next_even
    return output
