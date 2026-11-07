import base64
import hashlib
import hmac
import html
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PANEL_USER = os.environ.get("PANEL_USER", "admin")
PANEL_PASSWORD = os.environ.get("PANEL_PASSWORD", "")
PANEL_PORT = int(os.environ.get("PANEL_PORT", "8090"))
PHONE_HOST = os.environ.get("PHONE_HOST", "192.168.1.5")
PC_HOST = os.environ.get("PC_HOST", "192.168.1.11")
PC_AGENT_URL = os.environ.get("PC_AGENT_URL", f"http://{PC_HOST}:8091").rstrip("/")
PC_AGENT_TOKEN = os.environ.get("PC_AGENT_TOKEN", "")
SVDIR = os.environ.get(
    "SVDIR",
    str(Path(os.environ.get("PREFIX", "/data/data/com.termux/files/usr")) / "var/service"),
)
LOG_BASE = os.environ.get(
    "LOG_BASE",
    str(Path(os.environ.get("PREFIX", "/data/data/com.termux/files/usr")) / "var/log/sv"),
)
SESSION_SECRET = os.environ.get("PANEL_SECRET") or hashlib.sha256(
    f"homelab:{PANEL_PASSWORD}".encode()
).hexdigest()
SESSION_MAX_AGE = 7 * 24 * 3600

PHONE_SERVICES = [
    {"id": "sshd", "name": "SSH", "controllable": True},
    {"id": "postgres", "name": "PostgreSQL", "controllable": True},
    {"id": "redis", "name": "Redis", "controllable": True},
    {"id": "cloudflared", "name": "Cloudflare Tunnel", "controllable": True},
    {"id": "stack", "name": "UNKRE + NoCensGen", "controllable": True},
    {"id": "panel", "name": "Панель", "controllable": False},
]


def run(cmd: list[str], timeout: int = 10, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, **(env or {})},
    )


def phone_status(service: dict) -> dict:
    try:
        result = run(["sv", "status", service["id"]], env={"SVDIR": SVDIR})
        text = (result.stdout + result.stderr).strip()
    except Exception as exc:  # noqa: BLE001
        return {**service, "state": "unknown", "detail": f"sv unavailable: {exc}"}
    state = "unknown"
    if "run:" in text and "down:" not in text:
        state = "running"
    elif "down:" in text:
        state = "stopped"
    elif "fail:" in text:
        state = "failed"
    return {**service, "state": state, "detail": text}


def phone_action(service_id: str, action: str) -> dict:
    allowed = {"up", "down", "restart"}
    ids = {item["id"] for item in PHONE_SERVICES if item["controllable"]}
    if service_id not in ids:
        return {"ok": False, "output": "unknown service"}
    if action not in allowed:
        return {"ok": False, "output": "bad action"}
    try:
        result = run(["sv", action, service_id], timeout=30, env={"SVDIR": SVDIR})
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "output": f"{type(exc).__name__}: {exc}"}
    return {
        "ok": result.returncode == 0,
        "output": (result.stdout + result.stderr).strip(),
    }


def agent_request(path: str, method: str = "GET") -> tuple[bool, dict | str]:
    if not PC_AGENT_TOKEN:
        return False, "PC_AGENT_TOKEN is not set"
    request_obj = urllib.request.Request(
        f"{PC_AGENT_URL}{path}",
        method=method,
        headers={"X-Agent-Token": PC_AGENT_TOKEN},
    )
    try:
        with urllib.request.urlopen(request_obj, timeout=8) as response:
            body = response.read().decode("utf-8", "replace")
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                return True, json.loads(body)
            return True, body
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:500]}"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def probe(url: str) -> bool:
    try:
        host = url.split("//", 1)[1].split("/", 1)[0]
        if ":" in host:
            hostname, port_text = host.rsplit(":", 1)
            port = int(port_text)
        else:
            hostname = host
            port = 443 if url.startswith("https://") else 80
        with socket.create_connection((hostname, port), timeout=0.5):
            return True
    except Exception:  # noqa: BLE001
        return False


