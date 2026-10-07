#include "pyrowave_rdo_density.hpp"
#include <cassert>
#include <cstdio>
#include <initializer_list>

int main() {
    using namespace PyroWave;
    const auto legacy = parse_rdo_pixels_per_degree(nullptr);
    const auto headset = rdo_density_from_pixels_per_degree(2752.0f / 99.0f);
    assert(rdo_cpd_nyquist(headset) == 0.5f * 2752.0f / 99.0f);
    for (int level = 0; level < 5; ++level) for (int component = 0; component < 3; ++component) {
        for (int band = 0; band < 4; ++band) {
            // Off preserves existing monitor and explicitly selected RDO behavior.
            for (const auto &density : {legacy, headset})
                assert(rdo_quant_csf(density, level, component, band, true, 5) ==
                       rdo_quant_csf(density, level, component, band, true, 5, false));
            // Independent amplitude factors, including the coarsest chroma exception.
            const float luma = rdo_quant_csf(headset, level, 0, band, true, 5);
            const float expected = luma * (level >= 3 ? 6.0f : 1.0f) *
                (component && level != 4 ? 1.6f : 1.0f);
            const float actual = rdo_quant_csf(headset, level, component, band, true, 5, true);
            assert(std::abs(actual - expected) < 1e-6f);
            assert(std::isfinite(actual) && actual > 0.0f);
        }
    }
    puts("headset CSF off/on density, LF and chroma weights passed");
}
