"""
setup_remote_access.py
======================
Script de configuración automática para:
  1. xRDP   → Escritorio remoto (puerto 3389) desde Windows mstsc
  2. Node-RED → Dashboard visual en el puerto 1880
  3. sudo sin contraseña → Necesario para shutdown/reboot desde Node-RED
  4. Firewall → Abre los puertos 1880 y 3389

Ejecutar desde Windows con Python instalado:
  cd C:\\Users\\ASUS\\Documents\\complexivo\\Proyecto_grado\\deploy
  python setup_remote_access.py
"""

import os
import sys
import time
import json

# Fix UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from credentials import SSH_HOST_LOCAL, SSH_USER, SSH_PASSWORD, SSH_PORT, NETBIRD_FQDN

try:
    import paramiko
except ImportError:
    print("[ERROR] Librería 'paramiko' no instalada. Ejecuta: pip install paramiko")
    sys.exit(1)

REMOTE_DIR     = "/home/user/proyecto_grado"
NODERED_DATA   = f"{REMOTE_DIR}/nodered_data"

BANNER = """
+================================================================+
|   CONFIGURACION DE ACCESO REMOTO - PROYECTO DE GRADO          |
|   > xRDP   (Escritorio Remoto / mstsc)     ->  puerto 3389    |
|   > Node-RED (Dashboard IoT)               ->  puerto 1880    |
+================================================================+
"""


