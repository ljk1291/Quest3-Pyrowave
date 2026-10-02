"""Fail-closed offline PyroWave frame-bank quality harness.

This module never touches ADB, SteamVR, or an arm record. `run` starts PC codec
work only while WO-0's read-only lease status remains active. Raw evidence is
private below results/local; the public report carries only aggregate scores and
hash provenance.
"""
from __future__ import annotations

import argparse, hashlib, json, math, os, re, shutil, subprocess, sys, tempfile, time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterator, Sequence

import numpy as np
from PIL import Image
from .ratequality import bytes_per_frame

SCHEMA = 3
HVS_HEIGHT_FACTORS = tuple(1.0 + index / 8.0 for index in range(16))
FPS = 90
WAVELETS = ("haar", "53", "97")
RATES_MBPS = (300, 500, 600, 800)
GEOMETRIES = ((3072, 3232), (2560, 2688), (2080, 2208))
DISPLAY_EYE = (3072, 3232)
DEFAULT_CROPS = (
    {"name":"text","eye":"left","x":.08,"y":.08,"w":.26,"h":.18},
    {"name":"foliage","eye":"left","x":.52,"y":.30,"w":.34,"h":.34},
    {"name":"dark_gradient","eye":"right","x":.08,"y":.58,"w":.34,"h":.28},
    {"name":"thin_lines","eye":"right","x":.58,"y":.08,"w":.28,"h":.25},
)

@dataclass(frozen=True)
class Y4MInfo:
    width:int; height:int; fps_num:int; fps_den:int; chroma:str; color_range:str; frame_bytes:int; frames:int

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def _chroma(token:str)->str:
    value=token.lower()
    if value in ("444","444p8"): return "444"
    if value in ("420","420jpeg","420mpeg2","420paldv","420p8"): return "420"
    if value.startswith(("444p","420p")): raise ValueError("high-bit-depth Y4M is unsupported")
    raise ValueError(f"unsupported Y4M chroma C{token}")

