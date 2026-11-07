# Home Lab panel v2

Панель для керування телефоном (Termux + Debian proot) і ПК (Docker) з будь-якого браузера в мережі роутера.

## Можливості

- вхід через окрему сторінку логіна (cookie-сесія, без Basic Auth popup);
- захист від перебору пароля (5 спроб / 5 хвилин);
- статус сервісів телефону: SSH, PostgreSQL, Redis, Cloudflare Tunnel, nginx, proot-стек, сама панель;
- health-check замість сліпого `sv status` (порти, `pg_isready`, `redis-cli ping`, HTTP);
- керування proot-стеком окремими скриптами (`stack-start.sh`, `stack-stop.sh`) без дублювання процесів;
- статус усіх Docker-контейнерів ПК, CPU/RAM по кожному, start/stop/restart, логи;
- системні метрики телефону: RAM, диск, load, температура, модель, Android, wake lock;
- системні метрики ПК: RAM, диск, load, uptime, Docker, GPU (якщо є `nvidia-smi`);
- пошук по контейнерах, автооновлення 5/10/30/60 с, темна/світла тема;
- логи з оновленням, копіюванням і завантаженням;
- швидкі дії: wake lock, перезапуск стеку, перезапуск nginx, підняти SSH;
- історія останніх дій;
- посилання на всі сайти й адмінки з індикацією online/offline.

## Архітектура

```text
Телефон
  Termux / runit
    sshd, postgres, redis, cloudflared, panel
    nginx-unkre      :18080 / :18081
    nginx-nocensgen  :18082 / :18083
  Debian proot / supervisord
    UNKRE API :8000, worker
    NoCensGen API :8001, worker
    Next.js :3000 / :3001
    MinIO :9000
  Cloudflare Tunnel

ПК
  Docker: UNKRE, NoCensGen, WYNC, Persk, Wildfield
  homelab-agent :8091 (systemd user service)
```

`nginx` працює **нативно в Termux** (не в proot), бо proot на Android 16 має проблеми з `epoll_wait` для nginx. Застосунки й MinIO працюють у Debian proot.

## Встановлення

### ПК

```bash
AGENT_TOKEN='<token>' bash install-agent.sh
```

Агент слухає `0.0.0.0:8091`, керує Docker CLI, захищений `X-Agent-Token`.

### Телефон

```bash
PC_AGENT_TOKEN='<token>' PANEL_PASSWORD='<password>' \
  bash install-panel.sh
```

Скрипт ставить Termux-пакети, створює runit-сервіси `panel`, `nginx-unkre`, `nginx-nocensgen`, налаштовує proot-стек, автозапуск і друкує URL/пароль.

## Керування

```bash
sv status panel nginx-unkre nginx-nocensgen sshd postgres redis cloudflared
sv restart panel
tail -f $PREFIX/var/log/sv/panel/current
```

Стек:

```bash
bash ~/stack-start.sh
bash ~/stack-stop.sh
```

ПК:

```bash
systemctl --user status homelab-agent
systemctl --user restart homelab-agent
```

## Автозапуск

- `~/.bashrc` піднімає `runsvdir` і proot-стек при відкритті Termux;
- `~/.termux/boot/start-all.sh` — для Termux:Boot;
- на ПК — systemd user service `homelab-agent` з `loginctl enable-linger`.

## Телефон не засинає

На POCO F6 через ADB застосовано:

```bash
adb shell dumpsys deviceidle whitelist +com.termux
adb shell cmd appops set com.termux RUN_ANY_IN_BACKGROUND allow
adb shell am set-standby-bucket com.termux active
adb shell device_config put activity_manager max_phantom_processes 2147483647
adb shell appops set com.android.shell WRITE_SETTINGS allow
adb shell settings put system screen_off_timeout 2147483647
```

Плюс `termux-wake-lock` у `.bashrc` і кнопка **Wake lock** у панелі.

Повернути звичайний таймаут екрана:

```bash
adb shell settings put system screen_off_timeout 600000
```