def run(client, cmd, use_sudo=False, timeout=120, ignore_errors=False):
    """Ejecuta un comando SSH, opcionalmente con sudo."""
    if use_sudo:
        cmd = f"echo '{SSH_PASSWORD}' | sudo -S bash -c \"{cmd}\""
    print(f"  $ {cmd[:90]}{'...' if len(cmd) > 90 else ''}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    # Filtrar mensajes de sudo de stderr
    err_filtered = '\n'.join(
        l for l in err.splitlines()
        if not l.startswith('[sudo]') and 'password for' not in l
    ).strip()
    if out:
        print(f"    -> {out[:200]}")
    if err_filtered and not ignore_errors:
        print(f"    [WARN] {err_filtered[:200]}")
    return out, err_filtered


def connect_ssh():
    """Crea y devuelve un cliente SSH conectado a la Raspberry Pi.
    
    Usa múltiples estrategias para compatibilidad con OpenSSH 10.3+
    (que puede rechazar ciertos algoritmos de paramiko por defecto).
    """
    hosts_to_try = [
        (SSH_HOST_LOCAL, f"IP Local ({SSH_HOST_LOCAL})"),
        (NETBIRD_FQDN,   f"Netbird VPN ({NETBIRD_FQDN})")
    ]
    
    # Estrategias de conexión: primero normal, luego con algoritmos deshabilitados
    strategies = [
        # Estrategia 1: conexión estándar
        dict(
            allow_agent=False,
            look_for_keys=False,
        ),
        # Estrategia 2: deshabilitar algoritmos problemáticos con OpenSSH 10.x
        dict(
            allow_agent=False,
            look_for_keys=False,
            disabled_algorithms={
                "pubkeys": ["rsa-sha2-256", "rsa-sha2-512"],
            },
        ),
        # Estrategia 3: autenticación por teclado interactivo
        dict(
            allow_agent=False,
            look_for_keys=False,
            auth_strategy=None,
        ),
    ]
    
    for host, label in hosts_to_try:
        for i, extra_kwargs in enumerate(strategies, 1):
            try:
                print(f"  [*] Intentando conectar a {label} (estrategia {i})...")
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(
                    hostname=host,
                    port=SSH_PORT,
                    username=SSH_USER,
                    password=SSH_PASSWORD,
                    timeout=12,
                    **extra_kwargs
                )
                print(f"  [OK] Conectado exitosamente via {label}")
                return client, host
            except paramiko.AuthenticationException as e:
                print(f"  [FAIL Auth] {label} estrategia {i}: {e}")
                # Intentar con keyboard-interactive como fallback
                try:
                    client2 = paramiko.SSHClient()
                    client2.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    transport = client2.get_transport()
                    client2.connect(
                        hostname=host,
                        port=SSH_PORT,
                        username=SSH_USER,
                        password=SSH_PASSWORD,
                        timeout=12,
                        allow_agent=False,
                        look_for_keys=False,
                        gss_auth=False,
                        gss_kex=False,
                    )
                    print(f"  [OK] Conectado via {label} (fallback gss_auth=False)")
                    return client2, host
                except Exception as e2:
                    print(f"  [FAIL Fallback] {label}: {e2}")
                break  # Si falla auth, no tiene sentido reintentar otras estrategias para el mismo host
            except Exception as e:
                print(f"  [FAIL] {label} estrategia {i}: {e}")
                break
    
    raise ConnectionError(
        "No se pudo autenticar en la Raspberry Pi.\n"
        f"  Usuario: {SSH_USER}\n"
        f"  Contrasena: {SSH_PASSWORD}\n"
        "  Verifica que la contrasena sea correcta ejecutando en la Pi:\n"
        "    sudo passwd user\n"
        "  O activa PasswordAuthentication en /etc/ssh/sshd_config"
    )


def configure_sudo_nopasswd(client):
    """Configura sudo sin contraseña para el usuario 'user' (necesario para shutdown/reboot)."""
    print("\n[1/5] Configurando sudo sin contraseña (para Node-RED control del sistema)...")
    
    sudoers_rule = f"{SSH_USER} ALL=(ALL) NOPASSWD: /sbin/shutdown, /sbin/reboot, /sbin/poweroff, /bin/systemctl"
    sudoers_file = f"/etc/sudoers.d/99-{SSH_USER}-nopasswd"
    
    # Escribir archivo de sudoers
    cmd = f"echo '{sudoers_rule}' | sudo tee {sudoers_file} && sudo chmod 440 {sudoers_file}"
    out, err = run(client, cmd, use_sudo=False)
    
    # Verificar sintaxis
    run(client, f"visudo -c -f {sudoers_file}", use_sudo=True, ignore_errors=True)
    print("  [OK] sudo sin contraseña configurado para shutdown/reboot.")


def install_xfce_and_xrdp(client):
    """Instala XFCE4 (escritorio ligero) y xRDP para acceso remoto desde Windows."""
    print("\n[2/5] Instalando entorno gráfico XFCE4 y xRDP...")
    
    # Actualizar base de datos de paquetes
    print("  [OK] Actualizando base de datos de paquetes de pacman (puede tardar)...")
    run(client, "pacman -Sy --noconfirm", use_sudo=True, timeout=300)
    
    # Verificar si XFCE ya está instalado
    out, _ = run(client, "pacman -Q xfce4 2>/dev/null || echo 'NOT_INSTALLED'", timeout=30)
    if "NOT_INSTALLED" in out:
        print("  -> Instalando XFCE4 (escritorio ligero, ~150MB)...")
        run(client, "pacman -S --noconfirm xfce4 xfce4-goodies", use_sudo=True, timeout=600)
        print("  [OK] XFCE4 instalado.")
    else:
        print("  [OK] XFCE4 ya estaba instalado.")
    
    # Verificar si xRDP ya está instalado
    out, _ = run(client, "pacman -Q xrdp 2>/dev/null || echo 'NOT_INSTALLED'", timeout=30)
    if "NOT_INSTALLED" in out:
        print("  → Instalando xRDP y xorgxrdp (puede tardar)...")
        # En Arch/EndeavourOS, xrdp puede estar en AUR. Primero intentar con paru/yay
        # Verificar si hay AUR helper disponible
        out_paru, _ = run(client, "which paru 2>/dev/null || which yay 2>/dev/null || echo ''", timeout=10)
        
        if out_paru.strip():
            aur_helper = out_paru.strip().split('\n')[0]
            print(f"  -> Usando AUR helper: {aur_helper}")
            run(client, f"{aur_helper} -S --noconfirm xrdp xorgxrdp", timeout=600)
        else:
            # Intentar instalar desde repositorios extra/community (puede estar disponible)
            run(client, "pacman -S --noconfirm xrdp", use_sudo=True, timeout=300, ignore_errors=True)
    else:
        print("  [OK] xRDP ya estaba instalado.")
    
    # Configurar sesión XFCE para xRDP
    print("  → Configurando sesión XFCE para xRDP...")
    xsession_content = "startxfce4"
    run(client, f"echo '{xsession_content}' | tee /home/{SSH_USER}/.xsession", use_sudo=False, timeout=10)
    run(client, f"chmod +x /home/{SSH_USER}/.xsession", timeout=10)
    
    # Configurar xRDP para usar XFCE
    startwm_content = "startxfce4"
    run(client, f"echo '#!/bin/sh\\n{startwm_content}' | sudo tee /etc/xrdp/startwm.sh", timeout=10)
    run(client, "chmod +x /etc/xrdp/startwm.sh", use_sudo=True, timeout=10)
    
    # Habilitar e iniciar servicio xRDP
    print("  -> Habilitando servicio xRDP (puerto 3389)...")
    run(client, "systemctl enable --now xrdp", use_sudo=True, timeout=30)
    
    # Verificar estado
    out, _ = run(client, "systemctl is-active xrdp", timeout=10)
    if out.strip() == "active":
        print("  [OK] xRDP está activo y escuchando en el puerto 3389.")
    else:
        print(f"  [WARN] Estado de xRDP: {out} - puede necesitar reinicio.")
    
    return True


def open_firewall_ports(client):
    """Abre los puertos necesarios en firewalld."""
    print("\n[3/5] Configurando reglas de Firewall...")
    
    out, _ = run(client, "systemctl is-active firewalld", timeout=10)
    if out.strip() != "active":
        print("  [INFO] firewalld no está activo. Verificando iptables...")
        # Intentar abrir con iptables como fallback
        ports_tcp = [1880, 3389]
        for port in ports_tcp:
            run(client, f"iptables -I INPUT -p tcp --dport {port} -j ACCEPT", use_sudo=True, timeout=10, ignore_errors=True)
        print("  [OK] Puertos abiertos via iptables (no persistente en reinicios).")
        return

    puertos = {
        "1880/tcp": "Node-RED",
        "3389/tcp": "xRDP (Escritorio Remoto)",
        "3389/udp": "xRDP (Escritorio Remoto UDP)",
    }
    
    for puerto, desc in puertos.items():
        out, _ = run(client, f"firewall-cmd --permanent --add-port={puerto}", use_sudo=True, timeout=15)
        estado = "OK" if "success" in out.lower() or "already" in out.lower() else "WARN"
        print(f"  [{estado}] Puerto {puerto} ({desc})")
    
    run(client, "firewall-cmd --reload", use_sudo=True, timeout=15)
    print("  [OK] Reglas de firewall aplicadas y recargadas.")


def deploy_nodered(client, sftp):
    """Sube nodered_data/flows.json y levanta el contenedor de Node-RED."""
    print("\n[4/5] Desplegando Node-RED...")
    
    # Crear directorio de datos de Node-RED en la Pi
    run(client, f"mkdir -p {NODERED_DATA}", timeout=15)
    
    # Subir el flujo de Node-RED
    local_flows = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'nodered_data', 'flows.json'))
    remote_flows = f"{NODERED_DATA}/flows.json"
    
    if os.path.exists(local_flows):
        print(f"  → Subiendo flows.json a {remote_flows}...")
        sftp.put(local_flows, remote_flows)
        print("  [OK] Flujo de Node-RED subido.")
    else:
        print(f"  [WARN] No se encontró {local_flows}. Node-RED iniciará sin flujo pre-configurado.")
    
    # Subir docker-compose.yml actualizado
    local_compose = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docker-compose.yml'))
    remote_compose = f"{REMOTE_DIR}/docker-compose.yml"
    sftp.put(local_compose, remote_compose)
    print("  [OK] docker-compose.yml actualizado en la Pi.")
    
    # Subir nginx.conf actualizado
    local_nginx = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'nginx.conf'))
    remote_nginx = f"{REMOTE_DIR}/nginx.conf"
    sftp.put(local_nginx, remote_nginx)
    print("  [OK] nginx.conf actualizado en la Pi.")
    
    # Subir main_control.py actualizado (con endpoints /shutdown, /reboot, /status)
    local_main = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'main_control.py'))
    remote_main = f"{REMOTE_DIR}/main_control.py"
    sftp.put(local_main, remote_main)
    print("  [OK] main_control.py actualizado en la Pi.")
    
    # Levantar o actualizar contenedores (sin rebuild para ser rápido)
    print("  → Levantando contenedores (docker compose up -d)...")
    compose_up = (
        f"cd {REMOTE_DIR} && "
        f"echo '{SSH_PASSWORD}' | sudo -S docker compose up -d --pull missing 2>&1 | tail -20"
    )
    out, err = run(client, compose_up, timeout=300)
    
    # Verificar que nodered está corriendo
    time.sleep(5)
    out, _ = run(client, "docker inspect --format='{{.State.Status}}' nodered 2>/dev/null || echo 'not_found'", use_sudo=True, timeout=15)
    if "running" in out:
        print("  [OK] Contenedor Node-RED está corriendo.")
    else:
        print(f"  [INFO] Estado del contenedor nodered: {out}")
    
    # Instalar node-red-dashboard dentro del contenedor
    print("  → Instalando node-red-dashboard (plugin UI)...")
    install_dashboard_cmd = (
        "docker exec nodered bash -c "
        "'cd /data && npm install node-red-dashboard 2>&1 | tail -5' 2>/dev/null"
    )
    run(client, install_dashboard_cmd, use_sudo=True, timeout=120, ignore_errors=True)
    
    # Reiniciar Node-RED para aplicar el plugin
    print("  → Reiniciando Node-RED para aplicar el dashboard...")
    run(client, "docker restart nodered", use_sudo=True, timeout=30)
    time.sleep(8)
    print("  [OK] Node-RED con dashboard listo.")


