"""
monitor_docker.py
=================
Monitorea el build Docker que corre en background en la Raspberry Pi.
No relanza el build, solo consulta el log y el estado de los contenedores.
"""
import os, sys, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from credentials import SSH_USER, SSH_PASSWORD, SSH_PORT, SSH_HOST_LOCAL
import paramiko

REMOTE_LOG = "/tmp/docker_build.log"

def ssh_run(client, cmd, sudo=False, timeout=20):
    if sudo:
        cmd = f"echo '{SSH_PASSWORD}' | sudo -S {cmd}"
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out, err

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(SSH_HOST_LOCAL, port=SSH_PORT, username=SSH_USER, password=SSH_PASSWORD,
               timeout=15, allow_agent=False, look_for_keys=False)
print("[OK] Conectado a la Raspberry Pi")

print(f"\n--- Monitoreando {REMOTE_LOG} ---")
for i in range(60):
    time.sleep(10)
    out, _ = ssh_run(client, f"tail -8 {REMOTE_LOG} 2>/dev/null")
    safe = out.encode('ascii', 'replace').decode('ascii')
    print(f"\n[{(i+1)*10}s]\n{safe}")

    fin, _ = ssh_run(client, f"grep -c 'BUILD FINALIZADO' {REMOTE_LOG} 2>/dev/null")
    if fin.strip() == "1":
        print("\n=== BUILD COMPLETADO ===")
        break

print("\n--- docker ps ---")
out, _ = ssh_run(client, "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'", sudo=True, timeout=15)
print(out.encode('ascii', 'replace').decode('ascii'))

print("\n--- Ultimas 30 lineas del log ---")
out, _ = ssh_run(client, f"tail -30 {REMOTE_LOG}")
print(out.encode('ascii', 'replace').decode('ascii'))

client.close()
