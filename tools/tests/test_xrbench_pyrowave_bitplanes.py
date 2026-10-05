import struct
import unittest

from xrbench import pyrowave_bitplanes as bp
from xrbench.pyrowave_wave import MAGIC


def _sequence(width=32, height=32, sequence=1, total_blocks=1, code=0, chroma=1):
    first = (width - 1) | ((height - 1) << 14) | (sequence << 28) | (1 << 31)
    second = total_blocks | (code << 24) | (chroma << 26)
    return struct.pack("<II", first, second)


def _block(sequence=1, index=0, ballot=1, q_bits=0, planes=b"\x03\x80", signs=b"\x00"):
    controls16 = struct.pack("<H", 2)
    controls8 = bytes([q_bits])
    used = 8 + len(controls16) + len(controls8) + len(planes) + len(signs)
    words = (used + 3) // 4
    first = ballot | (words << 16) | (sequence << 28)
    second = index << 8
    return struct.pack("<II", first, second) + controls16 + controls8 + planes + signs + b"\0" * (words * 4 - used)


def _wave(frame=None):
    frame = frame if frame is not None else _sequence() + _block()
    return MAGIC + struct.pack("<8i", 32, 32, 1, 1, 1, 90, 1, 0) + struct.pack("<I", len(frame)) + frame


class PyroWaveBitplaneParserTests(unittest.TestCase):
    def test_parser_accounts_for_each_serialized_class(self):
        result = bp.analyze_wave_bytes(_wave())
        self.assertEqual(result["frames"]["count"], 1)
        self.assertEqual(result["sequence"], {"width": 32, "height": 32, "codec_code": 0, "chroma_resolution": 1})
        self.assertEqual(result["payload_byte_classes"], {
            "sequence_header_bytes": 8, "block_header_bytes": 8, "control_bytes": 3,
            "bitplane_bytes": 2, "sign_bytes": 1, "alignment_padding_bytes": 2,
            "payload_bytes": 24,
        })
        self.assertEqual(result["bitplane_h0"]["symbols"], 2)
        self.assertAlmostEqual(result["bitplane_h0"]["aggregate_h0_bits_per_byte"], 1.0)
        self.assertEqual(result["bitplane_h0"]["context"], "native q_bits control nibble plus plane ordinal")
        self.assertAlmostEqual(result["bitplane_h0"]["per_q_bits_and_plane_h0_bytes_sum"], 0.0)

    def test_parser_rejects_trailing_frame_bytes(self):
        with self.assertRaisesRegex(bp.BitplaneFormatError, "truncated frame length"):
            bp.parse_wave_bytes(_wave() + b"\0")

    def test_parser_rejects_block_sequence_mismatch(self):
        frame = _sequence(sequence=1) + _block(sequence=2)
        with self.assertRaisesRegex(bp.BitplaneFormatError, "sequence does not match"):
            bp.analyze_wave_bytes(_wave(frame))

    def test_parser_rejects_inconsistent_block_word_length(self):
        block = bytearray(_block())
        first = struct.unpack_from("<I", block, 0)[0]
        struct.pack_into("<I", block, 0, (first & ~(0xFFF << 16)) | (3 << 16))
        frame = _sequence() + bytes(block)
        with self.assertRaisesRegex(bp.BitplaneFormatError, "inconsistent word length"):
            bp.analyze_wave_bytes(_wave(frame))


if __name__ == "__main__":
    unittest.main()
