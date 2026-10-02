@echo off
rem Builds the ALVR 20.13.0 server driver (alvr_server_openvr.dll) with the PyroWave encoder, from
rem the workspace clone (research\ALVR-20.13.0) against research\pyrowave\build-interop.
rem Build PyroWave first: build_pyrowave_pc.cmd interop
setlocal
set "WS=%~dp0..\..\.."
if not "%XRWIRED_INPUTS%"=="" set "WS=%XRWIRED_INPUTS%"
set "ALVR=%WS%\research\ALVR-20.13.0"
set "ALVR_PYROWAVE_DIR=%WS%\research\pyrowave"
for /f "usebackq delims=" %%i in (`python "%~dp0..\ci\source_lock.py" --value rust`) do set "RUST_TOOLCHAIN=%%i"
if "%RUST_TOOLCHAIN%"=="" ( echo could not read Rust toolchain from sources.lock.json & exit /b 1 )
if not exist "%ALVR_PYROWAVE_DIR%\build-interop\Release\pyrowave-shared.lib" ( echo build pyrowave interop first & exit /b 1 )
if not exist "%ALVR_PYROWAVE_DIR%\build-interop\Release\libpyrowave-shared-0.dll" ( echo missing PyroWave runtime DLL & exit /b 1 )
python "%~dp0..\ci\stamp_alvr_version.py" "%ALVR%" || exit /b 1
cd /d "%ALVR%"
cargo +%RUST_TOOLCHAIN% build --release -p alvr_server_openvr || exit /b 1
if not exist target\release\alvr_server_openvr.dll ( echo server driver DLL was not produced & exit /b 1 )
dir /b target\release\alvr_server_openvr.dll
echo BUILD_OK
