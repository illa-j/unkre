#!/usr/bin/env bash
set -euo pipefail

DIR="$HOME/.local/share/homelab"
BASE_URL="https://cdn.jsdelivr.net/gh/illa-j/unkre@main/deploy/homelab"

mkdir -p "$DIR" "$HOME/.config/systemd/user"
curl -fsSL "$BASE_URL/agent.py" -o "$DIR/agent.py"

if [ ! -x "$DIR/.venv/bin/uvicorn" ]; then
  if ! command -v uv >/dev/null 2>&1; then
    echo "uv is required (https://docs.astral.sh/uv/)" >&2
    exit 1
  fi
  uv venv "$DIR/.venv"
  uv pip install --python "$DIR/.venv/bin/python" fastapi uvicorn
fi

if [ -z "${AGENT_TOKEN:-}" ]; then
  AGENT_TOKEN="$(openssl rand -hex 24)"
fi
cat > "$DIR/agent.env" <<EOF
AGENT_TOKEN=$AGENT_TOKEN
EOF
chmod 600 "$DIR/agent.env"

cat > "$HOME/.config/systemd/user/homelab-agent.service" <<EOF
[Unit]
Description=Home Lab PC Agent
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$DIR
EnvironmentFile=$DIR/agent.env
ExecStart=$DIR/.venv/bin/uvicorn agent:app --host 0.0.0.0 --port 8091
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now homelab-agent.service
loginctl enable-linger "$USER" 2>/dev/null || true
sleep 2

echo "==============================================="
echo " Agent: http://$(hostname -I | awk '{print $1}'):8091"
echo " Token: $AGENT_TOKEN"
echo " Status: $(systemctl --user is-active homelab-agent.service)"
echo "==============================================="
