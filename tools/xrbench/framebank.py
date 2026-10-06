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

SCHEMA = 4
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
    chroma='420jpeg' if info.chroma=='420' else info.chroma
    return f"YUV4MPEG2 W{info.width} H{info.height} F{info.fps_num}:{info.fps_den} Ip A1:1 C{chroma} XCOLORRANGE={info.color_range}\n".encode("ascii")

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

def validate_crops(crops, *, resolved=False):
    clean=[]; names=set(); required={"name","eye","x","y","w","h"}
    for c in crops:
        if not isinstance(c,dict) or set(c) != (required | ({"resolved_pixels"} if resolved else set())): raise ValueError("crop schema is exactly name, eye, x, y, w, h" + (", resolved_pixels" if resolved else ""))
        if not isinstance(c["name"],str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}",c["name"]): raise ValueError("crop name must be a safe lowercase filename label")
        if c["name"] in names or c["eye"] not in ("left","right"): raise ValueError("crop names must be unique and eye must be left or right")
        vals=[c[k] for k in ("x","y","w","h")]
        if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in vals): raise ValueError("crop coordinates must be finite")
        x,y,w,h=vals
        if x<0 or y<0 or w<=0 or h<=0 or x+w>1 or y+h>1: raise ValueError("crop crosses its eye boundary or falls outside the eye")
        names.add(c["name"]);clean.append(dict(c))
    if not clean: raise ValueError("at least one fixed crop is required")
    return clean

