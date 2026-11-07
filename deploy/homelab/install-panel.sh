#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

BASE_URL="https://cdn.jsdelivr.net/gh/illa-j/unkre@main/deploy/homelab"
PANEL_DIR="$HOME/panel"
ENV_FILE="$HOME/.panel.env"
SVDIR="${PREFIX}/var/service"
TERMUX_PREFIX="${PREFIX}"
export SVDIR

termux-wake-lock 2>/dev/null || true
touch "$HOME/.wake-lock" 2>/dev/null || true

echo "[1/8] Installing Termux packages…"
pkg install -y python curl nginx >/dev/null 2>&1 || true

mkdir -p \
  "$PANEL_DIR" \
  "$TERMUX_PREFIX/etc/nginx" \
  "$TERMUX_PREFIX/var/lib/nginx/client_body" \
  "$TERMUX_PREFIX/var/lib/nginx/proxy" \
  "$TERMUX_PREFIX/var/lib/nginx/fastcgi" \
  "$TERMUX_PREFIX/var/lib/nginx/uwsgi" \
  "$TERMUX_PREFIX/var/lib/nginx/scgi" \
  "$TERMUX_PREFIX/var/log/nginx" \
  "$TERMUX_PREFIX/var/run" \
  "$TERMUX_PREFIX/share/nginx/html/unkre" \
  "$TERMUX_PREFIX/share/nginx/html/nocensgen" \
  "$TERMUX_PREFIX/var/log/sv/panel" \
  "$TERMUX_PREFIX/var/log/sv/nginx-unkre" \
  "$TERMUX_PREFIX/var/log/sv/nginx-nocensgen"

echo "[2/8] Downloading panel, nginx configs and helpers…"
curl -fsSL "$BASE_URL/panel.py" -o "$PANEL_DIR/panel.py"
curl -fsSL "$BASE_URL/nginx/nginx-termux-unkre.conf" -o "$TERMUX_PREFIX/etc/nginx/nginx-unkre.conf"
curl -fsSL "$BASE_URL/nginx/nginx-termux-nocensgen.conf" -o "$TERMUX_PREFIX/etc/nginx/nginx-nocensgen.conf"
curl -fsSL "$BASE_URL/nginx/404-unkre.html" -o "$TERMUX_PREFIX/share/nginx/html/unkre/404.html"
curl -fsSL "$BASE_URL/nginx/404-nocensgen.html" -o "$TERMUX_PREFIX/share/nginx/html/nocensgen/404.html"
curl -fsSL "$BASE_URL/stack-start.sh" -o "$HOME/stack-start.sh"
curl -fsSL "$BASE_URL/stack-stop.sh" -o "$HOME/stack-stop.sh"
curl -fsSL "$BASE_URL/patch-supervisor.py" -o "$HOME/patch-supervisor.py"
curl -fsSL "$BASE_URL/patch-stack-conf.py" -o "$HOME/patch-stack-conf.py"
chmod +x "$HOME/stack-start.sh" "$HOME/stack-stop.sh"

echo "[3/8] Writing configuration…"
if [ -z "${PC_AGENT_TOKEN:-}" ]; then
  read -r -p "PC agent token: " PC_AGENT_TOKEN </dev/tty
fi
if [ -z "${PC_AGENT_TOKEN:-}" ]; then
  echo "PC_AGENT_TOKEN is required" >&2
  exit 1
fi
if [ -f "$ENV_FILE" ] && [ -z "${PANEL_PASSWORD:-}" ]; then
  # shellcheck disable=SC1090
  . "$ENV_FILE"
fi
if [ -z "${PANEL_PASSWORD:-}" ]; then
  PANEL_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(9))')"
fi

