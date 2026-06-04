"""
fix_ssh_auth.py
===============
Script de diagnóstico y reparación de autenticación SSH.

Uso: python deploy\\fix_ssh_auth.py
"""
import sys
import os
import subprocess

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from credentials import SSH_HOST_LOCAL, SSH_USER, SSH_PASSWORD, SSH_PORT, NETBIRD_FQDN

import paramiko

def test_password(host, label, password):
    """Intenta autenticar con una contraseña dada."""
    try:
        t = paramiko.Transport((host, SSH_PORT))
        t.connect()
        t.auth_password(SSH_USER, password)
        t.close()
        return True
    except paramiko.AuthenticationException:
        return False
    except Exception as e:
        print(f"  [ERROR] {label}: {e}")
        return False


def main():
    print("\n=== DIAGNOSTICO DE AUTENTICACION SSH ===\n")
    
    # 1. Probar conectividad TCP
    hosts = [
        (SSH_HOST_LOCAL, "IP Local"),
        (NETBIRD_FQDN, "Netbird VPN"),
    ]
    
    reachable_host = None
    for host, label in hosts:
        try:
            t = paramiko.Transport((host, SSH_PORT))
            t.start_client(timeout=8)
            print(f"[OK] {label} ({host}) - TCP conectado, SSH handshake OK")
            
            # Obtener metodos de auth disponibles
            try:
                t.auth_none(SSH_USER)
            except paramiko.BadAuthenticationType as e:
                print(f"     Metodos de auth disponibles: {e.allowed_types}")
                methods = e.allowed_types
            except Exception:
                methods = ['password', 'publickey']
            
            t.close()
            reachable_host = (host, label)
            break
        except Exception as e:
            print(f"[FAIL] {label} ({host}): {e}")
    
    if not reachable_host:
        print("\n[ERROR] No se puede alcanzar la Raspberry Pi por ninguna via.")
        print("  -> Verifica que la Pi este encendida y conectada a la red.")
        sys.exit(1)
    
    host, label = reachable_host
    print(f"\n[*] Usando host: {label} ({host})")
    
    # 2. Probar contrasenas comunes
    passwords_to_try = [
        SSH_PASSWORD,          # 'taipt' del credentials.py
        "taipt_iot_2026",      # password del AP
        "raspberry",           # default Raspbian
        "user",                # username como pass
        "root",
        "",                    # sin contrasena
        "admin",
    ]
    
    print(f"\n[*] Probando {len(passwords_to_try)} contrasenas para usuario '{SSH_USER}'...")
    
    found_password = None
    for pwd in passwords_to_try:
        display = pwd if pwd else "(vacia)"
        try:
            t = paramiko.Transport((host, SSH_PORT))
            t.start_client(timeout=8)
            t.auth_password(SSH_USER, pwd)
            print(f"  [OK] Contrasena correcta: '{display}'")
            t.close()
            found_password = pwd
            break
        except paramiko.AuthenticationException:
            print(f"  [X]  '{display}' - INCORRECTO")
        except Exception as e:
            print(f"  [?]  '{display}' - Error: {e}")
    
    print()
    if found_password is not None:
        print("=" * 60)
        print(f"  CONTRASENA ENCONTRADA: '{found_password}'")
        print("=" * 60)
        print(f"\nActualiza credentials.py con:")
        print(f"  SSH_PASSWORD = \"{found_password}\"")
        
        # Actualizar credentials.py automáticamente
        try:
            creds_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'credentials.py'))
            with open(creds_path, 'r', encoding='utf-8') as f:
                content = f.read()
            content_new = content.replace(
                f'SSH_PASSWORD = "{SSH_PASSWORD}"',
                f'SSH_PASSWORD = "{found_password}"'
            )
            if content_new != content:
                with open(creds_path, 'w', encoding='utf-8') as f:
                    f.write(content_new)
                print(f"\n[AUTO] credentials.py actualizado con la nueva contrasena.")
                print(f"[AUTO] Ahora ejecuta: python deploy\\setup_remote_access.py")
            else:
                print(f"\n[INFO] credentials.py no cambio (misma contrasena).")
        except Exception as e:
            print(f"\n[WARN] No se pudo actualizar credentials.py automaticamente: {e}")
    else:
        print("=" * 60)
        print("  NINGUNA CONTRASENA FUNCIONA")
        print("=" * 60)
        print("""
La Raspberry Pi rechaza todas las contrasenas probadas.

SOLUCION: Necesitas acceso fisico o a la consola de la Pi.

Opcion A - Resetear la contrasena (acceso fisico):
  1. Conecta un teclado y monitor a la Raspberry Pi
  2. Inicia sesion con cualquier metodo disponible
  3. Ejecuta: sudo passwd user
  4. Ingresa la nueva contrasena dos veces
  5. Vuelve a ejecutar: python deploy\\setup_remote_access.py

Opcion B - Cambiar a autenticacion por clave SSH:
  1. En tu PC Windows, ejecuta:
       ssh-keygen -t ed25519 -f %USERPROFILE%\\.ssh\\id_rpi_ed25519
  2. Copia la clave publica a la Pi (requiere acceso fisico):
       type %USERPROFILE%\\.ssh\\id_rpi_ed25519.pub
  3. En la Pi, agrega esa clave a:
       ~/.ssh/authorized_keys

Opcion C - Verificar sshd_config en la Pi:
  Asegurate que /etc/ssh/sshd_config tenga:
       PasswordAuthentication yes
       UsePAM yes
""")


if __name__ == "__main__":
    main()