def build_links() -> list[dict]:
    links = [
        ("Телефон", "UNKRE", f"http://{PHONE_HOST}:18080"),
        ("Телефон", "NoCensGen", f"http://{PHONE_HOST}:18082"),
        ("Телефон", "UNKRE admin", f"http://{PHONE_HOST}:18081"),
        ("Телефон", "NoCensGen admin", f"http://{PHONE_HOST}:18083"),
        ("Телефон", "MinIO Console", f"http://{PHONE_HOST}:9001"),
        ("Телефон", "Ця панель", f"http://{PHONE_HOST}:8090"),
        ("ПК", "UNKRE", f"http://{PC_HOST}:18080"),
        ("ПК", "NoCensGen", f"http://{PC_HOST}:18082"),
        ("ПК", "UNKRE admin", f"http://{PC_HOST}:18081"),
        ("ПК", "NoCensGen admin", f"http://{PC_HOST}:18083"),
        ("ПК", "WYNC", f"http://{PC_HOST}:8089"),
        ("ПК", "WYNC HTTPS", f"https://{PC_HOST}:4443"),
        ("ПК", "Persk", f"http://{PC_HOST}/"),
        ("ПК", "Persk admin", f"http://{PC_HOST}:8010"),
        ("ПК", "Wildfield", f"http://{PC_HOST}:8088"),
        ("ПК", "Wildfield admin", f"http://{PC_HOST}:8018"),
    ]
    with ThreadPoolExecutor(max_workers=16) as pool:
        online = list(pool.map(lambda item: probe(item[2]), links))
    return [
        {"group": group, "name": name, "url": url, "online": is_online}
        for (group, name, url), is_online in zip(links, online)
    ]


def overview() -> dict:
    phone = [phone_status(service) for service in PHONE_SERVICES]
    pc_ok, pc_data = agent_request("/api/status")
    containers = pc_data.get("containers", []) if pc_ok and isinstance(pc_data, dict) else []
    return {
        "phone": phone,
        "pc_ok": pc_ok,
        "pc_error": "" if pc_ok else str(pc_data),
        "pc": containers,
        "links": build_links(),
    }


def make_session(username: str) -> str:
    payload = f"{username}:{int(time.time())}"
    signature = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}:{signature}".encode()).decode()


def valid_session(token: str | None) -> bool:
    if not token:
        return False
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        username, timestamp, signature = raw.rsplit(":", 2)
        payload = f"{username}:{timestamp}"
        expected = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return False
        if time.time() - int(timestamp) > SESSION_MAX_AGE:
            return False
        return hmac.compare_digest(username, PANEL_USER)
    except Exception:  # noqa: BLE001
        return False


def get_session(handler: BaseHTTPRequestHandler) -> str | None:
    cookie = SimpleCookie(handler.headers.get("Cookie", ""))
    morsel = cookie.get("panel_session")
    return morsel.value if morsel else None


