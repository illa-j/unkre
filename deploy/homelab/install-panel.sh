#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

BASE_URL="https://raw.githubusercontent.com/illa-j/unkre/main/deploy/homelab"
PANEL_DIR="$HOME/panel"
ENV_FILE="$HOME/.panel.env"
SVDIR="${PREFIX}/var/service"

if ! command -v python >/dev/null 2>&1; then
  pkg install -y python
fi
if ! command -v curl >/dev/null 2>&1; then
  pkg install -y curl
fi

echo "[1/6] Installing Python dependencies…"
python -m pip install --quiet --upgrade flask waitress

echo "[2/6] Downloading panel…"
mkdir -p "$PANEL_DIR"
curl -fsSL "$BASE_URL/panel.py" -o "$PANEL_DIR/panel.py"

echo "[3/6] Writing configuration…"
if [ -z "${PC_AGENT_TOKEN:-}" ]; then
  read -r -p "PC agent token: " PC_AGENT_TOKEN </dev/tty
fi
if [ -z "${PC_AGENT_TOKEN:-}" ]; then
  echo "PC_AGENT_TOKEN is required" >&2
  exit 1
fi

if [ -f "$ENV_FILE" ] && [ -z "${PANEL_PASSWORD:-}" ]; then
  # Keep the existing password on reinstall.
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

echo "[4/6] Creating runit service…"
mkdir -p "$SVDIR/panel/log" "${PREFIX}/var/log/sv/panel"
cat > "$SVDIR/panel/run" <<'EOF'
#!/data/data/com.termux/files/usr/bin/sh
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

echo "[5/6] Starting runit and the panel…"
if ! pgrep -x runsvdir >/dev/null 2>&1; then
  setsid runsvdir "$SVDIR" > "$HOME/runsvdir.log" 2>&1 < /dev/null &
  sleep 5
fi
for service in sshd postgres redis cloudflared stack panel; do
  sv up "$service" 2>/dev/null || true
done
sleep 3

mkdir -p "$HOME/.termux/boot"
cat > "$HOME/.termux/boot/start-all.sh" <<'EOF'
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock 2>/dev/null || true
sleep 5
pgrep -x runsvdir >/dev/null 2>&1 || setsid runsvdir "$PREFIX/var/service" >/dev/null 2>&1 &
EOF
chmod +x "$HOME/.termux/boot/start-all.sh"

echo "[6/6] Exposing admin panels to the LAN…"
if command -v proot-distro >/dev/null 2>&1; then
  proot-distro login debian -- bash -lc \
    "sed -i 's/listen 127.0.0.1:18081;/listen 18081;/' /etc/nginx/unkre.conf; \
     sed -i 's/listen 127.0.0.1:18083;/listen 18083;/' /etc/nginx/nocensgen.conf; \
     nginx -t -c /etc/nginx/unkre.conf >/dev/null 2>&1; \
     nginx -t -c /etc/nginx/nocensgen.conf >/dev/null 2>&1" || true
  sv restart stack 2>/dev/null || true
  sleep 5
fi

echo
echo "==============================================="
echo " Панель:  http://${PHONE_HOST:-192.168.1.5}:${PANEL_PORT:-8090}"
echo " Логін:   ${PANEL_USER:-admin}"
echo " Пароль:  $PANEL_PASSWORD"
echo "==============================================="
echo
echo "Перевірка: $(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PANEL_PORT:-8090}/healthz" || true)"
echo "Керування: sv status panel | sv restart panel | tail -f ${PREFIX}/var/log/sv/panel/current"
