"""
_run_netbird.py
===============
Configura la red Netbird en la Raspberry Pi via SSH (LAN 192.168.18.251).

Pasos:
  1. Conecta por SSH usando la IP LAN local
  2. Ejecuta: sudo netbird up --setup-key <KEY>  (en background)
  3. Espera 30s y verifica el estado final
"""
import sys
import time
sys.path.insert(0, r'c:\Users\ASUS\Documents\complexivo\Proyecto_grado')

from ssh_raspberry import RaspberrySSH
from credentials import SSH_USER, SSH_PASSWORD, SSH_PORT, SSH_HOST_LOCAL, NETBIRD_SETUP_KEY

RASPBERRY_IP = SSH_HOST_LOCAL  # 192.168.18.251


def main():
    print("=" * 55)
    print("  Configuracion Netbird via SSH")
    print(f"  Host : {RASPBERRY_IP}")
    print(f"  Key  : {NETBIRD_SETUP_KEY}")
    print("=" * 55)

    with RaspberrySSH(
        host=RASPBERRY_IP,
        user=SSH_USER,
        password=SSH_PASSWORD,
        port=SSH_PORT,
        timeout=15,
    ) as rpi:

        # ── 1. Ejecutar netbird down y logout ──────────────────────────────
        print("\n[1/4] Desconectando y cerrando sesion anterior de Netbird...")
        rpi.ejecutar_sudo("netbird down", timeout=30)
        rpi.ejecutar_sudo("netbird logout", timeout=30)

        # ── 2. Ejecutar netbird up con setup-key ───────────────────────────
        print("\n[2/4] Conectando a la nueva red con setup-key...")
        cmd = f"netbird up --setup-key {NETBIRD_SETUP_KEY}"
        res = rpi.ejecutar_sudo(cmd, timeout=120)
        print("Salida de netbird up:")
        print(res or "    (sin salida)")

        # ── 3. Esperar conexion ───────────────────────────────────────────
        print("\n[3/4] Esperando 10 segundos...")
        time.sleep(10)

        # ── 4. Verificar estado final ──────────────────────────────────────
        print("\n[4/4] Verificando estado final de Netbird:")

        # Usar exec_command directo
        s = rpi.ejecutar("netbird status", timeout=15)
        print(s or "    (sin salida)")

        # Mostrar IP VPN nueva si ya esta conectado
        print("\n--- Nueva IP Netbird (wt0) ---")
        ip = rpi.ejecutar(
            "ip addr show wt0 2>/dev/null | grep 'inet ' | awk '{print $2}' "
            "|| echo '(interfaz wt0 aun no disponible)'",
            timeout=10,
        )
        print(ip)

    print("\n[OK] Script finalizado.")


if __name__ == "__main__":
    main()