def login_page(error: str = "") -> str:
    error_html = f'<div class="error">{html.escape(error)}</div>' if error else ""
    return f"""<!doctype html>
<html lang="uk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Home Lab · Вхід</title>
<style>
  :root {{ --bg:#0b0e14; --panel:#131823; --border:#263044; --text:#e8eefc; --muted:#8b98b3; --red:#f87171; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; min-height:100vh; display:grid; place-items:center; padding:20px;
    font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; color:var(--text);
    background:radial-gradient(900px 500px at 15% -10%, #1b2a4a 0%, transparent 55%),
               radial-gradient(700px 400px at 100% 0%, #2a1b3d 0%, transparent 50%), var(--bg); }}
  .card {{ width:min(380px,100%); background:linear-gradient(180deg,rgba(26,33,48,.96),rgba(19,24,35,.98));
    border:1px solid var(--border); border-radius:20px; padding:28px; box-shadow:0 24px 70px rgba(0,0,0,.35); }}
  h1 {{ margin:0; font-size:30px; letter-spacing:-.04em; }}
  .sub {{ color:var(--muted); font-size:13px; margin:6px 0 22px; }}
  label {{ display:block; font-size:12px; color:var(--muted); margin-bottom:12px; }}
  input {{ width:100%; margin-top:6px; padding:12px 13px; border-radius:11px; border:1px solid var(--border);
    background:#0e131c; color:var(--text); font:inherit; outline:none; }}
  input:focus {{ border-color:#3b82f6; box-shadow:0 0 0 3px rgba(59,130,246,.16); }}
  button {{ width:100%; margin-top:4px; padding:12px; border-radius:11px; border:1px solid #2563eb;
    background:#1d4ed8; color:#fff; font:inherit; font-weight:600; cursor:pointer; }}
  button:hover {{ background:#2563eb; }}
  .error {{ background:#2a1218; border:1px solid #7f1d1d; color:#fecaca; border-radius:10px;
    padding:10px 12px; font-size:13px; margin-bottom:14px; }}
  .hint {{ color:var(--muted); font-size:11px; margin-top:14px; text-align:center; }}
</style>
</head>
<body>
<main class="card">
  <h1>HOME LAB</h1>
  <div class="sub">Вхід до панелі керування</div>
  {error_html}
  <form method="post" action="/login">
    <label>Логін<input name="username" autocomplete="username" autofocus required></label>
    <label>Пароль<input name="password" type="password" autocomplete="current-password" required></label>
    <button type="submit">Увійти</button>
  </form>
  <div class="hint">Телефон · ПК · Docker</div>
</main>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "HomeLabPanel/1.0"

    def log_message(self, fmt: str, *args) -> None:
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)

    def _send(self, body: str | bytes, status: int = 200, content_type: str = "text/plain; charset=utf-8") -> None:
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, payload: dict, status: int = 200) -> None:
        self._send(json.dumps(payload, ensure_ascii=False), status, "application/json; charset=utf-8")

    def _redirect(self, location: str, cookie: str | None = None) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _authorized(self) -> bool:
        return valid_session(get_session(self))

    def _deny(self, api: bool) -> None:
        if api:
            self._json({"ok": False, "error": "unauthorized"}, 401)
        else:
            self._redirect("/login")

    def do_GET(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if path == "/healthz":
            self._json({"ok": True, "service": "homelab-panel"})
            return
        if path == "/login":
            if self._authorized():
                self._redirect("/")
            else:
                self._send(login_page(), 200, "text/html; charset=utf-8")
            return
        if path == "/logout":
            self._redirect(
                "/login",
                "panel_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax",
            )
            return
        if not self._authorized():
            self._deny(path.startswith("/api/"))
            return
        if path == "/":
            self._send(INDEX_HTML, 200, "text/html; charset=utf-8")
        elif path == "/api/overview":
            self._json(overview())
        elif path.startswith("/api/phone/") and path.endswith("/logs"):
            service_id = urllib.parse.unquote(path.split("/")[3])
            if service_id not in {item["id"] for item in PHONE_SERVICES}:
                self._send("unknown service", 404)
                return
            log_path = Path(LOG_BASE) / service_id / "current"
            if not log_path.exists():
                self._send(f"log file not found: {log_path}")
                return
            result = run(["tail", "-n", "150", str(log_path)])
            self._send((result.stdout + result.stderr).strip() or "(empty log)")
        elif path.startswith("/api/pc/") and path.endswith("/logs"):
            name = urllib.parse.unquote(path.split("/")[3])
            ok, data = agent_request(f"/api/containers/{name}/logs")
            self._send(str(data) if ok else f"agent error: {data}", 200 if ok else 502)
        else:
            self._send("not found", 404)

    def do_POST(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if path == "/login":
            length = int(self.headers.get("Content-Length", "0") or 0)
            body = self.rfile.read(length).decode("utf-8", "replace")
            form = urllib.parse.parse_qs(body)
            username = form.get("username", [""])[0]
            password = form.get("password", [""])[0]
            if hmac.compare_digest(username, PANEL_USER) and hmac.compare_digest(
                password, PANEL_PASSWORD
            ):
                cookie = (
                    f"panel_session={make_session(PANEL_USER)}; Path=/; "
                    f"Max-Age={SESSION_MAX_AGE}; HttpOnly; SameSite=Lax"
                )
                self._redirect("/", cookie)
            else:
                self._send(login_page("Невірний логін або пароль"), 401, "text/html; charset=utf-8")
            return
        if not self._authorized():
            self._deny(True)
            return
        if self.headers.get("X-Panel") != "1":
            self._json({"ok": False, "output": "missing panel header"}, 403)
            return
        parts = [urllib.parse.unquote(part) for part in path.strip("/").split("/")]
        if len(parts) == 4 and parts[0] == "api" and parts[1] == "phone":
            _, _, service_id, action = parts
            self._json(phone_action(service_id, action))
        elif len(parts) == 4 and parts[0] == "api" and parts[1] == "pc":
            _, _, name, action = parts
            if action not in {"start", "stop", "restart"}:
                self._json({"ok": False, "output": "bad action"}, 400)
                return
            ok, data = agent_request(f"/api/containers/{name}/{action}", method="POST")
            self._json(data if ok and isinstance(data, dict) else {"ok": ok, "output": str(data)}, 200 if ok else 502)
        else:
            self._send("not found", 404)


INDEX_HTML = r"""<!doctype html>
<html lang="uk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Home Lab</title>
<style>
  :root {
    --bg: #0b0e14;
    --panel: #131823;
    --panel-2: #1a2130;
    --border: #263044;
    --text: #e8eefc;
    --muted: #8b98b3;
    --green: #34d399;
    --red: #f87171;
    --amber: #fbbf24;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    min-height: 100vh;
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
    background:
      radial-gradient(1200px 600px at 10% -10%, #1b2a4a 0%, transparent 55%),
      radial-gradient(900px 500px at 100% 0%, #2a1b3d 0%, transparent 50%),
      var(--bg);
    color: var(--text);
  }
  .wrap { max-width: 1240px; margin: 0 auto; padding: 28px 18px 60px; }
  header { display: flex; flex-wrap: wrap; gap: 18px; align-items: flex-end; justify-content: space-between; margin-bottom: 22px; }
  h1 { margin: 0; font-size: clamp(28px, 5vw, 44px); letter-spacing: -0.04em; }
  .sub { color: var(--muted); margin-top: 6px; font-size: 14px; }
  .header-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  .chip { display: inline-flex; align-items: center; gap: 8px; padding: 8px 12px; border: 1px solid var(--border); border-radius: 999px; background: rgba(19,24,35,.75); color: var(--muted); font-size: 13px; }
  .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--muted); box-shadow: 0 0 0 3px rgba(139,152,179,.12); }
  .dot.green { background: var(--green); box-shadow: 0 0 0 3px rgba(52,211,153,.14); }
  .dot.red { background: var(--red); box-shadow: 0 0 0 3px rgba(248,113,113,.14); }
  .dot.amber { background: var(--amber); box-shadow: 0 0 0 3px rgba(251,191,36,.14); }
  button { font: inherit; cursor: pointer; border: 1px solid var(--border); background: var(--panel-2); color: var(--text); padding: 8px 12px; border-radius: 10px; transition: .15s; }
  button:hover { border-color: #3d4c68; background: #222b3d; }
  button.primary { background: #1d4ed8; border-color: #2563eb; }
  button.primary:hover { background: #2563eb; }
  button.ghost { background: transparent; }
  button:disabled { opacity: .45; cursor: not-allowed; }
  section { margin-top: 26px; }
  h2 { font-size: 15px; text-transform: uppercase; letter-spacing: .14em; color: var(--muted); margin: 0 0 12px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }
  .card { background: linear-gradient(180deg, rgba(26,33,48,.95), rgba(19,24,35,.95)); border: 1px solid var(--border); border-radius: 16px; padding: 16px; box-shadow: 0 16px 40px rgba(0,0,0,.18); }
  .card-top { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
  .name { font-weight: 700; letter-spacing: -.01em; }
  .state { font-size: 12px; color: var(--muted); margin-top: 4px; word-break: break-word; }
  .actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
  .actions button { padding: 7px 10px; font-size: 13px; }
  .links { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 10px; }
  a.link { display: flex; align-items: center; justify-content: space-between; gap: 10px; text-decoration: none; color: var(--text); background: var(--panel); border: 1px solid var(--border); border-radius: 14px; padding: 13px 14px; transition: .15s; }
  a.link:hover { border-color: #3d4c68; transform: translateY(-1px); }
  a.chip { text-decoration: none; color: var(--muted); transition: .15s; }
  a.chip:hover { color: var(--text); border-color: #3d4c68; }
  a.link .meta { display: flex; flex-direction: column; gap: 2px; }
  a.link small { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .1em; }
  .table { width: 100%; border-collapse: collapse; overflow: hidden; border-radius: 14px; border: 1px solid var(--border); }
  .table th, .table td { text-align: left; padding: 11px 12px; border-bottom: 1px solid var(--border); vertical-align: top; font-size: 13px; }
  .table th { color: var(--muted); font-weight: 600; background: var(--panel); }
  .table tr:last-child td { border-bottom: 0; }
  .table td.actions-cell { min-width: 190px; }
  .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; color: var(--muted); }
  .modal { position: fixed; inset: 0; background: rgba(4,7,12,.72); display: none; align-items: center; justify-content: center; padding: 18px; z-index: 50; }
  .modal.open { display: flex; }
  .modal-body { width: min(950px, 100%); max-height: 82vh; overflow: auto; background: #0e131c; border: 1px solid var(--border); border-radius: 16px; padding: 18px; }
  .modal-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
  pre { margin: 0; white-space: pre-wrap; word-break: break-word; font-size: 12px; line-height: 1.55; color: #c9d5ee; }
  .toast { position: fixed; right: 18px; bottom: 18px; max-width: min(420px, calc(100vw - 36px)); background: #1b2333; border: 1px solid var(--border); border-radius: 12px; padding: 12px 14px; color: var(--text); box-shadow: 0 18px 50px rgba(0,0,0,.35); opacity: 0; transform: translateY(8px); transition: .2s; pointer-events: none; z-index: 60; }
  .toast.show { opacity: 1; transform: translateY(0); }
  .empty { color: var(--muted); font-size: 13px; padding: 12px 0; }
  @media (max-width: 640px) {
    .table { display: block; overflow-x: auto; }
    .table th, .table td { white-space: nowrap; }
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1>HOME LAB</h1>
      <div class="sub">Керування телефоном і ПК · <span id="updated">—</span></div>
    </div>
    <div class="header-actions">
      <span class="chip"><span id="phone-dot" class="dot"></span><span id="phone-summary">Телефон</span></span>
      <span class="chip"><span id="pc-dot" class="dot"></span><span id="pc-summary">ПК</span></span>
      <button id="refresh" class="primary">Оновити</button>
      <a class="chip" href="/logout">Вийти</a>
    </div>
  </header>

  <section>
    <h2>Телефон · runit</h2>
    <div id="phone-grid" class="grid"></div>
  </section>

  <section>
    <h2>ПК · Docker</h2>
    <div id="pc-wrap"></div>
  </section>

  <section>
    <h2>Посилання</h2>
    <div id="links" class="links"></div>
  </section>
</div>

<div id="modal" class="modal">
  <div class="modal-body">
    <div class="modal-head">
      <div class="name" id="modal-title">Логи</div>
      <button id="modal-close" class="ghost">Закрити</button>
    </div>
    <pre id="modal-text">Завантаження…</pre>
  </div>
</div>
<div id="toast" class="toast"></div>

<script>
const $ = (id) => document.getElementById(id);
let busy = false;

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
}

function stateClass(state) {
  if (state === 'running' || state === 'Up' || state === 'up') return 'green';
  if (state === 'failed' || state === 'unknown') return 'amber';
  return 'red';
}

function toast(message, isError = false) {
  const el = $('toast');
  el.textContent = message;
  el.style.borderColor = isError ? '#7f1d1d' : '#263044';
  el.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove('show'), 3500);
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response;
}

function renderPhone(items) {
  $('phone-grid').innerHTML = items.map((item) => `
    <div class="card">
      <div class="card-top">
        <div>
          <div class="name">${esc(item.name)}</div>
          <div class="state">${esc(item.detail || item.state)}</div>
        </div>
        <span class="dot ${stateClass(item.state)}"></span>
      </div>
      <div class="actions">
        ${item.controllable ? `
          <button data-kind="phone" data-id="${esc(item.id)}" data-action="up" ${item.state === 'running' ? 'disabled' : ''}>Увімкнути</button>
          <button data-kind="phone" data-id="${esc(item.id)}" data-action="restart">Перезапустити</button>
          <button data-kind="phone" data-id="${esc(item.id)}" data-action="down" ${item.state !== 'running' ? 'disabled' : ''}>Вимкнути</button>
        ` : ''}
        <button data-logs="phone" data-id="${esc(item.id)}" class="ghost">Логи</button>
      </div>
    </div>
  `).join('');
}

function renderPC(ok, error, items) {
  if (!ok) {
    $('pc-wrap').innerHTML = `<div class="empty">Агент ПК недоступний: ${esc(error)}</div>`;
    return;
  }
  if (!items.length) {
    $('pc-wrap').innerHTML = '<div class="empty">Контейнерів не знайдено.</div>';
    return;
  }
  $('pc-wrap').innerHTML = `
    <table class="table">
      <thead><tr><th>Контейнер</th><th>Стан</th><th>Порти</th><th>Дії</th></tr></thead>
      <tbody>
      ${items.map((item) => {
        const running = item.state === 'running';
        return `<tr>
          <td><div class="name">${esc(item.name)}</div><div class="mono">${esc(item.image)}</div></td>
          <td><span class="chip"><span class="dot ${running ? 'green' : 'red'}"></span>${esc(item.status || item.state)}</span>${item.health ? `<div class="mono">health: ${esc(item.health)}</div>` : ''}</td>
          <td class="mono">${esc(item.ports || '—')}</td>
          <td class="actions-cell">
            <div class="actions">
              <button data-kind="pc" data-id="${esc(item.name)}" data-action="start" ${running ? 'disabled' : ''}>Старт</button>
              <button data-kind="pc" data-id="${esc(item.name)}" data-action="restart" ${running ? '' : 'disabled'}>Рестарт</button>
              <button data-kind="pc" data-id="${esc(item.name)}" data-action="stop" ${running ? '' : 'disabled'}>Стоп</button>
              <button data-logs="pc" data-id="${esc(item.name)}" class="ghost">Логи</button>
            </div>
          </td>
        </tr>`;
      }).join('')}
      </tbody>
    </table>`;
}

function renderLinks(items) {
  $('links').innerHTML = items.map((item) => `
    <a class="link" href="${esc(item.url)}" target="_blank" rel="noreferrer">
      <span class="meta"><small>${esc(item.group)}</small><span>${esc(item.name)}</span></span>
      <span class="dot ${item.online ? 'green' : 'red'}"></span>
    </a>
  `).join('');
}

function updateSummaries(data) {
  const phoneRunning = data.phone.filter((item) => item.state === 'running').length;
  const pcRunning = data.pc.filter((item) => item.state === 'running').length;
  $('phone-summary').textContent = `Телефон ${phoneRunning}/${data.phone.length}`;
  $('phone-dot').className = `dot ${phoneRunning === data.phone.length ? 'green' : (phoneRunning ? 'amber' : 'red')}`;
  if (data.pc_ok) {
    $('pc-summary').textContent = `ПК ${pcRunning}/${data.pc.length}`;
    $('pc-dot').className = `dot ${pcRunning === data.pc.length ? 'green' : (pcRunning ? 'amber' : 'red')}`;
  } else {
    $('pc-summary').textContent = 'ПК offline';
    $('pc-dot').className = 'dot red';
  }
  $('updated').textContent = new Date().toLocaleTimeString('uk-UA');
}

async function refresh() {
  if (busy) return;
  busy = true;
  try {
    const data = await (await api('/api/overview')).json();
    renderPhone(data.phone || []);
    renderPC(data.pc_ok, data.pc_error, data.pc || []);
    renderLinks(data.links || []);
    updateSummaries(data);
  } catch (error) {
    toast(`Помилка: ${error.message}`, true);
  } finally {
    busy = false;
  }
}

async function doAction(kind, id, action) {
  const label = `${action} ${id}`;
  try {
    const response = await api(`/api/${kind}/${encodeURIComponent(id)}/${action}`, {
      method: 'POST',
      headers: { 'X-Panel': '1' }
    });
    const data = await response.json().catch(() => ({}));
    toast(data.ok === false ? `${label}: ${data.output || 'помилка'}` : `${label}: ok`, data.ok === false);
    await refresh();
  } catch (error) {
    toast(`${label}: ${error.message}`, true);
  }
}

async function showLogs(kind, id) {
  $('modal').classList.add('open');
  $('modal-title').textContent = `${kind === 'phone' ? 'Телефон' : 'ПК'} · ${id}`;
  $('modal-text').textContent = 'Завантаження…';
  try {
    const response = await api(`/api/${kind}/${encodeURIComponent(id)}/logs`);
    $('modal-text').textContent = await response.text();
  } catch (error) {
    $('modal-text').textContent = `Помилка: ${error.message}`;
  }
}

document.addEventListener('click', (event) => {
  const button = event.target.closest('button');
  if (!button || button.disabled) return;
  if (button.dataset.logs) {
    showLogs(button.dataset.logs, button.dataset.id);
    return;
  }
  if (button.dataset.kind) {
    doAction(button.dataset.kind, button.dataset.id, button.dataset.action);
  }
});

$('refresh').addEventListener('click', refresh);
$('modal-close').addEventListener('click', () => $('modal').classList.remove('open'));
$('modal').addEventListener('click', (event) => {
  if (event.target === $('modal')) $('modal').classList.remove('open');
});

refresh();
setInterval(refresh, 10000);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    ThreadingHTTPServer.allow_reuse_address = True
    httpd = ThreadingHTTPServer(("0.0.0.0", PANEL_PORT), Handler)
    print(f"panel listening on http://0.0.0.0:{PANEL_PORT}", flush=True)
    httpd.serve_forever()
