@echo off
rem Builds the full beta streamer (driver + dashboard + PyroWave) into
rem research\ALVR-20.13.0\build\alvr_streamer_windows, the folder testers unzip and run.
rem Build PyroWave first: build_pyrowave_pc.cmd interop
setlocal
set "WS=%~dp0..\..\.."
if not "%XRWIRED_INPUTS%"=="" set "WS=%XRWIRED_INPUTS%"
set "ALVR=%WS%\research\ALVR-20.13.0"
set "ALVR_PYROWAVE_DIR=%WS%\research\pyrowave"
set "PYRO_DLL=%ALVR_PYROWAVE_DIR%\build-interop\Release\libpyrowave-shared-0.dll"
for /f "usebackq delims=" %%i in (`python "%~dp0..\ci\source_lock.py" --value rust`) do set "RUST_TOOLCHAIN=%%i"
if "%RUST_TOOLCHAIN%"=="" ( echo could not read Rust toolchain from sources.lock.json & exit /b 1 )
if not exist "%PYRO_DLL%" ( echo build pyrowave interop first & exit /b 1 )
python "%~dp0..\ci\stamp_alvr_version.py" "%ALVR%" || exit /b 1
rem xtask's nested cargo calls inherit the pinned toolchain from here
set "RUSTUP_TOOLCHAIN=%RUST_TOOLCHAIN%"
cd /d "%ALVR%"
cargo xtask build-streamer --release || exit /b 1
copy /y "%PYRO_DLL%" build\alvr_streamer_windows\bin\win64\ >nul || exit /b 1
if not exist build\alvr_streamer_windows\bin\win64\driver_alvr_server.dll ( echo streamer driver DLL was not produced & exit /b 1 )
if not exist build\alvr_streamer_windows\bin\win64\libpyrowave-shared-0.dll ( echo PyroWave runtime DLL was not packaged & exit /b 1 )
dir /b build\alvr_streamer_windows build\alvr_streamer_windows\bin\win64
echo BUILD_OK
