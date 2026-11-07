import base64
import glob
import hashlib
import hmac
import html
import json
import os
import platform
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
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
HOME = os.environ.get("HOME", "/data/data/com.termux/files/home")
PREFIX = os.environ.get("PREFIX", "/data/data/com.termux/files/usr")
SVDIR = os.environ.get("SVDIR", str(Path(PREFIX) / "var/service"))
LOG_BASE = os.environ.get("LOG_BASE", str(Path(PREFIX) / "var/log/sv"))
SESSION_SECRET = os.environ.get("PANEL_SECRET") or hashlib.sha256(
    f"homelab:{PANEL_PASSWORD}".encode()
).hexdigest()
SESSION_MAX_AGE = 7 * 24 * 3600

PHONE_SERVICES = [
    {"id": "sshd", "name": "SSH", "kind": "runit", "controllable": True},
    {"id": "postgres", "name": "PostgreSQL", "kind": "runit", "controllable": True},
    {"id": "redis", "name": "Redis", "kind": "runit", "controllable": True},
    {"id": "cloudflared", "name": "Cloudflare Tunnel", "kind": "runit", "controllable": True},
    {"id": "nginx-unkre", "name": "nginx · UNKRE", "kind": "runit", "controllable": True},
    {"id": "nginx-nocensgen", "name": "nginx · NoCensGen", "kind": "runit", "controllable": True},
    {"id": "stack", "name": "Застосунки (proot)", "kind": "stack", "controllable": True},
    {"id": "panel", "name": "Панель", "kind": "self", "controllable": False},
]

ACTIVITY = deque(maxlen=60)
ACTIVITY_LOCK = threading.Lock()
LOGIN_FAILS: dict[str, tuple[int, float]] = {}
LOGIN_LOCK = threading.Lock()


def log_activity(text: str, ok: bool = True) -> None:
    with ACTIVITY_LOCK:
        ACTIVITY.appendleft({"ts": int(time.time()), "text": text, "ok": ok})


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
        return (
            hmac.compare_digest(signature, expected)
            and time.time() - int(timestamp) <= SESSION_MAX_AGE
            and hmac.compare_digest(username, PANEL_USER)
        )
    except Exception:  # noqa: BLE001
        return False


def get_session(handler: BaseHTTPRequestHandler) -> str | None:
    cookie = SimpleCookie(handler.headers.get("Cookie", ""))
    morsel = cookie.get("panel_session")
    return morsel.value if morsel else None


def login_allowed(ip: str) -> bool:
    now = time.time()
    with LOGIN_LOCK:
        count, first = LOGIN_FAILS.get(ip, (0, now))
        if now - first > 300:
            count, first = 0, now
        LOGIN_FAILS[ip] = (count, first)
        return count < 5


def login_failed(ip: str) -> None:
    now = time.time()
    with LOGIN_LOCK:
        count, first = LOGIN_FAILS.get(ip, (0, now))
        if now - first > 300:
            count, first = 0, now
        LOGIN_FAILS[ip] = (count + 1, first)


def login_success(ip: str) -> None:
    with LOGIN_LOCK:
        LOGIN_FAILS.pop(ip, None)


def run(cmd: list[str], timeout: int = 12, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, **(env or {})},
    )


