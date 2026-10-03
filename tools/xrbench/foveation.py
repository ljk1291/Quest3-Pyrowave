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
# The unrounded ratio-2 derivative peaks at 2r-1 = 3 source pixels/output
# pixel.  Allocation is rounded to 32 pixels, which raises the actual Q3
# maximum to 3.18; at s=1 it is 6.35.  A nine-pixel support safely covers that
# footprint at every subpixel phase.  This is a support bound, never a clamp:
# an unsupported geometry fails before producing a different filter.
MAX_FOOTPRINT_PIXELS = 7.0
FILTER_RADIUS = 4
TILE_ROWS = 96

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

def hlsl_forward_map_uv(uv: np.ndarray, full_size: tuple[int,int], encoded_size_: tuple[int,int], config: FoveationConfig) -> np.ndarray:
    """Float32 evaluation of the compiled HLSL ``compressedUV`` algebra.

    This is intentionally separate from :func:`forward_map_uv`.  The parity
    test samples joins, asymmetric shifts and both ends with the shader's
    float32 precision, while the normal frame-bank path retains float64 only
    so that offline reference scores do not accumulate numerical noise.
    """
    uv=np.asarray(uv,dtype=np.float32)
    if uv.shape[-1] != 2: raise ValueError("uv must end in xy")
    if config.blur_only: return uv.copy()
    out=np.empty_like(uv)
    for axis,(full,enc,shift) in enumerate(zip(full_size,encoded_size_,config.center_shift)):
        er,c1,c2,lo,hi=(np.float32(x) for x in _params(full,enc,config.center_fraction,config.edge_ratio,shift))
        x=uv[...,axis]/er
        center=x*c2/np.float32(config.edge_ratio)+c1
        d2=x*c2; d3=(x-np.float32(1.0))*c2+np.float32(1.0)
        left=(x/lo)*center+(np.float32(1.0)-x/lo)*d2
        right=((np.float32(1.0)-x)/(np.float32(1.0)-hi))*center+(np.float32(1.0)-(np.float32(1.0)-x)/(np.float32(1.0)-hi))*d3
        out[...,axis]=np.where(x < lo,left,np.where(x > hi,right,center))
    return out

def hlsl_area_weights(source_uv: np.ndarray, footprint: np.ndarray, size: tuple[int,int]) -> tuple[np.ndarray, np.ndarray]:
    """Return the exact 9x9 overlap weights and source indices used by HLSL.

    The result is used only by the CPU parity gate.  The image path keeps a
    tile-local accumulation instead of materialising this tensor.
    """
    width,height=size
    centre=np.asarray(source_uv,dtype=np.float32)*np.array((width,height),np.float32)
    fp=np.asarray(footprint,dtype=np.float32)
    left=centre-fp*.5; right=centre+fp*.5; base=np.floor(centre).astype(np.int32)
    weights=[]; indices=[]
    for ox in range(-FILTER_RADIUS,FILTER_RADIUS+1):
        for oy in range(-FILTER_RADIUS,FILTER_RADIUS+1):
            pixel=base+np.array((ox,oy),np.int32)
            p0=pixel.astype(np.float32); p1=p0+1.
            overlap=np.maximum(0.,np.minimum(right,p1)-np.maximum(left,p0))
            weights.append(overlap[...,0]*overlap[...,1])
            indices.append(np.stack((np.clip(pixel[...,0],0,width-1),np.clip(pixel[...,1],0,height-1)),axis=-1))
    return np.stack(weights,axis=-1),np.stack(indices,axis=-2)

