import pytest

from tools.xrbench import dequant_decode_parity as parity


def _y4m(path, frames):
    header = b"YUV4MPEG2 W2 H2 F90:1 Ip A0:0 C420jpeg XYSCSS=420JPEG XCOLORRANGE=FULL\n"
    frame = b"FRAME\n" + bytes([1, 2, 3, 4, 128, 128])
    path.write_bytes(header + frame * frames)


def test_retained_decode_parity_accepts_matching_frames(tmp_path):
    old = tmp_path / "old.y4m"
    zero = tmp_path / "zero.y4m"
    _y4m(old, 2)
    _y4m(zero, 2)
    report = parity.verify(old, zero, expected_frames=2, label="test")
    assert report["matched_frames"] == 2
    assert report["frame_sha256"] and len(report["frame_sha256"]) == 2


def test_retained_decode_parity_rejects_one_changed_frame(tmp_path):
    old = tmp_path / "old.y4m"
    zero = tmp_path / "zero.y4m"
    _y4m(old, 2)
    _y4m(zero, 2)
    contents = bytearray(zero.read_bytes())
    contents[-1] ^= 1
    zero.write_bytes(contents)
    with pytest.raises(ValueError, match="decoded_frame_hash_mismatch:2"):
        parity.verify(old, zero, expected_frames=2)
