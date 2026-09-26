#!/usr/bin/env bash
# =============================================================================
# AlgorithmLab · 算法设计与分析课程评审平台 —— 服务器一键部署脚本
#
# 适用：Ubuntu 22.04 / 24.04（已在阿里云 ECS Ubuntu 24.04、2 核 2G 上验证）
#
#   sudo bash deploy/install.sh               # 接管 80 端口根路径（默认）
#   sudo bash deploy/install.sh --no-nginx    # 只起服务，不改 nginx
#   sudo bash deploy/install.sh --port 9000   # 自定义内部端口
#
# 设计原则
#   * 幂等：重复执行不会重复建库、不会写重复配置
#   * 可回滚：改 nginx 前先备份；`nginx -t` 不通过就自动还原
#   * 不删数据：被接管的旧站点配置只做「移出 + 备份」，文件与进程都不动
#   * 自启动：注册 systemd 服务，服务器重启后自动拉起
# =============================================================================
set -euo pipefail

APP_DIR=/opt/algorithm-review-platform
REPO=${AJP_REPO:-https://github.com/kikolijia-debug/algorithm-review-platform.git}
SERVICE=algorithm-review-platform
PORT=8080
MANAGE_NGINX=1
STAMP=$(date +%Y%m%d%H%M%S)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)      PORT="$2"; shift 2 ;;
    --no-nginx)  MANAGE_NGINX=0; shift ;;
    --repo)      REPO="$2"; shift 2 ;;
    -h|--help)   sed -n '2,14p' "$0"; exit 0 ;;
    *)           echo "未知参数：$1"; exit 1 ;;
  esac
done