def inverse_map_uv(uv: np.ndarray, full_size: tuple[int,int], encoded_size_: tuple[int,int], config: FoveationConfig) -> np.ndarray:
    """Inverse of :func:`forward_map_uv` for reconstruction.

    The normal live profile has a zero centre shift.  For it, use the exact
    quadratic inverse from upstream 061dc0b rather than forty-two bisection
    passes per pixel.  Non-zero diagnostic shifts retain bisection because the
    shifted join algebra is deliberately kept in the shader forward form.
    """
    uv=np.asarray(uv,dtype=np.float64); out=np.empty_like(uv)
    if config.blur_only: return uv.copy()
    if config.center_shift == (0.0, 0.0):
        for axis,(full,enc) in enumerate(zip(full_size,encoded_size_)):
            ratio=config.edge_ratio; c=config.center_fraction
            edge=full-c*full
            center=1.0-math.ceil(edge/(ratio*2.0))*(ratio*2.0)/full
            scale=(center+(1.0-center)/ratio)*full/enc
            c0=(1.0-center)*.5
            c1=(ratio-1.0)*c0/ratio
            c2=(ratio-1.0)*center+1.0
            loc=c0/c2; hic=1.0-c0/c2
            al=c2*(1.0-ratio)/(ratio*loc)
            bl=(c1+c2*loc)/loc
            ar=c2*(ratio-1.0)/(ratio*(1.0-hic))
            br=(c2-ratio*c1-2*ratio*c2+c2*ratio*(1.0-hic)+ratio)/(ratio*(1.0-hic))
            cr=(c2*ratio-c2)*(c1-hic+c2*hic)/(ratio*(1.0-hic)**2)
            source=uv[...,axis]
            left=(-bl+np.sqrt(np.maximum(0.0,bl*bl+4.0*al*source)))/(2.0*al)
            right=(-br+np.sqrt(np.maximum(0.0,br*br-4.0*(cr-ar*source))))/(2.0*ar)
            middle=(source-c1)*ratio/c2
            out[...,axis]=np.where(source < c0,left,np.where(source > 1.0-c0,right,middle))*scale
        return out
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

def _area_box(image: np.ndarray, source_uv: np.ndarray, footprint: np.ndarray) -> np.ndarray:
    """Exact normalized overlap weights for a bounded source-pixel box footprint."""
    h,w=image.shape; cx=source_uv[...,0]*w; cy=source_uv[...,1]*h
    fx=footprint[...,0]; fy=footprint[...,1]
    if np.any(fx > MAX_FOOTPRINT_PIXELS + 1e-8) or np.any(fy > MAX_FOOTPRINT_PIXELS + 1e-8):
        raise ValueError("foveation footprint exceeds declared profile bound")
    left=cx-fx*.5; right=cx+fx*.5; top=cy-fy*.5; bottom=cy+fy*.5
    accum=np.zeros(cx.shape,np.float64); weight=np.zeros(cx.shape,np.float64)
    # A seven-pixel box can overlap nine source cells at an adverse subpixel
    # phase.  The same [-4, 4] support is unrolled by the native shader.
    bx=np.floor(cx).astype(int); by=np.floor(cy).astype(int)
    for ox in range(-FILTER_RADIUS,FILTER_RADIUS+1):
        ix=np.clip(bx+ox,0,w-1); px0=bx+ox; px1=px0+1
        wx=np.maximum(0.,np.minimum(right,px1)-np.maximum(left,px0))
        for oy in range(-FILTER_RADIUS,FILTER_RADIUS+1):
            iy=np.clip(by+oy,0,h-1); py0=by+oy; py1=py0+1
            wy=np.maximum(0.,np.minimum(bottom,py1)-np.maximum(top,py0)); ww=wx*wy
            accum += image[iy,ix]*ww; weight += ww
    return accum/np.maximum(weight,1e-12)

def forward_eye(image: np.ndarray, config: FoveationConfig, *, tile_rows: int=TILE_ROWS) -> np.ndarray:
    """Area-prefilter and resample one plane into encoded space.

    The filter integrates one source-pixel box exactly. The footprint is the
    forward-map Jacobian once, not a Jacobian-sized offset fed through the map.
    """
    if image.ndim != 2: raise ValueError("one image plane expected")
    h,w=image.shape; ew,eh=encoded_size(w,h,config); out=np.empty((eh,ew),np.float64); x=(np.arange(ew)+.5)/ew
    for start in range(0,eh,tile_rows):
        stop=min(eh,start+tile_rows); y=(np.arange(start,stop)+.5)/eh; xx,yy=np.meshgrid(x,y)
        uv=np.stack((xx,yy),axis=-1); source=forward_map_uv(uv,(w,h),(ew,eh),config)
        footprint=local_squeeze(uv,(w,h),(ew,eh),config)*(1+config.softness*softness_ramp(uv,config)[...,None])
        out[start:stop]=_area_box(image,source,footprint)
    return out