def resolve_crop_pixels(crop, eye_width:int, eye_height:int, chroma:str):
    """Resolve one normalized eye crop once; C420 dimensions are inward aligned."""
    validate_crops([crop]);
    if not isinstance(eye_width,int) or not isinstance(eye_height,int) or eye_width <= 0 or eye_height <= 0: raise ValueError("crop eye geometry is invalid")
    left=0 if crop["eye"]=="left" else eye_width
    x=left+round(crop["x"]*eye_width); y=round(crop["y"]*eye_height)
    width=max(1,round(crop["w"]*eye_width)); height=max(1,round(crop["h"]*eye_height))
    if chroma=="420":
        x-=x%2; y-=y%2; width-=width%2; height-=height%2
        if width <= 0 or height <= 0: raise ValueError("C420 crop is smaller than one chroma sample")
    if x < left or x+width > left+eye_width or y < 0 or y+height > eye_height: raise ValueError("rounded crop crosses stereo seam")
    return {"eye_x":x-left,"stereo_x":x,"y":y,"width":width,"height":height,"chroma_aligned":chroma=="420"}

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
    validate_crops([crop], resolved="resolved_pixels" in crop); y_h, y_w2 = planes[0].shape; y_w = y_w2 // 2
    resolved_crop=resolve_crop_pixels({key:crop[key] for key in ("name","eye","x","y","w","h")},y_w,y_h,info.chroma)
    if "resolved_pixels" in crop and crop["resolved_pixels"] != resolved_crop: raise ValueError("frozen crop pixels drifted")
    x,top,width,height=(resolved_crop[key] for key in ("stereo_x","y","width","height"))
    left = 0 if crop["eye"] == "left" else y_w
    result=[]
    for index,p in enumerate(planes):
        factor=2 if info.chroma=="420" and index else 1
        result.append(p[top//factor:(top+height)//factor, x//factor:(x+width)//factor].copy())
    return result

def frame_records(source):
    info=inspect_y4m(source); return [{"source_frame":i,"source_sha256":d} for i,_,d in iter_y4m(source,info)]

def hvs_calibration_for_vertical_ppd(pixels_per_degree:float, image_height:int)->dict:
    """Calibration for the scorer-only PyroWave HVS adapter.

    Upstream psnr.cpp uses ``nyquist_cpd = image_height * factor * pi / 360``.
    The adapter accepts a measured *vertical* pixels/degree value and emits this
    derived factor, so each scaled frame or crop is calibrated to its own height.
    """
    if not isinstance(pixels_per_degree,(int,float)) or not math.isfinite(pixels_per_degree) or pixels_per_degree <= 0 or not isinstance(image_height,int) or image_height <= 0: raise ValueError("HVS calibration inputs must be finite and positive")
    factor=float(pixels_per_degree) * 180.0 / (image_height * math.pi)
    return {"vertical_pixels_per_degree":float(pixels_per_degree),"image_height":image_height,"height_factor":factor,"adapter_required":True}

def _crop_height(crop, eye_height, chroma):
    height=max(1,round(crop["h"]*eye_height))
    return max(2,height-(height%2)) if chroma=="420" else height

def build_plan(source:Path,vertical_pixels_per_degree:float,*,horizontal_pixels_per_degree:float|None=None,projection_evidence:str,crop_evidence:str|None=None,fixture:bool=False,fps:int=FPS,wavelets=WAVELETS,rates_mbps=RATES_MBPS,geometries=GEOMETRIES,display_eye=DISPLAY_EYE,crops=None)->dict:
    if not isinstance(vertical_pixels_per_degree,(int,float)) or not math.isfinite(vertical_pixels_per_degree) or vertical_pixels_per_degree<=0: raise ValueError("vertical_pixels_per_degree must be finite and positive")
    if horizontal_pixels_per_degree is not None and (not isinstance(horizontal_pixels_per_degree,(int,float)) or not math.isfinite(horizontal_pixels_per_degree) or horizontal_pixels_per_degree<=0): raise ValueError("horizontal_pixels_per_degree must be finite and positive")
    if not isinstance(projection_evidence,str) or not projection_evidence.strip(): raise ValueError("projection_evidence must name logged projection measurement")
    if not fixture and (not isinstance(crop_evidence,str) or not crop_evidence.strip()): raise ValueError("production plan requires semantic crop evidence")
    if crops is None and not fixture: raise ValueError("production plan requires caller-selected crops")
    if crops is None: crops=DEFAULT_CROPS
    info=inspect_y4m(source)
    if (info.fps_num,info.fps_den) not in ((72,1),(90,1)): raise ValueError("source dump header must be F72:1 or F90:1")
    if (info.width//2,info.height)!=tuple(display_eye): raise ValueError("source dump must be logged presentation input")
    if not fixture and info.frames != 90: raise ValueError("production frame bank requires exactly 90 source frames")
    input_crops=validate_crops(crops)
    clean_crops=[{**crop,"resolved_pixels":resolve_crop_pixels(crop,display_eye[0],display_eye[1],info.chroma)} for crop in input_crops]
    cells=[]
    for wv in wavelets:
        if wv not in WAVELETS: raise ValueError(f"unsupported wavelet {wv}")
        for rate in rates_mbps:
            for ew,eh in geometries:
                cap=cap_bytes(int(rate),fps); cells.append({"wavelet":wv,"rate_mbps":int(rate),"fps":fps,"eye_width":int(ew),"eye_height":int(eh),"stereo_width":int(ew)*2,"encoded_chroma":info.chroma,"cap_bytes":cap,"bits_per_pixel":bpp(cap,int(ew),int(eh))})
    display_hvs=hvs_calibration_for_vertical_ppd(float(vertical_pixels_per_degree),int(display_eye[1]))
    codec_hvs=[hvs_calibration_for_vertical_ppd(float(vertical_pixels_per_degree)*(cell["eye_height"]/display_eye[1]),cell["eye_height"]) for cell in cells]
    crop_hvs=[hvs_calibration_for_vertical_ppd(float(vertical_pixels_per_degree),crop["resolved_pixels"]["height"]) for crop in clean_crops]
    hvs={"source_formula":"ppd=height*height_factor*pi/180","adapter":"pyrowave_psnr_hvs_ppd_scorer","display":display_hvs,"codec_cells":codec_hvs,"crops":crop_hvs}
    projection={"vertical_pixels_per_degree":float(vertical_pixels_per_degree),"horizontal_pixels_per_degree":None if horizontal_pixels_per_degree is None else float(horizontal_pixels_per_degree),"hvs_axis":"vertical"}
    return {"schema":SCHEMA,"kind":"pyrowave_frame_bank","fixture_only":bool(fixture),"source":{"sha256":sha256_file(source),"geometry":[info.width,info.height],"frames":info.frames,"header_fps":[info.fps_num,info.fps_den],"target_fps":fps,"chroma":info.chroma,"color_range":info.color_range,"frame_identity":frame_records(source)},"presentation_eye":list(display_eye),"projection":projection,"projection_evidence":projection_evidence.strip(),"crop_evidence":"fixture" if fixture else crop_evidence.strip(),"hvs_calibration":hvs,"resize":{"scope":"per_eye","filter":"lanczos3","seam_crossing":False},"crops":clean_crops,"cells":cells,"required_metrics":["psnr_y","psnr_cb","psnr_cr","ssim","vmaf","psnr_hvs_m_h"]}

def validate_plan(plan):
    if not isinstance(plan,dict) or plan.get("schema")!=SCHEMA or plan.get("kind")!="pyrowave_frame_bank": raise ValueError("not a frame-bank schema-4 manifest")
    src=plan.get("source",{}); ids=src.get("frame_identity")
    if src.get("chroma") not in ("420","444") or src.get("color_range") not in ("FULL","LIMITED"): raise ValueError("source format/range is unsupported")
    if not isinstance(ids,list) or len(ids)!=src.get("frames") or [x.get("source_frame") for x in ids]!=list(range(len(ids))): raise ValueError("source frame identities must be ordered and contiguous")
    if not isinstance(src.get("sha256"),str) or len(src["sha256"])!=64: raise ValueError("source hash is missing")
    clean_crops=validate_crops(plan.get("crops",[]),resolved=True)
    if plan.get("fixture_only") is not True:
        if src.get("frames") != 90: raise ValueError("production frame bank requires exactly 90 source frames")
        if not isinstance(plan.get("crop_evidence"),str) or not plan["crop_evidence"].strip(): raise ValueError("production plan requires semantic crop evidence")
        if plan.get("crops") == list(DEFAULT_CROPS): raise ValueError("production plan requires caller-selected crops")
    if plan.get("resize") != {"scope":"per_eye","filter":"lanczos3","seam_crossing":False}: raise ValueError("resize provenance does not match implementation")
    if not isinstance(src.get("geometry"),list) or len(src["geometry"]) != 2 or not all(isinstance(v,int) and v > 0 for v in src["geometry"]): raise ValueError("source geometry is invalid")
    if src.get("target_fps") != FPS or src.get("header_fps") not in ([72,1],[90,1]): raise ValueError("source frame-rate provenance is invalid")
    projection=plan.get("projection",{})
    if not isinstance(projection,dict) or projection.get("hvs_axis") != "vertical": raise ValueError("vertical projection calibration is missing")
    vertical=projection.get("vertical_pixels_per_degree")
    if not isinstance(vertical,(int,float)) or not math.isfinite(vertical) or vertical <= 0: raise ValueError("vertical projection calibration is invalid")
    calibration=plan.get("hvs_calibration")
    if not isinstance(calibration,dict) or calibration.get("adapter") != "pyrowave_psnr_hvs_ppd_scorer": raise ValueError("HVS scorer adapter calibration is missing")
    expected_display=hvs_calibration_for_vertical_ppd(vertical,plan["presentation_eye"][1])
    if calibration.get("display") != expected_display: raise ValueError("display HVS calibration drifted")
    if not plan.get("cells"): raise ValueError("frame bank contains no cells")
    for c in plan["cells"]:
        if c.get("encoded_chroma") != src.get("chroma"): raise ValueError("cell chroma must preserve the native dump format")
        if not all(isinstance(c.get(key),int) and c[key] > 0 for key in ("fps","eye_width","eye_height","stereo_width","rate_mbps","cap_bytes")): raise ValueError("cell geometry/rate is invalid")
        if c.get("fps") != src.get("target_fps") or c.get("fps") != FPS: raise ValueError("WO-1 target frame rate must be 90 Hz")
        if src.get("chroma") == "420" and (c["eye_width"] % 2 or c["eye_height"] % 2): raise ValueError("C420 cell geometry must be even")
        if c.get("cap_bytes")!=cap_bytes(c.get("rate_mbps"),c.get("fps")): raise ValueError("cell cap math does not match its rate and frame rate")
        if c.get("stereo_width")!=c.get("eye_width",0)*2: raise ValueError("cell stereo geometry is not two separate eyes")
    expected_codec=[hvs_calibration_for_vertical_ppd(vertical*(cell["eye_height"]/plan["presentation_eye"][1]),cell["eye_height"]) for cell in plan["cells"]]
    expected_crops=[]
    for crop in clean_crops:
        source_crop={key:crop[key] for key in ("name","eye","x","y","w","h")}
        expected_pixels=resolve_crop_pixels(source_crop,plan["presentation_eye"][0],plan["presentation_eye"][1],src["chroma"])
        if crop.get("resolved_pixels") != expected_pixels: raise ValueError("frozen crop pixels drifted")
        expected_crops.append(hvs_calibration_for_vertical_ppd(vertical,expected_pixels["height"]))
    if calibration.get("codec_cells") != expected_codec or calibration.get("crops") != expected_crops: raise ValueError("HVS calibration drifted")
    return plan

class _OwnedPcJobRegistry:
    """Lazy WO-0 bridge; importing it is deferred until a real child starts."""
    def register(self, state_path:Path, pid:int, arm_path:Path|None):
        from tools.quest3 import unattended
        state=unattended.json_read(state_path); host=unattended.Host(state.get("adb","adb"))
        identity=host.process_identity(pid)
        return unattended.register_owned_pc_job(state_path,pid,identity["path"],identity["started_epoch_s"],arm_path=arm_path or unattended.ARM,host=host)
    def unregister(self, state_path:Path, pid:int, *, completion_observed=False):
        from tools.quest3 import unattended
        return unattended.unregister_owned_pc_job(state_path,pid)

class WindowGuard:
    def __init__(self,window:Path,arm:Path|None=None,status_command:Sequence[str]|None=None,clock:Callable[[],float]=time.time,job_registry=None,*,supervised=False):
        self.window=Path(window);self.arm=None if arm is None else Path(arm);self.command=list(status_command or [sys.executable,"-m","tools.quest3.unattended","status"]);self.clock=clock;self.job_registry=job_registry or _OwnedPcJobRegistry();self.owned_jobs=[]
        self.supervised=supervised
        if supervised:
            if arm is not None or status_command is not None: raise ValueError('supervised lease has its own status authority')
            from tools.quest3.supervised import JobRegistry
            self.command=[sys.executable,'-m','tools.quest3.supervised','status']
            self.job_registry=job_registry or JobRegistry()
    def status(self):
        cmd=[*self.command,"--window",str(self.window),"--require-allow","frame_bank_pc"]+([] if self.arm is None else ["--arm",str(self.arm)])
        try: r=subprocess.run(cmd,capture_output=True,text=True,timeout=10,check=False)
        except (OSError,subprocess.SubprocessError) as exc: raise PermissionError("WO-0 lease status unavailable") from exc
        try: data=json.loads(r.stdout)
        except ValueError as exc: raise PermissionError("WO-0 lease status is not valid JSON") from exc
        if r.returncode or data.get("schema")!=1 or data.get("lease",{}).get("active") is not True: raise PermissionError("WO-0 lease is inactive")
        deadline=data["lease"].get("deadline_epoch_s")
        guards=data.get("guards",{}); cancel=data.get("cancellation",{})
        authority_ok=data.get('arm',{}).get('active') is True
        required_guards=('restorer','monitor')
        if self.supervised:
            auth=data.get('authorization',{})
            authority_ok=(auth.get('kind')=='owner_supervised_pc' and auth.get('owner_present') is True and isinstance(auth.get('evidence'),str) and bool(auth['evidence'].strip()) and auth.get('allow')==['frame_bank_pc'])
            required_guards=('monitor',)
        if not isinstance(deadline,(int,float)) or not math.isfinite(deadline) or deadline<=self.clock() or not authority_ok or any(guards.get(x,{}).get(k) is not True for x in required_guards for k in ("ready","alive")) or cancel.get("stop_requested") or cancel.get("paused") or cancel.get("competing_gpu") or not cancel.get("monitor_fresh"):
            raise PermissionError("WO-0 lease health check failed")
        return data
    def run(self,argv,*,cwd:Path,env:dict,timeout_s:float):
        self.status()
        if not isinstance(timeout_s,(int,float)) or not math.isfinite(timeout_s) or timeout_s<=0: raise ValueError("subprocess timeout must be finite and positive")
        # Retain production logs privately even when registration/lease checks
        # raise; disk-backed output also avoids undrained PIPE deadlocks.
        private_logs=Path(cwd).resolve().is_relative_to(_private_root().resolve())
        log=(tempfile.NamedTemporaryFile(mode="w+t",encoding="utf-8",dir=cwd,
                                        prefix="command-",suffix=".log",delete=False)
             if private_logs else tempfile.TemporaryFile(mode="w+t",encoding="utf-8"))
        with log as output:
            proc=subprocess.Popen(list(argv),cwd=str(cwd),env=env,stdout=output,stderr=output,text=True)
            registered=False
            deadline=time.monotonic()+timeout_s
            try:
                # The monitor excludes only the exact WO-0-owned process identity.
                # A registration refusal terminates this child and fails the cell.
                self.job_registry.register(self.window/"state.json",proc.pid,self.arm); registered=True
                self.owned_jobs.append({"argv_sha256":hashlib.sha256("\0".join(map(str,argv)).encode()).hexdigest(),"pid":proc.pid})
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
            finally:
                if registered:
                    try: self.job_registry.unregister(self.window/"state.json",proc.pid,
                                                     completion_observed=proc.poll() is not None)
                    except TypeError:
                        # Keep injected legacy registries usable in CPU tests;
                        # the production supervised registry receives explicit
                        # Popen completion evidence above.
                        self.job_registry.unregister(self.window/"state.json",proc.pid)
                    except Exception:
                        if proc.poll() is None: proc.terminate()
                        raise PermissionError("WO-0 owned PC job could not be unregistered")
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

def codec_environment(base, wavelet):
    """Reject inherited codec experiments by constructing one explicit policy."""
    if wavelet not in WAVELETS: raise ValueError('unsupported wavelet')
    env={key:value for key,value in base.items() if not key.upper().startswith('PYROWAVE_')}
    effective={'PYROWAVE_WAVELET':wavelet,'PYROWAVE_FORCE_COMPUTE':'1'}
    env.update(effective)
    return env,{'set':effective,'other_pyrowave_variables':'unset',
                'decode_path':'compute requested; PC image-quality only'}

def _lock_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def _load_lock(path: Path) -> tuple[str, dict]:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError('source-lock snapshot is unreadable') from exc
    if not isinstance(data, dict):
        raise ValueError('source-lock snapshot is malformed')
    return _lock_sha256(path), data


def _lock_leaves(value, prefix=''):
    """Return canonical leaf paths so a compatibility exception cannot hide a sibling."""
    if isinstance(value, dict):
        rows = []
        for key in sorted(value):
            if not isinstance(key, str) or not key:
                raise ValueError('source-lock object key is malformed')
            rows.extend(_lock_leaves(value[key], f'{prefix}.{key}' if prefix else key))
        return rows
    if isinstance(value, list):
        return [(prefix, value)]
    return [(prefix, value)]


def _lock_change_rows(old: dict, new: dict) -> list[dict]:
    old_leaves, new_leaves = dict(_lock_leaves(old)), dict(_lock_leaves(new))
    sentinel = object()
    return [{'path': path, 'old': old_leaves.get(path), 'new': new_leaves.get(path)}
            for path in sorted(set(old_leaves) | set(new_leaves))
            if old_leaves.get(path, sentinel) != new_leaves.get(path, sentinel)]


# These are the only overlay leaves that may differ for the one qualified
# historical scorer. The Light patch affects live presentation and the RDO
# readback patch only adds native/server observability; neither changes the HVS
# scorer source, shader, imports, or offline frame-bank codec inputs.
_HISTORICAL_HVS_ALLOWED_LOCK_ROLES = {
    'patches.pyrowave_rdo_density.path': 'codec_encoder_only',
    'patches.pyrowave_rdo_density.sha256': 'codec_encoder_only',
    'patches.pyrowave_rdo_live_readback.path': 'observability_only',
    'patches.pyrowave_rdo_live_readback.sha256': 'observability_only',
    'patches.pyrowave_rdo_session_setting.path': 'session_rdo_setting_only',
    'patches.pyrowave_rdo_session_setting.sha256': 'session_rdo_setting_only',
    'patches.wo8_light_centre_phase.path': 'presentation_foveation_only',
    'patches.wo8_light_centre_phase.sha256': 'presentation_foveation_only',
    'patches.alvr_pyrowave_rdo_live_readback.path': 'observability_only',
    'patches.alvr_pyrowave_rdo_live_readback.sha256': 'observability_only',
    'patches.alvr_pyrowave_rdo_session_setting.path': 'session_rdo_setting_only',
    'patches.alvr_pyrowave_rdo_session_setting.sha256': 'session_rdo_setting_only',
    'patches.foveated_staging_correctness.path': 'alvr_presentation_and_geometry_only',
    'patches.foveated_staging_correctness.sha256': 'alvr_presentation_and_geometry_only',
    'patches.nvenc_dimension_preflight.path': 'encoder_capability_preflight_inactive_only',
    'patches.nvenc_dimension_preflight.sha256': 'encoder_capability_preflight_inactive_only',
}
_HISTORICAL_HVS_DESCRIPTOR_RELATIVE = Path(
    'tools/xrbench/historical_locks/qualified-hvs-scorer-b4a61-compatibility.json')
# Normalized EOL hash of the one reviewed descriptor. It is intentionally not
# a generic descriptor mechanism: callers must name this tracked proof.
_HISTORICAL_HVS_DESCRIPTOR_SHA256 = 'cfa5edb0879cd4db21aabf8485ba3d5346b039ad38f72afe79beb08328e295ff'


def _verify_tools_build_against_lock(tools, metadata_path, *, lock_hash: str, lock_data: dict):
    """Shared strict package verifier with an explicitly supplied immutable lock."""
    from . import hvs_scorer
    path=Path(metadata_path); meta=json.loads(path.read_text(encoding='utf-8-sig'))
    bundle=path.parent; build=json.loads((bundle/'BUILD-METADATA.json').read_text(encoding='utf-8-sig'))
    root=Path(__file__).resolve().parents[2]
    fork=json.loads((root/'fork.json').read_text(encoding='utf-8'))
    source_manifest=bundle/'HVS-SCORER-SOURCE.json'
    source_record=json.loads(source_manifest.read_text(encoding='utf-8-sig'))
    shader=bundle/'psnr_hvs_m.comp'
    imports_path=bundle/'FRAMEBANK-IMPORTS.json'
    if (meta.get('schema')!=1 or meta.get('kind')!='pyrowave_framebank_tools_build'
            or meta.get('source_lock_sha256')!=lock_hash
            or meta.get('source_psnr_cpp_sha256')!=hvs_scorer.PATCHED_PSNR_SHA256
            or meta.get('source_manifest_sha256')!=sha256_file(source_manifest)
            or source_record!=hvs_scorer.manifest()):
        raise ValueError('offline tool source provenance mismatch')
    if (not shader.is_file() or sha256_file(shader)!=hvs_scorer.SCORER_SHADER_SHA256
            or build.get('artifact_sha256',{}).get(shader.name)!=sha256_file(shader)):
        raise ValueError('offline HVS shader is missing or mismatched')
    if (not imports_path.is_file() or meta.get('imports_manifest_sha256')!=sha256_file(imports_path)
            or build.get('artifact_sha256',{}).get(imports_path.name)!=sha256_file(imports_path)):
        raise ValueError('offline tool import provenance is missing or mismatched')
    imports=json.loads(imports_path.read_text(encoding='utf-8-sig'))
    expected_names={_tool_path(tools[key]).name for key in ('encode','decode','psnr_hvs_m_h')}
    if imports.get('schema')!=1 or imports.get('kind')!='framebank_windows_imports' or set(imports.get('tools',{}))!=expected_names:
        raise ValueError('offline tool import identity mismatch')
    for rows in imports['tools'].values():
        if not isinstance(rows,list) or not rows: raise ValueError('offline tool imports incomplete')
        for row in rows:
            name=row.get('name',''); provider=row.get('provider')
            if not re.fullmatch(r'[A-Za-z0-9_.+-]+\.dll',name,re.I) or provider not in ('windows_system','api_set','bundle'):
                raise ValueError('offline tool import record invalid')
            if provider=='api_set' and not name.casefold().startswith(('api-ms-win-','ext-ms-win-')):
                raise ValueError('offline tool import provider invalid')
            if provider=='bundle':
                dll=bundle/name
                if (not dll.is_file() or row.get('sha256')!=sha256_file(dll)
                        or build.get('artifact_sha256',{}).get(name)!=sha256_file(dll)):
                    raise ValueError('offline tool dependency missing or mismatched')
            if provider=='windows_system' and os.name=='nt':
                if not (Path(os.environ.get('WINDIR',r'C:\Windows'))/'System32'/name).is_file():
                    raise ValueError('offline tool Windows prerequisite is missing: '+name)
    if (not re.fullmatch(r'[0-9a-f]{40}',str(build.get('repository_commit','')))
            or build.get('sources_lock_sha256')!=lock_hash
            or build.get('protocol_version')!=fork['protocol_version']
            or build.get('client_package_id')!=fork['client_package_id']
            or build.get('dependency_revisions')!=lock_data
            or not build.get('shader_hashes')):
        raise ValueError('offline tool build identity incomplete or mismatched')
    for role,field in (('encode','encode_sha256'),('decode','decode_sha256'),('psnr_hvs_m_h','scorer_sha256')):
        tool=_tool_path(tools[role]); digest=sha256_file(tool)
        if meta.get('tools',{}).get(field)!=digest or build.get('artifact_sha256',{}).get(tool.name)!=digest:
            raise ValueError('offline tool binary differs from its packaged build: '+role)
    return {'metadata_sha256':sha256_file(path),'package_metadata_sha256':sha256_file(bundle/'BUILD-METADATA.json'),
            'repository_commit':build['repository_commit'],'sources_lock_sha256':lock_hash,
            'dependency_revisions':build['dependency_revisions'],'shader_hashes':build['shader_hashes'],
            'protocol_version':build['protocol_version'],'client_package_id':build['client_package_id'],
            'scorer_source':source_record,'imports_manifest_sha256':sha256_file(imports_path),
            'scorer_shader_sha256':sha256_file(shader)}


def verify_tools_build(tools, metadata_path):
    """Bind a codec/scorer package to this checkout's current pinned inputs."""
    root=Path(__file__).resolve().parents[2]
    lock_hash, lock_data = _load_lock(root/'sources.lock.json')
    return _verify_tools_build_against_lock(tools, metadata_path, lock_hash=lock_hash, lock_data=lock_data)


def verify_historical_hvs_scorer(tools, metadata_path, compatibility_path):
    """Verify the one retained qualified HVS package under a pinned lock exception.

    This is scorer-only: a current codec package must still use
    :func:`verify_tools_build`.  The descriptor binds one exact retained scorer
    executable and permits only its listed structural lock changes.
    """
    root = Path(__file__).resolve().parents[2]
    try:
        descriptor_path = Path(compatibility_path).resolve()
        expected_descriptor = (root / _HISTORICAL_HVS_DESCRIPTOR_RELATIVE).resolve()
        if descriptor_path != expected_descriptor:
            raise ValueError('historical HVS compatibility descriptor is not the reviewed tracked proof')
        descriptor_hash = _lock_sha256(descriptor_path)
        if descriptor_hash != _HISTORICAL_HVS_DESCRIPTOR_SHA256:
            raise ValueError('historical HVS compatibility descriptor hash differs from the reviewed proof')
        descriptor = json.loads(descriptor_path.read_text(encoding='utf-8-sig'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError('historical HVS compatibility descriptor is unreadable') from exc
    if not isinstance(descriptor, dict) or descriptor.get('schema') != 1 or descriptor.get('kind') != 'framebank_historical_hvs_scorer_compatibility':
        raise ValueError('historical HVS compatibility descriptor is malformed')
    snapshot_name = descriptor.get('historical_lock_snapshot')
    if not isinstance(snapshot_name, str) or not snapshot_name.startswith('tools/xrbench/historical_locks/'):
        raise ValueError('historical HVS lock snapshot path is invalid')
    snapshot_root = (root/'tools/xrbench/historical_locks').resolve()
    snapshot = (root / snapshot_name).resolve()
    if snapshot_root not in snapshot.parents:
        raise ValueError('historical HVS lock snapshot path escapes the tracked snapshot directory')
    historical_hash, historical_lock = _load_lock(snapshot)
    if historical_hash != descriptor.get('historical_lock_sha256'):
        raise ValueError('historical HVS lock snapshot hash differs from descriptor')
    qualified = descriptor.get('qualified_scorer_bundle')
    if not isinstance(qualified, dict):
        raise ValueError('historical HVS qualified scorer identity is missing')
    required = ('tools_metadata_sha256', 'package_metadata_sha256', 'scorer_sha256',
                'source_manifest_sha256', 'scorer_shader_sha256', 'imports_manifest_sha256',
                'source_psnr_cpp_sha256')
    if any(not isinstance(qualified.get(key), str) or not re.fullmatch(r'[0-9a-f]{64}', qualified[key]) for key in required):
        raise ValueError('historical HVS qualified scorer identity is malformed')
    path = Path(metadata_path); bundle = path.parent
    files = {
        'tools_metadata_sha256': path,
        'package_metadata_sha256': bundle/'BUILD-METADATA.json',
        'scorer_sha256': _tool_path(tools.get('psnr_hvs_m_h')),
        'source_manifest_sha256': bundle/'HVS-SCORER-SOURCE.json',
        'scorer_shader_sha256': bundle/'psnr_hvs_m.comp',
        'imports_manifest_sha256': bundle/'FRAMEBANK-IMPORTS.json',
    }
    if any(value is None or not Path(value).is_file() for value in files.values()):
        raise ValueError('historical HVS qualified scorer file is missing')
    for key, value in files.items():
        if sha256_file(value) != qualified[key]:
            raise ValueError('historical HVS qualified scorer identity differs: ' + key)
    meta = json.loads(path.read_text(encoding='utf-8-sig'))
    if meta.get('source_psnr_cpp_sha256') != qualified['source_psnr_cpp_sha256']:
        raise ValueError('historical HVS qualified scorer source differs')
    current_hash, current_lock = _load_lock(root/'sources.lock.json')
    expected_changes = descriptor.get('allowed_current_lock_changes')
    if not isinstance(expected_changes, list) or not expected_changes:
        raise ValueError('historical HVS allowed lock changes are missing')
    expected_rows = []
    for row in expected_changes:
        if (not isinstance(row, dict) or set(row) != {'path', 'old', 'new', 'role'}
                or not isinstance(row['path'], str) or not row['path']
                or row['role'] != _HISTORICAL_HVS_ALLOWED_LOCK_ROLES.get(row['path'])):
            raise ValueError('historical HVS allowed lock change is malformed')
        expected_rows.append({'path': row['path'], 'old': row['old'], 'new': row['new']})
    if len({row['path'] for row in expected_rows}) != len(expected_rows):
        raise ValueError('historical HVS allowed lock changes repeat a path')
    if {row['path'] for row in expected_rows} != set(_HISTORICAL_HVS_ALLOWED_LOCK_ROLES):
        raise ValueError('historical HVS allowed lock changes are not the reviewed scorer exception')
    actual_rows = _lock_change_rows(historical_lock, current_lock)
    if actual_rows != sorted(expected_rows, key=lambda row: row['path']):
        raise ValueError('historical HVS lock changes exceed the explicit scorer compatibility proof')
    verified = _verify_tools_build_against_lock(tools, path, lock_hash=historical_hash, lock_data=historical_lock)
    proof = {'schema': 1, 'compatibility_descriptor_sha256': descriptor_hash,
             'historical_sources_lock_sha256': historical_hash,
             'current_sources_lock_sha256': current_hash,
             'qualified_scorer_bundle': json.loads(json.dumps(qualified, sort_keys=True)),
             'allowed_current_lock_changes': json.loads(json.dumps(expected_changes, sort_keys=True))}
    return {**verified,
            'historical_scorer_mode': True,
            'historical_sources_lock_sha256': historical_hash,
            'current_sources_lock_sha256': current_hash,
            'compatibility_descriptor_sha256': descriptor_hash,
            'allowed_current_lock_changes': proof['allowed_current_lock_changes'],
            'historical_scorer_proof': proof}

def parse_hvs_m_h(text,pixels_per_degree:float,image_height:int)->dict:
    expected=hvs_calibration_for_vertical_ppd(pixels_per_degree,image_height)
    pats=re.findall(r"PixelsPerDegree\s*=\s*([+0-9.eE-]+).*?HeightFactor\s*=\s*([+0-9.eE-]+).*?PSNR-HVS-M-H:\s*\(Y\)\s*([+0-9.eEinfINF-]+)",text,re.S)
    for ppd,factor,value in pats:
        ppd,factor,val=float(ppd),float(factor),float(value)
        if not math.isfinite(ppd) or not math.isfinite(factor) or math.isnan(val): continue
        if math.isclose(ppd,float(pixels_per_degree),rel_tol=0,abs_tol=1e-5) and math.isclose(factor,expected["height_factor"],rel_tol=0,abs_tol=1e-5):
            return {"value":val,"vertical_pixels_per_degree":ppd,"height_factor":factor,"image_height":image_height}
    raise ValueError("PSNR-HVS-M-H scorer did not emit the requested vertical calibration")
def _score_hvs_m_h(tool,reference,distorted,frames,vertical_ppd,image_height,guard,cwd,env,timeout):
    code,out,err=guard.run([str(tool),"--reference",str(reference),"--distorted",str(distorted),"--frames",str(frames),"--pixels-per-degree",f"{vertical_ppd:.9g}"],cwd=cwd,env=env,timeout_s=timeout)
    if code: raise RuntimeError("PSNR-HVS-M-H scorer failed")
    counts=re.findall(r'ScoredFrames\s*=\s*(\d+)',out+err)
    if counts!=[str(frames)]: raise ValueError('HVS scorer frame count is missing or mismatched')
    result=parse_hvs_m_h(out+err,vertical_ppd,image_height)
    result['scored_frames']=frames
    return result

def hvs_gpu_sanity(tool,directory,vertical_ppd,guard,env,timeout):
    """Finite owned-GPU gate: identity and a known 2x-amplitude error ratio."""
    directory=Path(directory); directory.mkdir()
    info=Y4MInfo(64,64,90,1,'420','FULL',64*64*3//2,3)
    paths={}
    for name,value in (('zero',0),('shift32',32),('shift64',64)):
        path=directory/(name+'.y4m'); paths[name]=path
        planes=[np.full((64,64),value,np.uint8),np.full((32,32),128,np.uint8),np.full((32,32),128,np.uint8)]
        with _open_writer(path,info) as stream:
            for _ in range(info.frames): _write_frame(stream,info,planes)
    scores={}
    for name in paths:
        scores[name]=_score_hvs_m_h(tool,paths['zero'],paths[name],info.frames,vertical_ppd,
                                  info.height,guard,directory,env,min(timeout,60))['value']
    expected=20*math.log10(2); observed=scores['shift32']-scores['shift64']
    if (scores['zero']!=math.inf or not all(math.isfinite(scores[k]) for k in ('shift32','shift64'))
            or not math.isclose(observed,expected,rel_tol=0,abs_tol=.03)):
        raise ValueError('HVS GPU identity or amplitude sanity gate failed')
    return {'passed':True,'frames_per_case':info.frames,'geometry':[64,64],
            'identity_psnr_db':scores['zero'],'uniform_shift_scores_db':{k:scores[k] for k in ('shift32','shift64')},
            'amplitude_ratio_delta_db':observed,'expected_delta_db':expected,'tolerance_db':.03}

def _valid_metric(k,v): return isinstance(v,(int,float)) and not math.isnan(v) and (math.isfinite(v) or k.startswith("psnr"))
def parse_psnr_summary(text):
    """Sequence PSNR from FFmpeg's summary, never a rounded per-frame row.

    The summary uses the mean squared error across the complete comparison.
    Per-frame stats cannot substitute for it, particularly in a log tail.
    Exactly one summary is required by our fixed one-PSNR-filter graph.
    """
    number=r'(?:[0-9]+(?:\.[0-9]+)?|inf)'
    summaries=re.findall(r'\bPSNR y:('+number+r') u:('+number+r') v:('+number+r') average:',text)
    if len(summaries)!=1: raise ValueError('exactly one aggregate PSNR summary is required')
    return dict(zip(('psnr_y','psnr_u','psnr_v'),map(float,summaries[0])))

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
    values=parse_psnr_summary(text); values.update(rdmatrix.parse_ssim(text) or {})
    log=Path(workdir)/"vmaf.json"
    values.update(rdmatrix.parse_vmaf_log(log))
    log.unlink(missing_ok=True)
    return values

def score_pair(tools,distorted,reference,workdir,vertical_ppd,*,frames,image_height,guard,env,timeout_s):
    values=_score_ffmpeg(tools["ffmpeg"],distorted,reference,workdir,guard,env,timeout_s)
    expected=("psnr_y","psnr_u","psnr_v","ssim_y","ssim_all","vmaf")
    missing=[k for k in expected if not _valid_metric(k,values.get(k))]
    if missing: raise RuntimeError("ffmpeg/libvmaf did not emit required metrics: "+", ".join(missing))
    return {"psnr_y":values["psnr_y"],"psnr_cb":values["psnr_u"],"psnr_cr":values["psnr_v"],"ssim":values["ssim_y"],"ssim_all":values["ssim_all"],"vmaf":values["vmaf"],"psnr_hvs_m_h":_score_hvs_m_h(tools["psnr_hvs_m_h"],reference,distorted,frames,vertical_ppd,image_height,guard,workdir,env,timeout_s),"vertical_pixels_per_degree":vertical_ppd}

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

def canonicalize_decoded_header(path:Path):
    """Adapt the pinned decoder's plain C420 spelling; never change samples.

    d2997ac decode.cpp emits C420 and repeats YUV4MPEG2 in its params.
    Only its 8-bit JPEG-sited spelling and C444 are accepted here. Other
    chroma positions/precision must not be relabelled as JPEG-sited samples.
    """
    path=Path(path)
    with path.open('rb') as stream: original=stream.readline(4097)
    tokens=original.decode('ascii').strip().split()
    chroma=[token for token in tokens if token.startswith('C')]
    if len(chroma)!=1 or chroma[0] not in ('C420','C420jpeg','C444'):
        raise ValueError('unsupported decoded chroma spelling or precision')
    info=_parse_header(original,path);canonical=_header(info)
    record={'original_header':original.decode('ascii').strip(),
            'canonical_header':canonical.decode('ascii').strip(),'changed':original!=canonical}
    if original==canonical: return record
    temporary=path.with_suffix(path.suffix+'.canonical.tmp')
    payload=hashlib.sha256()
    try:
        with path.open('rb') as source,temporary.open('xb') as dest:
            if source.readline(4097)!=original: raise ValueError('decoded header changed during normalization')
            dest.write(canonical)
            for chunk in iter(lambda:source.read(1024*1024),b''):
                payload.update(chunk);dest.write(chunk)
        copied=hashlib.sha256()
        with temporary.open('rb') as stream:
            stream.readline()
            for chunk in iter(lambda:stream.read(1024*1024),b''): copied.update(chunk)
        if copied.digest()!=payload.digest(): raise ValueError('decoded payload changed during header normalization')
        temporary.replace(path)
        record['frame_payload_sha256']=payload.hexdigest()
        record['frame_payload_unchanged']=True
        return record
    finally: temporary.unlink(missing_ok=True)

def run_plan(plan_path:Path,source:Path,private_out:Path,tools:dict,window:Path,*,arm:Path|None=None,status_command:Sequence[str]|None=None,command_timeout_s:float=900,keep_artifacts:bool=False,allow_fixture:bool=False,score_fn=score_pair,tools_metadata:Path|None=None,supervised=False):
    raw_plan=Path(plan_path).read_bytes();plan=validate_plan(json.loads(raw_plan)); source=Path(source); private_out=_private_path(private_out); guard=WindowGuard(window,arm,status_command,supervised=supervised)
    if private_out.exists(): raise FileExistsError('private output must be a fresh directory')
    if plan.get("fixture_only") and not allow_fixture: raise ValueError("fixture-only plans cannot run outside a CPU test")
    required_tools(tools); guard.status(); initial={n:sha256_file(_tool_path(v)) for n,v in tools.items()};
    if sha256_file(source)!=plan["source"]["sha256"]: raise ValueError("source dump hash differs from frozen plan")
    source_info=inspect_y4m(source)
    if source_info.frames!=plan["source"]["frames"]: raise ValueError("source dump frame count differs from frozen plan")
    if not plan.get('fixture_only') and tools_metadata is None: raise ValueError('packaged offline tools metadata is required')
    build_provenance=verify_tools_build(tools,tools_metadata) if tools_metadata is not None else None
    private_out.mkdir(parents=True,exist_ok=False); result={"schema":SCHEMA,"kind":"pyrowave_frame_bank_result","frozen_plan_sha256":hashlib.sha256(raw_plan).hexdigest(),"source_sha256_start":sha256_file(source),"source_sha256_end":None,"tool_provenance_start":initial,"tool_provenance_end":None,"tools_build_provenance":build_provenance,"projection":plan["projection"],"projection_evidence":plan["projection_evidence"],"crop_definitions":plan["crops"],"cells":[],"complete":False,"failure_reasons":[]}
    if not plan.get('fixture_only'):
        try:
            env,_=codec_environment(os.environ,'haar')
            result['hvs_gpu_sanity']=hvs_gpu_sanity(tools['psnr_hvs_m_h'],private_out/'scorer-sanity',
                plan['projection']['vertical_pixels_per_degree'],guard,env,command_timeout_s)
        except (PermissionError,TimeoutError,ValueError,RuntimeError):
            result['failure_reasons'].append('hvs_gpu_sanity_failed')
    for index,cell in enumerate(plan["cells"] if not result['failure_reasons'] else []):
        directory=private_out/f"cell-{index:02d}-{cell['wavelet']}-{cell['rate_mbps']}-{cell['eye_width']}x{cell['eye_height']}";directory.mkdir(parents=True,exist_ok=True); ref=directory/f"reference-c{cell['encoded_chroma']}.y4m";wave=directory/"encoded.wave";decoded=directory/f"decoded-c{cell['encoded_chroma']}.y4m"; row=dict(cell)
        try:
            ref_info,ids=_stream_reference(source,source_info,cell,ref); row["identity_count"]=len(ids)
            if [x["source_sha256"] for x in ids] != [x["source_sha256"] for x in plan["source"]["frame_identity"]]: raise ValueError("source_frame_identity_drift")
            env,row['codec_environment']=codec_environment(os.environ,cell['wavelet'])
            # Pinned pyrowave-encode CLI: input.y4m output.wave bytes_per_frame.
            code,encode_out,encode_err=guard.run([str(tools["encode"]),str(ref),str(wave),str(cell["cap_bytes"])],cwd=directory,env=env,timeout_s=command_timeout_s)
            if code or not wave.is_file() or wave.stat().st_size<=0: raise RuntimeError("encode_failed")
            wavelet_name={'haar':'Haar','53':'CDF 5/3','97':'CDF 9/7'}[cell['wavelet']]
            if not plan.get('fixture_only') and ('XRW: wavelet = '+wavelet_name) not in encode_out+encode_err:
                raise RuntimeError('encoder_wavelet_not_confirmed')
            row["actual_container_bytes"]=wave.stat().st_size
            # Pinned pyrowave-decode CLI: input.wave output.y4m.
            code,decode_out,decode_err=guard.run([str(tools["decode"]),str(wave),str(decoded)],cwd=directory,env=env,timeout_s=command_timeout_s)
            if code or not decoded.is_file(): raise RuntimeError("decode_failed")
            decode_log=decode_out+decode_err
            if not plan.get('fixture_only'):
                if 'decode path = compute' not in decode_log or ('XRW: wavelet = '+wavelet_name) not in decode_log:
                    raise RuntimeError('decoder_configuration_not_confirmed')
                row['codec_environment'].update(observed_decoder_path='compute',observed_encoder_wavelet=wavelet_name,
                                                 observed_decoder_wavelet=wavelet_name)
            row['decoded_y4m_header']=canonicalize_decoded_header(decoded)
            dec_info=_assert_same_frames(ref,decoded,ref_info);row["decoded_frame_identity"]=[{"cell_frame":i,"source_frame":x["source_frame"],"reference_sha256":x["reference_sha256"],"decoded_sha256":d} for (i,_,d),x in zip(iter_y4m(decoded,dec_info),ids)]
            if len(row["decoded_frame_identity"])!=len(ids): raise ValueError("decoded_identity_or_geometry_mismatch")
            common=dict(frames=ref_info.frames,guard=guard,env=env,timeout_s=command_timeout_s)
            codec_ppd=plan["hvs_calibration"]["codec_cells"][index]["vertical_pixels_per_degree"]
            row["codec_only"]=score_fn(tools,decoded,ref,directory,codec_ppd,image_height=ref_info.height,**common)
            display_ref=directory/"source-display.y4m";display_dec=directory/"decoded-display.y4m";_write_display(source,source_info,display_ref,plan["presentation_eye"]);_write_display(decoded,dec_info,display_dec,plan["presentation_eye"])
            display_common=common
            row["displayed"]=score_fn(tools,display_dec,display_ref,directory,plan["hvs_calibration"]["display"]["vertical_pixels_per_degree"],image_height=plan["presentation_eye"][1],**display_common);row["crops"]={}
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
                crop_calibration=plan["hvs_calibration"]["crops"][plan["crops"].index(crop)]
                row["crops"][crop["name"]]=score_fn(tools,gp,rp,directory,crop_calibration["vertical_pixels_per_degree"],image_height=ci.height,**common);_grid_png(directory/"grids"/f"PRIVATE-{crop['name']}.png",c0,crop_y4m(gp0,disp_info,crop))
                if not keep_artifacts:
                    rp.unlink(); gp.unlink()
        except (PermissionError,TimeoutError,ValueError,RuntimeError) as exc:
            row["error"]=str(exc) if str(exc) in {"encode_failed","decode_failed","decoded_identity_or_geometry_mismatch"} else "cell_failed";result["failure_reasons"].append(row["error"])
        result["cells"].append(row)
        (private_out/"framebank-progress.json").write_text(report_json(result),encoding="utf-8")
        if not keep_artifacts:
            for p in (ref,wave,decoded,directory/"source-display.y4m",directory/"decoded-display.y4m"): p.unlink(missing_ok=True)
            for p in directory.glob('crop-*.y4m'): p.unlink()
        if row.get("error"):
            # Preserve the invalid partial result; do not replay a failing codec
            # or revoked lease across all remaining frozen configurations.
            break
    result["source_sha256_end"]=sha256_file(source); result["tool_provenance_end"]={n:sha256_file(_tool_path(v)) for n,v in tools.items()}
    if result["source_sha256_end"]!=result["source_sha256_start"]: result["failure_reasons"].append("source_changed_during_run")
    if result["tool_provenance_end"]!=result["tool_provenance_start"]: result["failure_reasons"].append("tool_changed_during_run")
    if tools_metadata is not None:
        try:
            if verify_tools_build(tools,tools_metadata)!=build_provenance: result['failure_reasons'].append('tool_build_provenance_changed_during_run')
        except (OSError,ValueError,KeyError): result['failure_reasons'].append('tool_build_provenance_changed_during_run')
    if hashlib.sha256(Path(plan_path).read_bytes()).hexdigest()!=result["frozen_plan_sha256"]: result["failure_reasons"].append("plan_changed_during_run")
    result["complete"]=not result["failure_reasons"] and len(result["cells"])==len(plan["cells"]); (private_out/"framebank-private.json").write_text(report_json(result),encoding="utf-8"); return result

def report_json(result):
    """Strict JSON transport; keep the in-memory metric API numeric and unchanged."""
    def transport(value):
        if isinstance(value,dict): return {key:transport(item) for key,item in value.items()}
        if isinstance(value,(list,tuple)): return [transport(item) for item in value]
        if isinstance(value,float):
            if math.isnan(value): raise ValueError('NaN cannot be written as a frame-bank result')
            if math.isinf(value): return 'Infinity' if value>0 else '-Infinity'
        return value
    return json.dumps(transport(result),indent=2,allow_nan=False)

def sanitized_report(result):
    keep=("wavelet","rate_mbps","fps","eye_width","eye_height","encoded_chroma","cap_bytes","bits_per_pixel","actual_container_bytes","codec_environment","decoded_y4m_header","codec_only","displayed","crops","error")
    return {"schema":SCHEMA,"kind":"pyrowave_frame_bank_sanitized","complete":result.get("complete") is True,"failure_reasons":list(result.get("failure_reasons",[])),"frozen_plan_sha256":result.get("frozen_plan_sha256"),"source_sha256":result.get("source_sha256_end"),"tool_provenance":result.get("tool_provenance_end"),"tools_build_provenance":result.get('tools_build_provenance'),"hvs_gpu_sanity":result.get('hvs_gpu_sanity'),"projection":result.get("projection"),"crop_definitions":result.get("crop_definitions"),"cells":[{k:r.get(k) for k in keep} for r in result.get("cells",[])],"optical_latency_ms":None,"display_fps":None}
def parse_crops_argument(value:str):
    try:
        raw=Path(value[1:]).read_text(encoding="utf-8") if value.startswith("@") else value
        parsed=json.loads(raw)
    except (OSError, ValueError, json.JSONDecodeError) as exc: raise ValueError("--crops must be a JSON array or @JSON-file") from exc
    return parsed

def _main_plan(a):
    p=build_plan(Path(a.source),a.vertical_pixels_per_degree,horizontal_pixels_per_degree=a.horizontal_pixels_per_degree,projection_evidence=a.projection_evidence,crop_evidence=a.crop_evidence,crops=parse_crops_argument(a.crops));Path(a.out).write_text(json.dumps(p,indent=2),encoding="utf-8");print(f"wrote frozen plan with {len(p['cells'])} cells; no codec/scorer was run");return 0
def _main_run(a):
    tools={"encode":a.encode,"decode":a.decode,"ffmpeg":a.ffmpeg,"psnr_hvs_m_h":a.psnr_hvs_m_h};r=run_plan(Path(a.plan),Path(a.source),Path(a.private_out),tools,Path(a.window),arm=None if not a.arm else Path(a.arm),command_timeout_s=a.command_timeout_s,keep_artifacts=a.keep_artifacts,tools_metadata=Path(a.tools_metadata),supervised=getattr(a,'supervised',False));report=sanitized_report(r);Path(a.report).write_text(report_json(report),encoding="utf-8");print(f"wrote sanitized report: complete={report['complete']}");return 0 if report["complete"] else 2
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    s=p.add_subparsers(dest='command',required=True)
    v=s.add_parser('verify-tools',help='verify packaged provenance without executing binaries or using a GPU')
    v.add_argument('--tools-metadata',required=True)
    a=s.add_parser('plan')
    for name in ('source','projection-evidence','crop-evidence','out'): a.add_argument('--'+name,required=True)
    a.add_argument('--vertical-pixels-per-degree',type=float,required=True)
    a.add_argument('--horizontal-pixels-per-degree',type=float)
    a.add_argument('--crops',required=True,help='JSON crop array or @JSON-file; production never uses defaults')
    r=s.add_parser('run')
    for name in ('plan','source','private-out','report','window','encode','decode','ffmpeg','psnr-hvs-m-h','tools-metadata'):
        r.add_argument('--'+name,required=True)
    r.add_argument('--arm')
    r.add_argument('--supervised',action='store_true',help='use an existing owner-attested PC-only lease')
    r.add_argument('--command-timeout-s',type=float,default=900)
    r.add_argument('--keep-artifacts',action='store_true')
    x=p.parse_args(argv)
    if x.command=='verify-tools':
        bundle=Path(x.tools_metadata).resolve().parent
        record=verify_tools_build({'encode':bundle/'pyrowave-encode.exe','decode':bundle/'pyrowave-decode.exe',
                                  'psnr_hvs_m_h':bundle/'pyrowave-psnr-hvs-m.exe'},Path(x.tools_metadata))
        print(json.dumps({'verified':True,'repository_commit':record['repository_commit'],
                          'metadata_sha256':record['metadata_sha256']}))
        return 0
    return _main_plan(x) if x.command=='plan' else _main_run(x)
if __name__=="__main__": raise SystemExit(main())
