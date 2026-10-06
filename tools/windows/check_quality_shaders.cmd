@echo off
rem Recompile/hash experimental DXBC and read back tiny images through software WARP.
setlocal
set "REPO=%~dp0..\.."
set "ALVR=%XRWIRED_INPUTS%\research\ALVR-20.13.0"
if not "%~1"=="" set "ALVR=%~1"
set "OUTPUT=%XRWIRED_INPUTS%\quality-shaders"
set "FXC=%ProgramFiles(x86)%\Windows Kits\10\bin\10.0.26100.0\x64\fxc.exe"
if not exist "%FXC%" ( echo Required recorded SDK fxc is missing & exit /b 1 )
python "%REPO%\tools\ci\check_quality_shaders.py" "%ALVR%" --fxc "%FXC%" --compile-out "%OUTPUT%" || exit /b 1
for /f "usebackq tokens=*" %%i in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "QUALITY_VS=%%i"
if not defined QUALITY_VS ( echo Visual C++ tools missing & exit /b 1 )
call "%QUALITY_VS%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cl /nologo /EHsc /std:c++17 /O2 /W4 /WX "%REPO%\tools\ci\quality_shaders_test.cpp" /Fo"%OUTPUT%\quality-shaders-test.obj" /Fe"%OUTPUT%\quality-shaders-test.exe" d3d11.lib d3dcompiler.lib || exit /b 1
"%OUTPUT%\quality-shaders-test.exe" "%ALVR%\alvr\server_openvr\cpp\platform\win32\FrameRenderPSArea.cso" "%ALVR%\alvr\server_openvr\cpp\platform\win32\rgbtoyuvplanardither.cso" "%ALVR%\alvr\server_openvr\cpp\platform\win32\CompressAxisAlignedPixelShader.cso" "%ALVR%\alvr\server_openvr\cpp\platform\win32\FrameRenderPSAdaptive.cso" || exit /b 1
