#!/data/data/com.termux/files/usr/bin/bash
export PATH="$PREFIX/bin:$HOME/bin:$PATH"

LOCK="$HOME/.stack-start.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null || true' EXIT

if pgrep -f 'supervisord -n -c /etc/supervisor/supervisord.conf' >/dev/null 2>&1; then
  exit 0
fi

setsid proot-distro login debian -- bash -lc \
  'exec supervisord -n -c /etc/supervisor/supervisord.conf' \
  > "$HOME/stack.log" 2>&1 < /dev/null &
sleep 3