cat > "$ENV_FILE" <<EOF
PANEL_USER=${PANEL_USER:-admin}
PANEL_PASSWORD=$PANEL_PASSWORD
PANEL_PORT=${PANEL_PORT:-8090}
PHONE_HOST=${PHONE_HOST:-192.168.1.5}
PC_HOST=${PC_HOST:-192.168.1.11}
PC_AGENT_URL=${PC_AGENT_URL:-http://192.168.1.11:8091}
PC_AGENT_TOKEN=$PC_AGENT_TOKEN
SVDIR=$SVDIR
LOG_BASE=${PREFIX}/var/log/sv
EOF
chmod 600 "$ENV_FILE"

echo "[4/8] Creating runit services…"
cat > "$SVDIR/panel/run" <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
export PATH="/data/data/com.termux/files/usr/bin:$PATH"
set -a
. /data/data/com.termux/files/home/.panel.env
set +a
exec /data/data/com.termux/files/usr/bin/python /data/data/com.termux/files/home/panel/panel.py 2>&1
EOF
cat > "$SVDIR/panel/log/run" <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
svlogger="/data/data/com.termux/files/usr/share/termux-services/svlogger"
exec "${svlogger}" "$@"
EOF
chmod +x "$SVDIR/panel/run" "$SVDIR/panel/log/run"

for name in nginx-unkre nginx-nocensgen; do
  mkdir -p "$SVDIR/$name/log"
  cat > "$SVDIR/$name/run" <<EOF
#!/data/data/com.termux/files/usr/bin/sh
exec /data/data/com.termux/files/usr/bin/nginx -c /data/data/com.termux/files/usr/etc/nginx/$name.conf 2>&1
EOF
  cat > "$SVDIR/$name/log/run" <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
svlogger="/data/data/com.termux/files/usr/share/termux-services/svlogger"
exec "${svlogger}" "$@"
EOF
  chmod +x "$SVDIR/$name/run" "$SVDIR/$name/log/run"
  rm -f "$SVDIR/$name/down"
done

rm -f "$SVDIR/sshd/down" 2>/dev/null || true
touch "$SVDIR/stack/down" 2>/dev/null || true

echo "[5/8] Starting runit services…"
if ! pgrep -x runsvdir >/dev/null 2>&1; then
  setsid runsvdir "$SVDIR" > "$HOME/runsvdir.log" 2>&1 < /dev/null &
  sleep 5
fi
for service in sshd postgres redis cloudflared panel nginx-unkre nginx-nocensgen; do
  sv up "$service" 2>/dev/null || true
done

echo "[6/8] Configuring the Debian proot stack…"
if command -v proot-distro >/dev/null 2>&1; then
  proot-distro login debian -- python3 /data/data/com.termux/files/home/patch-supervisor.py >/dev/null 2>&1 || true
  proot-distro login debian -- python3 /data/data/com.termux/files/home/patch-stack-conf.py >/dev/null 2>&1 || true
  bash "$HOME/stack-start.sh" || true
fi

echo "[7/8] Configuring autostart…"
python3 - <<'PY'
from pathlib import Path

path = Path.home() / ".bashrc"
marker = "# HOME_LAB_AUTOSTART"
block = """# HOME_LAB_AUTOSTART
termux-wake-lock 2>/dev/null && touch "$HOME/.wake-lock" || true
if ! pgrep -x runsvdir >/dev/null 2>&1; then
  setsid runsvdir "$PREFIX/var/service" >/dev/null 2>&1 &
fi
if ! pgrep -f 'supervisord -n -c /etc/supervisor/supervisord.conf' >/dev/null 2>&1; then
  ( sleep 5; bash "$HOME/stack-start.sh" >/dev/null 2>&1 ) &
fi
"""
text = path.read_text() if path.exists() else ""
if marker not in text:
    with path.open("a") as handle:
        handle.write(("\n" if text else "") + block)
PY

mkdir -p "$HOME/.termux/boot"
cat > "$HOME/.termux/boot/start-all.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock 2>/dev/null && touch "$HOME/.wake-lock" || true
sleep 5
pgrep -x runsvdir >/dev/null 2>&1 || setsid runsvdir "$PREFIX/var/service" >/dev/null 2>&1 &
sleep 5
bash "$HOME/stack-start.sh" >/dev/null 2>&1 || true
EOF
chmod +x "$HOME/.termux/boot/start-all.sh"

echo "[8/8] Checking…"
sleep 10
echo
echo "==============================================="
echo " Панель:  http://${PHONE_HOST:-192.168.1.5}:${PANEL_PORT:-8090}"
echo " Логін:   ${PANEL_USER:-admin}"
echo " Пароль:  $PANEL_PASSWORD"
echo "==============================================="
echo "panel:   $(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PANEL_PORT:-8090}/healthz" || true)"
echo "unkre:   $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18080/ || true)"
echo "nocens:  $(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18082/ || true)"
echo "Керування: sv status panel | sv restart panel | tail -f ${PREFIX}/var/log/sv/panel/current"
