"""Bind opt-in Windows shader sources to their embedded DXBC; never use a GPU."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from check_foveation_linkage import check as check_foveation_linkage

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / 'tools/windows/quality-shaders.json'
SHADER = 'alvr/server_openvr/cpp/alvr_server/shader/'
WINDOWS = 'alvr/server_openvr/cpp/platform/win32/'
SOURCES = ('FrameRender.fx', 'FrameRenderPSArea.hlsl', 'FrameRenderPSAdaptive.hlsl', 'RgbToYuvPlanar.hlsl', 'RgbToYuvPlanarDither.hlsl')
BINARY = ('FrameRenderPS.cso', 'rgbtoyuvplanar.cso', 'FrameRenderPSArea.cso', 'FrameRenderPSAdaptive.cso', 'rgbtoyuvplanardither.cso')
VARIANTS = (('FrameRenderPSArea.hlsl', 'PS', 'FrameRenderPSArea.cso'),
            ('FrameRenderPSAdaptive.hlsl', 'main', 'FrameRenderPSAdaptive.cso'),
            ('RgbToYuvPlanarDither.hlsl', 'main', 'rgbtoyuvplanardither.cso'))
FOVEATION_VARIANT = ('CompressAxisAlignedPixelShader.hlsl', 'main', 'CompressAxisAlignedPixelShader.cso')

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def hashes(root): return {name:sha(root/name) for name in (*[SHADER+x for x in SOURCES], *[WINDOWS+x for x in BINARY])}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('alvr',type=Path);p.add_argument('--fxc',type=Path)
    p.add_argument('--compile-out',type=Path);p.add_argument('--write',action='store_true')
    a=p.parse_args(); actual=hashes(a.alvr)
    check_foveation_linkage(a.alvr)
    if (a.alvr/SHADER/'FrameRenderPSAdaptive.hlsl').read_bytes() != (REPO/'tools/downsample/frame_downsample.hlsl').read_bytes():
        raise SystemExit('Embedded Adaptive source differs from canonical HLSL')
    if a.write:
        if not a.fxc or not a.fxc.is_file(): p.error('--write requires the actual fxc executable')
        MANIFEST.write_text(json.dumps({'schema':1,'sdk':'10.0.26100.0','fxc_sha256':sha(a.fxc),
            'flags':['/nologo','/O3','/T','ps_5_0'], 'files':actual,
            'default_shader_policy':'legacy FrameRenderPS.cso and rgbtoyuvplanar.cso preserved byte-for-byte',
            'variants':[{'source':s,'entry':e,'binary':b} for s,e,b in VARIANTS]},indent=2)+'\n',encoding='utf-8')
        return
    manifest=json.loads(MANIFEST.read_text(encoding='utf-8'))
    if actual != manifest['files']: raise SystemExit('Windows composition shader manifest differs')
    if a.compile_out:
        if not a.fxc or not a.fxc.is_file(): p.error('--compile-out requires fxc')
        if sha(a.fxc) != manifest['fxc_sha256']: raise SystemExit('Use the recorded Windows SDK fxc binary')
        a.compile_out.mkdir(parents=True,exist_ok=True)
        for source,entry,binary in VARIANTS:
            output=(a.compile_out/binary).resolve()
            subprocess.run([str(a.fxc.resolve()),*manifest['flags'],'/E',entry,
                '/Fo',str(output),str((a.alvr/SHADER/source).resolve())],check=True,timeout=60)
            if sha(output) != manifest['files'][WINDOWS+binary]: raise SystemExit('Regenerated DXBC differs: '+binary)
        # WO-8 is a cumulative source patch, so its shader is not present in
        # this repository's immutable legacy manifest. Bind it directly to the
        # rebuilt embedded binary before the WARP readback fixture executes it.
        source,entry,binary=FOVEATION_VARIANT
        output=(a.compile_out/binary).resolve()
        subprocess.run([str(a.fxc.resolve()),*manifest['flags'],'/E',entry,
            '/Fo',str(output),str((a.alvr/SHADER/source).resolve())],check=True,timeout=60)
        if sha(output) != sha(a.alvr/WINDOWS/binary):
            raise SystemExit('Regenerated DXBC differs: '+binary)
    print('Windows composition shader sources, embedded binaries and legacy defaults verified')

if __name__=='__main__': main()
