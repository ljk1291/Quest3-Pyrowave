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
            struct O { float4 pos:SV_POSITION; float2 uv:TEXCOORD; uint view:VIEW; };
            O VS(uint id:SV_VertexID) {
                float2 p=float2((id==1)?3:-1,(id==2)?-3:1);
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
        context->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
        context->VSSetShader(vs.Get(),nullptr,0);context->PSSetShader(ps,nullptr,0);context->Draw(3,0);
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
        require(argc==4,"expected area, dither and foveation CSO paths");Warp w;
        auto area=w.shader(argv[1]),dither=w.shader(argv[2]),foveated=w.shader(argv[3]);
        const std::vector<float> params={1,0,0,0,0,0,1,1,0,0,1,1},uv={0,0,1,1};
        auto dc=w.draw(area.Get(),std::vector<float>(64,.37f),8,8,4,4,params,uv)[0];
        for(float x:dc) require(std::abs(x-.37f)<1e-6f,"area DC changed");
        std::vector<float> checker(64);for(unsigned y=0;y<8;y++)for(unsigned x=0;x<8;x++)checker[y*8+x]=float((x+y)%2);
        auto average=w.draw(area.Get(),checker,8,8,4,4,params,uv)[0];
        for(float x:average) require(std::abs(x-.5f)<1e-6f,"checkerboard area average");

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
        std::vector<float> foveatedStereo(128); for(unsigned y=0;y<8;y++) for(unsigned x=8;x<16;x++) foveatedStereo[y*16+x]=1;
        // Blur-only retains matching source/output geometry while exercising
        // the same source-pixel filter. A compressed profile needs its real
        // smaller optimized dimensions, which this compact seam fixture does
        // not model.
        auto seamFoveation=foveation; seamFoveation[15]=1;
        auto fseam=w.draw(foveated.Get(),foveatedStereo,16,8,16,8,seamFoveation,uv)[0];
        for(unsigned y=0;y<8;y++) for(unsigned x=0;x<16;x++)
            require(std::abs(fseam[y*16+x]-(x<8?0.f:1.f))<1e-6f,"foveation crossed eye seam");
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
        std::cout<<"WARP area/dither correctness passed; no hardware timing claim\n";return 0;
    } catch(const std::exception &e){std::cerr<<e.what()<<'\n';return 1;}
}
