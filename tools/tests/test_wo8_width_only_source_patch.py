"""Contract checks for the layered, opt-in native WO8 source patch.

These checks intentionally inspect the source patch rather than pretending to
compile the separately pinned native tree.  They keep the required Rust,
C++, and HLSL branches together until that tree is built by its owner.
"""

from pathlib import Path
import unittest


PATCH = (
    Path(__file__).resolve().parents[2]
    / "patches"
    / "wo8-width-only-h264.patch"
)


class WidthOnlyNativeSourcePatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.patch = PATCH.read_text(encoding="utf-8")

    def test_opt_in_profile_has_explicit_identity_y_contract(self) -> None:
        self.assertIn("H264WidthOnly", self.patch)
        self.assertIn("FoveationProfile::H264WidthOnly => (23.0 / 41.0, 2.0", self.patch)
        self.assertIn("config.center_size_x = 23.0 / 41.0", self.patch)
        self.assertIn("FoveationProfile::H264WidthOnly => 1.0", self.patch)
        self.assertIn("1.0 / 1.0 is a deliberate identity-Y sentinel", self.patch)

    def test_cpp_branches_before_zero_height_band_division(self) -> None:
        branch = self.patch.index("const bool verticalIdentity")
        shift_division = self.patch.index("centerShiftRightY * edgeSizeYAligned")
        self.assertLess(branch, shift_division)
        self.assertIn("float foveationScaleY = (Settings::Instance().m_foveationBlurOnly || verticalIdentity)", self.patch)
        self.assertIn("verticalIdentity ? 1.f : 0.f", self.patch)

    def test_forward_shader_bypasses_y_mapping_and_derivative(self) -> None:
        self.assertIn("float verticalIdentity;", self.patch)
        self.assertIn("compressedUV.y = outputEyeUV.y", self.patch)
        self.assertIn("mappingDerivative.y = 1.", self.patch)
        self.assertIn("Peripheral softness expands the shared two-axis footprint above", self.patch)
        self.assertIn("c2.y = 1.", self.patch)

    def test_receiver_uses_finite_placeholder_then_restores_identity_y(self) -> None:
        self.assertIn("fn receiver_foveation_profile", self.patch)
        self.assertIn("alvr_session::FoveationProfile::H264WidthOnly", self.patch)
        self.assertIn('("FFE_IDENTITY_Y", if identity_y { 1.0 } else { 0.0 })', self.patch)
        self.assertIn("override FFE_IDENTITY_Y: f32 = 0.0", self.patch)
        self.assertIn("corrected_uv.y = pre_inverse_y", self.patch)
        self.assertIn("config.center_size_y = 0.5", self.patch)


if __name__ == "__main__":
    unittest.main()
