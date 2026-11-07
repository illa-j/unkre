from pathlib import Path

path = Path("/etc/supervisor/conf.d/stack.conf")
lines = path.read_text().splitlines()
result = []
skip = False
for line in lines:
    stripped = line.strip()
    if stripped in {"[program:nginx-unkre]", "[program:nginx-nocensgen]"}:
        skip = True
        continue
    if skip and stripped.startswith("[") and stripped.endswith("]"):
        skip = False
    if not skip:
        result.append(line)
path.write_text("\n".join(result) + "\n")
print("nginx programs removed from supervisor")
