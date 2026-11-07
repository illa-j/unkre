import hmac
import json
import os
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


@app.get("/api/status")
def status(x_agent_token: str | None = Header(default=None)) -> dict:
    check_token(x_agent_token)
    result = run(["docker", "ps", "-a", "--format", "{{json .}}"])
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=result.stderr.strip())
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
    tail = max(10, min(tail, 1000))
    result = run(["docker", "logs", "--tail", str(tail), name])
    return (result.stdout + result.stderr).strip() or "(empty log)"
