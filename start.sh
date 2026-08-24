#!/usr/bin/env bash
# hiagent 辅助 Web 服务 — 一键启动脚本 (Linux / macOS)
# 用法: ./start.sh [--port 8080] [--host 0.0.0.0] [--reload] [--no-check]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=8080
HOST="0.0.0.0"
RELOAD=false
NO_CHECK=false

# ── 参数解析 ──────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case "$1" in
        --port)    PORT="$2"; shift 2 ;;
        --host)    HOST="$2"; shift 2 ;;
        --reload)  RELOAD=true; shift ;;
        --no-check) NO_CHECK=true; shift ;;
        -h|--help)
            echo "用法: ./start.sh [选项]"
            echo ""
            echo "选项:"
            echo "  --port PORT      服务端口 (默认: 8080)"
            echo "  --host HOST      绑定地址 (默认: 0.0.0.0)"
            echo "  --reload         启用开发模式 (热重载)"
            echo "  --no-check       跳过环境检查和依赖安装"
            echo "  -h, --help       显示帮助信息"
            exit 0
            ;;
        *)
            echo "[ERROR] 未知参数: $1"
            exit 1
            ;;
    esac
done

# ── 日志辅助 ──────────────────────────────────────────────

log_info()  { echo -e "\033[36m[INFO]\033[0m  $1"; }
log_ok()    { echo -e "\033[32m[OK]\033[0m    $1"; }
log_warn()  { echo -e "\033[33m[WARN]\033[0m  $1"; }
log_err()   { echo -e "\033[31m[ERROR]\033[0m $1"; }

# ── 环境检查 ──────────────────────────────────────────────

check_environment() {
    log_info "检查 Python 环境..."

    local python_cmd=""
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            local ver
            ver=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
            local major minor
            major=$(echo "$ver" | cut -d. -f1)
            minor=$(echo "$ver" | cut -d. -f2)
            if [[ "$major" -ge 3 && "$minor" -ge 10 ]]; then
                python_cmd="$cmd"
                break
            fi
        fi
    done

    if [[ -z "$python_cmd" ]]; then
        log_err "未检测到 Python >= 3.10，请先安装"
        log_err "安装方式: https://www.python.org/downloads/"
        exit 1
    fi

    PYTHON_CMD="$python_cmd"
    log_ok "Python 环境: $($PYTHON_CMD --version 2>&1)"

    # 检测 pip
    if ! $PYTHON_CMD -m pip --version &>/dev/null; then
        log_err "未检测到 pip，请执行: $PYTHON_CMD -m ensurepip --upgrade"
        exit 1
    fi
    log_ok "pip 已就绪"
}

# ── 虚拟环境 ──────────────────────────────────────────────

init_venv() {
    local venv_dir="$SCRIPT_DIR/venv"
    local activate_script="$venv_dir/bin/activate"

    if [[ ! -d "$venv_dir" ]]; then
        log_info "创建虚拟环境..."
        $PYTHON_CMD -m venv "$venv_dir"
        log_ok "虚拟环境已创建: $venv_dir"
    else
        log_ok "虚拟环境已存在"
    fi

    if [[ ! -f "$activate_script" ]]; then
        log_err "虚拟环境激活脚本不存在: $activate_script"
        log_err "请删除 venv/ 目录后重试"
        exit 1
    fi

    # shellcheck disable=SC1090
    source "$activate_script"
    log_ok "虚拟环境已激活"
}

# ── 依赖安装 ──────────────────────────────────────────────

install_dependencies() {
    local req_file="$SCRIPT_DIR/requirements.txt"
    local marker_file="$SCRIPT_DIR/venv/.req_installed"

    if [[ ! -f "$req_file" ]]; then
        log_warn "requirements.txt 不存在，跳过依赖安装"
        return
    fi

    local need_install=true
    if [[ -f "$marker_file" ]]; then
        local current_hash saved_hash
        if command -v md5sum &>/dev/null; then
            current_hash=$(md5sum "$req_file" | awk '{print $1}')
        else
            current_hash=$(md5 -q "$req_file")
        fi
        saved_hash=$(cat "$marker_file")
        if [[ "$current_hash" == "$saved_hash" ]]; then
            need_install=false
        fi
    fi

    if [[ "$need_install" == true ]]; then
        log_info "安装 Python 依赖..."
        pip install -r "$req_file" --quiet
        local hash
        if command -v md5sum &>/dev/null; then
            hash=$(md5sum "$req_file" | awk '{print $1}')
        else
            hash=$(md5 -q "$req_file")
        fi
        echo "$hash" > "$marker_file"
        log_ok "依赖安装完成"
    else
        log_ok "依赖已是最新，跳过安装"
    fi
}

# ── 配置初始化 ────────────────────────────────────────────

init_config() {
    local env_file="$SCRIPT_DIR/.env"
    local env_example="$SCRIPT_DIR/.env.example"

    if [[ ! -f "$env_file" ]]; then
        if [[ -f "$env_example" ]]; then
            cp "$env_example" "$env_file"
            log_ok "已从 .env.example 生成 .env 配置文件"
        else
            log_warn ".env.example 不存在，跳过配置初始化"
        fi
    else
        log_ok ".env 配置文件已存在"
    fi

    for dir in tmp_files data; do
        local full_path="$SCRIPT_DIR/$dir"
        if [[ ! -d "$full_path" ]]; then
            mkdir -p "$full_path"
            log_ok "已创建目录: $dir/"
        fi
    done
}

# ── 端口检查 ──────────────────────────────────────────────

check_port() {
    local port="$1"
    if command -v ss &>/dev/null; then
        if ss -tlnp 2>/dev/null | grep -q ":${port} "; then
            return 0
        fi
    elif command -v lsof &>/dev/null; then
        if lsof -i :"$port" -sTCP:LISTEN &>/dev/null; then
            return 0
        fi
    fi
    return 1
}

# ── 主流程 ────────────────────────────────────────────────

echo ""
echo "========================================"
echo "  hiagent 辅助 Web 服务 — 启动脚本"
echo "========================================"
echo ""

cd "$SCRIPT_DIR"

# 1. 环境检查
if [[ "$NO_CHECK" != true ]]; then
    check_environment
    init_venv
    install_dependencies
else
    log_warn "已跳过环境检查和依赖安装 (--no-check)"
    local_activate="$SCRIPT_DIR/venv/bin/activate"
    if [[ -f "$local_activate" ]]; then
        # shellcheck disable=SC1090
        source "$local_activate"
    fi
fi

# 2. 配置初始化
init_config

# 3. 端口检查
if check_port "$PORT"; then
    log_err "端口 $PORT 已被占用，请更换端口或关闭占用进程"
    log_err "示例: ./start.sh --port 9000"
    exit 1
fi

# 4. 启动服务
echo ""
log_info "启动服务: http://$HOST:$PORT"
if [[ "$RELOAD" == true ]]; then
    log_info "开发模式: 热重载已启用"
fi
log_info "API 文档: http://localhost:$PORT/docs"
echo ""

uvicorn_args=("app.main:app" "--host" "$HOST" "--port" "$PORT")
if [[ "$RELOAD" == true ]]; then
    uvicorn_args+=("--reload")
fi

python -m uvicorn "${uvicorn_args[@]}"
