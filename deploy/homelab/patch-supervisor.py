from pathlib import Path

path = Path("/etc/supervisor/supervisord.conf")
lines = path.read_text().splitlines()
remove_sections = {"[unix_http_server]", "[inet_http_server]", "[supervisorctl]", "[rpcinterface:supervisor]"}
result = []
skip = False
for line in lines:
    stripped = line.strip()
    if stripped in remove_sections:
        skip = True
        continue
    if skip and stripped.startswith("[") and stripped.endswith("]"):
        skip = False
    if not skip:
        result.append(line)
path.write_text("\n".join(result) + "\n")
print("supervisor config cleaned")
