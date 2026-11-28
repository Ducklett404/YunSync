#!/usr/bin/env bash
set -euo pipefail

board_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
env_file="$board_dir/.env"

compose() {
  docker compose --project-name yunsync-orangepi --env-file "$env_file" \
    -f "$board_dir/compose.yml" "$@"
}

require_env() {
  [[ -f "$env_file" ]] || {
    echo '请先运行：bash deploy/orangepi/board.sh init' >&2
    exit 1
  }
}

check_board() {
  [[ "$(uname -s)" == Linux ]] || { echo '请在板卡的 Linux 系统中运行。' >&2; exit 1; }
  case "$(uname -m)" in
    aarch64|arm64) ;;
    *) echo '需要 ARM64（aarch64）系统，请检查板卡镜像。' >&2; exit 1 ;;
  esac
  python3 -c 'import sys; sys.exit(sys.version_info < (3, 7))' || { echo '板端检查与验收需要 Python 3.7 或更新版本。' >&2; exit 1; }
  command -v docker >/dev/null || { echo '请先安装 Docker Engine 和 Compose v2。' >&2; exit 1; }
  local version architecture
  version="$(docker compose version --short)"
  if [[ ! "$version" =~ ^v?([0-9]+)\.([0-9]+) ]] || (( BASH_REMATCH[1] < 2 || (BASH_REMATCH[1] == 2 && BASH_REMATCH[2] < 20) )); then
    echo "需要 Docker Compose 2.20 或更新版本，当前版本为 $version。" >&2
    exit 1
  fi
  architecture="$(docker info --format '{{.Architecture}}')" || { echo '无法连接 Docker 引擎，请检查服务和当前用户权限。' >&2; exit 1; }
  case "$architecture" in
    aarch64|arm64) ;;
    *) echo 'Docker 引擎需要运行在 ARM64 板卡上。' >&2; exit 1 ;;
  esac
  if [[ -r /etc/os-release ]]; then
    cat /etc/os-release
  fi
  echo 'ARM64 / Docker 检查通过。'
}

web_port() {
  compose config --format json | python3 "$board_dir/check_config.py"
}

smoke() {
  local port
  port="$(web_port)"
  no_proxy="127.0.0.1,localhost,${no_proxy:-${NO_PROXY:-}}" \
    python3 "$board_dir/smoke.py" --base-url "http://127.0.0.1:$port" "$@"
  printf '局域网访问地址：http://<板卡IP>:%s/\n' "$port"
}

case "${1:-help}" in
  init)
    if [[ -e "$env_file" ]]; then
      echo '已保留现有 deploy/orangepi/.env（数据库密码未更改）。'
      exit 0
    fi
    if command -v docker >/dev/null && docker volume inspect yunsync-orangepi_postgres-data >/dev/null 2>&1; then
      echo '发现已有 PostgreSQL 数据卷，请从备份恢复 deploy/orangepi/.env 或填入原数据库密码后再启动。' >&2
      exit 1
    fi
    password="$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')"
    [[ ${#password} == 48 ]] || { echo '生成数据库密码失败。' >&2; exit 1; }
    temp_env="$(mktemp "$board_dir/.env.XXXXXX")"
    trap 'rm -f -- "$temp_env"' EXIT
    sed "s/^YUNSYNC_BOARD_DB_PASSWORD=.*/YUNSYNC_BOARD_DB_PASSWORD=$password/" \
      "$board_dir/.env.example" > "$temp_env"
    ln -- "$temp_env" "$env_file"
    echo '已生成 deploy/orangepi/.env；请随数据库备份保存此文件。'
    ;;
  check)
    check_board
    if [[ -f "$env_file" ]]; then web_port >/dev/null; fi
    ;;
  up)
    check_board
    require_env
    web_port >/dev/null
    compose up -d --build --wait --wait-timeout 240
    smoke --wait-seconds 60
    ;;
  smoke)
    require_env
    smoke "${@:2}"
    ;;
  status)
    require_env
    compose ps
    ;;
  logs)
    require_env
    compose logs --tail=100 "${@:2}"
    ;;
  stop)
    require_env
    compose stop
    ;;
  down)
    require_env
    compose down
    ;;
  help|-h|--help)
    echo '用法：bash deploy/orangepi/board.sh {init|check|up|smoke|status|logs [服务名]|stop|down}'
    echo '首次部署：init → up。up 构建并启动服务，随后验收页面与 API。'
    echo '重启或重建 API 后：smoke --wait-seconds 120'
    echo 'stop/down 均保留数据库卷；更新代码后再次执行 up。'
    ;;
  *)
    echo "未知命令：$1" >&2
    exit 2
    ;;
esac