def read_text(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except Exception:  # noqa: BLE001
        return ""


def http_code(url: str, timeout: float = 2.0) -> int:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception:  # noqa: BLE001
        return 0


def port_open(port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except Exception:  # noqa: BLE001
        return False


def sv_line(service_id: str) -> str:
    try:
        result = run(["sv", "status", service_id], env={"SVDIR": SVDIR})
        text = (result.stdout + result.stderr).strip()
        return text.splitlines()[0] if text else ""
    except Exception as exc:  # noqa: BLE001
        return f"sv error: {exc}"


def service_health(service_id: str) -> tuple[bool, str]:
    if service_id == "sshd":
        return port_open(8022), "порт 8022"
    if service_id == "postgres":
        try:
            result = run(["pg_isready", "-h", "127.0.0.1", "-p", "5432"], timeout=4)
            return result.returncode == 0, "pg_isready"
        except Exception:  # noqa: BLE001
            return False, "pg_isready"
    if service_id == "redis":
        try:
            result = run(["redis-cli", "-h", "127.0.0.1", "ping"], timeout=4)
            return "PONG" in result.stdout, "redis ping"
        except Exception:  # noqa: BLE001
            return False, "redis ping"
    if service_id == "cloudflared":
        try:
            result = run(["pgrep", "-x", "cloudflared"], timeout=3)
            return bool(result.stdout.strip()), "процес cloudflared"
        except Exception:  # noqa: BLE001
            return False, "процес cloudflared"
    if service_id == "nginx-unkre":
        code = http_code("http://127.0.0.1:18080/", timeout=2)
        return code == 200, f"HTTP {code}"
    if service_id == "nginx-nocensgen":
        code = http_code("http://127.0.0.1:18082/", timeout=2)
        return code == 200, f"HTTP {code}"
    if service_id == "panel":
        return True, "panel process"
    return False, ""


def stack_status() -> dict:
    supervisor = ""
    try:
        result = run(["pgrep", "-f", "supervisord -n -c /etc/supervisor/supervisord.conf"], timeout=3)
        supervisor = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    except Exception:  # noqa: BLE001
        pass
    unkre = http_code("http://127.0.0.1:18080/", timeout=2)
    nocens = http_code("http://127.0.0.1:18082/", timeout=2)
    apps_ok = unkre == 200 and nocens == 200
    running = bool(supervisor) and apps_ok
    return {
        "id": "stack",
        "name": "Застосунки (proot)",
        "kind": "stack",
        "controllable": True,
        "state": "running" if running else ("failed" if supervisor else "stopped"),
        "detail": f"UNKRE {unkre} · NoCensGen {nocens} · supervisor {supervisor or '—'}",
    }


def phone_status(service: dict) -> dict:
    if service["id"] == "stack":
        return stack_status()
    if service["id"] == "panel":
        return {**service, "state": "running", "detail": "панель відповідає"}
    sv = sv_line(service["id"])
    healthy, health_detail = service_health(service["id"])
    if healthy:
        state = "running"
    elif sv.startswith("run:"):
        state = "running"
    elif sv.startswith("down:"):
        state = "stopped"
    elif sv.startswith("fail:"):
        state = "failed"
    else:
        state = "unknown"
    return {
        **service,
        "state": state,
        "detail": f"{sv or '—'} · {health_detail}",
    }


def phone_action(service_id: str, action: str) -> dict:
    allowed = {"up", "down", "restart"}
    ids = {item["id"] for item in PHONE_SERVICES if item["controllable"]}
    if service_id not in ids or action not in allowed:
        return {"ok": False, "output": "unknown service or action"}
    try:
        if service_id == "stack":
            if action in {"down", "restart"}:
                stop = run(["bash", f"{HOME}/stack-stop.sh"], timeout=30)
                if action == "down":
                    log_activity("Стек зупинено", stop.returncode == 0)
                    return {"ok": stop.returncode == 0, "output": (stop.stdout + stop.stderr)[-2000:]}
            start = run(["bash", f"{HOME}/stack-start.sh"], timeout=40)
            log_activity("Стек запущено", start.returncode == 0)
            return {"ok": start.returncode == 0, "output": (start.stdout + start.stderr)[-2000:]}
        result = run(["sv", action, service_id], timeout=30, env={"SVDIR": SVDIR})
        ok = result.returncode == 0
        log_activity(f"{service_id}: {action}", ok)
        return {"ok": ok, "output": (result.stdout + result.stderr).strip()[-2000:]}
    except Exception as exc:  # noqa: BLE001
        log_activity(f"{service_id}: {action} — {exc}", False)
        return {"ok": False, "output": f"{type(exc).__name__}: {exc}"}


def agent_request(path: str, method: str = "GET") -> tuple[bool, dict | str]:
    if not PC_AGENT_TOKEN:
        return False, "PC_AGENT_TOKEN is not set"
    request_obj = urllib.request.Request(
        f"{PC_AGENT_URL}{path}",
        method=method,
        headers={"X-Agent-Token": PC_AGENT_TOKEN},
    )
    try:
        with urllib.request.urlopen(request_obj, timeout=12) as response:
            body = response.read().decode("utf-8", "replace")
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                return True, json.loads(body)
            return True, body
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:500]}"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def meminfo() -> dict:
    values = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, _, rest = line.partition(":")
            if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
                values[key] = int(rest.strip().split()[0]) * 1024
    except Exception:  # noqa: BLE001
        pass
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", 0)
    return {
        "total": total,
        "used": max(0, total - available),
        "available": available,
        "percent": round((total - available) / total * 100, 1) if total else 0,
        "swap_total": values.get("SwapTotal", 0),
        "swap_used": max(0, values.get("SwapTotal", 0) - values.get("SwapFree", 0)),
    }


def phone_system() -> dict:
    uptime_seconds = None
    try:
        uptime_seconds = float(Path("/proc/uptime").read_text().split()[0])
    except Exception:  # noqa: BLE001
        pass
    try:
        load = list(os.getloadavg())
    except Exception:  # noqa: BLE001
        load = [0, 0, 0]
    try:
        disk = shutil.disk_usage("/data/data/com.termux/files")
        disk_info = {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": round(disk.used / disk.total * 100, 1) if disk.total else 0,
        }
    except Exception:  # noqa: BLE001
        disk_info = {"total": 0, "used": 0, "free": 0, "percent": 0}

    battery = {"capacity": None, "status": ""}
    for base in ("/sys/class/power_supply/battery", "/sys/class/power_supply/bms"):
        capacity = read_text(f"{base}/capacity")
        status = read_text(f"{base}/status")
        if capacity:
            battery = {"capacity": capacity, "status": status}
            break

    temperature = None
    temps = []
    for path in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        value = read_text(path)
        try:
            number = int(value)
            temps.append(number / 1000 if number > 1000 else number)
        except Exception:  # noqa: BLE001
            continue
    if temps:
        temperature = round(max(temps), 1)

    model = ""
    try:
        model = run(["getprop", "ro.product.marketname"], timeout=3).stdout.strip()
        if not model:
            model = run(["getprop", "ro.product.model"], timeout=3).stdout.strip()
        android = run(["getprop", "ro.build.version.release"], timeout=3).stdout.strip()
    except Exception:  # noqa: BLE001
        android = ""
    wake_lock = Path(HOME, ".wake-lock").exists()

    return {
        "hostname": model or platform.node(),
        "platform": f"Android {android}" if android else platform.release(),
        "uptime_seconds": uptime_seconds,
        "load": load,
        "cpu_count": os.cpu_count() or 0,
        "memory": meminfo(),
        "disk": disk_info,
        "battery": battery,
        "temperature": temperature,
        "wake_lock": wake_lock,
        "ip": PHONE_HOST,
    }


