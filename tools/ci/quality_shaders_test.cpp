// Tiny Windows WARP checks: real embedded experimental shaders, software only.
// This verifies pixels and eye boundaries, not GPU performance or headset quality.
#include <d3d11.h>
#include <d3dcompiler.h>
#include <wrl/client.h>
#include <algorithm>
#include <cmath>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
using Microsoft::WRL::ComPtr;
static void check(HRESULT hr) { if (FAILED(hr)) throw std::runtime_error("D3D call failed"); }
static void require(bool value, const char *why) { if (!value) throw std::runtime_error(why); }
static float u32bits(unsigned value) { float out; std::memcpy(&out,&value,sizeof(out)); return out; }

// Independent direct convolution; the shader uses paired bilinear fetches.
static double cubic(double x) {
    x=std::abs(x);
    if(x<1) return (1.5*x-2.5)*x*x+1;
    if(x<2) return ((-.5*x+2.5)*x-4)*x+2;
    return 0;
}
static double adaptiveReference(const std::vector<float>& image,unsigned sw,unsigned sh,
        double cx,double cy,double sx,double sy,int loX,int hiX,int loY,int hiY) {
    require(image.size()==size_t(sw)*sh,"reference geometry");
    sx=std::clamp(sx,1.,3.);sy=std::clamp(sy,1.,3.);
    double sum=0,weight=0;
    for(int y=int(std::floor(cy-.5-2*sy));y<=int(std::floor(cy-.5+2*sy));y++)
        for(int x=int(std::floor(cx-.5-2*sx));x<=int(std::floor(cx-.5+2*sx));x++) {
            const double w=cubic((x+.5-cx)/sx)*cubic((y+.5-cy)/sy);
            sum+=w*image[size_t(std::clamp(y,loY,hiY))*sw+std::clamp(x,loX,hiX)];weight+=w;
        }
    return (std::max)(0.,sum/weight);
}

