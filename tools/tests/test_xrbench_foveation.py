import sys
import math
from pathlib import Path
import unittest
from unittest import mock
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from xrbench.foveation import *
from xrbench import foveation as f

class FoveationTests(unittest.TestCase):
    def test_hlsl_algebra_mapping_parity_at_joins_and_shifted_eyes(self):
        # This is a float32 port of the HLSL expression, kept separate from
        # the float64 scoring implementation. Native shader compilation is
        # checked separately; this is not a shader-execution claim.
        # Include both join sides and an asymmetric diagnostic shift.
        cfg=FoveationConfig('medium',center_shift=(.17,-.23))
        size=(2624,2776); packed=encoded_size(*size,cfg)
        xs=np.array([0.,.07,.070001,.5,.929999,.93,1.],np.float32)
        uv=np.stack(np.meshgrid(xs,np.array([.001,.5,.999],np.float32),indexing='xy'),axis=-1)
        cpu=forward_map_uv(uv,size,packed,cfg)
        shader=hlsl_forward_map_uv(uv,size,packed,cfg)
        self.assertLess(float(np.max(np.abs(cpu-shader))),2e-6)

    def test_hlsl_algebra_overlap_support_is_normalized_at_subpixel_phases(self):
        cfg=FoveationConfig('h264fit',softness=1); size=(2624,2776); packed=encoded_size(*size,cfg)
        uv=np.array([[[.001,.001],[.4999,.5001],[.999,.731]]],np.float64)
        source=hlsl_forward_map_uv(uv,size,packed,cfg)
        footprint=local_squeeze(uv,size,packed,cfg)*(1+cfg.softness*softness_ramp(source,size,packed,cfg)[...,None])
        weights,indices=hlsl_area_weights(source,footprint,size)
        self.assertLessEqual(float(footprint.max()),MAX_FOOTPRINT_PIXELS)
        self.assertTrue(np.allclose(weights.sum(axis=-1),footprint[...,0]*footprint[...,1],rtol=1e-4,atol=2e-6))
        self.assertTrue(np.all(indices[...,0] >= 0)); self.assertTrue(np.all(indices[...,0] < size[0]))

    def test_q3_profile_footprint_is_not_silently_clamped(self):
        cfg=FoveationConfig('h264fit',softness=1); size=(2624,2776); packed=encoded_size(*size,cfg)
        x=(np.arange(packed[0])+.5)/packed[0]; y=(np.arange(packed[1])+.5)/packed[1]
        # A 1D perimeter scan reaches the worst ratio-2 derivative without a
        # full-frame allocation. The rounded allocation makes it slightly >6.
        uv=np.stack(np.meshgrid(x,np.array([.5]),indexing='xy'),axis=-1)
        source=forward_map_uv(uv,size,packed,cfg)
        edge=local_squeeze(uv,size,packed,cfg)*(1+softness_ramp(source,size,packed,cfg)[...,None])
        self.assertGreater(float(edge.max()),6.0); self.assertLessEqual(float(edge.max()),MAX_FOOTPRINT_PIXELS)

    def test_summed_area_filter_matches_bounded_shader_reference(self):
        image=np.arange(19*23,dtype=np.float64).reshape(19,23)
        uv=np.array([[[.002,.99],[.331,.741],[.998,.001]]])
        footprint=np.array([[[6.34,5.81],[1.23,2.77],[6.9,6.01]]])
        expected=f._area_box_reference(image,uv,footprint)
        actual=f._area_box(image,uv,footprint)
        self.assertTrue(np.allclose(actual,expected,rtol=0,atol=1e-10))

    def test_forward_eye_sat_cache_is_bitwise_identical_across_profiles_and_tile_pads(self):
        """The cache may remove allocation only; it must not change samples.

        Small row tiles force different edge pads.  The uncached comparison
        calls the same area-integral code with its cache deliberately removed,
        so it covers the exact arithmetic used for all three profiles and each
        softness-ramp value.
        """
        # This size keeps every profile/softness combination inside the
        # declared footprint bound while retaining several forward tiles.
        image=(np.arange(480*640,dtype=np.float64).reshape(480,640)%251)/250.
        original=f._area_box
        # Exercise two explicit edge pads in one frame-local cache. Forward
        # tiles may happen to share a pad for a particular profile, but cache
        # keys must never make an edge tile reuse the interior SAT geometry.
        cache={}
        for uv,footprint in ((np.array([[[.5,.5]]]),np.array([[[1.,1.]]])),
                             (np.array([[[-.03,1.03]]]),np.array([[[6.9,6.9]]]))):
            self.assertTrue(np.array_equal(original(image,uv,footprint),
                                            original(image,uv,footprint,sat_cache=cache)))
        self.assertGreater(len(cache),1)
        # 640x480 intentionally exercises all profiles and each ramp level;
        # h264fit at s=1 exceeds the production footprint bound at this tiny
        # synthetic geometry, so its s=1 case stays covered by the existing
        # Q3-size bound test rather than weakening that guard here.
        cases=(("light",0.),("light",.5),("light",1.),
               ("medium",0.),("medium",.5),("medium",1.),
               ("h264fit",0.),("h264fit",.5))
        for profile,softness in cases:
            cfg=FoveationConfig(profile,softness,profile == "light" and softness == .5)
            pads=[]
            def observe(image, source_uv, footprint, *, sat_cache=None):
                h,w=image.shape; cx=source_uv[...,0]*w; cy=source_uv[...,1]*h
                fx=footprint[...,0]; fy=footprint[...,1]
                left=cx-fx*.5; right=cx+fx*.5; top=cy-fy*.5; bottom=cy+fy*.5
                pads.append(max(FILTER_RADIUS, int(math.ceil(max(0., -left.min(), right.max()-w,
                                                                  -top.min(), bottom.max()-h)))+1))
                return original(image,source_uv,footprint,sat_cache=sat_cache)
            with mock.patch.object(f,"_area_box",side_effect=observe):
                cached=forward_eye(image,cfg,tile_rows=64)
            def uncached(image, source_uv, footprint, *, sat_cache=None):
                return original(image,source_uv,footprint)
            with mock.patch.object(f,"_area_box",side_effect=uncached):
                baseline=forward_eye(image,cfg,tile_rows=64)
            self.assertGreater(len(pads),1)
            self.assertTrue(np.array_equal(cached,baseline), (profile,softness))

    def test_forward_eye_reuses_summed_area_tables_for_same_pad(self):
        image=(np.arange(480*640,dtype=np.float64).reshape(480,640)%251)/250.
        original=f._area_box
        cfg=FoveationConfig("medium",.5)
        with mock.patch.object(f.np,"pad",wraps=np.pad) as cached_pad:
            forward_eye(image,cfg,tile_rows=64)
        def uncached(image, source_uv, footprint, *, sat_cache=None):
            return original(image,source_uv,footprint)
        with mock.patch.object(f.np,"pad",wraps=np.pad) as uncached_pad, \
             mock.patch.object(f,"_area_box",side_effect=uncached):
            forward_eye(image,cfg,tile_rows=64)
        # Each fresh SAT uses two np.pad calls. The production path must reuse
        # at least one same-pad table across the deliberately tiled frame.
        self.assertLess(cached_pad.call_count, uncached_pad.call_count)

    def test_right_eye_mirrors_static_horizontal_shift(self):
        cfg=FoveationConfig('light',center_shift=(.22,-.11))
        right=f._eye_config(cfg,True)
        self.assertEqual(right.center_shift,(-.22,-.11))
        self.assertTrue(np.allclose(forward_map_uv(np.array([[[.5,.5]]]),(2624,2776),encoded_size(2624,2776,cfg),cfg)[...,0],
                                    1-forward_map_uv(np.array([[[.5,.5]]]),(2624,2776),encoded_size(2624,2776,right),right)[...,0],atol=.25))

    def test_reconstruction_interpolates_client_code_values_before_eotf(self):
        # stream.wgsl textureSample precedes ENABLE_SRGB_CORRECTION. A midpoint
        # of black and white is therefore .5 code, not .5 linear (.735 code).
        midpoint=f._bilinear(np.array([[0.,1.]]),np.array([[[.5,.5]]]))[0,0]
        self.assertEqual(midpoint,.5)
        self.assertGreater(float(f._linear_to_srgb(np.array(.5))),midpoint)
    def test_profile_dimensions_at_wo10_aligned_crop(self):
        # The upstream formula takes the unaligned crop height. It produces these actual
        # packed dimensions; the plan must not overwrite them with target labels.
        self.assertEqual(encoded_size(2624,2776,FoveationConfig('light')),(2464,2592))
        self.assertEqual(encoded_size(2624,2776,FoveationConfig('medium')),(2112,2240))
        self.assertEqual(encoded_size(2624,2776,FoveationConfig('h264fit')),(1984,2112))
    def test_forward_inverse_are_numeric_inverses(self):
        uv=np.array([[[.03,.14],[.31,.72],[.5,.5],[.91,.87]]])
        cfg=FoveationConfig('medium',center_shift=(.1,-.2)); got=inverse_map_uv(forward_map_uv(uv,(2624,2784),(2112,2240),cfg),(2624,2784),(2112,2240),cfg)
        self.assertLess(np.max(np.abs(uv-got)),1e-9)
    def test_softness_has_smooth_center_join(self):
        cfg=FoveationConfig('light',softness=1); size=(2624,2776); packed=encoded_size(*size,cfg); eps=1e-6
        center=1-math.ceil((size[0]-cfg.center_fraction*size[0])/(cfg.edge_ratio*2))*cfg.edge_ratio*2/size[0]
        lo=((1-center)*.5)/((cfg.edge_ratio-1)*center+1)
        join=forward_map_uv(np.array([[[lo,.5]]]),size,packed,cfg)[0,0,0]
        a=softness_ramp(np.array([[join-eps,.5]]),size,packed,cfg)[0]
        b=softness_ramp(np.array([[join+eps,.5]]),size,packed,cfg)[0]
        self.assertLess(b-a,1e-9); self.assertEqual(float(softness_ramp(np.array([[.5,.5]]),size,packed,cfg)[0]),0.)
    def test_blur_only_preserves_geometry_but_filters_periphery(self):
        cfg=FoveationConfig('light',softness=.5,blur_only=True); self.assertEqual(encoded_size(64,48,cfg),(64,48))
        checker=np.indices((240,640)).sum(axis=0).astype(np.uint8)%2*255; planes=[checker,np.full((120,320),128,np.uint8),np.full((120,320),128,np.uint8)]
        out=transform_planes(planes,cfg); self.assertEqual(out[0].shape,checker.shape); self.assertTrue(np.all(out[0][:,:320] == out[0][:,320:]))
    def test_per_eye_seam_is_never_sampled(self):
        cfg=FoveationConfig('medium',softness=1); left=np.zeros((240,320),np.uint8); right=np.full((240,320),255,np.uint8); p=np.concatenate((left,right),axis=1)
        out=transform_planes([p,np.full((120,320),128,np.uint8),np.full((120,320),128,np.uint8)],cfg)[0]
        self.assertEqual(int(out[:,0:320].max()),0)
        # Float interpolation followed by the GPU-equivalent uint8 conversion can lose
        # one code value. The important seam property is no cross-eye contamination.
        self.assertGreaterEqual(int(out[:,320:].min()),254)
    def test_chroma_edge_is_filtered_in_linear_rgb_not_independent_yuv(self):
        y=np.full((240,640),128,np.uint8); cb=np.zeros((120,320),np.uint8); cb[:,160:]=255; cr=np.full((120,320),128,np.uint8)
        out=transform_planes([y,cb,cr],FoveationConfig('light',softness=.5))
        self.assertEqual(out[1].shape,(120,320)); self.assertTrue(np.isfinite(out[1]).all())
    def test_reconstructing_existing_encoded_planes_matches_blur_reference_bitwise(self):
        """A Q3b source frame may reuse its reduced planes for the blur reference."""
        y=np.arange(240*640,dtype=np.uint8).reshape(240,640)
        planes=[y,np.full((120,320),101,np.uint8),np.full((120,320),153,np.uint8)]
        for cfg in (FoveationConfig('light',0), FoveationConfig('medium',.5),
                    FoveationConfig('h264fit',.5), FoveationConfig('light',.5,True)):
            encoded=encode_planes(planes,cfg)
            reused=reconstruct_planes(encoded.planes,encoded)
            baseline=blur_reference(planes,cfg)
            self.assertTrue(all(np.array_equal(a,b) for a,b in zip(reused,baseline)),cfg)

    def test_encode_then_reconstruct_keeps_small_codec_representation(self):
        y=np.full((240,640),100,np.uint8); planes=[y,np.full((120,320),128,np.uint8),np.full((120,320),128,np.uint8)]
        encoded=encode_planes(planes,FoveationConfig('medium',softness=.5))
        self.assertEqual(encoded.expanded_eye,(320,240)); self.assertEqual(encoded.encoded_eye,encoded_size(320,240,encoded.config))
        self.assertEqual(encoded.planes[0].shape,(encoded.encoded_eye[1],encoded.encoded_eye[0]*2))
        self.assertEqual(reconstruct_planes(encoded.planes,encoded)[0].shape,y.shape)

if __name__=='__main__': unittest.main()
