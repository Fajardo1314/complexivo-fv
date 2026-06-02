"""Sube main_control.py parcheado y reinicia backend-control con sudo sh -c."""
import sys, os, time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from credentials import SSH_USER, SSH_PASSWORD, SSH_PORT, SSH_HOST_LOCAL
import paramiko

REMOTE_DIR = "/home/user/proyecto_grado"
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

def run(client, cmd, timeout=30):
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out, err

def sudo(client, cmd, timeout=30):
    return run(client, f"echo '{SSH_PASSWORD}' | sudo -S sh -c \"{cmd}\"", timeout=timeout)

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(SSH_HOST_LOCAL, port=SSH_PORT, username=SSH_USER, password=SSH_PASSWORD,
               timeout=15, allow_agent=False, look_for_keys=False)
print("[OK] Conectado")

# 1. Subir main_control.py
print("[1] Subiendo main_control.py...")
sftp = client.open_sftp()
sftp.put(os.path.join(BASE, "main_control.py"), f"{REMOTE_DIR}/main_control.py")
sftp.close()
print("    [OK] Subido")

# 2. Reconstruir solo backend-control
print("[2] Reconstruyendo backend-control...")
out, err = sudo(client,
    f"cd {REMOTE_DIR} && docker-compose up --build -d --no-deps backend-control",
    timeout=300
)
print("OUT:", out.encode('ascii','replace').decode('ascii'))
print("ERR:", err.encode('ascii','replace').decode('ascii'))

# 3. Esperar y verificar
print("[3] Esperando 10s...")
time.sleep(10)

out, _ = sudo(client, "docker ps --format 'table {{.Names}}\\t{{.Status}}'", timeout=15)
print("\n--- Estado contenedores ---")
print(out.encode('ascii','replace').decode('ascii'))

out, _ = sudo(client, "docker logs backend-control --tail 25", timeout=15)
print("\n--- Logs backend-control ---")
print(out.encode('ascii','replace').decode('ascii'))

client.close()
