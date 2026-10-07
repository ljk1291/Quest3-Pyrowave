"""Verify fast53's generated variants and byte-identical pre-existing SPIR-V."""
import argparse
from pathlib import Path
import re


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


def verify(baseline, candidate):
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
            key = ('idwt', (precision, 1), fp16)
            if key not in new:
                raise ValueError(f'missing fast53 variant: {key}')
            check_local_shader(new[key])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('candidate', type=Path)
    args = parser.parse_args()
    try:
        verify(args.baseline.read_text(), args.candidate.read_text())
    except ValueError as error:
        raise SystemExit(str(error)) from error
    print('Default SPIR-V is byte-identical; all six fast53 variants have no barriers or workgroup storage')


if __name__ == '__main__':
    main()
