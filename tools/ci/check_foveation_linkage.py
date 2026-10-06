"""Check the embedded FFR shader pair's DXBC signatures without a GPU or SDK."""
import argparse
import struct
from pathlib import Path

WINDOWS = Path('alvr/server_openvr/cpp/platform/win32')


def signature(path, kind):
    data = Path(path).read_bytes()
    if data[:4] != b'DXBC':
        raise ValueError(f'{path}: expected DXBC')
    count = struct.unpack_from('<I', data, 28)[0]
    for offset in struct.unpack_from(f'<{count}I', data, 32):
        if data[offset:offset + 4] != kind:
            continue
        size = struct.unpack_from('<I', data, offset + 4)[0]
        chunk = data[offset + 8:offset + 8 + size]
        entries = struct.unpack_from('<I', chunk)[0]
        result = {}
        for i in range(entries):
            name, index, system, dtype, register, mask, used = struct.unpack_from(
                '<5I2B', chunk, 8 + 24 * i)
            semantic = chunk[name:chunk.index(b'\0', name)].decode('ascii').upper()
            result[semantic, index] = (system, dtype, register, mask, used)
        return result
    raise ValueError(f'{path}: missing {kind.decode()} signature')


def check(alvr):
    vertex = signature(alvr / WINDOWS / 'QuadVertexShader.cso', b'OSGN')
    pixel = signature(alvr / WINDOWS / 'CompressAxisAlignedPixelShader.cso', b'ISGN')
    # This pass consumes just interpolated UVs. Checking the compiled registers
    # catches a source struct reorder even when TEXCOORD0's name still matches.
    key = ('TEXCOORD', 0)
    output, source = vertex[key], pixel[key]
    if (source[:3] != output[:3] or source[3] & ~output[3]
            or source[4] != 3):
        raise ValueError(f'FFR TEXCOORD0 linkage mismatch: VS={output}, PS={source}')
    if any(value[4] and key != ('TEXCOORD', 0) for key, value in pixel.items()):
        raise ValueError('FFR unexpectedly consumes another pixel input')
    print(f'FFR production DXBC linkage verified: TEXCOORD0 register {source[2]}, xy')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('alvr', type=Path)
    check(parser.parse_args().alvr)
