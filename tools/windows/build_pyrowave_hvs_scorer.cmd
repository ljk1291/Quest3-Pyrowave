@echo off
rem Builds only the opt-in offline PSNR-HVS-M-H scorer source prepared by
rem tools.xrbench.hvs_scorer. It never replaces the runtime PyroWave build.
setlocal
set "WS=%~dp0..\..\.."
if not "%XRWIRED_INPUTS%"=="" set "WS=%XRWIRED_INPUTS%"
set "PW=%WS%\research\pyrowave-hvs-scorer"
if not exist "%PW%\PYROWAVE-HVS-PPD-SCORER.json" ( echo scorer source is not prepared & exit /b 1 )
set "GEN=Visual Studio 17 2022"
if not "%Q3PW_CMAKE_GENERATOR%"=="" set "GEN=%Q3PW_CMAKE_GENERATOR%"
cmake -S "%PW%" -B "%PW%\build-hvs-scorer" -G "%GEN%" -DCMAKE_BUILD_TYPE=Release -DPYROWAVE_UTILS=ON -DPYROWAVE_DEVEL=OFF -DSHADERC_ENABLE_SHARED_CRT=ON || exit /b 1
cmake --build "%PW%\build-hvs-scorer" --config Release --target pyrowave-psnr-hvs-m -j 16 || exit /b 1
dir /b "%PW%\build-hvs-scorer\Release\pyrowave-psnr-hvs-m.exe" || exit /b 1
