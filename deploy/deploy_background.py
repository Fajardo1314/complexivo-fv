"""
deploy_background.py
====================
Despliegue optimizado: lanza el docker compose build en background (nohup)
en la Raspberry Pi para evitar timeouts SSH. Luego monitorea el progreso
consultando el log remoto.
"""
import os
import sys
import time
import paramiko

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from credentials import SSH_USER, SSH_PASSWORD, SSH_PORT, SSH_HOST_LOCAL

REMOTE_DIR = "/home/user/proyecto_grado"
REMOTE_LOG  = "/tmp/docker_build.log"

def ejecutar(client, cmd, run_as_sudo=False, timeout=30):
    if run_as_sudo:
        cmd = f"echo '{SSH_PASSWORD}' | sudo -S {cmd}"
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out, err

def conectar():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=SSH_HOST_LOCAL,
        port=SSH_PORT,
        username=SSH_USER,
        password=SSH_PASSWORD,
        timeout=15,
        allow_agent=False,
        look_for_keys=False,
    )
    return client

def subir_directorio(sftp, local_dir, remote_dir):
    try:
        sftp.mkdir(remote_dir)
    except IOError:
        pass
    for item in os.listdir(local_dir):
        local_path = os.path.join(local_dir, item)
        remote_path = f"{remote_dir}/{item}"
        if os.path.isdir(local_path):
            if item in ('.git', '__pycache__', 'deploy'):
                continue
            subir_directorio(sftp, local_path, remote_path)
        else:
            if item.endswith('.pyc'):
                continue
            print(f"  [SFTP] {item}")
            sftp.put(local_path, remote_path)

def main():
    print("=" * 65)
    print("  DESPLIEGUE DOCKER EN RASPBERRY PI (modo background)")
    print(f"  Host: {SSH_HOST_LOCAL}")
    print("=" * 65)

    # ── 1. Subir archivos (siempre necesario para sincronizar cambios) ─
    print("\n[1/5] Conectando y subiendo archivos...")
    client = conectar()
    print("  [OK] Conectado.")

    sftp = client.open_sftp()
    ejecutar(client, f"mkdir -p {REMOTE_DIR}")

    base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    archivos = [
        "main_control.py", "automation.py", "credentials.py",
        "google-services.json", "requirements.txt",
        "Dockerfile.control", "Dockerfile.automation",
        "nginx.conf", "docker-compose.yml"
    ]
    for f in archivos:
        lp = os.path.join(base, f)
        if os.path.exists(lp):
            print(f"  [SFTP] {f}")
            sftp.put(lp, f"{REMOTE_DIR}/{f}")
    subir_directorio(sftp, os.path.join(base, "web_dashboard"), f"{REMOTE_DIR}/web_dashboard")
    sftp.close()
    print("  [OK] Archivos subidos.")

    # ── 2. Instalar dependencias extras si faltan ──────────────────────
    print("\n[2/5] Verificando paquetes del sistema...")

    # docker ya instalado, pero verificar docker-buildx
    out, _ = ejecutar(client, "docker buildx version", run_as_sudo=True, timeout=10)
    if "buildx" not in out.lower():
        print("  -> Instalando docker-buildx...")
        ejecutar(client, "pacman -Sy --noconfirm docker-buildx", run_as_sudo=True, timeout=120)

    # ── 3. Firewall ────────────────────────────────────────────────────
    print("\n[3/5] Verificando reglas de firewall...")
    for puerto in ["80/tcp", "5000/tcp", "1883/tcp", "443/tcp"]:
        out, _ = ejecutar(client, f"firewall-cmd --query-port={puerto}", run_as_sudo=True, timeout=10)
        if out.strip() != "yes":
            ejecutar(client, f"firewall-cmd --permanent --add-port={puerto}", run_as_sudo=True, timeout=10)
            print(f"  -> Puerto {puerto} abierto.")
        else:
            print(f"  [OK] Puerto {puerto} ya estaba abierto.")
    ejecutar(client, "firewall-cmd --reload", run_as_sudo=True, timeout=10)

    # ── 4. Build en background con nohup ──────────────────────────────
    print("\n[4/5] Lanzando 'docker compose up --build' en background...")
    build_script = (
        f"#!/bin/sh\n"
        f"cd {REMOTE_DIR}\n"
        f"docker-compose down 2>&1 | tee {REMOTE_LOG}\n"
        f"docker-compose up --build -d 2>&1 | tee -a {REMOTE_LOG}\n"
        f"echo '=== BUILD FINALIZADO ===' >> {REMOTE_LOG}\n"
    )

    # Escribir script de build en la Raspberry
    build_sh = f"{REMOTE_DIR}/build_docker.sh"
    sftp = client.open_sftp()
    with sftp.open(build_sh, 'w') as f:
        f.write(build_script)
    sftp.close()

    # Dar permisos y ejecutar en background
    ejecutar(client, f"chmod +x {build_sh}")
    ejecutar(client, f"nohup sh {build_sh} >/dev/null 2>&1 &", run_as_sudo=True, timeout=10)
    print("  [OK] Build iniciado en background.")

    # ── 5. Monitorear log hasta que finalice ──────────────────────────
    print(f"\n[5/5] Monitoreando progreso (log: {REMOTE_LOG})...")
    print("      Esto puede tardar 5-10 minutos...")
    print("-" * 65)

    intentos = 0
    max_espera = 600  # 10 minutos máximo

    while intentos < max_espera // 10:
        time.sleep(10)
        intentos += 1
        out, _ = ejecutar(client, f"tail -5 {REMOTE_LOG} 2>/dev/null")
        safe_out = out.encode('ascii', 'replace').decode('ascii')
        print(f"  [{intentos*10}s] {safe_out[:120]}")

        # Verificar si el build finalizó
        fin, _ = ejecutar(client, f"grep -c 'BUILD FINALIZADO' {REMOTE_LOG} 2>/dev/null")
        if fin.strip() == "1":
            print("\n  [OK] Build completado.")
            break

    # Mostrar resultado final
    print("\n--- Estado final de contenedores ---")
    out, _ = ejecutar(client, "docker ps --format 'table {{.Names}}\\t{{.Status}}\\t{{.Ports}}'", run_as_sudo=True, timeout=15)
    print(out)

    print("\n--- Ultimas líneas del log ---")
    out, _ = ejecutar(client, f"tail -20 {REMOTE_LOG}")
    print(out)

    print("\n" + "=" * 65)
    print("  [OK] Despliegue completado.")
    print(f"  Dashboard -> http://{SSH_HOST_LOCAL}")
    print(f"  Dashboard -> http://100.105.63.234  (Netbird VPN)")
    print(f"  Flask API -> http://{SSH_HOST_LOCAL}:5000/api/sensores")
    print("=" * 65)
    client.close()

if __name__ == "__main__":
    main()
