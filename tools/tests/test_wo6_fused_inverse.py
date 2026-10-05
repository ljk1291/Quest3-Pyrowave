import math
import random

from tools.xrbench import wo6_fused_inverse as model


def check(low, high, fp16=False):
    reference = model.reference_53(low, high, fp16_shared=fp16)
    candidate = model.pair_local_53(low, high, fp16_shared=fp16)
    assert candidate == reference


def test_boundary_clamp_and_adversarial_impulses_are_exact():
    for count in (1, 2, 3, 17):
        for index in range(count):
            low, high = [0.0] * count, [0.0] * count
            low[index] = 7.0
            check(low, high)
            low, high = [0.0] * count, [0.0] * count
            high[index] = -11.0
            check(low, high)


def test_randomized_reference_and_pair_local_match_for_float_and_fp16_shared():
    rng = random.Random(0x53F0ED)
    for count in range(1, 65):
        for _ in range(12):
            low = [rng.uniform(-200, 200) for _ in range(count)]
            high = [rng.uniform(-200, 200) for _ in range(count)]
            check(low, high)
            check(low, high, fp16=True)


def test_actual_shader_apron_loops_and_pair_local_neighbourhood_are_exact():
    rng = random.Random(0xA930)
    # These are already-gathered rows: the test exercises the literal idwt
    # loops, including non-core apron pairs, rather than only a convenient
    # whole-line formulation.
    for pairs in range(3, 17):
        for start in range(1, pairs - 1):
            for count in range(1, pairs - start):
                samples = [rng.uniform(-80, 80) for _ in range(2 * pairs)]
                for fp16 in (False, True):
                    assert model.pair_local_apron_53(samples, start, count, fp16_shared=fp16) == model.shader_apron_53(
                        samples, start, count, fp16_shared=fp16)


def test_invalid_shapes_and_finite_fp16_results_are_rejected_or_preserved():
    for fn in (model.reference_53, model.pair_local_53):
        try:
            fn([], [])
        except ValueError:
            pass
        else:
            raise AssertionError("empty bands accepted")
        try:
            fn([1.0], [1.0, 2.0])
        except ValueError:
            pass
        else:
            raise AssertionError("unequal bands accepted")
    values = model.pair_local_53([1.0, -2.0], [.25, -.5], fp16_shared=True)
    assert all(math.isfinite(value) for value in values)
    for fn in (model.shader_apron_53, model.pair_local_apron_53):
        for args in (([1.0], 1, 1), ([1.0] * 6, 0, 1), ([1.0] * 6, 2, 1)):
            try:
                fn(*args)
            except ValueError:
                pass
            else:
                raise AssertionError("invalid apron accepted")
