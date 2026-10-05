"""Source-wire checks for the opt-in, direct ALVR RDO setting.

These checks cover source and patch intent only. Native export, full build and a
vrserver marker remain separate release gates.
"""
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def _patch(name: str) -> str:
    return (REPO / "patches" / name).read_text(encoding="utf-8")


def test_pyrowave_direct_setting_keeps_zero_on_the_legacy_environment_path():
    patch = _patch("pyrowave-rdo-session-setting.patch")
    assert "float rdo_pixels_per_degree;" in patch
    assert "const bool has_embedding_override = rdo_pixels_per_degree > 0.0f;" in patch
    assert "has_embedding_override ? nullptr : std::getenv(\"PYROWAVE_RDO_PX_PER_DEG\")" in patch
    assert "rdo_density_from_pixels_per_degree(rdo_pixels_per_degree)" in patch
    assert "!std::isfinite(info->rdo_pixels_per_degree)" in patch
    assert "info->rdo_pixels_per_degree < 0.0f" in patch
    assert "info->rdo_pixels_per_degree > 10000.0f" in patch
    assert "!rdo_density_from_pixels_per_degree(0.0f).valid" in patch


def test_alvr_setting_is_opt_in_and_forwards_to_the_native_create_info():
    patch = _patch("alvr-pyrowave-rdo-session-setting.patch")
    assert "pub rdo_pixels_per_degree: Switch<f32>," in patch
    assert "enabled: false," in patch
    assert "content: 24.0," in patch
    assert "pyrowave_rdo_pixels_per_degree: pyrowave.rdo_pixels_per_degree.unwrap_or(0.0)," in patch
    assert "m_pyrowaveRdoPixelsPerDegree" in patch
    assert "encoderInfo.rdo_pixels_per_degree = Settings::Instance().m_pyrowaveRdoPixelsPerDegree;" in patch
    assert "ALVR session RDO setting" in patch
    assert "rdo_px_per_deg=legacy" in patch
