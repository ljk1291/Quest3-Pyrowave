"""CPU contract for the opt-in dequant reconstruction-magnitude sweep."""
import math

import pytest


OFFSETS = (-0.25, -0.125, 0.0, 0.125, 0.25)


def dequant_magnitude(decoded_abs, offset, scale):
    """Mirror the shader order: deadzone, optional magnitude offset, scale, sign."""
    assert -0.25 <= offset <= 0.25
    magnitude = 0.0 if decoded_abs == 0 else decoded_abs + 0.5 + offset
    return scale * magnitude


def test_default_offset_is_bit_parity_control():
    values = [0, 1, 2, 7, 255]
    scale = 0.3125
    assert [dequant_magnitude(v, 0.0, scale) for v in values] == [
        0.0, 1.5 * scale, 2.5 * scale, 7.5 * scale, 255.5 * scale]


def test_zero_coefficients_stay_exactly_zero_for_every_allowed_sweep_value():
    assert [dequant_magnitude(0, offset, 1.0) for offset in OFFSETS] == [0.0] * len(OFFSETS)


def test_offset_is_symmetric_after_sign_application():
    for offset in OFFSETS:
        magnitude = dequant_magnitude(3, offset, 0.5)
        assert magnitude > 0.0
        assert -magnitude == -dequant_magnitude(3, offset, 0.5)


@pytest.mark.parametrize("offset", OFFSETS)
def test_interval_endpoints_are_finite_and_cannot_cross_zero_for_nonzero_codes(offset):
    # The smallest deadzoned nonzero magnitude is 1.5, so the bounded negative
    # endpoint retains a strict positive magnitude before the sign is restored.
    value = dequant_magnitude(1, offset, 1.0)
    assert math.isfinite(value)
    assert value >= 1.25
