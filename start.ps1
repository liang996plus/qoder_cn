# hiagent 辅助 Web 服务 — 一键启动脚本 (Windows PowerShell)
# 用法: .\start.ps1 [-Port 8080] [-Host "0.0.0.0"] [-Reload] [-NoCheck]

param(
    [int]$Port = 8080,
    [string]$Host_ = "0.0.0.0",
    [switch]$Reload,
    [switch]$NoCheck
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# ── 日志辅助 ──────────────────────────────────────────────

function Write-Info    { param([string]$Msg) Write-Host "[INFO]  $Msg" -ForegroundColor Cyan }
function Write-Ok      { param([string]$Msg) Write-Host "[OK]    $Msg" -ForegroundColor Green }
function Write-Warn    { param([string]$Msg) Write-Host "[WARN]  $Msg" -ForegroundColor Yellow }
function Write-Err     { param([string]$Msg) Write-Host "[ERROR] $Msg" -ForegroundColor Red }

# ── 环境检查 ──────────────────────────────────────────────

function Test-Environment {
    Write-Info "检查 Python 环境..."

    # 检测 Python
    $pythonCmd = $null
    foreach ($cmd in @("python", "python3", "py")) {
        try {
            $ver = & $cmd --version 2>&1
            if ($ver -match "Python (\d+)\.(\d+)") {
                $major = [int]$Matches[1]
                $minor = [int]$Matches[2]
                if ($major -ge 3 -and $minor -ge 10) {
                    $pythonCmd = $cmd
                    break
                }
            }
        } catch { }
    }

    if (-not $pythonCmd) {
        Write-Err "未检测到 Python >= 3.10，请先安装 Python 3.10+"
        Write-Err "下载地址: https://www.python.org/downloads/"
        exit 1
    }

    $ver = & $pythonCmd --version 2>&1
    Write-Ok "Python 环境: $ver"

    # 检测 pip
    try {
        $pipVer = & $pythonCmd -m pip --version 2>&1
        if ($LASTEXITCODE -ne 0) { throw "pip not found" }
    } catch {
        Write-Err "未检测到 pip，请执行: python -m ensurepip --upgrade"
        exit 1
    }
    Write-Ok "pip 已就绪"

    return $pythonCmd
}

# ── 虚拟环境 ──────────────────────────────────────────────

function Initialize-Venv {
    param([string]$PythonCmd)

    $venvDir = Join-Path $ScriptDir "venv"
    $activateScript = Join-Path $venvDir "Scripts\Activate.ps1"

    if (-not (Test-Path $venvDir)) {
        Write-Info "创建虚拟环境..."
        & $PythonCmd -m venv $venvDir
        if ($LASTEXITCODE -ne 0) {
            Write-Err "创建虚拟环境失败"
            exit 1
        }
        Write-Ok "虚拟环境已创建: $venvDir"
    } else {
        Write-Ok "虚拟环境已存在"
    }

    # 激活虚拟环境
    if (-not (Test-Path $activateScript)) {
        Write-Err "虚拟环境激活脚本不存在: $activateScript"
        Write-Err "请删除 venv/ 目录后重试"
        exit 1
    }
    . $activateScript
    Write-Ok "虚拟环境已激活"
}

# ── 依赖安装 ──────────────────────────────────────────────

function Install-Dependencies {
    $reqFile = Join-Path $ScriptDir "requirements.txt"
    $markerFile = Join-Path $ScriptDir "venv\.req_installed"

    if (-not (Test-Path $reqFile)) {
        Write-Warn "requirements.txt 不存在，跳过依赖安装"
        return
    }

    # 通过对比 hash 判断是否需要重装
    $needInstall = $true
    if (Test-Path $markerFile) {
        $currentHash = (Get-FileHash $reqFile -Algorithm MD5).Hash
        $savedHash = Get-Content $markerFile -Raw
        if ($currentHash -eq $savedHash.Trim()) {
            $needInstall = $false
        }
    }

    if ($needInstall) {
        Write-Info "安装 Python 依赖..."
        python -m pip install -r $reqFile --quiet
        if ($LASTEXITCODE -ne 0) {
            Write-Err "依赖安装失败，请检查 requirements.txt"
            exit 1
        }
        $currentHash = (Get-FileHash $reqFile -Algorithm MD5).Hash
        Set-Content -Path $markerFile -Value $currentHash -NoNewline
        Write-Ok "依赖安装完成"
    } else {
        Write-Ok "依赖已是最新，跳过安装"
    }
}

# ── 配置初始化 ────────────────────────────────────────────

function Initialize-Config {
    # .env 文件
    $envFile = Join-Path $ScriptDir ".env"
    $envExample = Join-Path $ScriptDir ".env.example"

    if (-not (Test-Path $envFile)) {
        if (Test-Path $envExample) {
            Copy-Item $envExample $envFile
            Write-Ok "已从 .env.example 生成 .env 配置文件"
        } else {
            Write-Warn ".env.example 不存在，跳过配置初始化"
        }
    } else {
        Write-Ok ".env 配置文件已存在"
    }

    # 运行时目录
    $dirs = @("tmp_files", "data")
    foreach ($dir in $dirs) {
        $fullPath = Join-Path $ScriptDir $dir
        if (-not (Test-Path $fullPath)) {
            New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
            Write-Ok "已创建目录: $dir/"
        }
    }
}

# ── 端口检查 ──────────────────────────────────────────────

function Test-PortInUse {
    param([int]$PortNum)
    $conn = Get-NetTCPConnection -LocalPort $PortNum -ErrorAction SilentlyContinue
    return ($null -ne $conn)
}

# ── 主流程 ────────────────────────────────────────────────

Write-Host ""
Write-Host "========================================" -ForegroundColor White
Write-Host "  hiagent 辅助 Web 服务 — 启动脚本" -ForegroundColor White
Write-Host "========================================" -ForegroundColor White
Write-Host ""

Set-Location $ScriptDir

# 1. 环境检查
if (-not $NoCheck) {
    $pythonCmd = Test-Environment
    Initialize-Venv -PythonCmd $pythonCmd
    Install-Dependencies
} else {
    Write-Warn "已跳过环境检查和依赖安装 (--no-check)"
    # 尝试激活已有的虚拟环境
    $activateScript = Join-Path $ScriptDir "venv\Scripts\Activate.ps1"
    if (Test-Path $activateScript) {
        . $activateScript
    }
}

# 2. 配置初始化
Initialize-Config

# 3. 端口检查
if (Test-PortInUse -PortNum $Port) {
    Write-Err "端口 $Port 已被占用，请更换端口或关闭占用进程"
    Write-Err "示例: .\start.ps1 -Port 9000"
    exit 1
}

# 4. 启动服务
Write-Host ""
Write-Info "启动服务: http://$Host_`:$Port"
if ($Reload) {
    Write-Info "开发模式: 热重载已启用"
}
Write-Info "API 文档: http://localhost:$Port/docs"
Write-Host ""

$uvicornArgs = @(
    "app.main:app",
    "--host", $Host_,
    "--port", "$Port"
)
if ($Reload) {
    $uvicornArgs += "--reload"
}

python -m uvicorn @uvicornArgs
