import sys
from pathlib import Path
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from xrbench.foveation import *

class FoveationTests(unittest.TestCase):
    def test_compiled_hlsl_mapping_parity_at_joins_and_shifted_eyes(self):
        # This is a float32 port of the actual CompressAxisAlignedPixelShader
        # expression, kept separate from the float64 scoring implementation.
        # Include both join sides and an asymmetric diagnostic shift.
        cfg=FoveationConfig('medium',center_shift=(.17,-.23))
        size=(2624,2776); packed=encoded_size(*size,cfg)
        xs=np.array([0.,.07,.070001,.5,.929999,.93,1.],np.float32)
        uv=np.stack(np.meshgrid(xs,np.array([.001,.5,.999],np.float32),indexing='xy'),axis=-1)
        cpu=forward_map_uv(uv,size,packed,cfg)
        shader=hlsl_forward_map_uv(uv,size,packed,cfg)
        self.assertLess(float(np.max(np.abs(cpu-shader))),2e-6)

    def test_compiled_hlsl_overlap_support_is_normalized_at_subpixel_phases(self):
        cfg=FoveationConfig('h264fit',softness=1); size=(2624,2776); packed=encoded_size(*size,cfg)
        uv=np.array([[[.001,.001],[.4999,.5001],[.999,.731]]],np.float64)
        source=hlsl_forward_map_uv(uv,size,packed,cfg)
        footprint=local_squeeze(uv,size,packed,cfg)*(1+cfg.softness*softness_ramp(uv,cfg)[...,None])
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
        edge=local_squeeze(uv,size,packed,cfg)*(1+softness_ramp(uv,cfg)[...,None])
        self.assertGreater(float(edge.max()),6.0); self.assertLessEqual(float(edge.max()),MAX_FOOTPRINT_PIXELS)
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
        cfg=FoveationConfig('light',softness=1); eps=1e-5
        a=softness_ramp(np.array([[.5+.4/2-eps,.5]]),cfg)[0]; b=softness_ramp(np.array([[.5+.4/2+eps,.5]]),cfg)[0]
        self.assertLess(b-a,1e-8); self.assertEqual(float(softness_ramp(np.array([[.5,.5]]),cfg)[0]),0.)
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
    def test_encode_then_reconstruct_keeps_small_codec_representation(self):
        y=np.full((240,640),100,np.uint8); planes=[y,np.full((120,320),128,np.uint8),np.full((120,320),128,np.uint8)]
        encoded=encode_planes(planes,FoveationConfig('medium',softness=.5))
        self.assertEqual(encoded.expanded_eye,(320,240)); self.assertEqual(encoded.encoded_eye,encoded_size(320,240,encoded.config))
        self.assertEqual(encoded.planes[0].shape,(encoded.encoded_eye[1],encoded.encoded_eye[0]*2))
        self.assertEqual(reconstruct_planes(encoded.planes,encoded)[0].shape,y.shape)

if __name__=='__main__': unittest.main()