def probe(url: str) -> bool:
    try:
        host = url.split("//", 1)[1].split("/", 1)[0]
        if ":" in host:
            hostname, port_text = host.rsplit(":", 1)
            port = int(port_text)
        else:
            hostname = host
            port = 443 if url.startswith("https://") else 80
        with socket.create_connection((hostname, port), timeout=0.6):
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
    pc_ok, pc_data = agent_request("/api/status?stats=true")
    containers = pc_data.get("containers", []) if pc_ok and isinstance(pc_data, dict) else []
    pc_system_ok, pc_system_data = agent_request("/api/system")
    pc_system = pc_system_data.get("system") if pc_system_ok and isinstance(pc_system_data, dict) else None
    return {
        "phone": phone,
        "phone_system": phone_system(),
        "pc_ok": pc_ok,
        "pc_error": "" if pc_ok else str(pc_data),
        "pc": containers,
        "pc_system": pc_system,
        "pc_system_error": "" if pc_system_ok else str(pc_system_data),
        "links": build_links(),
        "activity": list(ACTIVITY),
    }


def quick_action(action: str) -> dict:
    try:
        if action == "wake":
            result = run(["termux-wake-lock"], timeout=10)
            if result.returncode == 0:
                try:
                    Path(HOME, ".wake-lock").write_text(str(int(time.time())))
                except Exception:  # noqa: BLE001
                    pass
            log_activity("Wake lock", result.returncode == 0)
            return {"ok": result.returncode == 0, "output": (result.stdout + result.stderr).strip()}
        if action == "stack-restart":
            return phone_action("stack", "restart")
        if action == "nginx-restart":
            outputs = []
            ok = True
            for service in ("nginx-unkre", "nginx-nocensgen"):
                result = run(["sv", "restart", service], timeout=20, env={"SVDIR": SVDIR})
                outputs.append(f"{service}: {(result.stdout + result.stderr).strip()}")
                ok = ok and result.returncode == 0
            log_activity("nginx перезапущено", ok)
            return {"ok": ok, "output": "\n".join(outputs)}
        if action == "sshd-up":
            return phone_action("sshd", "up")
        return {"ok": False, "output": "unknown action"}
    except Exception as exc:  # noqa: BLE001
        log_activity(f"quick {action}: {exc}", False)
        return {"ok": False, "output": f"{type(exc).__name__}: {exc}"}


def login_page(error: str = "") -> str:
    error_html = f'<div class="error">{html.escape(error)}</div>' if error else ""
    return LOGIN_HTML.replace("__ERROR__", error_html)


LOGIN_HTML = r"""<!doctype html>
<html lang="uk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Home Lab · Вхід</title>
<style>
  :root { --bg:#0b0e14; --panel:#131823; --border:#263044; --text:#e8eefc; --muted:#8b98b3; --blue:#60a5fa; }
  * { box-sizing:border-box; }
  body { margin:0; min-height:100vh; display:grid; place-items:center; padding:20px;
    font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif; color:var(--text);
    background:radial-gradient(900px 500px at 15% -10%, #1b2a4a 0%, transparent 55%),
               radial-gradient(700px 400px at 100% 0%, #2a1b3d 0%, transparent 50%), var(--bg); }
  .card { width:min(390px,100%); background:linear-gradient(180deg,rgba(26,33,48,.96),rgba(19,24,35,.98));
    border:1px solid var(--border); border-radius:20px; padding:28px; box-shadow:0 24px 70px rgba(0,0,0,.35); }
  .mark { width:42px; height:42px; border-radius:12px; display:grid; place-items:center; margin-bottom:16px;
    background:linear-gradient(135deg,#2563eb,#7c3aed); font-weight:800; letter-spacing:-.05em; }
  h1 { margin:0; font-size:28px; letter-spacing:-.04em; }
  .sub { color:var(--muted); font-size:13px; margin:6px 0 22px; }
  label { display:block; font-size:12px; color:var(--muted); margin-bottom:12px; }
  input { width:100%; margin-top:6px; padding:12px 13px; border-radius:11px; border:1px solid var(--border);
    background:#0e131c; color:var(--text); font:inherit; outline:none; }
  input:focus { border-color:#3b82f6; box-shadow:0 0 0 3px rgba(59,130,246,.16); }
  button { width:100%; margin-top:4px; padding:12px; border-radius:11px; border:1px solid #2563eb;
    background:#1d4ed8; color:#fff; font:inherit; font-weight:600; cursor:pointer; }
  button:hover { background:#2563eb; }
  .error { background:#2a1218; border:1px solid #7f1d1d; color:#fecaca; border-radius:10px;
    padding:10px 12px; font-size:13px; margin-bottom:14px; }
  .hint { color:var(--muted); font-size:11px; margin-top:14px; text-align:center; }
</style>
</head>
<body>
<main class="card">
  <div class="mark">HL</div>
  <h1>HOME LAB</h1>
  <div class="sub">Вхід до панелі керування</div>
  __ERROR__
  <form method="post" action="/login">
    <label>Логін<input name="username" autocomplete="username" autofocus required></label>
    <label>Пароль<input name="password" type="password" autocomplete="current-password" required></label>
    <button type="submit">Увійти</button>
  </form>
  <div class="hint">Телефон · ПК · Docker</div>
</main>
</body>
</html>"""