def reconstruct_eye(encoded: np.ndarray, full_size: tuple[int,int], config: FoveationConfig, *, tile_rows: int=TILE_ROWS) -> np.ndarray:
    w,h=full_size; out=np.empty((h,w),np.float64); x=(np.arange(w)+.5)/w
    for start in range(0,h,tile_rows):
        stop=min(h,start+tile_rows); y=(np.arange(start,stop)+.5)/h; xx,yy=np.meshgrid(x,y)
        uv=np.stack((xx,yy),axis=-1)
        out[start:stop]=_bilinear(encoded,inverse_map_uv(uv,full_size,(encoded.shape[1],encoded.shape[0]),config))
    return out

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

@dataclass(frozen=True)
class EncodedPlanes:
    """Small per-eye YUV representation; no implied reconstruction or codec result."""
    planes: tuple[np.ndarray,np.ndarray,np.ndarray]
    expanded_eye: tuple[int,int]
    encoded_eye: tuple[int,int]
    chroma420: bool
    config: FoveationConfig

def _split_eyes(planes):
    y,cb,cr=planes; h,w2=y.shape; w=w2//2
    chroma420=cb.shape == (h//2,w2//2) and cr.shape == (h//2,w2//2)
    factor=2 if chroma420 else 1
    return [(y[:,:w],cb[:,:w//factor],cr[:,:w//factor]),(y[:,w:],cb[:,w//factor:],cr[:,w//factor:])],(w,h),chroma420

def encode_planes(planes, config: FoveationConfig) -> EncodedPlanes:
    """Convert already-cropped stereo C420jpeg/FULL frames into smaller encoded planes."""
    eyes,size,chroma420=_split_eyes(planes); enc=[]
    for eye in eyes:
        rgb=_decode_709_full(eye); out=[]
        for channel in range(3): out.append(forward_eye(rgb[...,channel],config))
        enc.append(_encode_709_full(np.stack(out,axis=-1),chroma420))
    return EncodedPlanes(tuple(np.concatenate((enc[0][i],enc[1][i]),axis=1) for i in range(3)),size,encoded_size(*size,config),chroma420,config)

def reconstruct_planes(decoded_planes, encoded: EncodedPlanes):
    """Expand codec-decoded small planes back to the already-cropped stereo reference size."""
    eyes,small_size,chroma420=_split_eyes(decoded_planes)
    if small_size != encoded.encoded_eye or chroma420 != encoded.chroma420: raise ValueError("decoded geometry/chroma drifted")
    rebuilt=[]
    for eye in eyes:
        rgb=_decode_709_full(eye); out=[]
        for channel in range(3): out.append(reconstruct_eye(rgb[...,channel],encoded.expanded_eye,encoded.config))
        rebuilt.append(_encode_709_full(np.stack(out,axis=-1),encoded.chroma420))
    return [np.concatenate((rebuilt[0][i],rebuilt[1][i]),axis=1) for i in range(3)]

def blur_reference(planes, config: FoveationConfig):
    """Reference reconstructed from the same foveated prefilter without codec loss."""
    encoded=encode_planes(planes,config)
    return reconstruct_planes(encoded.planes,encoded)

def transform_planes(planes, config: FoveationConfig):
    """Frame-bank forward/reconstruct transform in the live shader's colour domain.

    The server samples an sRGB composition target and only subsequently produces YUV.
    Therefore C420 input is expanded with centred chroma, converted from full-range
    BT.709 R'G'B' to linear RGB, filtered/remapped there, converted back, then
    chroma-subsampled once. This deliberately does *not* average nonlinear Y/Cb/Cr
    planes independently. Input is already cropped by WO-10/Q3; eye halves never mix.
    """
    encoded=encode_planes(planes,config)
    return reconstruct_planes(encoded.planes,encoded)
