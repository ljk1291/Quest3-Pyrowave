<#
Builds the Q3PW Idle APK fully offline (no Gradle, no network).
Usage:  powershell -NoProfile -ExecutionPolicy Bypass -File build.ps1
Output: <repo>\out\idle-app\q3pw-idle.apk
Idempotent: intermediates are rebuilt each run; the debug keystore is created once.
#>
[CmdletBinding()]
param(
    [string]$Toolchain = 'C:\q3pw\fast\toolchain',
    [string]$NdkVersion = '27.2.12479018'
)
$ErrorActionPreference = 'Stop'

function Run([string]$exe, [string[]]$argv) {
    # run a native tool; fail on non-zero exit (stderr is not redirected, avoiding PS 5.1 ErrorRecord quirks)
    $prev = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    & $exe @argv
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    if ($code -ne 0) { throw "Command failed ($code): $exe $($argv -join ' ')" }
}

$here = $PSScriptRoot
$repo = (Resolve-Path (Join-Path $here '..\..\..')).Path
$outDir = Join-Path $repo 'out\idle-app'
$obj = Join-Path $outDir 'obj'
$apkOut = Join-Path $outDir 'q3pw-idle.apk'
$signDir = Join-Path $repo 'results\local\signing'
$ks = Join-Path $signDir 'q3pw-idle-debug.keystore'
$ksPwFile = Join-Path $signDir 'q3pw-idle-debug-password.txt'

# --- locate tools -----------------------------------------------------------
$sdk = Join-Path $Toolchain 'android-sdk'
$ndk = Join-Path $sdk "ndk\$NdkVersion"
$llvmBin = Join-Path $ndk 'toolchains\llvm\prebuilt\windows-x86_64\bin'
$clang = Join-Path $llvmBin 'aarch64-linux-android29-clang.cmd'
$readelf = Join-Path $llvmBin 'llvm-readelf.exe'
$glueDir = Join-Path $ndk 'sources\android\native_app_glue'
$btDir = Get-ChildItem (Join-Path $sdk 'build-tools') -Directory | Sort-Object { [version]($_.Name -replace '[^0-9.].*$','') } -Descending | Select-Object -First 1
$bt = $btDir.FullName
$aapt2 = Join-Path $bt 'aapt2.exe'
$zipalign = Join-Path $bt 'zipalign.exe'
$apksigner = Join-Path $bt 'apksigner.bat'
$androidJar = Get-ChildItem (Join-Path $sdk 'platforms') -Directory | Sort-Object Name -Descending |
    ForEach-Object { Join-Path $_.FullName 'android.jar' } | Where-Object { Test-Path $_ } | Select-Object -First 1
$loaderSo = Join-Path $Toolchain 'openxr\libopenxr_loader.so'

$javaHome = $env:JAVA_HOME
if (-not $javaHome -or -not (Test-Path (Join-Path $javaHome 'bin\java.exe'))) {
    $javaHome = [Environment]::GetEnvironmentVariable('JAVA_HOME', 'User')
}
if (-not $javaHome -or -not (Test-Path (Join-Path $javaHome 'bin\java.exe'))) { throw 'JAVA_HOME (JDK 17) not found' }
$env:JAVA_HOME = $javaHome
$env:Path = (Join-Path $javaHome 'bin') + ';' + $env:Path
$keytool = Join-Path $javaHome 'bin\keytool.exe'

foreach ($p in @($clang, $readelf, $glueDir, $aapt2, $zipalign, $apksigner, $androidJar, $loaderSo, $keytool)) {
    if (-not $p -or -not (Test-Path $p)) { throw "Missing toolchain piece: $p" }
}
Write-Host "build-tools : $bt"
Write-Host "android.jar : $androidJar"
Write-Host "NDK         : $ndk"
Write-Host "JAVA_HOME   : $javaHome"

# --- clean intermediates ----------------------------------------------------
if (Test-Path $obj) { Remove-Item $obj -Recurse -Force }
New-Item -ItemType Directory -Force $obj | Out-Null
if (Test-Path $apkOut) { Remove-Item $apkOut -Force }

# --- compile + link libmain.so ---------------------------------------------
$libStage = Join-Path $obj 'lib\arm64-v8a'
New-Item -ItemType Directory -Force $libStage | Out-Null
$mainSo = Join-Path $libStage 'libmain.so'
Copy-Item $loaderSo (Join-Path $libStage 'libopenxr_loader.so') -Force