INDEX_HTML = r"""<!doctype html>
<html lang="uk">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Home Lab</title>
<style>
  :root {
    --bg:#0b0e14; --panel:#131823; --panel-2:#1a2130; --border:#263044;
    --text:#e8eefc; --muted:#8b98b3; --green:#34d399; --red:#f87171;
    --amber:#fbbf24; --blue:#60a5fa; --violet:#a78bfa;
  }
  body[data-theme="light"] {
    --bg:#eef2f9; --panel:#ffffff; --panel-2:#f3f6fb; --border:#d7dfec;
    --text:#162033; --muted:#5d6b84; --green:#059669; --red:#dc2626;
    --amber:#d97706; --blue:#2563eb; --violet:#7c3aed;
  }
  * { box-sizing:border-box; }
  html { scroll-behavior:smooth; }
  body { margin:0; min-height:100vh; font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
    color:var(--text); background:
      radial-gradient(1200px 600px at 10% -10%, rgba(27,42,74,.9) 0%, transparent 55%),
      radial-gradient(900px 500px at 100% 0%, rgba(42,27,61,.7) 0%, transparent 50%), var(--bg); }
  body[data-theme="light"] { background:var(--bg); }
  .wrap { max-width:1280px; margin:0 auto; padding:20px 16px 70px; }
  .topbar { display:flex; align-items:center; justify-content:space-between; gap:16px; flex-wrap:wrap; margin-bottom:16px; }
  .brand { display:flex; align-items:center; gap:12px; }
  .mark { width:42px; height:42px; border-radius:12px; display:grid; place-items:center;
    background:linear-gradient(135deg,#2563eb,#7c3aed); color:#fff; font-weight:800; letter-spacing:-.05em; }
  h1 { margin:0; font-size:clamp(24px,4vw,34px); letter-spacing:-.04em; }
  .sub { color:var(--muted); font-size:12px; margin-top:3px; }
  .actions { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
  .pill { display:inline-flex; align-items:center; gap:7px; padding:7px 11px; border:1px solid var(--border);
    border-radius:999px; background:color-mix(in srgb, var(--panel) 80%, transparent); color:var(--muted); font-size:12px; text-decoration:none; }
  .dot { width:9px; height:9px; border-radius:50%; background:var(--muted); box-shadow:0 0 0 3px rgba(139,152,179,.12); flex:none; }
  .dot.green { background:var(--green); box-shadow:0 0 0 3px rgba(52,211,153,.14); }
  .dot.red { background:var(--red); box-shadow:0 0 0 3px rgba(248,113,113,.14); }
  .dot.amber { background:var(--amber); box-shadow:0 0 0 3px rgba(251,191,36,.14); }
  button { font:inherit; cursor:pointer; border:1px solid var(--border); background:var(--panel-2); color:var(--text);
    padding:8px 12px; border-radius:10px; transition:.15s; }
  button:hover { border-color:#3d4c68; background:color-mix(in srgb, var(--panel-2) 80%, #fff); }
  button.primary { background:#1d4ed8; border-color:#2563eb; color:#fff; }
  button.primary:hover { background:#2563eb; }
  button.ghost { background:transparent; }
  button.danger { color:#fecaca; border-color:#7f1d1d; }
  button:disabled { opacity:.45; cursor:not-allowed; }
  .tabs { display:flex; gap:6px; flex-wrap:wrap; border-bottom:1px solid var(--border); margin-bottom:22px; }
  .tabs a { color:var(--muted); text-decoration:none; font-size:13px; padding:9px 11px; border-radius:9px 9px 0 0; }
  .tabs a:hover { color:var(--text); background:var(--panel); }
  section { margin-top:26px; scroll-margin-top:16px; }
  h2 { font-size:13px; text-transform:uppercase; letter-spacing:.14em; color:var(--muted); margin:0 0 12px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:12px; }
  .card { background:linear-gradient(180deg, color-mix(in srgb, var(--panel-2) 92%, transparent), var(--panel));
    border:1px solid var(--border); border-radius:16px; padding:16px; box-shadow:0 16px 40px rgba(0,0,0,.12); }
  .card-top { display:flex; align-items:flex-start; justify-content:space-between; gap:10px; }
  .name { font-weight:700; letter-spacing:-.01em; }
  .state { font-size:12px; color:var(--muted); margin-top:4px; word-break:break-word; }
  .actions-row { display:flex; gap:8px; flex-wrap:wrap; margin-top:14px; }
  .actions-row button { padding:7px 10px; font-size:12px; }
  .system-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:12px; }
  .system-head { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:14px; }
  .metric { display:flex; justify-content:space-between; gap:10px; font-size:12px; padding:5px 0; }
  .metric span:last-child { color:var(--muted); text-align:right; }
  .bar { height:7px; border-radius:999px; background:color-mix(in srgb, var(--border) 70%, transparent); overflow:hidden; margin:5px 0 9px; }
  .bar > i { display:block; height:100%; background:linear-gradient(90deg,#2563eb,#7c3aed); border-radius:999px; }
  .bar.green > i { background:linear-gradient(90deg,#059669,#34d399); }
  .bar.amber > i { background:linear-gradient(90deg,#d97706,#fbbf24); }
  .quick { display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }
  .toolbar { display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin-bottom:10px; }
  input[type="search"], select { font:inherit; color:var(--text); background:var(--panel); border:1px solid var(--border);
    border-radius:10px; padding:8px 11px; outline:none; }
  input[type="search"] { flex:1; min-width:180px; }
  input[type="search"]:focus, select:focus { border-color:var(--blue); }
  .table { width:100%; border-collapse:collapse; overflow:hidden; border-radius:14px; border:1px solid var(--border); }
  .table th, .table td { text-align:left; padding:10px 11px; border-bottom:1px solid var(--border); vertical-align:top; font-size:12.5px; }
  .table th { color:var(--muted); font-weight:600; background:var(--panel); position:sticky; top:0; }
  .table tr:last-child td { border-bottom:0; }
  .mono { font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:11.5px; color:var(--muted); }
  .chip { display:inline-flex; align-items:center; gap:6px; padding:4px 8px; border:1px solid var(--border);
    border-radius:999px; background:var(--panel); font-size:11px; color:var(--muted); white-space:nowrap; }
  .links { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:10px; }
  a.link { display:flex; align-items:center; justify-content:space-between; gap:10px; text-decoration:none; color:var(--text);
    background:var(--panel); border:1px solid var(--border); border-radius:14px; padding:12px 13px; transition:.15s; }
  a.link:hover { border-color:#3d4c68; transform:translateY(-1px); }
  a.link small { color:var(--muted); font-size:10px; text-transform:uppercase; letter-spacing:.1em; display:block; }
  .activity { display:flex; flex-direction:column; gap:6px; }
  .activity-item { display:flex; gap:10px; align-items:baseline; font-size:12px; padding:7px 10px;
    border:1px solid var(--border); border-radius:10px; background:var(--panel); }
  .activity-item time { color:var(--muted); font-size:11px; min-width:64px; }
  .modal { position:fixed; inset:0; background:rgba(4,7,12,.72); display:none; align-items:center; justify-content:center; padding:16px; z-index:50; }
  .modal.open { display:flex; }
  .modal-body { width:min(1000px,100%); max-height:85vh; overflow:auto; background:var(--panel); border:1px solid var(--border);
    border-radius:16px; padding:16px; }
  .modal-head { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:12px; flex-wrap:wrap; }
  pre { margin:0; white-space:pre-wrap; word-break:break-word; font-size:12px; line-height:1.55; color:var(--text);
    background:color-mix(in srgb, var(--bg) 80%, transparent); padding:12px; border-radius:10px; border:1px solid var(--border); }
  .toast { position:fixed; right:16px; bottom:16px; max-width:min(460px,calc(100vw - 32px)); background:var(--panel);
    border:1px solid var(--border); border-radius:12px; padding:11px 13px; color:var(--text);
    box-shadow:0 18px 50px rgba(0,0,0,.35); opacity:0; transform:translateY(8px); transition:.2s; pointer-events:none; z-index:60; font-size:13px; }
  .toast.show { opacity:1; transform:translateY(0); }
  .empty { color:var(--muted); font-size:13px; padding:14px 0; }
  @media (max-width:700px) {
    .table { display:block; overflow-x:auto; white-space:nowrap; }
    .table th { position:static; }
    .topbar { align-items:flex-start; }
    .actions { width:100%; }
  }
</style>
</head>
<body data-theme="dark">
<div class="wrap">
  <div class="topbar">
    <div class="brand">
      <div class="mark">HL</div>
      <div>
        <h1>HOME LAB</h1>
        <div class="sub">Телефон · ПК · Docker · <span id="updated">—</span></div>
      </div>
    </div>
    <div class="actions">
      <span class="pill"><span id="phone-dot" class="dot"></span><span id="phone-pill">Телефон</span></span>
      <span class="pill"><span id="pc-dot" class="dot"></span><span id="pc-pill">ПК</span></span>
      <button id="refresh" class="primary">Оновити</button>
      <button id="theme-btn" class="ghost" title="Тема">☀</button>
      <a class="pill" href="/logout">Вийти</a>
    </div>
  </div>

  <nav class="tabs">
    <a href="#overview">Огляд</a>
    <a href="#phone">Телефон</a>
    <a href="#pc">ПК</a>
    <a href="#links">Посилання</a>
    <a href="#activity">Дії</a>
  </nav>

  <section id="overview">
    <h2>Система</h2>
    <div class="system-grid">
      <div class="card" id="phone-system"></div>
      <div class="card" id="pc-system"></div>
    </div>
    <div class="quick">
      <button data-quick="wake" class="ghost">Wake lock</button>
      <button data-quick="stack-restart">Перезапустити стек</button>
      <button data-quick="nginx-restart">Перезапустити nginx</button>
      <button data-quick="sshd-up" class="ghost">Підняти SSH</button>
    </div>
  </section>

  <section id="phone">
    <h2>Телефон · сервіси</h2>
    <div id="phone-grid" class="grid"></div>
  </section>

  <section id="pc">
    <h2>ПК · Docker</h2>
    <div class="toolbar">
      <input id="search" type="search" placeholder="Пошук за назвою або образом…">
      <select id="refresh-rate" title="Автооновлення">
        <option value="5000">5 с</option>
        <option value="10000" selected>10 с</option>
        <option value="30000">30 с</option>
        <option value="60000">60 с</option>
      </select>
      <span class="chip" id="pc-count">—</span>
    </div>
    <div id="pc-wrap"></div>
  </section>

  <section id="links">
    <h2>Посилання</h2>
    <div id="links" class="links"></div>
  </section>

  <section id="activity">
    <h2>Останні дії</h2>
    <div id="activity-list" class="activity"></div>
  </section>
</div>

<div id="modal" class="modal">
  <div class="modal-body">
    <div class="modal-head">
      <div class="name" id="modal-title">Логи</div>
      <div class="actions">
        <button id="logs-refresh" class="ghost">Оновити</button>
        <button id="logs-copy" class="ghost">Копіювати</button>
        <button id="logs-download" class="ghost">Завантажити</button>
        <button id="modal-close" class="ghost">Закрити</button>
      </div>
    </div>
    <pre id="modal-text">Завантаження…</pre>
  </div>
</div>
<div id="toast" class="toast"></div>

<script>
const $ = (id) => document.getElementById(id);
const state = {
  data: null,
  search: '',
  timer: null,
  interval: Number(localStorage.getItem('hl_interval') || 10000),
  theme: localStorage.getItem('hl_theme') || 'dark',
  logs: null,
  busy: false,
};

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
  }[ch]));
}
function fmtBytes(value) {
  const n = Number(value || 0);
  if (!n) return '0 B';
  const units = ['B','KB','MB','GB','TB'];
  const i = Math.min(units.length - 1, Math.floor(Math.log(n) / Math.log(1024)));
  return `${(n / Math.pow(1024, i)).toFixed(i ? 1 : 0)} ${units[i]}`;
}
function fmtUptime(seconds) {
  if (seconds === null || seconds === undefined || seconds === '') return '—';
  let s = Math.floor(Number(seconds || 0));
  const d = Math.floor(s / 86400); s %= 86400;
  const h = Math.floor(s / 3600); s %= 3600;
  const m = Math.floor(s / 60);
  if (d) return `${d}д ${h}г`;
  if (h) return `${h}г ${m}хв`;
  return `${m}хв`;
}
function dotClass(state) {
  if (state === 'running' || state === 'Up') return 'green';
  if (state === 'failed' || state === 'unknown') return 'amber';
  return 'red';
}
function bar(percent, tone = '') {
  const p = Math.max(0, Math.min(100, Number(percent || 0)));
  return `<div class="bar ${tone}"><i style="width:${p}%"></i></div>`;
}
function toast(message, ok = true) {
  const el = $('toast');
  el.textContent = message;
  el.style.borderColor = ok ? 'var(--border)' : '#7f1d1d';
  el.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove('show'), 4000);
}
async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response;
}
function setTheme(theme) {
  state.theme = theme;
  document.body.dataset.theme = theme;
  localStorage.setItem('hl_theme', theme);
  $('theme-btn').textContent = theme === 'dark' ? '☀' : '☾';
}
function renderSystem(phone, pc, pcError) {
  const p = phone || {};
  const mem = p.memory || {};
  const disk = p.disk || {};
  const battery = p.battery || {};
  const load = (p.load || [0,0,0])[0];
  $('phone-system').innerHTML = `
    <div class="system-head">
      <div><div class="name">Телефон</div><div class="mono">${esc(p.hostname || '')} · ${esc(p.ip || '')}</div></div>
      <span class="chip"><span class="dot green"></span>${esc(p.platform || 'Android')}</span>
    </div>
    <div class="metric"><span>Load (1m / ${esc(p.cpu_count || 0)} CPU)</span><span>${Number(load || 0).toFixed(2)}</span></div>
    ${bar(Math.min(100, Number(load || 0) / Math.max(1, p.cpu_count || 1) * 100))}
    <div class="metric"><span>RAM</span><span>${fmtBytes(mem.used)} / ${fmtBytes(mem.total)} (${esc(mem.percent || 0)}%)</span></div>
    ${bar(mem.percent, Number(mem.percent || 0) > 85 ? 'red' : '')}
    <div class="metric"><span>Диск /data</span><span>${fmtBytes(disk.used)} / ${fmtBytes(disk.total)} (${esc(disk.percent || 0)}%)</span></div>
    ${bar(disk.percent, Number(disk.percent || 0) > 90 ? 'red' : '')}
    <div class="metric"><span>Uptime</span><span>${fmtUptime(p.uptime_seconds)}</span></div>
    <div class="metric"><span>Батарея</span><span>${battery.capacity ? esc(battery.capacity) + '% · ' + esc(battery.status || '') : '—'}</span></div>
    <div class="metric"><span>Температура</span><span>${p.temperature != null ? esc(p.temperature) + ' °C' : '—'}</span></div>
    <div class="metric"><span>Wake lock</span><span>${p.wake_lock ? 'активний' : 'не активний'}</span></div>
  `;
  if (!pc) {
    $('pc-system').innerHTML = `<div class="empty">Системні дані ПК недоступні: ${esc(pcError || 'agent offline')}</div>`;
    return;
  }
  const pm = pc.memory || {};
  const pd = pc.disk || {};
  const docker = pc.docker || {};
  const gpu = (pc.gpu || [])[0];
  $('pc-system').innerHTML = `
    <div class="system-head">
      <div><div class="name">ПК</div><div class="mono">${esc(pc.hostname || '')} · ${esc(pc.platform || '')}</div></div>
      <span class="chip"><span class="dot green"></span>${esc(docker.running || 0)}/${esc(docker.total || 0)} containers</span>
    </div>
    <div class="metric"><span>Load (1m / ${esc(pc.cpu_count || 0)} CPU)</span><span>${Number((pc.load || [0])[0] || 0).toFixed(2)}</span></div>
    ${bar(Math.min(100, Number((pc.load || [0])[0] || 0) / Math.max(1, pc.cpu_count || 1) * 100))}
    <div class="metric"><span>RAM</span><span>${fmtBytes(pm.used)} / ${fmtBytes(pm.total)} (${esc(pm.percent || 0)}%)</span></div>
    ${bar(pm.percent, Number(pm.percent || 0) > 85 ? 'red' : '')}
    <div class="metric"><span>Диск /</span><span>${fmtBytes(pd.used)} / ${fmtBytes(pd.total)} (${esc(pd.percent || 0)}%)</span></div>
    ${bar(pd.percent, Number(pd.percent || 0) > 90 ? 'red' : '')}
    <div class="metric"><span>Uptime</span><span>${fmtUptime(pc.uptime_seconds)}</span></div>
    ${gpu ? `<div class="metric"><span>GPU · ${esc(gpu.name)}</span><span>${esc(gpu.util)}% · ${esc(gpu.mem_used)}/${esc(gpu.mem_total)} MiB · ${esc(gpu.temp)}°C</span></div>` : ''}
  `;
}
function renderPhone(items) {
  $('phone-grid').innerHTML = (items || []).map((item) => `
    <div class="card">
      <div class="card-top">
        <div><div class="name">${esc(item.name)}</div><div class="state">${esc(item.detail || item.state)}</div></div>
        <span class="dot ${dotClass(item.state)}"></span>
      </div>
      <div class="actions-row">
        ${item.controllable ? `
          <button data-kind="phone" data-id="${esc(item.id)}" data-action="up" ${item.state === 'running' ? 'disabled' : ''}>Увімкнути</button>
          <button data-kind="phone" data-id="${esc(item.id)}" data-action="restart">Рестарт</button>
          <button data-kind="phone" data-id="${esc(item.id)}" data-action="down" ${item.state === 'running' ? '' : 'disabled'}>Вимкнути</button>
        ` : ''}
        <button data-logs="phone" data-id="${esc(item.id)}" class="ghost">Логи</button>
      </div>
    </div>
  `).join('');
}
function filteredPC(items) {
  const q = state.search.trim().toLowerCase();
  if (!q) return items;
  return items.filter((item) => `${item.name} ${item.image}`.toLowerCase().includes(q));
}
function renderPC(ok, error, items) {
  if (!ok) {
    $('pc-wrap').innerHTML = `<div class="empty">Агент ПК недоступний: ${esc(error)}</div>`;
    $('pc-count').textContent = 'offline';
    return;
  }
  const list = filteredPC(items || []);
  $('pc-count').textContent = `${list.length} / ${(items || []).length}`;
  if (!list.length) {
    $('pc-wrap').innerHTML = '<div class="empty">Нічого не знайдено.</div>';
    return;
  }
  $('pc-wrap').innerHTML = `
    <table class="table">
      <thead><tr><th>Контейнер</th><th>Стан</th><th>CPU</th><th>RAM</th><th>Порти</th><th>Дії</th></tr></thead>
      <tbody>
      ${list.map((item) => {
        const running = item.state === 'running';
        const stats = item.stats || {};
        return `<tr>
          <td><div class="name">${esc(item.name)}</div><div class="mono">${esc(item.image)}</div></td>
          <td><span class="chip"><span class="dot ${running ? 'green' : 'red'}"></span>${esc(item.status || item.state)}</span>${item.health ? `<div class="mono">health: ${esc(item.health)}</div>` : ''}</td>
          <td class="mono">${esc(stats.cpu || '—')}</td>
          <td class="mono">${esc(stats.mem || '—')}<br>${esc(stats.mem_percent || '')}</td>
          <td class="mono">${esc(item.ports || '—')}</td>
          <td>
            <div class="actions-row" style="margin-top:0">
              <button data-kind="pc" data-id="${esc(item.name)}" data-action="start" ${running ? 'disabled' : ''}>Старт</button>
              <button data-kind="pc" data-id="${esc(item.name)}" data-action="restart" ${running ? '' : 'disabled'}>Рестарт</button>
              <button data-kind="pc" data-id="${esc(item.name)}" data-action="stop" class="danger" ${running ? '' : 'disabled'}>Стоп</button>
              <button data-logs="pc" data-id="${esc(item.name)}" class="ghost">Логи</button>
            </div>
          </td>
        </tr>`;
      }).join('')}
      </tbody>
    </table>`;
}
function renderLinks(items) {
  $('links').innerHTML = (items || []).map((item) => `
    <a class="link" href="${esc(item.url)}" target="_blank" rel="noreferrer">
      <span><small>${esc(item.group)}</small>${esc(item.name)}</span>
      <span class="dot ${item.online ? 'green' : 'red'}"></span>
    </a>
  `).join('');
}
function renderActivity(items) {
  $('activity-list').innerHTML = (items || []).length
    ? items.map((item) => `<div class="activity-item"><time>${new Date(item.ts * 1000).toLocaleTimeString('uk-UA')}</time><span class="dot ${item.ok ? 'green' : 'red'}" style="margin-top:4px"></span><span>${esc(item.text)}</span></div>`).join('')
    : '<div class="empty">Ще немає дій.</div>';
}
function updateTop(data) {
  const phone = data.phone || [];
  const pc = data.pc || [];
  const phoneRunning = phone.filter((item) => item.state === 'running').length;
  const pcRunning = pc.filter((item) => item.state === 'running').length;
  $('phone-pill').textContent = `Телефон ${phoneRunning}/${phone.length}`;
  $('phone-dot').className = `dot ${phoneRunning === phone.length ? 'green' : (phoneRunning ? 'amber' : 'red')}`;
  if (data.pc_ok) {
    $('pc-pill').textContent = `ПК ${pcRunning}/${pc.length}`;
    $('pc-dot').className = `dot ${pcRunning === pc.length ? 'green' : (pcRunning ? 'amber' : 'red')}`;
  } else {
    $('pc-pill').textContent = 'ПК offline';
    $('pc-dot').className = 'dot red';
  }
  $('updated').textContent = new Date().toLocaleTimeString('uk-UA');
}
function renderAll(data) {
  state.data = data;
  renderSystem(data.phone_system, data.pc_system, data.pc_system_error);
  renderPhone(data.phone);
  renderPC(data.pc_ok, data.pc_error, data.pc);
  renderLinks(data.links);
  renderActivity(data.activity);
  updateTop(data);
}
async function refresh() {
  if (state.busy) return;
  state.busy = true;
  try {
    const data = await (await api('/api/overview')).json();
    renderAll(data);
  } catch (error) {
    toast(`Помилка: ${error.message}`, false);
  } finally {
    state.busy = false;
  }
}
async function doAction(kind, id, action) {
  if (action === 'stop' || action === 'restart') {
    if (!confirm(`${action === 'stop' ? 'Зупинити' : 'Перезапустити'} ${id}?`)) return;
  }
  try {
    const response = await api(`/api/${kind}/${encodeURIComponent(id)}/${action}`, {
      method: 'POST',
      headers: { 'X-Panel': '1' }
    });
    const data = await response.json().catch(() => ({}));
    toast(data.ok === false ? `${id}: ${data.output || 'помилка'}` : `${id}: ok`, data.ok !== false);
    await refresh();
  } catch (error) {
    toast(`${id}: ${error.message}`, false);
  }
}
async function quick(action) {
  try {
    const response = await api(`/api/quick/${action}`, { method: 'POST', headers: { 'X-Panel': '1' } });
    const data = await response.json().catch(() => ({}));
    toast(data.ok === false ? `Помилка: ${data.output || action}` : `${action}: ok`, data.ok !== false);
    await refresh();
  } catch (error) {
    toast(`${action}: ${error.message}`, false);
  }
}
async function loadLogs() {
  if (!state.logs) return;
  const { kind, id } = state.logs;
  $('modal-text').textContent = 'Завантаження…';
  try {
    const response = await api(`/api/${kind}/${encodeURIComponent(id)}/logs`);
    $('modal-text').textContent = await response.text();
  } catch (error) {
    $('modal-text').textContent = `Помилка: ${error.message}`;
  }
}
function showLogs(kind, id) {
  state.logs = { kind, id };
  $('modal-title').textContent = `${kind === 'phone' ? 'Телефон' : 'ПК'} · ${id}`;
  $('modal').classList.add('open');
  loadLogs();
}
async function copyLogs() {
  try {
    await navigator.clipboard.writeText($('modal-text').textContent || '');
    toast('Логи скопійовано');
  } catch (error) {
    toast(`Не вдалося скопіювати: ${error.message}`, false);
  }
}
function downloadLogs() {
  if (!state.logs) return;
  const blob = new Blob([$('modal-text').textContent || ''], { type: 'text/plain' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `${state.logs.kind}-${state.logs.id}.log`;
  link.click();
  URL.revokeObjectURL(link.href);
}
function schedule() {
  clearInterval(state.timer);
  state.timer = setInterval(refresh, state.interval);
}
document.addEventListener('click', (event) => {
  const button = event.target.closest('button');
  if (!button || button.disabled) return;
  if (button.dataset.logs) return showLogs(button.dataset.logs, button.dataset.id);
  if (button.dataset.kind) return doAction(button.dataset.kind, button.dataset.id, button.dataset.action);
  if (button.dataset.quick) return quick(button.dataset.quick);
});
$('refresh').addEventListener('click', refresh);
$('theme-btn').addEventListener('click', () => setTheme(state.theme === 'dark' ? 'light' : 'dark'));
$('search').addEventListener('input', (event) => {
  state.search = event.target.value;
  if (state.data) renderPC(state.data.pc_ok, state.data.pc_error, state.data.pc);
});
$('refresh-rate').value = String(state.interval);
$('refresh-rate').addEventListener('change', (event) => {
  state.interval = Number(event.target.value);
  localStorage.setItem('hl_interval', String(state.interval));
  schedule();
});
$('modal-close').addEventListener('click', () => $('modal').classList.remove('open'));
$('modal').addEventListener('click', (event) => { if (event.target === $('modal')) $('modal').classList.remove('open'); });
$('logs-refresh').addEventListener('click', loadLogs);
$('logs-copy').addEventListener('click', copyLogs);
$('logs-download').addEventListener('click', downloadLogs);

setTheme(state.theme);
refresh();
schedule();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "HomeLabPanel/2.0"

    def log_message(self, fmt: str, *args) -> None:
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)

    def _send(self, body: str | bytes, status: int = 200, content_type: str = "text/plain; charset=utf-8") -> None:
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(data)
        except BrokenPipeError:
            pass

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
            self._json({"ok": True, "service": "homelab-panel", "version": 2})
            return
        if path == "/login":
            if self._authorized():
                self._redirect("/")
            else:
                self._send(login_page(), 200, "text/html; charset=utf-8")
            return
        if path == "/logout":
            self._redirect("/login", "panel_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax")
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
            if service_id == "stack":
                log_path = Path(HOME) / "stack.log"
            elif service_id in {item["id"] for item in PHONE_SERVICES}:
                log_path = Path(LOG_BASE) / service_id / "current"
            else:
                self._send("unknown service", 404)
                return
            if not log_path.exists():
                self._send(f"log file not found: {log_path}")
                return
            result = run(["tail", "-n", "200", str(log_path)])
            self._send((result.stdout + result.stderr).strip() or "(empty log)")
        elif path.startswith("/api/pc/") and path.endswith("/logs"):
            name = urllib.parse.unquote(path.split("/")[3])
            ok, data = agent_request(f"/api/containers/{name}/logs")
            self._send(str(data) if ok else f"agent error: {data}", 200 if ok else 502)
        else:
            self._send("not found", 404)

    def do_POST(self) -> None:  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        ip = self.client_address[0]
        if path == "/login":
            if not login_allowed(ip):
                self._send(login_page("Забагато спроб. Спробуй через 5 хвилин."), 429, "text/html; charset=utf-8")
                return
            length = int(self.headers.get("Content-Length", "0") or 0)
            body = self.rfile.read(length).decode("utf-8", "replace")
            form = urllib.parse.parse_qs(body)
            username = form.get("username", [""])[0]
            password = form.get("password", [""])[0]
            if hmac.compare_digest(username, PANEL_USER) and hmac.compare_digest(password, PANEL_PASSWORD):
                login_success(ip)
                cookie = (
                    f"panel_session={make_session(PANEL_USER)}; Path=/; "
                    f"Max-Age={SESSION_MAX_AGE}; HttpOnly; SameSite=Lax"
                )
                self._redirect("/", cookie)
            else:
                login_failed(ip)
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
            log_activity(f"ПК · {name}: {action}", ok)
            self._json(data if ok and isinstance(data, dict) else {"ok": ok, "output": str(data)}, 200 if ok else 502)
        elif len(parts) == 3 and parts[0] == "api" and parts[1] == "quick":
            self._json(quick_action(parts[2]))
        else:
            self._send("not found", 404)


if __name__ == "__main__":
    ThreadingHTTPServer.allow_reuse_address = True
    httpd = ThreadingHTTPServer(("0.0.0.0", PANEL_PORT), Handler)
    print(f"panel v2 listening on http://0.0.0.0:{PANEL_PORT}", flush=True)
    httpd.serve_forever()