def _plane_shapes(info:Y4MInfo):
    if info.chroma=="444": return [(info.height,info.width)]*3
    return [(info.height,info.width),(info.height//2,info.width//2),(info.height//2,info.width//2)]

def _frame_bytes(width:int,height:int,chroma:str)->int:
    return width*height*3 if chroma=="444" else width*height*3//2

def _parse_header(line:bytes,path:Path)->Y4MInfo:
    text=line.decode("ascii","replace").strip()
    if not text.startswith("YUV4MPEG2 "): raise ValueError(f"{path}: not YUV4MPEG2")
    def token(prefix,default=None):
        for item in text.split()[1:]:
            if item.startswith(prefix): return item[len(prefix):]
        if default is not None:return default
        raise ValueError(f"{path}: missing {prefix} in Y4M header")
    try: width,height=int(token("W")),int(token("H")); fn,fd=(int(v) for v in token("F","0:1").split(":"))
    except ValueError as exc: raise ValueError(f"{path}: invalid Y4M geometry/rate") from exc
    if width<=0 or height<=0 or width%2 or height%2 or fn<=0 or fd<=0: raise ValueError(f"{path}: invalid Y4M geometry/rate")
    chroma=_chroma(token("C","420jpeg"))
    range_match=re.search(r"\bXCOLORRANGE=(FULL|LIMITED)\b",text)
    if not range_match: raise ValueError(f"{path}: missing XCOLORRANGE")
    color_range=range_match.group(1)
    return Y4MInfo(width,height,fn,fd,chroma,color_range,_frame_bytes(width,height,chroma),0)

def inspect_y4m(path:Path)->Y4MInfo:
    path=Path(path)
    with path.open("rb") as f:
        base=_parse_header(f.readline(),path); frames=0
        while tag:=f.readline():
            if not tag.startswith(b"FRAME"): raise ValueError(f"{path}: frame {frames} has no FRAME tag")
            if len(f.read(base.frame_bytes))!=base.frame_bytes: raise ValueError(f"{path}: truncated frame {frames}")
            frames+=1
    if not frames: raise ValueError(f"{path}: no frames")
    return Y4MInfo(**{**asdict(base),"frames":frames})

def iter_y4m(path:Path,info:Y4MInfo|None=None)->Iterator[tuple[int,list[np.ndarray],str]]:
    path=Path(path); info=info or inspect_y4m(path)
    with path.open("rb") as f:
        _parse_header(f.readline(),path)
        for index in range(info.frames):
            if not f.readline().startswith(b"FRAME"): raise ValueError(f"{path}: frame {index} tag changed")
            raw=f.read(info.frame_bytes)
            if len(raw)!=info.frame_bytes: raise ValueError(f"{path}: truncated frame {index}")
            pos=0; planes=[]
            for shape in _plane_shapes(info):
                n=shape[0]*shape[1]; planes.append(np.frombuffer(raw[pos:pos+n],np.uint8).reshape(shape).copy()); pos+=n
            yield index,planes,hashlib.sha256(raw).hexdigest()

def _header(info:Y4MInfo)->bytes:
    return f"YUV4MPEG2 W{info.width} H{info.height} F{info.fps_num}:{info.fps_den} Ip A1:1 C{info.chroma} XCOLORRANGE={info.color_range}\n".encode("ascii")

def write_y4m(path:Path,info:Y4MInfo,frames:Sequence[Sequence[np.ndarray]])->list[str]:
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); hashes=[]
    with path.open("wb") as f:
        f.write(_header(info))
        for planes in frames:
            if len(planes)!=3 or any(p.shape!=shape for p,shape in zip(planes,_plane_shapes(info))): raise ValueError("frame does not match declared Y4M geometry")
            raw=b"".join(np.ascontiguousarray(p).tobytes() for p in planes); f.write(b"FRAME\n"+raw); hashes.append(hashlib.sha256(raw).hexdigest())
    return hashes

def _open_writer(path:Path,info:Y4MInfo):
    path.parent.mkdir(parents=True,exist_ok=True); f=path.open("wb"); f.write(_header(info)); return f

def _write_frame(f,info:Y4MInfo,planes:Sequence[np.ndarray])->str:
    if len(planes)!=3 or any(p.shape!=shape for p,shape in zip(planes,_plane_shapes(info))): raise ValueError("frame does not match declared Y4M geometry")
    raw=b"".join(np.ascontiguousarray(p).tobytes() for p in planes); f.write(b"FRAME\n"+raw); return hashlib.sha256(raw).hexdigest()

def cap_bytes(mbps:int,fps:int=FPS)->int:
    if not isinstance(mbps,int) or not isinstance(fps,int) or mbps<=0 or fps<=0: raise ValueError("mbps and fps must be positive integers")
    return bytes_per_frame(mbps,fps)
def bpp(cap:int,ew:int,eh:int)->float:
    if min(cap,ew,eh)<=0: raise ValueError("cap and geometry must be positive")
    return cap*8/(2*ew*eh)
def _resize(plane,w,h): return np.asarray(Image.fromarray(plane).resize((w,h),Image.Resampling.LANCZOS)).copy()
def resize_per_eye(planes:Sequence[np.ndarray],ew:int,eh:int)->list[np.ndarray]:
    if len(planes)!=3 or planes[0].shape[1]%2: raise ValueError("expected side-by-side stereo planes")
    result=[]
    for plane in planes:
        h,w2=plane.shape; w=w2//2
        result.append(np.concatenate((_resize(plane[:,:w],ew,eh),_resize(plane[:,w:],ew,eh)),axis=1))
    return result

def to_420(planes:Sequence[np.ndarray])->list[np.ndarray]:
    y,cb,cr=planes; h,w2=y.shape; w=w2//2
    def down(p): return np.concatenate((_resize(p[:,:w],w//2,h//2),_resize(p[:,w:],w//2,h//2)),axis=1)
    return [y.copy(),down(cb),down(cr)]
def _resize_matching(planes,info:Y4MInfo,ew,eh):
    if info.chroma=="444": return resize_per_eye(planes,ew,eh)
    y=resize_per_eye([planes[0]]*3,ew,eh)[0]; ch=resize_per_eye([planes[1]]*3,ew//2,eh//2)[0]; cr=resize_per_eye([planes[2]]*3,ew//2,eh//2)[0]; return [y,ch,cr]

def validate_crops(crops):
    clean=[]; names=set()
    for c in crops:
        if not isinstance(c,dict) or set(c)!={"name","eye","x","y","w","h"}: raise ValueError("crop schema is exactly name, eye, x, y, w, h")
        if c["name"] in names or c["eye"] not in ("left","right"): raise ValueError("crop names must be unique and eye must be left or right")
        vals=[c[k] for k in ("x","y","w","h")]
        if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in vals): raise ValueError("crop coordinates must be finite")
        x,y,w,h=vals
        if x<0 or y<0 or w<=0 or h<=0 or x+w>1 or y+h>1: raise ValueError("crop crosses its eye boundary or falls outside the eye")
        names.add(c["name"]);clean.append(dict(c))
    if not clean: raise ValueError("at least one fixed crop is required")
    return clean

def crop_eye(planes,crop):
    validate_crops([crop]); result=[]
    for p in planes:
        h,w2=p.shape; w=w2//2; left=0 if crop["eye"]=="left" else w
        x=left+round(crop["x"]*w); y=round(crop["y"]*h); cw=max(1,round(crop["w"]*w)); ch=max(1,round(crop["h"]*h))
        if x<left or x+cw>left+w or y<0 or y+ch>h: raise ValueError("rounded crop crosses stereo seam")
        result.append(p[y:y+ch,x:x+cw].copy())
    return result

def crop_y4m(planes, info:Y4MInfo, crop):
    """Crop one eye using luma coordinates, then map exactly to C420 planes."""
    validate_crops([crop]); y_h, y_w2 = planes[0].shape; y_w = y_w2 // 2
    left = 0 if crop["eye"] == "left" else y_w
    x = left + round(crop["x"] * y_w); top = round(crop["y"] * y_h)
    width = max(1, round(crop["w"] * y_w)); height = max(1, round(crop["h"] * y_h))
    # C420 scoring needs chroma-aligned luma coordinates. Round inward, never
    # across an eye boundary; the normalized crop remains fixed for every cell.
    if info.chroma == "420":
        x -= x % 2; top -= top % 2; width -= width % 2; height -= height % 2
        if width <= 0 or height <= 0: raise ValueError("C420 crop is smaller than one chroma sample")
    if x < left or x + width > left + y_w or top < 0 or top + height > y_h: raise ValueError("rounded crop crosses stereo seam")
    result=[]
    for index,p in enumerate(planes):
        factor=2 if info.chroma=="420" and index else 1
        result.append(p[top//factor:(top+height)//factor, x//factor:(x+width)//factor].copy())
    return result

def frame_records(source):
    info=inspect_y4m(source); return [{"source_frame":i,"source_sha256":d} for i,_,d in iter_y4m(source,info)]

def hvs_factor_for_ppd(pixels_per_degree:float, image_height:int)->dict:
    """Map the upstream source formula to one emitted height factor, if possible.

    psnr.cpp computes nyquist_cpd = height * factor * pi / 360; therefore
    displayed pixels/degree = height * factor * pi / 180. No interpolation or
    invented factor is allowed: the binary emits only HVS_HEIGHT_FACTORS.
    """
    if not isinstance(pixels_per_degree,(int,float)) or not math.isfinite(pixels_per_degree) or pixels_per_degree <= 0 or not isinstance(image_height,int) or image_height <= 0: raise ValueError("HVS calibration inputs must be finite and positive")
    required=pixels_per_degree * 180.0 / (image_height * math.pi)
    selected=next((factor for factor in HVS_HEIGHT_FACTORS if abs(factor-required) <= 1e-6),None)
    return {"pixels_per_degree":pixels_per_degree,"image_height":image_height,"required_height_factor":required,"supported_height_factor":selected,"supported":selected is not None}

def _crop_height(crop, eye_height, chroma):
    height=max(1,round(crop["h"]*eye_height))
    return max(2,height-(height%2)) if chroma=="420" else height

def build_plan(source:Path,projection_px_per_deg:float,*,projection_evidence:str,crop_evidence:str|None=None,fixture:bool=False,fps:int=FPS,wavelets=WAVELETS,rates_mbps=RATES_MBPS,geometries=GEOMETRIES,display_eye=DISPLAY_EYE,crops=DEFAULT_CROPS)->dict:
    if not isinstance(projection_px_per_deg,(int,float)) or not math.isfinite(projection_px_per_deg) or projection_px_per_deg<=0: raise ValueError("projection_px_per_deg must be finite and positive")
    if not isinstance(projection_evidence,str) or not projection_evidence.strip(): raise ValueError("projection_evidence must name logged projection measurement")
    if not fixture and (not isinstance(crop_evidence,str) or not crop_evidence.strip()): raise ValueError("production plan requires semantic crop evidence")
    info=inspect_y4m(source)
    if (info.fps_num,info.fps_den) not in ((72,1),(90,1)): raise ValueError("source dump header must be F72:1 or F90:1")
    if (info.width//2,info.height)!=tuple(display_eye): raise ValueError("source dump must be logged presentation input")
    if not fixture and info.frames != 90: raise ValueError("production frame bank requires exactly 90 source frames")
    clean_crops=validate_crops(crops)
    cells=[]
    for wv in wavelets:
        if wv not in WAVELETS: raise ValueError(f"unsupported wavelet {wv}")
        for rate in rates_mbps:
            for ew,eh in geometries:
                cap=cap_bytes(int(rate),fps); cells.append({"wavelet":wv,"rate_mbps":int(rate),"fps":fps,"eye_width":int(ew),"eye_height":int(eh),"stereo_width":int(ew)*2,"encoded_chroma":info.chroma,"cap_bytes":cap,"bits_per_pixel":bpp(cap,int(ew),int(eh))})
    display_hvs=hvs_factor_for_ppd(float(projection_px_per_deg),int(display_eye[1]))
    codec_hvs=[hvs_factor_for_ppd(float(projection_px_per_deg)*math.sqrt((cell["eye_width"]/display_eye[0])*(cell["eye_height"]/display_eye[1])),cell["eye_height"]) for cell in cells]
    crop_hvs=[hvs_factor_for_ppd(float(projection_px_per_deg),_crop_height(crop,display_eye[1],info.chroma)) for crop in clean_crops]
    hvs={"source_formula":"ppd=height*height_factor*pi/180","display":display_hvs,"codec_cells":codec_hvs,"crops":crop_hvs,"all_supported":all(x["supported"] for x in [display_hvs,*codec_hvs,*crop_hvs])}
    return {"schema":SCHEMA,"kind":"pyrowave_frame_bank","fixture_only":bool(fixture),"source":{"sha256":sha256_file(source),"geometry":[info.width,info.height],"frames":info.frames,"header_fps":[info.fps_num,info.fps_den],"target_fps":fps,"chroma":info.chroma,"color_range":info.color_range,"frame_identity":frame_records(source)},"presentation_eye":list(display_eye),"projection_px_per_deg":float(projection_px_per_deg),"projection_evidence":projection_evidence.strip(),"crop_evidence":"fixture" if fixture else crop_evidence.strip(),"hvs_calibration":hvs,"resize":{"scope":"per_eye","filter":"lanczos3","seam_crossing":False},"crops":clean_crops,"cells":cells,"required_metrics":["psnr_y","psnr_cb","psnr_cr","ssim","vmaf","psnr_hvs_m_h"]}

def validate_plan(plan):
    if not isinstance(plan,dict) or plan.get("schema")!=SCHEMA or plan.get("kind")!="pyrowave_frame_bank": raise ValueError("not a frame-bank schema-3 manifest")
    src=plan.get("source",{}); ids=src.get("frame_identity")
    if src.get("chroma") not in ("420","444") or src.get("color_range") not in ("FULL","LIMITED"): raise ValueError("source format/range is unsupported")
    if not isinstance(ids,list) or len(ids)!=src.get("frames") or [x.get("source_frame") for x in ids]!=list(range(len(ids))): raise ValueError("source frame identities must be ordered and contiguous")
    if not isinstance(src.get("sha256"),str) or len(src["sha256"])!=64: raise ValueError("source hash is missing")
    clean_crops=validate_crops(plan.get("crops",[]))
    if plan.get("fixture_only") is not True:
        if src.get("frames") != 90: raise ValueError("production frame bank requires exactly 90 source frames")
        if not isinstance(plan.get("crop_evidence"),str) or not plan["crop_evidence"].strip(): raise ValueError("production plan requires semantic crop evidence")
    if plan.get("resize") != {"scope":"per_eye","filter":"lanczos3","seam_crossing":False}: raise ValueError("resize provenance does not match implementation")
    if not isinstance(src.get("geometry"),list) or len(src["geometry"]) != 2 or not all(isinstance(v,int) and v > 0 for v in src["geometry"]): raise ValueError("source geometry is invalid")
    if src.get("target_fps") != FPS or src.get("header_fps") not in ([72,1],[90,1]): raise ValueError("source frame-rate provenance is invalid")
    calibration=plan.get("hvs_calibration")
    if not isinstance(calibration,dict) or "all_supported" not in calibration: raise ValueError("HVS calibration is missing")
    expected_display=hvs_factor_for_ppd(plan["projection_px_per_deg"],plan["presentation_eye"][1])
    if calibration.get("display") != expected_display: raise ValueError("display HVS calibration drifted")
    if not plan.get("cells"): raise ValueError("frame bank contains no cells")
    for c in plan["cells"]:
        if c.get("encoded_chroma") != src.get("chroma"): raise ValueError("cell chroma must preserve the native dump format")
        if not all(isinstance(c.get(key),int) and c[key] > 0 for key in ("fps","eye_width","eye_height","stereo_width","rate_mbps","cap_bytes")): raise ValueError("cell geometry/rate is invalid")
        if c.get("fps") != src.get("target_fps") or c.get("fps") != FPS: raise ValueError("WO-1 target frame rate must be 90 Hz")
        if src.get("chroma") == "420" and (c["eye_width"] % 2 or c["eye_height"] % 2): raise ValueError("C420 cell geometry must be even")
        if c.get("cap_bytes")!=cap_bytes(c.get("rate_mbps"),c.get("fps")): raise ValueError("cell cap math does not match its rate and frame rate")
        if c.get("stereo_width")!=c.get("eye_width",0)*2: raise ValueError("cell stereo geometry is not two separate eyes")
    expected_codec=[hvs_factor_for_ppd(plan["projection_px_per_deg"]*math.sqrt((cell["eye_width"]/plan["presentation_eye"][0])*(cell["eye_height"]/plan["presentation_eye"][1])),cell["eye_height"]) for cell in plan["cells"]]
    expected_crops=[hvs_factor_for_ppd(plan["projection_px_per_deg"],_crop_height(crop,plan["presentation_eye"][1],src["chroma"])) for crop in clean_crops]
    if calibration.get("codec_cells") != expected_codec or calibration.get("crops") != expected_crops or calibration.get("all_supported") != all(item["supported"] for item in [expected_display,*expected_codec,*expected_crops]): raise ValueError("HVS calibration drifted")
    return plan

class WindowGuard:
    def __init__(self,window:Path,arm:Path|None=None,status_command:Sequence[str]|None=None,clock:Callable[[],float]=time.time): self.window=Path(window);self.arm=None if arm is None else Path(arm);self.command=list(status_command or [sys.executable,"-m","tools.quest3.unattended","status"]);self.clock=clock
    def status(self):
        cmd=[*self.command,"--window",str(self.window),"--require-allow","frame_bank_pc"]+([] if self.arm is None else ["--arm",str(self.arm)])
        try: r=subprocess.run(cmd,capture_output=True,text=True,timeout=10,check=False)
        except (OSError,subprocess.SubprocessError) as exc: raise PermissionError("WO-0 lease status unavailable") from exc
        try: data=json.loads(r.stdout)
        except ValueError as exc: raise PermissionError("WO-0 lease status is not valid JSON") from exc
        if r.returncode or data.get("schema")!=1 or data.get("lease",{}).get("active") is not True: raise PermissionError("WO-0 lease is inactive")
        deadline=data["lease"].get("deadline_epoch_s")
        guards=data.get("guards",{}); cancel=data.get("cancellation",{})
        if not isinstance(deadline,(int,float)) or not math.isfinite(deadline) or deadline<=self.clock() or data.get("arm",{}).get("active") is not True or any(guards.get(x,{}).get(k) is not True for x in ("restorer","monitor") for k in ("ready","alive")) or cancel.get("stop_requested") or cancel.get("paused") or cancel.get("competing_gpu") or not cancel.get("monitor_fresh"):
            raise PermissionError("WO-0 lease health check failed")
        return data
    def run(self,argv,*,cwd:Path,env:dict,timeout_s:float):
        self.status()
        if not isinstance(timeout_s,(int,float)) or not math.isfinite(timeout_s) or timeout_s<=0: raise ValueError("subprocess timeout must be finite and positive")
        # Disk-backed logs prevent a chatty child from blocking on undrained PIPEs.
        with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as output:
            proc=subprocess.Popen(list(argv),cwd=str(cwd),env=env,stdout=output,stderr=output,text=True)
            deadline=time.monotonic()+timeout_s
            try:
                while proc.poll() is None:
                    if time.monotonic()>=deadline: raise TimeoutError("subprocess timeout")
                    self.status(); time.sleep(.5)
                self.status()  # a lease can be revoked between poll() and return.
            except Exception:
                if proc.poll() is None:
                    proc.terminate()
                    try: proc.wait(timeout=10)
                    except subprocess.TimeoutExpired: proc.kill();proc.wait()
                raise
            output.seek(0); text=output.read()[-8192:]
        return proc.returncode,text,""

def _window_allowed(path:Path)->dict: return WindowGuard(path,status_command=[]).status() # retained only for legacy callers; intentionally unusable without WO-0

def _tool_path(value):
    if not isinstance(value,(str,Path)) or not str(value).strip(): return None
    p=Path(str(value)); return p if p.exists() else (Path(shutil.which(str(value))) if shutil.which(str(value)) else None)
def required_tools(tools):
    missing=[n for n in ("encode","decode","ffmpeg","psnr_hvs_m_h") if (_tool_path(tools.get(n)) is None)]
    if missing: raise FileNotFoundError("required scorer/codec tool unavailable: "+", ".join(missing))
def tool_provenance(tools): return {n:{"sha256":sha256_file(p),"basename":p.name} for n,v in tools.items() if (p:=_tool_path(v)) is not None}

def parse_hvs_m_h(text,height_factor:float)->float:
    pats=re.findall(r"HeightFactor\s*=\s*([0-9.]+).*?PSNR-HVS-M-H:\s*\(Y\)\s*([+0-9.eEinfINF-]+)",text,re.S)
    for factor,value in pats:
        if abs(float(factor)-height_factor)<1e-4:
            val=float(value)
            if math.isnan(val): raise ValueError("PSNR-HVS-M-H scorer emitted NaN")
            return val
    raise ValueError("PSNR-HVS-M-H scorer did not emit the requested upstream height factor")
def _score_hvs_m_h(tool,reference,distorted,frames,hf,guard,cwd,env,timeout):
    code,out,err=guard.run([str(tool),"--reference",str(reference),"--distorted",str(distorted),"--frames",str(frames)],cwd=cwd,env=env,timeout_s=timeout)
    if code: raise RuntimeError("PSNR-HVS-M-H scorer failed")
    return parse_hvs_m_h(out+err,hf)
def _valid_metric(k,v): return isinstance(v,(int,float)) and not math.isnan(v) and (math.isfinite(v) or k.startswith("psnr"))
def _score_ffmpeg(tool,distorted,reference,workdir,guard,env,timeout_s):
    # This is rdmatrix.score's established ffmpeg graph, but the process is run
    # through WO-0 so a revoked lease terminates it too.
    from . import rdmatrix
    graph=("[0:v]split=3[a1][a2][a3];[1:v]split=3[b1][b2][b3];"
           "[a1][b1]psnr=stats_file=-[p];[a2][b2]ssim=stats_file=-[s];"
           "[a3][b3]libvmaf=feature=name=psnr_hvs:log_fmt=json:log_path=vmaf.json[v]")
    code,out,err=guard.run([str(tool),"-hide_banner","-i",str(Path(distorted).resolve()),"-i",str(Path(reference).resolve()),"-lavfi",graph,"-map","[p]","-map","[s]","-map","[v]","-f","null","-"],cwd=workdir,env=env,timeout_s=timeout_s)
    text=out+err
    if code: raise RuntimeError("ffmpeg/libvmaf scorer failed")
    values={}; values.update(rdmatrix.parse_psnr(text) or {}); values.update(rdmatrix.parse_ssim(text) or {})
    log=Path(workdir)/"vmaf.json"
    values.update(rdmatrix.parse_vmaf_log(log))
    log.unlink(missing_ok=True)
    return values

def score_pair(tools,distorted,reference,workdir,px_per_deg,*,frames,hvs_height_factor,guard,env,timeout_s):
    values=_score_ffmpeg(tools["ffmpeg"],distorted,reference,workdir,guard,env,timeout_s)
    expected=("psnr_y","psnr_u","psnr_v","ssim_y","ssim_all","vmaf")
    missing=[k for k in expected if not _valid_metric(k,values.get(k))]
    if missing: raise RuntimeError("ffmpeg/libvmaf did not emit required metrics: "+", ".join(missing))
    return {"psnr_y":values["psnr_y"],"psnr_cb":values["psnr_u"],"psnr_cr":values["psnr_v"],"ssim":values["ssim_y"],"ssim_all":values["ssim_all"],"vmaf":values["vmaf"],"psnr_hvs_m_h":_score_hvs_m_h(tools["psnr_hvs_m_h"],reference,distorted,frames,hvs_height_factor,guard,workdir,env,timeout_s),"projection_px_per_deg":px_per_deg,"hvs_height_factor":hvs_height_factor}

def _private_root()->Path: return Path(__file__).resolve().parents[2]/"results"/"local"
def _private_path(path:Path):
    root=_private_root().resolve(); candidate=Path(path).resolve()
    if not candidate.is_relative_to(root): raise ValueError("raw frame-bank evidence must be under this repository's results/local")
    return candidate
def _stream_reference(source,source_info,cell,path):
    info=Y4MInfo(cell["stereo_width"],cell["eye_height"],cell["fps"],1,source_info.chroma,source_info.color_range,_frame_bytes(cell["stereo_width"],cell["eye_height"],source_info.chroma),source_info.frames); ids=[]
    with _open_writer(path,info) as out:
        for index,planes,digest in iter_y4m(source,source_info):
            ids.append({"source_frame":index,"source_sha256":digest,"reference_sha256":_write_frame(out,info,_resize_matching(planes,source_info,cell["eye_width"],cell["eye_height"]))})
    return info,ids
def _write_display(source,info,out_path,display_eye):
    di=Y4MInfo(display_eye[0]*2,display_eye[1],info.fps_num,info.fps_den,info.chroma,info.color_range,_frame_bytes(display_eye[0]*2,display_eye[1],info.chroma),info.frames)
    with _open_writer(out_path,di) as out:
        for _,p,_ in iter_y4m(source,info): _write_frame(out,di,_resize_matching(p,info,*display_eye))
    return di
def _grid_png(path,source,decoded):
    tiles=[]; y_shape=source[0].shape
    for ref,got in zip(source,decoded):
        # Grids are qualitative. Upsampling C420 chroma here is solely to make a
        # viewable side-by-side PNG; all numeric scores use the original Y4M.
        if ref.shape != y_shape: ref = _resize(ref,y_shape[1],y_shape[0])
        if got.shape != y_shape: got = _resize(got,y_shape[1],y_shape[0])
        tiles += [np.repeat(ref[...,None],3,axis=2),np.repeat(got[...,None],3,axis=2)]
    path.parent.mkdir(parents=True,exist_ok=True);Image.fromarray(np.concatenate(tiles,axis=1)).save(path)

def _assert_same_frames(reference,decoded,ref_info):
    dec_info=inspect_y4m(decoded)
    if (dec_info.width,dec_info.height,dec_info.frames,dec_info.chroma,dec_info.color_range,dec_info.fps_num,dec_info.fps_den)!=(ref_info.width,ref_info.height,ref_info.frames,ref_info.chroma,ref_info.color_range,ref_info.fps_num,ref_info.fps_den): raise ValueError("decoded_identity_or_geometry_mismatch")
    return dec_info

def run_plan(plan_path:Path,source:Path,private_out:Path,tools:dict,window:Path,*,arm:Path|None=None,status_command:Sequence[str]|None=None,command_timeout_s:float=900,keep_artifacts:bool=False,allow_fixture:bool=False,score_fn=score_pair):
    raw_plan=Path(plan_path).read_bytes();plan=validate_plan(json.loads(raw_plan)); source=Path(source); private_out=_private_path(private_out); guard=WindowGuard(window,arm,status_command)
    if plan.get("fixture_only") and not allow_fixture: raise ValueError("fixture-only plans cannot run outside a CPU test")
    if not plan["hvs_calibration"]["all_supported"] and not allow_fixture: raise ValueError("PSNR-HVS-M-H calibration is unsupported at the recorded viewing density")
    required_tools(tools); guard.status(); initial={n:sha256_file(_tool_path(v)) for n,v in tools.items()};
    if sha256_file(source)!=plan["source"]["sha256"]: raise ValueError("source dump hash differs from frozen plan")
    source_info=inspect_y4m(source)
    if source_info.frames!=plan["source"]["frames"]: raise ValueError("source dump frame count differs from frozen plan")
    private_out.mkdir(parents=True,exist_ok=True); result={"schema":SCHEMA,"kind":"pyrowave_frame_bank_result","frozen_plan_sha256":hashlib.sha256(raw_plan).hexdigest(),"source_sha256_start":sha256_file(source),"source_sha256_end":None,"tool_provenance_start":initial,"tool_provenance_end":None,"projection_px_per_deg":plan["projection_px_per_deg"],"projection_evidence":plan["projection_evidence"],"cells":[],"complete":False,"failure_reasons":[]}
    for index,cell in enumerate(plan["cells"]):
        directory=private_out/f"cell-{index:02d}-{cell['wavelet']}-{cell['rate_mbps']}-{cell['eye_width']}x{cell['eye_height']}";directory.mkdir(parents=True,exist_ok=True); ref=directory/f"reference-c{cell['encoded_chroma']}.y4m";wave=directory/"encoded.wave";decoded=directory/f"decoded-c{cell['encoded_chroma']}.y4m"; row=dict(cell)
        try:
            ref_info,ids=_stream_reference(source,source_info,cell,ref); row["identity_count"]=len(ids)
            if [x["source_sha256"] for x in ids] != [x["source_sha256"] for x in plan["source"]["frame_identity"]]: raise ValueError("source_frame_identity_drift")
            env=os.environ.copy();env["PYROWAVE_WAVELET"]=cell["wavelet"]
            # Pinned pyrowave-encode CLI: input.y4m output.wave bytes_per_frame.
            code,_,_=guard.run([str(tools["encode"]),str(ref),str(wave),str(cell["cap_bytes"])],cwd=directory,env=env,timeout_s=command_timeout_s)
            if code or not wave.is_file() or wave.stat().st_size<=0: raise RuntimeError("encode_failed")
            row["actual_container_bytes"]=wave.stat().st_size
            # Pinned pyrowave-decode CLI: input.wave output.y4m.
            code,_,_=guard.run([str(tools["decode"]),str(wave),str(decoded)],cwd=directory,env=env,timeout_s=command_timeout_s)
            if code or not decoded.is_file(): raise RuntimeError("decode_failed")
            dec_info=_assert_same_frames(ref,decoded,ref_info);row["decoded_frame_identity"]=[{"cell_frame":i,"source_frame":x["source_frame"],"reference_sha256":x["reference_sha256"],"decoded_sha256":d} for (i,_,d),x in zip(iter_y4m(decoded,dec_info),ids)]
            if len(row["decoded_frame_identity"])!=len(ids): raise ValueError("decoded_identity_or_geometry_mismatch")
            common=dict(frames=ref_info.frames,hvs_height_factor=plan["hvs_calibration"]["codec_cells"][index]["supported_height_factor"],guard=guard,env=env,timeout_s=command_timeout_s)
            codec_ppd=plan["projection_px_per_deg"]*math.sqrt((cell["eye_width"]/plan["presentation_eye"][0])*(cell["eye_height"]/plan["presentation_eye"][1]))
            row["codec_only"]=score_fn(tools,decoded,ref,directory,codec_ppd,**common)
            display_ref=directory/"source-display.y4m";display_dec=directory/"decoded-display.y4m";_write_display(source,source_info,display_ref,plan["presentation_eye"]);_write_display(decoded,dec_info,display_dec,plan["presentation_eye"])
            display_common={**common,"hvs_height_factor":plan["hvs_calibration"]["display"]["supported_height_factor"]}
            row["displayed"]=score_fn(tools,display_dec,display_ref,directory,plan["projection_px_per_deg"],**display_common);row["crops"]={}
            # Crop score files are written/consumed one crop at a time; only one frame is retained for its grid.
            disp_info=inspect_y4m(display_ref)
            for crop in plan["crops"]:
                rp,gp=directory/f"crop-{crop['name']}-reference.y4m",directory/f"crop-{crop['name']}-decoded.y4m"; first=None
                with _open_writer(rp,Y4MInfo(1,1,disp_info.fps_num,disp_info.fps_den,disp_info.chroma,disp_info.color_range,0,disp_info.frames)) as rf: pass
                # Crops differ in size; derive from first stream frame before opening final writers.
                riter=iter_y4m(display_ref,disp_info); giter=iter_y4m(display_dec,inspect_y4m(display_dec)); _,rp0,_=next(riter); _,gp0,_=next(giter); riter.close(); giter.close(); c0=crop_y4m(rp0,disp_info,crop); ci=Y4MInfo(c0[0].shape[1],c0[0].shape[0],disp_info.fps_num,disp_info.fps_den,disp_info.chroma,disp_info.color_range,_frame_bytes(c0[0].shape[1],c0[0].shape[0],disp_info.chroma),disp_info.frames)
                with _open_writer(rp,ci) as rf,_open_writer(gp,ci) as gf:
                    # Reopen lockstep streams: bounded memory regardless of corpus length.
                    for (_,rplanes,_),(_,gplanes,_) in zip(iter_y4m(display_ref,disp_info),iter_y4m(display_dec,inspect_y4m(display_dec))):
                        _write_frame(rf,ci,crop_y4m(rplanes,disp_info,crop))
                        _write_frame(gf,ci,crop_y4m(gplanes,disp_info,crop))
                crop_common={**common,"hvs_height_factor":plan["hvs_calibration"]["crops"][plan["crops"].index(crop)]["supported_height_factor"]}
                row["crops"][crop["name"]]=score_fn(tools,gp,rp,directory,plan["projection_px_per_deg"],**crop_common);_grid_png(directory/"grids"/f"PRIVATE-{crop['name']}.png",c0,crop_y4m(gp0,disp_info,crop))
        except (PermissionError,TimeoutError,ValueError,RuntimeError) as exc:
            row["error"]=str(exc) if str(exc) in {"encode_failed","decode_failed","decoded_identity_or_geometry_mismatch"} else "cell_failed";result["failure_reasons"].append(row["error"])
        result["cells"].append(row)
        if not keep_artifacts:
            for p in (ref,wave,decoded,directory/"source-display.y4m",directory/"decoded-display.y4m"): p.unlink(missing_ok=True)
    result["source_sha256_end"]=sha256_file(source); result["tool_provenance_end"]={n:sha256_file(_tool_path(v)) for n,v in tools.items()}
    if result["source_sha256_end"]!=result["source_sha256_start"]: result["failure_reasons"].append("source_changed_during_run")
    if result["tool_provenance_end"]!=result["tool_provenance_start"]: result["failure_reasons"].append("tool_changed_during_run")
    if hashlib.sha256(Path(plan_path).read_bytes()).hexdigest()!=result["frozen_plan_sha256"]: result["failure_reasons"].append("plan_changed_during_run")
    result["complete"]=not result["failure_reasons"] and len(result["cells"])==len(plan["cells"]); (private_out/"framebank-private.json").write_text(json.dumps(result,indent=2),encoding="utf-8"); return result

def sanitized_report(result):
    keep=("wavelet","rate_mbps","fps","eye_width","eye_height","encoded_chroma","cap_bytes","bits_per_pixel","actual_container_bytes","codec_only","displayed","crops","error")
    return {"schema":SCHEMA,"kind":"pyrowave_frame_bank_sanitized","complete":result.get("complete") is True,"failure_reasons":list(result.get("failure_reasons",[])),"frozen_plan_sha256":result.get("frozen_plan_sha256"),"source_sha256":result.get("source_sha256_end"),"tool_provenance":result.get("tool_provenance_end"),"projection_px_per_deg":result.get("projection_px_per_deg"),"cells":[{k:r.get(k) for k in keep} for r in result.get("cells",[])],"optical_latency_ms":None,"display_fps":None}
def _main_plan(a):
    p=build_plan(Path(a.source),a.pixels_per_degree,projection_evidence=a.projection_evidence,crop_evidence=a.crop_evidence);Path(a.out).write_text(json.dumps(p,indent=2),encoding="utf-8");print(f"wrote frozen plan with {len(p['cells'])} cells; no codec/scorer was run");return 0
def _main_run(a):
    tools={"encode":a.encode,"decode":a.decode,"ffmpeg":a.ffmpeg,"psnr_hvs_m_h":a.psnr_hvs_m_h};r=run_plan(Path(a.plan),Path(a.source),Path(a.private_out),tools,Path(a.window),arm=None if not a.arm else Path(a.arm),command_timeout_s=a.command_timeout_s,keep_artifacts=a.keep_artifacts);report=sanitized_report(r);Path(a.report).write_text(json.dumps(report,indent=2),encoding="utf-8");print(f"wrote sanitized report: complete={report['complete']}");return 0 if report["complete"] else 2
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest="command",required=True);a=s.add_parser("plan");a.add_argument("--source",required=True);a.add_argument("--pixels-per-degree",type=float,required=True);a.add_argument("--projection-evidence",required=True);a.add_argument("--crop-evidence",required=True);a.add_argument("--out",required=True);r=s.add_parser("run");r.add_argument("--plan",required=True);r.add_argument("--source",required=True);r.add_argument("--private-out",required=True);r.add_argument("--report",required=True);r.add_argument("--window",required=True);r.add_argument("--arm");r.add_argument("--encode",required=True);r.add_argument("--decode",required=True);r.add_argument("--ffmpeg",required=True);r.add_argument("--psnr-hvs-m-h",required=True);r.add_argument("--command-timeout-s",type=float,default=900);r.add_argument("--keep-artifacts",action="store_true");x=p.parse_args(argv);return _main_plan(x) if x.command=="plan" else _main_run(x)
if __name__=="__main__": raise SystemExit(main())