log()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m    [ok] %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m    [!!] %s\033[0m\n' "$*"; }

[[ $EUID -eq 0 ]] || { echo "请用 root 执行：sudo bash deploy/install.sh"; exit 1; }

# ---------------------------------------------------------------- 1. 依赖
log "检查系统依赖"
missing=()
for cmd in python3 git curl g++; do
  command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
done
if [[ ${#missing[@]} -gt 0 ]]; then
  warn "缺少：${missing[*]}，开始安装（自动评测需要 g++）"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq python3 git curl g++ >/dev/null
fi
ok "python3 $(python3 -V 2>&1 | awk '{print $2}')  |  g++ $(g++ -dumpversion)"

# ---------------------------------------------------------------- 2. 代码
log "获取代码到 $APP_DIR"
if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch --quiet origin
  git -C "$APP_DIR" checkout --quiet main
  git -C "$APP_DIR" reset --hard --quiet origin/main
  ok "已更新到 $(git -C "$APP_DIR" rev-parse --short HEAD)"
else
  mkdir -p "$(dirname "$APP_DIR")"
  git clone --quiet "$REPO" "$APP_DIR"
  ok "已克隆 $(git -C "$APP_DIR" rev-parse --short HEAD)"
fi
mkdir -p "$APP_DIR/backend/data"

# ---------------------------------------------------------------- 3. 服务
log "注册 systemd 服务（$SERVICE，内部端口 $PORT）"
cat > "/etc/systemd/system/${SERVICE}.service" <<EOF
[Unit]
Description=AlgorithmLab · 算法设计与分析课程评审平台
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONIOENCODING=utf-8
ExecStart=/usr/bin/python3 ${APP_DIR}/run.py 127.0.0.1 ${PORT}
Restart=always
RestartSec=3
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --quiet "$SERVICE"
systemctl restart "$SERVICE"

log "等待服务就绪（首次启动会自动生成演示数据）"
ready=0
for _ in $(seq 1 60); do
  if curl -fsS --max-time 2 "http://127.0.0.1:${PORT}/api/health" >/dev/null 2>&1; then
    ready=1; break
  fi
  sleep 1
done
if [[ $ready -eq 1 ]]; then
  ok "服务已就绪：http://127.0.0.1:${PORT}"
else
  warn "服务未在 60 秒内就绪，最近日志："
  journalctl -u "$SERVICE" -n 30 --no-pager || true
  exit 1
fi

# ---------------------------------------------------------------- 4. nginx
if [[ $MANAGE_NGINX -eq 1 ]]; then
  log "把 80 端口根路径交给本平台"
  if ! command -v nginx >/dev/null 2>&1; then
    warn "未检测到 nginx，跳过。服务仍可通过 127.0.0.1:${PORT} 访问"
  else
    mkdir -p /etc/nginx/sites-available
    # 把现有的 default_server 站点移出启用目录（只移动 + 备份，不删除）
    for f in /etc/nginx/sites-enabled/*; do
      [[ -e "$f" ]] || continue
      if grep -qs 'listen 80 default_server' "$f"; then
        mv "$f" "/etc/nginx/sites-available/$(basename "$f").disabled-${STAMP}"
        ok "已停用旧站点 $(basename "$f")（配置备份在 sites-available）"
      fi
    done
    for f in /etc/nginx/conf.d/*.conf; do
      [[ -e "$f" ]] || continue
      if grep -qs 'listen 80 default_server' "$f"; then
        mv "$f" "/etc/nginx/conf.d/$(basename "$f").disabled-${STAMP}"
        ok "已停用旧站点配置 $(basename "$f")"
      fi
    done

    cat > /etc/nginx/sites-available/algorithm-review-platform <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    # 学生代码最大 1 MB，留足余地
    client_max_body_size 20m;

    access_log /var/log/nginx/algorithm-review.access.log;
    error_log  /var/log/nginx/algorithm-review.error.log;

    location / {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Connection "";
        proxy_buffering off;
        # 复杂度实测、批量重测可能跑几十秒到两分钟，超时放宽
        proxy_read_timeout 600s;
        proxy_send_timeout 600s;
    }
}
EOF
    ln -sfn /etc/nginx/sites-available/algorithm-review-platform /etc/nginx/sites-enabled/algorithm-review-platform

    if nginx -t >/dev/null 2>&1; then
      systemctl reload nginx
      ok "nginx 配置校验通过并已重载"
    else
      warn "nginx -t 未通过，正在回滚："
      nginx -t || true
      rm -f /etc/nginx/sites-enabled/algorithm-review-platform
      for f in /etc/nginx/sites-available/*.disabled-${STAMP}; do
        [[ -e "$f" ]] || continue
        base=$(basename "$f")
        target="/etc/nginx/sites-enabled/${base%.disabled-${STAMP}}"
        mv "$f" "$target"
        warn "已恢复 $target"
      done
      systemctl reload nginx || true
      exit 1
    fi
  fi
fi

# ---------------------------------------------------------------- 5. 验证
log "部署完成，开始验证"
PUBLIC_IP=$(curl -s --max-time 6 https://api.ipify.org 2>/dev/null || true)
[[ -n "$PUBLIC_IP" ]] || PUBLIC_IP="<服务器公网IP>"
if [[ $MANAGE_NGINX -eq 1 ]]; then URL="http://${PUBLIC_IP}/"; else URL="http://${PUBLIC_IP}:${PORT}/"; fi

printf '    health : '
curl -fsS --max-time 8 "http://127.0.0.1:${PORT}/api/health" | head -c 200; echo
printf '    首页   : HTTP '
curl -s -o /dev/null -w '%{http_code}\n' --max-time 8 "http://127.0.0.1:${PORT}/"

cat <<EOF

$(printf '\033[1;32m  ✔ 部署完成\033[0m')

    访问地址 ： ${URL}
    演示账号 ： teacher / 123456   （教师）
               stu1    / 123456   （学生）

    服务管理 ： systemctl status  ${SERVICE}
               systemctl restart ${SERVICE}
               journalctl -u ${SERVICE} -f

    代码目录 ： ${APP_DIR}
    数据文件 ： ${APP_DIR}/backend/data/platform.db
    重新部署 ： cd ${APP_DIR} && git pull && systemctl restart ${SERVICE}

    恢复旧站点 ： mv /etc/nginx/sites-available/*.disabled-${STAMP} \\
                     /etc/nginx/sites-enabled/  &&  systemctl reload nginx
EOF
