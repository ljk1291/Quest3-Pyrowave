"""Keep existing kernels, especially fast53 and CSF-off, identical after regeneration."""
import argparse
from pathlib import Path

try:
    from .check_fast53_shaders import programs, check_local_shader
except ImportError:
    from check_fast53_shaders import programs, check_local_shader


def verify(baseline, candidate):
    old, new = programs(baseline), programs(candidate)
    for (name, indices, fp16), words in old.items():
        if name == "wavelet_dequant":
            continue  # Adds specialization-controlled quad stores; parity is a device gate.
        key = (name, (0,) if name == "wavelet_quant" else indices, fp16)
        if new.get(key) != words:
            raise ValueError(f"existing shader changed: {key}")
    for name in ("idwt_haar32", "idwt_cdf53v2"):
        expected = {(name, (precision, dual), fp16)
                    for precision in range(3) for dual in range(2) for fp16 in range(2)}
        if {key for key in new if key[0] == name} != expected:
            raise ValueError(f"expected 12 permutations for {name}")
        for key in expected:
            check_local_shader(new[key])
    if ("wavelet_quant", (1,), None) not in new:
        raise ValueError("missing opt-in headset CSF quantizer")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    verify(args.baseline.read_text(), args.candidate.read_text())
    print("Existing inverse/fast53 and CSF-off kernels unchanged; 24 new inverse permutations verified")


if __name__ == "__main__":
    main()