def print_summary(host):
    """Imprime el resumen final con todos los enlaces de acceso."""
    netbird_host = NETBIRD_FQDN
    local_host   = SSH_HOST_LOCAL
    
    sep = "=" * 68
    print("\n" + sep)
    print("  [OK] CONFIGURACION COMPLETADA EXITOSAMENTE")
    print(sep)
    print()
    print("  [ESCRITORIO REMOTO] Conexion desde Windows (mstsc)")
    print(f"       1. Abre 'Conexion a Escritorio Remoto' (tecla Win, busca mstsc)")
    print(f"       2. Equipo: raspberryfv.nb  o  {local_host}")
    print(f"       3. Usuario: {SSH_USER}")
    print(f"       4. Contrasena: {SSH_PASSWORD}")
    print(f"       AVISO: Asegurate de tener Netbird conectado en tu PC Windows")
    print()
    print("  [NODE-RED EDITOR] Para editar flujos:")
    print(f"       http://{netbird_host}:1880")
    print(f"       http://{local_host}:1880  (red local)")
    print()
    print("  [NODE-RED DASHBOARD] Apagar / Reiniciar la Pi:")
    print(f"       http://{netbird_host}:1880/ui")
    print(f"       http://{local_host}:1880/ui  (red local)")
    print()
    print("  [WEB DASHBOARD] Panel principal del proyecto:")
    print(f"       http://{netbird_host}")
    print(f"       http://{local_host}")
    print()
    print("  NOTA: Para encender la Pi despues de apagarla,")
    print("        necesitaras acceso fisico o Wake-on-LAN.")
    print(sep)


def main():
    print(BANNER)
    
    client = None
    try:
        # ── Conectar SSH ──────────────────────────────────────────────────────
        print("[*] Conectando a la Raspberry Pi...")
        client, connected_host = connect_ssh()
        sftp = client.open_sftp()
        
        # ── Paso 1: sudo sin contraseña ───────────────────────────────────────
        configure_sudo_nopasswd(client)
        
        # ── Paso 2: XFCE + xRDP ──────────────────────────────────────────────
        install_xfce_and_xrdp(client)
        
        # ── Paso 3: Firewall ──────────────────────────────────────────────────
        open_firewall_ports(client)
        
        # ── Paso 4: Node-RED ──────────────────────────────────────────────────
        deploy_nodered(client, sftp)
        
        # ── Paso 5: Verificación final ────────────────────────────────────────
        print("\n[5/5] Verificación final de servicios...")
        run(client, "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'", use_sudo=True, timeout=15)
        run(client, "systemctl is-active xrdp", timeout=10)
        
        sftp.close()
        print_summary(connected_host)
        
    except ConnectionError as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR INESPERADO] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if client:
            client.close()


if __name__ == "__main__":
    main()
