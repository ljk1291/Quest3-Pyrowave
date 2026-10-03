"""ALVR-compatible, fixed-centre foveation for offline frame-bank cells.

The mapping is a literal port of ``CompressAxisAlignedPixelShader.hlsl``.  It
operates on a per-eye image; callers split side-by-side stereo before calling
it, which prevents filtering from crossing the eye seam.  The same profile
constants are used by the server patch.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np

PROFILE_CONSTANTS = {
    "light": (0.8, 1.5),
    "medium": (0.6, 2.0),
    "h264fit": (0.5, 2.0),
}
_TAPS = (-0.375, -0.125, 0.125, 0.375)

@dataclass(frozen=True)
class FoveationConfig:
    profile: str = "light"
    softness: float = 0.0
    blur_only: bool = False
    center_shift: tuple[float, float] = (0.0, 0.0)

    def __post_init__(self):
        if self.profile not in PROFILE_CONSTANTS:
            raise ValueError("profile must be light, medium or h264fit")
        if not math.isfinite(self.softness) or not 0.0 <= self.softness <= 1.0:
            raise ValueError("softness must be finite in [0, 1]")
        if len(self.center_shift) != 2 or any(not math.isfinite(x) or abs(x) >= 1 for x in self.center_shift):
            raise ValueError("center_shift must be finite and strictly inside [-1, 1]")

    @property
    def center_fraction(self) -> float: return PROFILE_CONSTANTS[self.profile][0]
    @property
    def edge_ratio(self) -> float: return PROFILE_CONSTANTS[self.profile][1]

def encoded_size(width: int, height: int, config: FoveationConfig) -> tuple[int, int]:
    """Exact ALVR FFR alignment, including its 32-pixel output allocation."""
    if min(width, height) <= 0: raise ValueError("invalid geometry")
    if config.blur_only: return width, height
    c, ratio = config.center_fraction, config.edge_ratio
    def axis(n):
        edge = n - c * n
        aligned_center = 1.0 - math.ceil(edge / (ratio * 2.0)) * (ratio * 2.0) / n
        scaled = (aligned_center + (1.0 - aligned_center) / ratio) * n
        return int(math.ceil(scaled / 32.0) * 32)
    return axis(width), axis(height)

def _params(full: int, encoded: int, center_fraction: float, ratio: float, shift: float):
    edge = full - center_fraction * full
    center = 1.0 - math.ceil(edge / (ratio * 2.0)) * (ratio * 2.0) / full
    eye_ratio = (center + (1.0-center)/ratio) * full / encoded
    c0 = (1.0-center)/2.0
    c1 = (ratio-1.0)*c0*(shift+1.0)/ratio
    c2 = (ratio-1.0)*center+1.0
    lo = c0*(shift+1.0)/c2
    hi = c0*(shift-1.0)/c2+1.0
    return eye_ratio, c1, c2, lo, hi

def forward_map_uv(uv: np.ndarray, full_size: tuple[int,int], encoded_size_: tuple[int,int], config: FoveationConfig) -> np.ndarray:
    """Map encoded UV to full-resolution source UV, matching the HLSL path."""
    uv=np.asarray(uv,dtype=np.float64)
    if uv.shape[-1] != 2: raise ValueError("uv must end in xy")
    if config.blur_only: return uv.copy()
    out=np.empty_like(uv)
    for axis,(full,enc,shift) in enumerate(zip(full_size,encoded_size_,config.center_shift)):
        er,c1,c2,lo,hi=_params(full,enc,config.center_fraction,config.edge_ratio,shift)
        x=uv[...,axis]/er
        center=x*c2/config.edge_ratio+c1
        d2=x*c2; d3=(x-1.0)*c2+1.0
        left=(x/lo)*center+(1.0-x/lo)*d2
        right=((1.0-x)/(1.0-hi))*center+(1.0-(1.0-x)/(1.0-hi))*d3
        out[...,axis]=np.where(x < lo,left,np.where(x > hi,right,center))
    return out

def inverse_map_uv(uv: np.ndarray, full_size: tuple[int,int], encoded_size_: tuple[int,int], config: FoveationConfig) -> np.ndarray:
    """Numerically stable inverse of :func:`forward_map_uv` for reconstruction."""
    uv=np.asarray(uv,dtype=np.float64); out=np.empty_like(uv)
    if config.blur_only: return uv.copy()
    # Each axis is monotonic; bisection gives the exact same piecewise mapping without
    # duplicating algebra that is easy to get wrong at the aligned join.
    lo=np.zeros(uv.shape[:-1],dtype=np.float64); hi=np.ones_like(lo)
    for axis in range(2):
        low=lo.copy(); high=hi.copy(); target=uv[...,axis]
        for _ in range(42):
            mid=(low+high)*.5
            probe=np.zeros((*mid.shape,2)); probe[...,axis]=mid
            other=1-axis; probe[...,other]=.5
            value=forward_map_uv(probe,full_size,encoded_size_,config)[...,axis]
            low=np.where(value < target,mid,low); high=np.where(value >= target,mid,high)
        out[...,axis]=(low+high)*.5
    return out

def local_squeeze(uv: np.ndarray, full_size: tuple[int,int], encoded_size_: tuple[int,int], config: FoveationConfig) -> np.ndarray:
    """Per-axis source-pixel footprint for one encoded pixel (the shader Jacobian)."""
    uv=np.asarray(uv,dtype=np.float64); result=np.empty_like(uv)
    if config.blur_only: return np.ones_like(uv)
    for axis,(full,enc,shift) in enumerate(zip(full_size,encoded_size_,config.center_shift)):
        er,c1,c2,lo,hi=_params(full,enc,config.center_fraction,config.edge_ratio,shift)
        x=uv[...,axis]/er
        # Central derivative is c2/ratio. Edge derivatives are from the HLSL blend.
        center=x*c2/config.edge_ratio+c1; d2=x*c2; d3=(x-1)*c2+1
        left_der=(center-d2)/lo+(x/lo)*(c2/config.edge_ratio)+(1-x/lo)*c2
        right_der=-(center-d3)/(1-hi)+((1-x)/(1-hi))*(c2/config.edge_ratio)+(1-(1-x)/(1-hi))*c2
        deriv=np.where(x < lo,left_der,np.where(x > hi,right_der,c2/config.edge_ratio))/er
        result[...,axis]=np.maximum(1.0,deriv*full/enc)
    return result

def softness_ramp(uv: np.ndarray, config: FoveationConfig) -> np.ndarray:
    """C1 smooth 0→1 ring beginning at the centre edge and ending at the panel edge."""
    p=np.asarray(uv,dtype=np.float64)
    r=np.maximum(np.abs(p[...,0]-.5),np.abs(p[...,1]-.5))*2.0
    edge=config.center_fraction
    t=np.clip((r-edge)/max(1e-6,1-edge),0,1)
    return t*t*(3-2*t)

def _bilinear(image: np.ndarray, uv: np.ndarray) -> np.ndarray:
    h,w=image.shape; x=np.clip(uv[...,0]*w-.5,0,w-1); y=np.clip(uv[...,1]*h-.5,0,h-1)
    x0=np.floor(x).astype(int); y0=np.floor(y).astype(int); x1=np.minimum(x0+1,w-1); y1=np.minimum(y0+1,h-1)
    fx=x-x0; fy=y-y0
    return (image[y0,x0]*(1-fx)*(1-fy)+image[y0,x1]*fx*(1-fy)+image[y1,x0]*(1-fx)*fy+image[y1,x1]*fx*fy)

def forward_eye(image: np.ndarray, config: FoveationConfig) -> np.ndarray:
    """Area-prefilter and resample one plane into its encoded foveated representation."""
    if image.ndim != 2: raise ValueError("one image plane expected")
    h,w=image.shape; ew,eh=encoded_size(w,h,config); yy,xx=np.mgrid[0:eh,0:ew]; uv=np.stack(((xx+.5)/ew,(yy+.5)/eh),axis=-1)
    squeeze=local_squeeze(uv,(w,h),(ew,eh),config); footprint=squeeze*(1+config.softness*softness_ramp(uv,config)[...,None])
    out=np.zeros((eh,ew),np.float64)
    for ox in _TAPS:
        for oy in _TAPS:
            sample_uv=uv+np.stack((ox*footprint[...,0]/ew,oy*footprint[...,1]/eh),axis=-1)
            out += _bilinear(image,forward_map_uv(np.clip(sample_uv,0,1),(w,h),(ew,eh),config))
    return (out/16).astype(image.dtype)

def reconstruct_eye(encoded: np.ndarray, full_size: tuple[int,int], config: FoveationConfig) -> np.ndarray:
    w,h=full_size; yy,xx=np.mgrid[0:h,0:w]; uv=np.stack(((xx+.5)/w,(yy+.5)/h),axis=-1)
    return _bilinear(encoded,inverse_map_uv(uv,full_size,(encoded.shape[1],encoded.shape[0]),config)).astype(encoded.dtype)

def _resize_plane(image: np.ndarray, width: int, height: int) -> np.ndarray:
    yy,xx=np.mgrid[0:height,0:width]
    return _bilinear(image,np.stack(((xx+.5)/width,(yy+.5)/height),axis=-1))

def _srgb_to_linear(value):
    return np.where(value <= .04045,value/12.92,((value+.055)/1.055)**2.4)

def _linear_to_srgb(value):
    return np.where(value <= .0031308,value*12.92,1.055*np.maximum(value,0.)**(1/2.4)-.055)

def _decode_709_full(planes):
    y,cb,cr=(p.astype(np.float64)/255. for p in planes)
    cb=_resize_plane(cb,y.shape[1],y.shape[0])-.5; cr=_resize_plane(cr,y.shape[1],y.shape[0])-.5
    rgb=np.stack((y+1.5748*cr,y-.187324*cb-.468124*cr,y+1.8556*cb),axis=-1)
    return _srgb_to_linear(np.clip(rgb,0.,1.))

def _encode_709_full(linear, chroma420):
    r,g,b=np.moveaxis(np.clip(_linear_to_srgb(linear),0.,1.),-1,0)
    y=.2126*r+.7152*g+.0722*b; cb=(b-y)/1.8556+.5; cr=(r-y)/1.5748+.5
    q=lambda x: np.rint(np.clip(x,0.,1.)*255).astype(np.uint8)
    if chroma420:
        # C420jpeg has centred chroma samples. Box downsampling is the matching area
        # footprint after the RGB-domain foveation filter, not an independent YUV blur.
        cb=(cb[0::2,0::2]+cb[1::2,0::2]+cb[0::2,1::2]+cb[1::2,1::2])*.25
        cr=(cr[0::2,0::2]+cr[1::2,0::2]+cr[0::2,1::2]+cr[1::2,1::2])*.25
    return [q(y),q(cb),q(cr)]

def transform_planes(planes, config: FoveationConfig):
    """Frame-bank forward/reconstruct transform in the live shader's colour domain.

    The server samples an sRGB composition target and only subsequently produces YUV.
    Therefore C420 input is expanded with centred chroma, converted from full-range
    BT.709 R'G'B' to linear RGB, filtered/remapped there, converted back, then
    chroma-subsampled once. This deliberately does *not* average nonlinear Y/Cb/Cr
    planes independently. Input is already cropped by WO-10/Q3; eye halves never mix.
    """
    if len(planes)!=3 or planes[0].dtype != np.uint8: raise ValueError("native 8-bit YUV planes required")
    y=planes[0]; h,w2=y.shape; w=w2//2
    if w2%2 or h%2: raise ValueError("stereo luma must be even")
    chroma420=planes[1].shape == (h//2,w2//2) and planes[2].shape == (h//2,w2//2)
    if not chroma420 and (planes[1].shape != y.shape or planes[2].shape != y.shape): raise ValueError("unsupported chroma geometry")
    rgb=_decode_709_full(planes); reconstructed=[]
    for eye_rgb in (rgb[:,:w],rgb[:,w:]):
        components=[]
        for component in range(3):
            coded=forward_eye(eye_rgb[...,component],config)
            components.append(reconstruct_eye(coded,(w,h),config))
        reconstructed.append(np.stack(components,axis=-1))
    return _encode_709_full(np.concatenate(reconstructed,axis=1),chroma420)
