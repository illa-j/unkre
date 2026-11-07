# Home Lab panel

Невелика панель для керування двома хостами:

- **Телефон (Termux + Debian proot)** — runit-сервіси: `sshd`, `postgres`, `redis`, `cloudflared`, `stack`.
- **ПК (Docker)** — контейнери через маленький агент на `:8091`.

## ПК: агент

```bash
AGENT_TOKEN='<token>' bash install-agent.sh
```

Агент слухає `0.0.0.0:8091`, керує Docker CLI, захищений заголовком `X-Agent-Token`.
Сервіс systemd: `systemctl --user status homelab-agent`.

## Телефон: панель

```bash
PC_AGENT_TOKEN='<token>' bash install-panel.sh
```

Панель ставиться як runit-сервіс `panel`, слухає `0.0.0.0:8090`.
Логін/пароль генеруються під час встановлення і друкуються в кінці.
Керування: `sv status panel`, `sv restart panel`.

## Що відкривається в LAN

- Телефон: `http://<phone>:8090` — панель
- Телефон: `http://<phone>:18080` — UNKRE, `:18082` — NoCensGen
- Телефон: `http://<phone>:18081` / `:18083` — адмінки
- ПК: `http://<pc>:18080` / `:18082` — сайти, `:18081` / `:18083` — адмінки
- ПК: `http://<pc>:8089` — WYNC, `http://<pc>/` — Persk, `http://<pc>:8088` — Wildfield
