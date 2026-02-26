<#
    Build executable artifacts for voice-cli-agent and copy run-ready output to ./release.
    - onedir: release\voice-cli-agent-dir\voice-cli-agent-dir.exe (기본 실행)
    - onefile: release\voice-cli-agent.exe (선택)
    Build is performed in %TEMP% with ASCII path to avoid path-encoding issues.
#>
$ErrorActionPreference = "Stop"

function Get-PythonPath {
    param([string]$Preferred)

    if ($Preferred -and (Test-Path $Preferred)) {
        return $Preferred
    }

    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    return $null
}

function ModuleAvailable {
    param([string]$ModuleName)

    & $script:python -c "import importlib.util; import sys; sys.exit(0 if importlib.util.find_spec('$ModuleName') else 1)" 2>$null
    return $LASTEXITCODE -eq 0
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path $root

$projectName = "voice-cli-agent"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$python = Get-PythonPath -Preferred $venvPython

if (-not $python) {
    Write-Host "[error] Python을 찾지 못했습니다. python이 PATH에 있거나 .venv\\Scripts\\python.exe가 있어야 합니다."
    exit 1
}
Set-Variable -Name python -Value $python -Scope Script

$checkPyinstaller = & $python -m pip show pyinstaller 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[info] pyinstaller가 설치되어 있지 않습니다. 설치를 시도합니다."
    & $python -m pip install pyinstaller
}

if (Test-Path ".\\requirements.txt") {
    & $python -m pip install --quiet -r requirements.txt
}

$collectModules = @()
$modulesToCollect = @("vosk", "speech_recognition", "pyttsx3", "openai", "python_dotenv", "dotenv", "pyaudio")
foreach ($module in $modulesToCollect) {
    if (ModuleAvailable $module) {
        $collectModules += "--collect-all"
        $collectModules += $module
    }
}

$envTemp = if ($env:TEMP) { $env:TEMP } else { Join-Path $env:LOCALAPPDATA "Temp" }
$tempRoot = Join-Path $envTemp "voice-cli-agent-build"
if (-not (Test-Path $tempRoot)) {
    New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$workDir = Join-Path $tempRoot $stamp
New-Item -ItemType Directory -Force -Path $workDir | Out-Null
$runtimeTmp = Join-Path $workDir "runtime_tmp"
New-Item -ItemType Directory -Force -Path $runtimeTmp | Out-Null

Copy-Item -Force "$root\app.py" "$workDir\app.py"
Copy-Item -Force "$root\requirements.txt" "$workDir\requirements.txt"
if (Test-Path "$root\README.md") {
    Copy-Item -Force "$root\README.md" "$workDir\README.md"
}
if (Test-Path "$root\.env") {
    Copy-Item -Force "$root\.env" "$workDir\.env"
}

$publish = Join-Path $root "release"
New-Item -ItemType Directory -Force -Path $publish | Out-Null

Set-Location -Path $workDir

$commonArgs = @(
    "--noconfirm",
    "--clean",
    "--distpath", (Join-Path $workDir "dist"),
    "--workpath", (Join-Path $workDir "build"),
    "--specpath", (Join-Path $workDir "build")
) + $collectModules

$buildSuccess = $false

Write-Host "[info] onedir 빌드 생성 중..."
$onedirName = "$($projectName)-dir"
& $python -m PyInstaller @commonArgs --onedir --name $onedirName app.py
if ($LASTEXITCODE -eq 0) {
    $buildSuccess = $true
    $distDir = Join-Path $workDir "dist\\$onedirName"
    $publishDir = Join-Path $publish $onedirName
    if (Test-Path $distDir) {
        if (Test-Path $publishDir) {
            Remove-Item -Recurse -Force $publishDir
        }
        Copy-Item -Force -Recurse $distDir $publishDir
        Write-Host "[done] onedir 생성 완료: release\\$onedirName\\$onedirName.exe"
    } else {
        Write-Host "[warn] onedir 산출물을 찾지 못했습니다: $distDir"
    }
} else {
    Write-Host "[warn] onedir 빌드가 실패했습니다."
}

Write-Host "[info] onefile 빌드 생성 중..."
& $python -m PyInstaller @commonArgs --onefile --name $projectName --runtime-tmpdir $runtimeTmp app.py
if ($LASTEXITCODE -eq 0) {
    $buildSuccess = $true
    $distExe = Join-Path $workDir "dist\\$projectName.exe"
    if (Test-Path $distExe) {
        Copy-Item -Force $distExe (Join-Path $publish "$projectName.exe")
        Write-Host "[done] onefile 생성 완료: release\\$projectName.exe"
    } else {
        Write-Host "[warn] onefile 산출물을 찾지 못했습니다: $distExe"
    }
} else {
    Write-Host "[warn] onefile 빌드가 실패했습니다."
}

if (Test-Path "$root\.env") {
    Copy-Item -Force "$root\.env" (Join-Path $publish ".env")
}
if (Test-Path "$root\README.md") {
    Copy-Item -Force "$root\README.md" (Join-Path $publish "README.txt")
}

if (-not $buildSuccess) {
    Write-Host "[error] 현재 환경에서 빌드가 실패했습니다. 로그를 확인하세요."
    exit 1
}

Write-Host "[done] 빌드 완료. 권장 실행 경로: release\\$onedirName\\$onedirName.exe"