$cflags = @('-O2', '-fPIC', '-std=gnu11', '-Wall', '-Wextra', '-Wno-unused-parameter', '-Wno-missing-field-initializers',
            '-ffunction-sections', '-fdata-sections', '-fvisibility=hidden',
            '-DXR_USE_PLATFORM_ANDROID', '-DXR_USE_GRAPHICS_API_OPENGL_ES',
            "-I$here\include", "-I$glueDir")
$glueObj = Join-Path $obj 'android_native_app_glue.o'
$mainObj = Join-Path $obj 'idle_main.o'
Run $clang ($cflags + @('-c', (Join-Path $glueDir 'android_native_app_glue.c'), '-o', $glueObj))
Run $clang ($cflags + @('-c', (Join-Path $here 'src\idle_main.c'), '-o', $mainObj))
Run $clang @('-shared', '-o', $mainSo, $mainObj, $glueObj,
             '-Wl,-soname,libmain.so', '-Wl,-u,ANativeActivity_onCreate',
             '-Wl,--gc-sections', '-Wl,--build-id=none', '-Wl,-z,max-page-size=16384', '-Wl,-s',
             "-L$libStage", '-lopenxr_loader', '-llog', '-landroid', '-lEGL', '-lGLESv3')

# --- aapt2 link manifest -> unsigned apk ------------------------------------
$unsigned = Join-Path $obj 'unsigned.apk'
Run $aapt2 @('link', '-o', $unsigned, '-I', $androidJar, '--manifest', (Join-Path $here 'AndroidManifest.xml'),
             '--min-sdk-version', '29', '--target-sdk-version', '32', '--version-code', '1', '--version-name', '1.0')

# --- add native libs (stored, no compression) -------------------------------
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::Open($unsigned, [System.IO.Compression.ZipArchiveMode]::Update)
try {
    foreach ($name in 'libmain.so', 'libopenxr_loader.so') {
        $entry = $zip.CreateEntry("lib/arm64-v8a/$name", [System.IO.Compression.CompressionLevel]::NoCompression)
        $es = $entry.Open()
        try {
            $bytes = [System.IO.File]::ReadAllBytes((Join-Path $libStage $name))
            $es.Write($bytes, 0, $bytes.Length)
        } finally { $es.Dispose() }
    }
} finally { $zip.Dispose() }

# --- zipalign (page-align stored .so) ---------------------------------------
$aligned = Join-Path $obj 'aligned.apk'
Run $zipalign @('-f', '-p', '4', $unsigned, $aligned)

# --- debug keystore (created once) ------------------------------------------
New-Item -ItemType Directory -Force $signDir | Out-Null
if (-not (Test-Path $ksPwFile)) { Set-Content -Path $ksPwFile -Value 'q3pw-idle-debug' -Encoding ASCII }
if (-not (Test-Path $ks)) {
    Write-Host 'Creating debug keystore (once)...'
    $pw = (Get-Content $ksPwFile -TotalCount 1).Trim()
    Run $keytool @('-genkeypair', '-keystore', $ks, '-storepass', $pw, '-keypass', $pw,
                   '-alias', 'q3pwidle', '-keyalg', 'RSA', '-keysize', '2048', '-validity', '10000',
                   '-dname', 'CN=Q3PW Idle Debug,O=q3pw,C=US')
}

# --- sign -------------------------------------------------------------------
$env:Q3PW_IDLE_KS_PW = (Get-Content $ksPwFile -TotalCount 1).Trim()
Run $apksigner @('sign', '--ks', $ks, '--ks-key-alias', 'q3pwidle',
                 '--v2-signing-enabled', 'true', '--v3-signing-enabled', 'true', '--ks-pass', 'env:Q3PW_IDLE_KS_PW', '--key-pass', 'env:Q3PW_IDLE_KS_PW',
                 '--out', $apkOut, $aligned)

# --- verify -----------------------------------------------------------------
Write-Host "`n=== apksigner verify ==="
Run $apksigner @('verify', '--verbose', '--print-certs', $apkOut)
Write-Host "`n=== zipalign check ==="
Run $zipalign @('-c', '-p', '4', $apkOut)
Write-Host 'zipalign OK'
Write-Host "`n=== aapt2 dump badging ==="
Run $aapt2 @('dump', 'badging', $apkOut)
Write-Host "`n=== libmain.so dynamic section (NEEDED) ==="
& $readelf -d $mainSo | Select-String 'NEEDED|SONAME'

$sz = (Get-Item $apkOut).Length
Write-Host ("`nAPK: {0}  ({1} bytes, {2:N1} KiB)" -f $apkOut, $sz, ($sz / 1KB))