struct Warp {
    ComPtr<ID3D11Device> device;
    ComPtr<ID3D11DeviceContext> context;
    ComPtr<ID3D11VertexShader> vs;
    Warp() {
        const D3D_FEATURE_LEVEL level=D3D_FEATURE_LEVEL_11_0;
        check(D3D11CreateDevice(nullptr,D3D_DRIVER_TYPE_WARP,nullptr,0,&level,1,
              D3D11_SDK_VERSION,&device,nullptr,&context));
        const char *source=R"(
            cbuffer Bounds : register(b1) { float4 uvBounds; float4 viewControl; };
            struct O { float4 pos:SV_POSITION; float2 uv:TEXCOORD0; uint view:VIEW; };
            O VS(uint id:SV_VertexID) {
                // A four-vertex strip keeps interpolated UVs in [0,1]. The
                // oversized full-screen triangle used by older fixtures made
                // the WARP seam fixture's b1 UV bounds hard to audit.
                float2 p=float2((id&1)?1:-1,(id&2)?-1:1);
                O o; o.pos=float4(p,0,1);
                float2 uv=float2((p.x+1)*.5,(1-p.y)*.5);
                o.uv=lerp(uvBounds.xy,uvBounds.zw,uv); o.view=(uint)viewControl.x; return o;
            })";
        ComPtr<ID3DBlob> blob,error;
        check(D3DCompile(source,std::strlen(source),nullptr,nullptr,nullptr,"VS","vs_5_0",
              D3DCOMPILE_OPTIMIZATION_LEVEL3,0,&blob,&error));
        check(device->CreateVertexShader(blob->GetBufferPointer(),blob->GetBufferSize(),nullptr,&vs));
        D3D11_RASTERIZER_DESC rd={};rd.FillMode=D3D11_FILL_SOLID;rd.CullMode=D3D11_CULL_NONE;
        ComPtr<ID3D11RasterizerState> raster;check(device->CreateRasterizerState(&rd,&raster));
        context->RSSetState(raster.Get());
    }
    ComPtr<ID3D11PixelShader> shader(const std::string &path) {
        ComPtr<ID3DBlob> blob;std::wstring wide(path.begin(),path.end());
        check(D3DReadFileToBlob(wide.c_str(),&blob));ComPtr<ID3D11PixelShader> result;
        check(device->CreatePixelShader(blob->GetBufferPointer(),blob->GetBufferSize(),nullptr,&result));
        return result;
    }
    ComPtr<ID3D11Buffer> buffer(const std::vector<float> &data) {
        D3D11_BUFFER_DESC desc={};desc.ByteWidth=UINT(data.size()*sizeof(float));
        desc.Usage=D3D11_USAGE_IMMUTABLE;desc.BindFlags=D3D11_BIND_CONSTANT_BUFFER;
        D3D11_SUBRESOURCE_DATA init={};init.pSysMem=data.data();ComPtr<ID3D11Buffer> out;
        check(device->CreateBuffer(&desc,&init,&out));return out;
    }
    std::vector<std::vector<float>> draw(ID3D11PixelShader *ps,const std::vector<float> &input,
            unsigned sw,unsigned sh,unsigned dw,unsigned dh,const std::vector<float> &params,
            const std::vector<float> &uvBounds, bool r8=false, unsigned eye=0) {
        require(input.size()==size_t(sw)*sh,"input geometry");
        std::vector<float> rgba;rgba.reserve(input.size()*4);
        for (float x:input) rgba.insert(rgba.end(),{x,x,x,1});
        D3D11_TEXTURE2D_DESC desc={};desc.Width=sw;desc.Height=sh;desc.MipLevels=1;
        desc.ArraySize=1;desc.Format=DXGI_FORMAT_R32G32B32A32_FLOAT;desc.SampleDesc.Count=1;
        desc.Usage=D3D11_USAGE_IMMUTABLE;desc.BindFlags=D3D11_BIND_SHADER_RESOURCE;
        D3D11_SUBRESOURCE_DATA init={};init.pSysMem=rgba.data();init.SysMemPitch=sw*16;
        ComPtr<ID3D11Texture2D> source;check(device->CreateTexture2D(&desc,&init,&source));
        ComPtr<ID3D11ShaderResourceView> view;check(device->CreateShaderResourceView(source.Get(),nullptr,&view));
        ID3D11ShaderResourceView *views[]={view.Get(),view.Get()};context->PSSetShaderResources(0,2,views);
        D3D11_SAMPLER_DESC sd={};sd.Filter=D3D11_FILTER_MIN_MAG_MIP_LINEAR;
        sd.AddressU=sd.AddressV=sd.AddressW=D3D11_TEXTURE_ADDRESS_CLAMP;sd.MaxLOD=D3D11_FLOAT32_MAX;
        ComPtr<ID3D11SamplerState> sampler;check(device->CreateSamplerState(&sd,&sampler));
        ID3D11SamplerState *sp=sampler.Get();context->PSSetSamplers(0,1,&sp);
        auto vparams=uvBounds;vparams.insert(vparams.end(),{float(eye),0,0,0});
        auto cb=buffer(params),ub=buffer(vparams);ID3D11Buffer *bp=cb.Get(),*up=ub.Get();
        context->PSSetConstantBuffers(0,1,&bp);context->VSSetConstantBuffers(1,1,&up);
        const unsigned targets=r8?3:1;
        std::vector<ComPtr<ID3D11Texture2D>> textures(targets);
        std::vector<ComPtr<ID3D11RenderTargetView>> rt(targets);std::vector<ID3D11RenderTargetView*> pointers;
        desc.Width=dw;desc.Height=dh;desc.Format=r8?DXGI_FORMAT_R8_UNORM:DXGI_FORMAT_R32G32B32A32_FLOAT;
        desc.Usage=D3D11_USAGE_DEFAULT;desc.BindFlags=D3D11_BIND_RENDER_TARGET;
        for (unsigned i=0;i<targets;i++) {
            check(device->CreateTexture2D(&desc,nullptr,&textures[i]));
            check(device->CreateRenderTargetView(textures[i].Get(),nullptr,&rt[i]));pointers.push_back(rt[i].Get());
        }
        context->OMSetRenderTargets(targets,pointers.data(),nullptr);
        D3D11_VIEWPORT vp={0,0,float(dw),float(dh),0,1};context->RSSetViewports(1,&vp);
        context->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLESTRIP);
        context->VSSetShader(vs.Get(),nullptr,0);context->PSSetShader(ps,nullptr,0);context->Draw(4,0);
        context->OMSetRenderTargets(0,nullptr,nullptr);
        std::vector<std::vector<float>> result(targets,std::vector<float>(dw*dh));
        desc.Usage=D3D11_USAGE_STAGING;desc.BindFlags=0;desc.CPUAccessFlags=D3D11_CPU_ACCESS_READ;
        for (unsigned i=0;i<targets;i++) {
            ComPtr<ID3D11Texture2D> staging;check(device->CreateTexture2D(&desc,nullptr,&staging));
            context->CopyResource(staging.Get(),textures[i].Get());D3D11_MAPPED_SUBRESOURCE mapped={};
            check(context->Map(staging.Get(),0,D3D11_MAP_READ,0,&mapped));
            for(unsigned y=0;y<dh;y++) for(unsigned x=0;x<dw;x++) {
                const auto *row=static_cast<const unsigned char*>(mapped.pData)+y*mapped.RowPitch;
                result[i][y*dw+x]=r8?float(row[x]):reinterpret_cast<const float*>(row)[x*4];
            }
            context->Unmap(staging.Get(),0);
        }
        ID3D11ShaderResourceView *empty[]={nullptr,nullptr};context->PSSetShaderResources(0,2,empty);
        return result;
    }
};

