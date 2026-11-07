import hmac
import json
import os
import platform
import shutil
import subprocess

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import PlainTextResponse

TOKEN = os.environ.get("AGENT_TOKEN", "")
app = FastAPI(title="Home Lab PC Agent")


def check_token(token: str | None) -> None:
    if not TOKEN or not token or not hmac.compare_digest(token, TOKEN):
        raise HTTPException(status_code=401, detail="bad token")


def run(cmd: list[str], timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def meminfo() -> dict:
    values = {}
    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
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


def system_info() -> dict:
    try:
        with open("/proc/uptime", encoding="utf-8") as handle:
            uptime_seconds = float(handle.read().split()[0])
    except Exception:  # noqa: BLE001
        uptime_seconds = 0
    try:
        load = list(os.getloadavg())
    except Exception:  # noqa: BLE001
        load = [0, 0, 0]
    try:
        disk = shutil.disk_usage("/")
        disk_info = {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": round(disk.used / disk.total * 100, 1) if disk.total else 0,
        }
    except Exception:  # noqa: BLE001
        disk_info = {"total": 0, "used": 0, "free": 0, "percent": 0}

    gpu = []
    try:
        result = run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            timeout=4,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                parts = [part.strip() for part in line.split(",")]
                if len(parts) >= 5:
                    gpu.append(
                        {
                            "name": parts[0],
                            "util": parts[1],
                            "mem_used": parts[2],
                            "mem_total": parts[3],
                            "temp": parts[4],
                        }
                    )
    except Exception:  # noqa: BLE001
        pass

    docker = {"running": 0, "total": 0}
    try:
        result = run(["docker", "ps", "-a", "--format", "{{.State}}"])
        states = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        docker = {"running": states.count("running"), "total": len(states)}
    except Exception:  # noqa: BLE001
        pass

    return {
        "hostname": platform.node(),
        "platform": f"{platform.system()} {platform.release()}",
        "uptime_seconds": uptime_seconds,
        "load": load,
        "cpu_count": os.cpu_count() or 0,
        "memory": meminfo(),
        "disk": disk_info,
        "docker": docker,
        "gpu": gpu,
    }


def docker_stats() -> dict:
    stats = {}
    try:
        result = run(
            ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
            timeout=25,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                stats[item.get("Name", "")] = {
                    "cpu": item.get("CPUPerc", ""),
                    "mem": item.get("MemUsage", ""),
                    "mem_percent": item.get("MemPerc", ""),
                    "net": item.get("NetIO", ""),
                    "block": item.get("BlockIO", ""),
                    "pids": item.get("PIDs", ""),
                }
    except Exception:  # noqa: BLE001
        pass
    return stats


def container_names() -> set[str]:
    result = run(["docker", "ps", "-a", "--format", "{{.Names}}"])
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def container_health(name: str) -> str:
    result = run(
        [
            "docker",
            "inspect",
            "--format",
            "{{if .State.Health}}{{.State.Health.Status}}{{end}}",
            name,
        ]
    )
    return result.stdout.strip() if result.returncode == 0 else ""


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "service": "homelab-agent"}


@app.get("/api/system")
def system(x_agent_token: str | None = Header(default=None)) -> dict:
    check_token(x_agent_token)
    return {"ok": True, "system": system_info()}


@app.get("/api/status")
def status(stats: bool = False, x_agent_token: str | None = Header(default=None)) -> dict:
    check_token(x_agent_token)
    result = run(["docker", "ps", "-a", "--format", "{{json .}}"])
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr.strip())
    stats_map = docker_stats() if stats else {}
    containers = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        item = json.loads(line)
        name = item.get("Names", "")
        containers.append(
            {
                "name": name,
                "image": item.get("Image", ""),
                "state": item.get("State", ""),
                "status": item.get("Status", ""),
                "ports": item.get("Ports", ""),
                "health": container_health(name),
                "stats": stats_map.get(name, {}),
            }
        )
    containers.sort(key=lambda entry: entry["name"])
    return {"ok": True, "containers": containers}


@app.post("/api/containers/{name}/{action}")
def container_action(
    name: str, action: str, x_agent_token: str | None = Header(default=None)
) -> dict:
    check_token(x_agent_token)
    if action not in {"start", "stop", "restart"}:
        raise HTTPException(status_code=400, detail="bad action")
    if name not in container_names():
        raise HTTPException(status_code=404, detail="container not found")
    result = run(["docker", action, name], timeout=60)
    return {
        "ok": result.returncode == 0,
        "output": (result.stdout + result.stderr).strip()[-2000:],
    }


@app.get("/api/containers/{name}/logs", response_class=PlainTextResponse)
def container_logs(
    name: str,
    tail: int = 120,
    x_agent_token: str | None = Header(default=None),
) -> str:
    check_token(x_agent_token)
    if name not in container_names():
        raise HTTPException(status_code=404, detail="container not found")
    tail = max(10, min(tail, 2000))
    result = run(["docker", "logs", "--tail", str(tail), name])
    return (result.stdout + result.stderr).strip() or "(empty log)"
