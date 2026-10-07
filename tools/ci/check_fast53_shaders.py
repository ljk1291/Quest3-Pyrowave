"""Verify fast53's generated variants and byte-identical pre-existing SPIR-V."""
import argparse
import hashlib
from pathlib import Path
import re
import struct

# Measured v1 from 74a3a3b's generated header, little-endian SPIR-V words.
# Keep this control immutable even after regenerated v2/v3 headers are folded in.
V1_SHA256 = {
    (0, 0): 'cc74d40a28f2ac0d13742a8d96a197973d1a169148cb0182887204e9f1dd64ab',
    (1, 0): 'cc74d40a28f2ac0d13742a8d96a197973d1a169148cb0182887204e9f1dd64ab',
    (2, 0): 'da5ecf9796d8239fab92cd41f5cbb801733a551d0b303ad5cc42a981984399ae',
    (0, 1): 'fe8856ada47a31599fc54175d58c78863b412b89f749c8bc8c98a08915c684ce',
    (1, 1): 'face1b0a1b86852f537375cd147c12705a3079445f6f266fe6598706d4a91fcb',
    (2, 1): 'da5ecf9796d8239fab92cd41f5cbb801733a551d0b303ad5cc42a981984399ae',
}


def spirv_sha256(words):
    return hashlib.sha256(struct.pack('<' + 'I' * len(words), *words)).hexdigest()


def programs(header):
    bank = re.search(r'static const uint32_t spirv_bank\[\]\s*=\s*\{(.*?)\};', header, re.S)
    if not bank:
        raise ValueError('missing SPIR-V bank')
    words = [int(word, 16) for word in re.findall(r'0x([0-9a-fA-F]+)u?', bank[1])]
    result = {}
    fp16 = None
    for line in header.splitlines():
        resolver = re.search(r'if \(resolver\("\w+", "FP16"\) == ([01])\)', line)
        if resolver:
            fp16 = int(resolver[1])
        assignment = re.search(r'this->(\w+)((?:\[\d+\])*) = device.request_(?:program|shader)'
                               r'\(spirv_bank \+ (\d+), (\d+), &layout\);', line)
        if assignment:
            name, indices, offset, size = assignment.groups()
            offset, size = int(offset), int(size)
            if size % 4 or offset + size // 4 > len(words):
                raise ValueError('invalid SPIR-V slice')
            key = (name, tuple(map(int, re.findall(r'\d+', indices))), fp16)
            if key in result:
                raise ValueError(f'duplicate program: {key}')
            result[key] = words[offset:offset + size // 4]
        if line.strip() == '}':
            fp16 = None
    if not result:
        raise ValueError('missing shader assignments')
    return result


def check_local_shader(words):
    if len(words) < 5 or words[0] != 0x07230203:
        raise ValueError('invalid SPIR-V header')
    offset = 5
    while offset < len(words):
        count, opcode = words[offset] >> 16, words[offset] & 0xffff
        if not count or offset + count > len(words):
            raise ValueError('invalid SPIR-V instruction')
        if opcode in (224, 225):  # OpControlBarrier / OpMemoryBarrier
            raise ValueError('fast53 contains a barrier')
        if opcode == 59 and count >= 4 and words[offset + 3] == 4:  # OpVariable, Workgroup
            raise ValueError('fast53 allocates workgroup storage')
        offset += count


def verify(baseline, candidate, v1_hashes=V1_SHA256):
    old, new = programs(baseline), programs(candidate)
    if {key for key in old if key[0] == 'idwt'} != {
            ('idwt', (precision,), fp16) for precision in range(3) for fp16 in range(2)}:
        raise ValueError('baseline must be the pre-fast53 header')
    for key, words in old.items():
        name, indices, fp16 = key
        mapped = (name, indices + (0,) if name == 'idwt' else indices, fp16)
        if new.get(mapped) != words:
            raise ValueError(f'pre-existing shader changed: {key}')
    for precision in range(3):
        for fp16 in range(2):
            for variant in (1, 2, 3):
                key = ('idwt', (precision, variant), fp16)
                if key not in new:
                    raise ValueError(f'missing fast53 variant: {key}')
                check_local_shader(new[key])
                if variant == 1 and spirv_sha256(new[key]) != v1_hashes[(precision, fp16)]:
                    raise ValueError(f'measured v1 shader changed: {key}')
    expected = {('idwt', (precision, variant), fp16)
                for precision in range(3) for variant in range(4) for fp16 in range(2)}
    if {key for key in new if key[0] == 'idwt'} != expected:
        raise ValueError('expected exactly 24 idwt permutations')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('candidate', type=Path)
    args = parser.parse_args()
    try:
        verify(args.baseline.read_text(), args.candidate.read_text())
    except ValueError as error:
        raise SystemExit(str(error)) from error
    print('Default and measured v1 SPIR-V are byte-identical; all 18 fast53 permutations have no barriers or workgroup storage')


if __name__ == '__main__':
    main()
