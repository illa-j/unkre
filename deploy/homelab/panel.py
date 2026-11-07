import base64
import hmac
import json
import os
import socket
import subprocess
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

PANEL_USER = os.environ.get("PANEL_USER", "admin")
PANEL_PASSWORD = os.environ.get("PANEL_PASSWORD", "")
PANEL_PORT = int(os.environ.get("PANEL_PORT", "8090"))
PHONE_HOST = os.environ.get("PHONE_HOST", "192.168.1.5")
PC_HOST = os.environ.get("PC_HOST", "192.168.1.11")
PC_AGENT_URL = os.environ.get("PC_AGENT_URL", f"http://{PC_HOST}:8091").rstrip("/")
PC_AGENT_TOKEN = os.environ.get("PC_AGENT_TOKEN", "")
SVDIR = os.environ.get("SVDIR", str(Path(os.environ.get("PREFIX", "/data/data/com.termux/files/usr")) / "var/service"))
LOG_BASE = os.environ.get("LOG_BASE", str(Path(os.environ.get("PREFIX", "/data/data/com.termux/files/usr")) / "var/log/sv"))

PHONE_SERVICES = [
    {"id": "sshd", "name": "SSH", "controllable": True},
    {"id": "postgres", "name": "PostgreSQL", "controllable": True},
    {"id": "redis", "name": "Redis", "controllable": True},
    {"id": "cloudflared", "name": "Cloudflare Tunnel", "controllable": True},
    {"id": "stack", "name": "UNKRE + NoCensGen", "controllable": True},
    {"id": "panel", "name": "Панель", "controllable": False},
]

app = FastAPI(title="Home Lab Panel")
security = HTTPBasic()


def require_auth(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    if not PANEL_PASSWORD:
        raise HTTPException(status_code=503, detail="PANEL_PASSWORD is not set")
    user_ok = hmac.compare_digest(credentials.username, PANEL_USER)
    pass_ok = hmac.compare_digest(credentials.password, PANEL_PASSWORD)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


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
    except Exception as exc:  # noqa: BLE001 - panel may run outside Termux too
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
        raise HTTPException(status_code=404, detail="unknown service")
    if action not in allowed:
        raise HTTPException(status_code=400, detail="bad action")
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
    request = urllib.request.Request(
        f"{PC_AGENT_URL}{path}",
        method=method,
        headers={"X-Agent-Token": PC_AGENT_TOKEN},
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            body = response.read().decode("utf-8", "replace")
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                return True, json.loads(body)
            return True, body
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:500]}"
    except Exception as exc:  # noqa: BLE001 - the panel must keep working
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


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "service": "homelab-panel"}


@app.get("/api/overview")
def overview(_: str = Depends(require_auth)) -> dict:
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


@app.post("/api/phone/{service_id}/{action}")
def phone_control(
    service_id: str, action: str, request: Request, _: str = Depends(require_auth)
) -> dict:
    if request.headers.get("x-panel") != "1":
        raise HTTPException(status_code=403, detail="missing panel header")
    return phone_action(service_id, action)


@app.get("/api/phone/{service_id}/logs", response_class=PlainTextResponse)
def phone_logs(service_id: str, _: str = Depends(require_auth)) -> str:
    ids = {item["id"] for item in PHONE_SERVICES}
    if service_id not in ids:
        raise HTTPException(status_code=404, detail="unknown service")
    path = Path(LOG_BASE) / service_id / "current"
    if not path.exists():
        return f"log file not found: {path}"
    result = run(["tail", "-n", "150", str(path)])
    return (result.stdout + result.stderr).strip() or "(empty log)"


@app.post("/api/pc/{name}/{action}")
def pc_control(
    name: str, action: str, request: Request, _: str = Depends(require_auth)
) -> dict:
    if request.headers.get("x-panel") != "1":
        raise HTTPException(status_code=403, detail="missing panel header")
    if action not in {"start", "stop", "restart"}:
        raise HTTPException(status_code=400, detail="bad action")
    ok, data = agent_request(f"/api/containers/{name}/{action}", method="POST")
    if not ok:
        raise HTTPException(status_code=502, detail=str(data))
    return data if isinstance(data, dict) else {"ok": True, "output": str(data)}


@app.get("/api/pc/{name}/logs", response_class=PlainTextResponse)
def pc_logs(name: str, _: str = Depends(require_auth)) -> str:
    ok, data = agent_request(f"/api/containers/{name}/logs")
    if not ok:
        raise HTTPException(status_code=502, detail=str(data))
    return str(data)


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
    --blue: #60a5fa;
    --violet: #a78bfa;
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


@app.get("/", response_class=HTMLResponse)
def index(_: str = Depends(require_auth)) -> str:
    return INDEX_HTML


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PANEL_PORT, log_level="info")
