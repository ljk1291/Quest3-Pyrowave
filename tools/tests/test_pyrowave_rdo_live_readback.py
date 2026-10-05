"""Source-wire checks for the read-only live RDO observability patch.

Native compilation and an initialized Vulkan encoder are separate CI/runtime gates.
These checks prove that reconstructed sources preserve the intended C API to
server-log wiring without claiming either gate has run.
"""
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def _patch(name):
    return (REPO / "patches" / name).read_text(encoding="utf-8")


def test_pyrowave_readback_api_forwards_the_initialized_encoder_state():
    patch = _patch("pyrowave-rdo-live-readback.patch")
    assert "typedef struct pyrowave_encoder_rdo_density" in patch
    assert "pyrowave_encoder_get_rdo_density(pyrowave_encoder encoder" in patch
    assert "if (!encoder || !density)" in patch
    assert "return PYROWAVE_ERROR_INVALID_ARGUMENT;" in patch
    assert "encoder->encoder.get_rdo_density(&density->pixels_per_degree," in patch
    assert "&density->nyquist_cycles_per_degree," in patch
    assert "density->legacy_equivalent = legacy_equivalent ? 1u : 0u;" in patch
    assert "const auto report = rdo_density_report(impl->rdo_density);" in patch


def test_alvr_emits_the_native_readback_after_encoder_creation_with_warn():
    patch = _patch("alvr-pyrowave-rdo-live-readback.patch")
    create = patch.index("PYRO_OR_THROW(pyrowave_encoder_create(&encoderInfo, &m_pyroEncoder));")
    getter = patch.index("PYRO_OR_THROW(pyrowave_encoder_get_rdo_density(m_pyroEncoder, &rdoDensity));")
    marker = patch.index('Warn("[PYROWAVE] native encoder RDO density applied:')
    assert create < getter < marker
    assert "rdoDensity.pixels_per_degree" in patch
    assert "rdoDensity.nyquist_cycles_per_degree" in patch
    assert "rdoDensity.legacy_equivalent" in patch
