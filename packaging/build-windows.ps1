param(
  [Parameter(Mandatory=$true)][string]$ObsSdkPrefix,
  [Parameter(Mandatory=$true)][string]$QtPrefix,
  [string]$IsccPath = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$nativeBuild = Join-Path $root 'build-native'
$stage = Join-Path $root 'stage'
$venv = Join-Path $root '.build-venv'

if (-not (Test-Path $ObsSdkPrefix) -or -not (Test-Path $QtPrefix)) {
  throw 'Provide installed OBS development artifacts and matching Qt6 prefix paths.'
}
if (-not (Test-Path $IsccPath)) { throw 'Install Inno Setup 6 and supply -IsccPath if installed elsewhere.' }
if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) { throw 'CMake is required.' }
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Python 3.11+ with py launcher is required.' }

& cmake -S (Join-Path $root 'native') -B $nativeBuild -A x64 "-DCMAKE_PREFIX_PATH=$ObsSdkPrefix;$QtPrefix"
if ($LASTEXITCODE -ne 0) { throw 'OBS plugin configuration failed.' }
& cmake --build $nativeBuild --config Release
if ($LASTEXITCODE -ne 0) { throw 'OBS plugin compilation failed.' }
& cmake --install $nativeBuild --config Release --prefix $stage
if ($LASTEXITCODE -ne 0) { throw 'OBS plugin staging failed.' }
$dll = Join-Path $stage 'forgecast\bin\64bit\forgecast.dll'
if (-not (Test-Path $dll)) { throw 'ForgeCast DLL was not staged.' }

& py -3 -m venv $venv
if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
$python = Join-Path $venv 'Scripts\python.exe'
& $python -m pip install -r (Join-Path $root 'requirements.txt') 'pyinstaller==6.16.0' 'pywebview==6.2.1'
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
& $python -m PyInstaller --noconfirm --clean --windowed --onedir --name ForgeCast `
  --paths $root --add-data "$(Join-Path $root 'web');web" `
  --distpath (Join-Path $root 'dist') --workpath (Join-Path $root 'build-pyinstaller') `
  --specpath (Join-Path $root 'build-pyinstaller') (Join-Path $root 'launcher.py')
if ($LASTEXITCODE -ne 0) { throw 'ForgeCast companion freeze failed.' }
if (-not (Test-Path (Join-Path $root 'dist\ForgeCast\ForgeCast.exe'))) { throw 'Companion executable missing.' }

& $IsccPath (Join-Path $PSScriptRoot 'ForgeCast.iss')
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed.' }
Write-Host "Installer created in $(Join-Path $root 'release'). Test it on a separate OBS installation before offering it."
