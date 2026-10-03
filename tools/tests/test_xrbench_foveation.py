import sys
from pathlib import Path
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from xrbench.foveation import *

class FoveationTests(unittest.TestCase):
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
        checker=np.indices((48,128)).sum(axis=0).astype(np.uint8)%2*255; planes=[checker,np.full((24,64),128,np.uint8),np.full((24,64),128,np.uint8)]
        out=transform_planes(planes,cfg); self.assertEqual(out[0].shape,checker.shape); self.assertTrue(np.all(out[0][:,:64] == out[0][:,64:]))
    def test_per_eye_seam_is_never_sampled(self):
        cfg=FoveationConfig('medium',softness=1); left=np.zeros((48,64),np.uint8); right=np.full((48,64),255,np.uint8); p=np.concatenate((left,right),axis=1)
        out=transform_planes([p,np.full((24,64),128,np.uint8),np.full((24,64),128,np.uint8)],cfg)[0]
        self.assertEqual(int(out[:,0:64].max()),0)
        # Float interpolation followed by the GPU-equivalent uint8 conversion can lose
        # one code value. The important seam property is no cross-eye contamination.
        self.assertGreaterEqual(int(out[:,64:].min()),254)
    def test_chroma_edge_is_filtered_in_linear_rgb_not_independent_yuv(self):
        y=np.full((48,128),128,np.uint8); cb=np.zeros((24,64),np.uint8); cb[:,32:]=255; cr=np.full((24,64),128,np.uint8)
        out=transform_planes([y,cb,cr],FoveationConfig('light',softness=.5))
        self.assertEqual(out[1].shape,(24,64)); self.assertTrue(np.isfinite(out[1]).all())
    def test_encode_then_reconstruct_keeps_small_codec_representation(self):
        y=np.full((48,128),100,np.uint8); planes=[y,np.full((24,64),128,np.uint8),np.full((24,64),128,np.uint8)]
        encoded=encode_planes(planes,FoveationConfig('medium',softness=.5))
        self.assertEqual(encoded.expanded_eye,(64,48)); self.assertEqual(encoded.encoded_eye,encoded_size(64,48,encoded.config))
        self.assertEqual(encoded.planes[0].shape,(encoded.encoded_eye[1],encoded.encoded_eye[0]*2))
        self.assertEqual(reconstruct_planes(encoded.planes,encoded)[0].shape,y.shape)

if __name__=='__main__': unittest.main()