int main(int argc,char **argv) {
    try {
        require(argc==5,"expected area, dither, foveation and adaptive CSO paths");Warp w;
        auto area=w.shader(argv[1]),dither=w.shader(argv[2]),foveated=w.shader(argv[3]);
        auto adaptive=w.shader(argv[4]);
        const std::vector<float> params={1,0,0,0,0,0,1,1,0,0,1,1},uv={0,0,1,1};
        auto dc=w.draw(area.Get(),std::vector<float>(64,.37f),8,8,4,4,params,uv)[0];
        for(float x:dc) require(std::abs(x-.37f)<1e-6f,"area DC changed");
        std::vector<float> checker(64);for(unsigned y=0;y<8;y++)for(unsigned x=0;x<8;x++)checker[y*8+x]=float((x+y)%2);
        auto average=w.draw(area.Get(),checker,8,8,4,4,params,uv)[0];
        for(float x:average) require(std::abs(x-.5f)<1e-6f,"checkerboard area average");

        for(auto* ps:{area.Get(),adaptive.Get()}) {
            auto identity=w.draw(ps,checker,8,8,8,8,params,uv)[0];
            for(unsigned i=0;i<64;i++)require(std::abs(identity[i]-checker[i])<1e-6f,"filter identity");
            auto constant=w.draw(ps,std::vector<float>(64,.37f),8,8,5,3,params,uv)[0];
            for(float x:constant)require(std::abs(x-.37f)<1e-5f,"filter DC");
        }
        // Fractional/anisotropic/minifying and magnifying footprints, including >3x cap.
        // Each case compares all pixels of both eyes, flipped bounds, non-flat data,
        // transfer/gamma/clamping and the clamped Catmull-Rom negative lobes.
        std::vector<float> pattern(20*12);
        for(unsigned y=0;y<12;y++)for(unsigned x=0;x<20;x++)
            pattern[y*20+x]=.2f+.6f*float(((x*17+y*23)%31))/30.f;
        for(unsigned dw:{3u,7u,16u})for(unsigned dh:{3u,9u,16u})for(unsigned eye:{0u,1u}) {
            for(bool flip:{false,true})for(unsigned control:{0u,2u,4u,32u,64u}) {
                const float u0=eye? .5f:0.f,u1=eye?1.f:.5f;
                const std::vector<float> bounds={flip?u1:u0,1.f/12,flip?u0:u1,11.f/12};
                auto p=params;p[0]=.8f;
                p[4]=u0;p[5]=1.f/12;p[6]=u1;p[7]=11.f/12;
                p[8]=u0;p[9]=1.f/12;p[10]=u1;p[11]=11.f/12;
                auto out=w.draw(adaptive.Get(),pattern,20,12,dw,dh,p,bounds,false,eye|control)[0];
                for(unsigned y=0;y<dh;y++)for(unsigned x=0;x<dw;x++) {
                    const double t=(x+.5)/dw;
                    double expected=adaptiveReference(pattern,20,12,
                        (flip?u1-t*(u1-u0):u0+t*(u1-u0))*20,1+(y+.5)*10/dh,
                        10./dw,10./dh,eye?10:0,eye?19:9,1,10);
                    if(control==32)expected=std::clamp(expected,0.,1.);
                    expected=std::pow(expected,.8);
                    if(control==2)expected=expected<=.0031308?expected*12.92:1.055*std::pow(expected,1./2.4)-.055;
                    if(control==4)expected=expected<=.04045?expected/12.92:std::pow((expected+.055)/1.055,2.4);
                    if(control==64)expected=std::clamp(expected,0.,1.);
                    // D3D linear sampling has finite subtexel precision; sharp random
                    // inputs amplify that rounding after gamma. Bound it to 0.3%.
                    if (!std::isfinite(out[y*dw+x]) || std::abs(out[y*dw+x]-expected)>=.003) {
                        std::cerr<<"Adaptive mismatch dw="<<dw<<" dh="<<dh<<" eye="<<eye
                            <<" flip="<<flip<<" control="<<control<<" x="<<x<<" y="<<y
                            <<" got="<<out[y*dw+x]<<" expected="<<expected<<'\n';
                        throw std::runtime_error("Adaptive differs from direct 2D reference/transfer");
                    }
                }
            }
        }

        // Execute the exact embedded WO-8 shader through WARP. targetResolution
        // and optimizedResolution are uint2 fields, hence their raw bit values.
        // This is only a numerical shader/readback gate, never a GPU timing test.
        const std::vector<float> foveation={u32bits(8),u32bits(8),u32bits(8),u32bits(8),
            1,1,.8f,.8f,0,0,0,0,1.5f,1.5f,1,0};
        auto fdc=w.draw(foveated.Get(),std::vector<float>(128,.37f),16,8,16,8,foveation,uv)[0];
        for(float x:fdc) require(std::abs(x-.37f)<1e-6f,"foveation DC changed");
        // c=.285714... yields loBound=.3125, exactly a pixel centre on this
        // 8-pixel eye. This catches the historical strict-predicate join hole.
        auto fjoin=foveation; fjoin[6]=fjoin[7]=2.f/7.f;
        auto joinDc=w.draw(foveated.Get(),std::vector<float>(128,.37f),16,8,16,8,fjoin,uv)[0];
        for(float x:joinDc) require(std::abs(x-.37f)<1e-6f,"foveation join emitted black");
        // Actual Medium-profile geometry from CalculateFoveationVars:
        // target=256, centre=0.6, ratio=2 -> aligned centre=.59375,
        // unpadded scale=.796875, output=224, eyeSizeRatio=204/224.
        // This executes compressedUV/localSqueeze on a genuinely smaller
        // surface and catches cross-eye sampling in aligned padding.
        const std::vector<float> compressedFoveation={
            u32bits(256),u32bits(256),u32bits(224),u32bits(224),
            204.f/224.f,204.f/224.f,.59375f,.59375f,0,0,0,0,2,2,1,0};
        std::vector<float> compressedStereo(512*256,.25f);
        for(unsigned y=0;y<256;y++) for(unsigned x=256;x<512;x++) compressedStereo[y*512+x]=.75f;
        // Render the two compositor viewports separately, as production does.
        // The synthetic full-screen vertex shader otherwise assigns its exact
        // UV=.5 centre boundary pixel to the left branch. Both logical eye
        // edges include aligned padding, so this catches a cross-eye read.
        auto fleft=w.draw(foveated.Get(),compressedStereo,512,256,224,224,
                          compressedFoveation,{0,0,.5f,1})[0];
        auto fright=w.draw(foveated.Get(),compressedStereo,512,256,224,224,
                           compressedFoveation,{.5f,0,1,1})[0];
        for(float value:fleft) require(std::abs(value-.25f)<1e-5f,"foveation left eye crossed seam");
        for(unsigned y=0;y<224;y++) for(unsigned x=0;x<224;x++)
            require(std::abs(fright[y*224+x]-.75f)<1e-5f,"foveation right eye crossed seam");
        // A non-flat eye proves the compressed UV/local squeeze path is active.
        // At the outer ring the Medium mapping samples farther toward the source
        // edge than identity output UV would. The 9x9 footprint is also active
        // here because peripheralSoftness is one.
        std::vector<float> compressedGradient(512*256);
        for(unsigned y=0;y<256;y++) for(unsigned x=0;x<512;x++) {
            const float eyeX=float(x % 256)/255.f;
            compressedGradient[y*512+x]=(x<256 ? .10f+.30f*eyeX : .60f+.20f*eyeX);
        }
        auto fgradient=w.draw(foveated.Get(),compressedGradient,512,256,224,224,
                              compressedFoveation,{0,0,.5f,1})[0];
        const float identityLeft=.10f+.30f*((8.f+.5f)/224.f);
        if (std::abs(fgradient[112*224+8]-identityLeft) <= .005f) {
            std::cerr << "compressed foveation did not apply its outer local squeeze: "
                      << fgradient[112*224+8] << " identity " << identityLeft << '\n'; return 1;
        }
        // Reduced Light geometry with a half-integral aligned central intercept:
        // target=512, c=.8/r=1.5 -> aligned c=407/512, pre-align output=477,
        // packed output=480 and c1*target=17.5. Without the phase correction,
        // output x=240 maps to source coordinate 258.0 and linearly averages
        // texels 257/258. The corrected shader deliberately ties down to source
        // texel centre 257.5, therefore returns exactly texel 257.
        const std::vector<float> lightPhase={
            u32bits(512),u32bits(512),u32bits(480),u32bits(480),
            477.f/480.f,477.f/480.f,407.f/512.f,407.f/512.f,0,0,0,0,1.5f,1.5f,0,0};
        std::vector<float> lightGradient(1024*512);
        for(unsigned y=0;y<512;y++) for(unsigned x=0;x<1024;x++) {
            const float rampX=float(x % 512)/511.f;
            lightGradient[y*1024+x]=(x<512 ? rampX : .5f+.5f*rampX);
        }
        auto lightOut=w.draw(foveated.Get(),lightGradient,1024,512,480,480,
                             lightPhase,{0,0,.5f,1})[0];
        const float correctedLight=257.f/511.f;
        const float uncorrectedLight=257.5f/511.f;
        const float observedLight=lightOut[240*480+240];
        require(std::abs(observedLight-correctedLight)<2e-5f,
                "Light central phase did not sample the aligned source texel centre");
        require(std::abs(observedLight-uncorrectedLight)>.0004f,
                "Light central phase still averaged neighbouring texels");

        std::vector<float> ramp(24);for(unsigned y=0;y<4;y++)for(unsigned x=0;x<6;x++)ramp[y*6+x]=float(x)/5;
        auto fractional=w.draw(area.Get(),ramp,6,4,4,4,params,uv)[0];
        const float expected[]={1.f/15,1.f/3,2.f/3,14.f/15};
        for(unsigned i=0;i<16;i++)require(std::abs(fractional[i]-expected[i%4])<1e-6f,"fractional area footprint");
        auto seamParams=params;seamParams[6]=.5f;
        std::vector<float> stereo(64);for(unsigned y=0;y<8;y++)for(unsigned x=4;x<8;x++)stereo[y*8+x]=1;
        auto seam=w.draw(area.Get(),stereo,8,8,2,4,seamParams,{0,0,.5f,1})[0];
        for(float x:seam)require(std::abs(x)<1e-6f,"area crossed eye boundary");
        seamParams[8]=.5f;
        auto right=w.draw(area.Get(),stereo,8,8,2,4,seamParams,{.5f,0,1,1},false,1)[0];
        for(float x:right)require(std::abs(x-1)<1e-6f,"right eye selection/boundary");
        auto adaptiveLeft=w.draw(adaptive.Get(),stereo,8,8,3,5,seamParams,{0,0,.5f,1})[0];
        auto adaptiveRight=w.draw(adaptive.Get(),stereo,8,8,3,5,seamParams,{1,1,.5f,0},false,1)[0];
        for(float x:adaptiveLeft)require(std::abs(x)<1e-6f,"Adaptive left eye seam");
        for(float x:adaptiveRight)require(std::abs(x-1)<1e-6f,"Adaptive right/flipped eye seam");
        // Identity planar coefficients isolate quantization from color-matrix math.
        const std::vector<float> planar={0,0,0,0,1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,0};
        for(float code:{0.f,16.f,24.f,48.f,128.f,235.f,255.f}) {
            auto out=w.draw(dither.Get(),std::vector<float>(16,code/255),4,4,4,4,planar,uv,true);
            for(const auto &plane:out)for(float x:plane)require(x==code,"dither changed integer neutral");
        }
        auto gradient=w.draw(dither.Get(),std::vector<float>(16,48.25f/255),4,4,4,4,planar,uv,true);
        for(const auto &plane:gradient) {
            float sum=0;for(float x:plane){require(x==48 || x==49,"dither range");sum+=x;}
            require(sum/16==48.25f,"dither mean bias");
        }
        std::cout<<"WARP adaptive/area/dither/foveation correctness passed; no hardware timing claim\n";return 0;
    } catch(const std::exception &e){std::cerr<<e.what()<<'\n';return 1;}
}
