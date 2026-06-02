import os
import sys
import time
import paramiko

# Agregar el directorio principal al PATH para importar las credenciales
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from credentials import SSH_USER, SSH_PASSWORD, SSH_PORT, SSH_HOST_LOCAL

# Ruta del proyecto en la Raspberry Pi
REMOTE_DIR = "/home/user/proyecto_grado"

def ejecutar_comando(client, cmd, run_as_sudo=False):
    """Ejecuta un comando SSH, manejando sudo de ser necesario."""
    if run_as_sudo:
        cmd = f"echo '{SSH_PASSWORD}' | sudo -S {cmd}"
    
    stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out, err

def subir_directorio(sftp, local_dir, remote_dir):
    """Sube un directorio completo de manera recursiva vía SFTP."""
    try:
        sftp.mkdir(remote_dir)
        print(f"  [SFTP] Creado directorio remoto: {remote_dir}")
    except IOError:
        pass # Ya existe
    
    for item in os.listdir(local_dir):
        local_path = os.path.join(local_dir, item)
        # Reemplazar barras invertidas en Windows
        remote_path = f"{remote_dir}/{item}"
        
        if os.path.isdir(local_path):
            if item in ('.git', '__pycache__', 'deploy'):
                continue
            subir_directorio(sftp, local_path, remote_path)
        else:
            if item.endswith('.pyc') or item in ('_fix_dns.py', '_run_netbird.py'):
                continue
            print(f"  [SFTP] Subiendo: {item} -> {remote_path}")
            sftp.put(local_path, remote_path)

def main():
    print("=" * 65)
    print("      AUTOMATIZACION DE DESPLIEGUE A RASPBERRY PI (DOCKER)")
    print(f"      Host de Destino Local: {SSH_HOST_LOCAL}")
    print("=" * 65)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print("\n[*] 1. Conectando a la Raspberry Pi por SSH...")
        client.connect(
            hostname=SSH_HOST_LOCAL,
            port=SSH_PORT,
            username=SSH_USER,
            password=SSH_PASSWORD,
            timeout=15,
            allow_agent=False,
            look_for_keys=False
        )
        print("[OK] Conexión establecida.")

        # --- 2. Verificar e Instalar Docker ---
        print("\n[*] 2. Verificando requerimientos de Docker...")
        out, _ = ejecutar_comando(client, "which docker")
        
        if not out:
            print("  -> Docker no está instalado. Instalando vía pacman...")
            # En EndeavourOS (Arch), docker y docker-compose están en repositorios oficiales
            install_cmd = "pacman -Sy --noconfirm docker docker-compose"
            out, err = ejecutar_comando(client, install_cmd, run_as_sudo=True)
            print(out)
            if err and "error" in err.lower():
                print(f"[ERROR] Error al instalar Docker: {err}")
                sys.exit(1)
        else:
            print("  [OK] Docker ya está instalado en el sistema.")

        # Habilitar e iniciar servicio Docker
        print("  -> Asegurando que el daemon de Docker esté iniciado...")
        ejecutar_comando(client, "systemctl enable --now docker", run_as_sudo=True)
        # Añadir usuario al grupo docker
        ejecutar_comando(client, f"usermod -aG docker {SSH_USER}", run_as_sudo=True)

        # --- 3. Configurar Firewall (Firewalld) ---
        print("\n[*] 3. Configurando reglas de Firewall (firewalld)...")
        # Verificar si firewalld está activo
        out, _ = ejecutar_comando(client, "systemctl is-active firewalld")
        if out == "active":
            print("  -> firewalld activo. Abriendo puertos para Dashboard, Flask API y MQTT...")
            puertos = ["80/tcp", "5000/tcp", "1883/tcp", "443/tcp"]
            for puerto in puertos:
                cmd = f"firewall-cmd --permanent --add-port={puerto}"
                out, _ = ejecutar_comando(client, cmd, run_as_sudo=True)
                print(f"     Port {puerto}: {out}")
            
            ejecutar_comando(client, "firewall-cmd --reload", run_as_sudo=True)
            print("  [OK] Reglas de firewall aplicadas y recargadas.")
        else:
            print("  [WARNING] firewalld no está activo o no está instalado. Asegúrate de proteger tus puertos.")

        # --- 4. Subir archivos por SFTP ---
        print("\n[*] 4. Subiendo código fuente y configuración...")
        sftp = client.open_sftp()
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        
        # Crear carpeta de destino
        ejecutar_comando(client, f"mkdir -p {REMOTE_DIR}")
        
        # Subir archivos raíz
        archivos_raiz = [
            "main_control.py",
            "automation.py",
            "credentials.py",
            "google-services.json",
            "requirements.txt",
            "Dockerfile.control",
            "Dockerfile.automation",
            "nginx.conf",
            "docker-compose.yml"
        ]
        
        for file in archivos_raiz:
            local_file = os.path.join(base_path, file)
            remote_file = f"{REMOTE_DIR}/{file}"
            if os.path.exists(local_file):
                print(f"  [SFTP] Subiendo: {file} -> {remote_file}")
                sftp.put(local_file, remote_file)
            else:
                print(f"  [WARNING] Archivo local no encontrado: {file}")

        # Subir directorio del web dashboard
        subir_directorio(sftp, os.path.join(base_path, "web_dashboard"), f"{REMOTE_DIR}/web_dashboard")
        sftp.close()
        print("[OK] Carga de archivos completada.")

        # --- 5. Ejecutar Docker Compose ---
        print("\n[*] 5. Levantando orquestacion de contenedores en la Raspberry Pi...")
        print("  -> Construyendo e iniciando contenedores (esto puede tardar unos minutos en la primera ejecución)...")
        compose_cmd = (
            f"cd {REMOTE_DIR} && "
            f"echo '{SSH_PASSWORD}' | sudo -S docker-compose down && "
            f"echo '{SSH_PASSWORD}' | sudo -S docker-compose up --build -d"
        )
        out, err = ejecutar_comando(client, compose_cmd)
        print("Salida de Docker Compose:")
        print(out)
        if err:
            print("Errores / Advertencias:")
            print(err)

        # --- 6. Verificar Estado ---
        print("\n[*] 6. Verificando estado final de contenedores...")
        time.sleep(5)
        out, _ = ejecutar_comando(client, "docker ps", run_as_sudo=True)
        print(out)

        print("\n" + "=" * 65)
        print("  [EXITO] Despliegue completado satisfactoriamente.")
        print("  Puedes acceder al Dashboard en:")
        print(f"    - URL Local: http://{SSH_HOST_LOCAL}")
        print("    - URL VPN (Netbird): http://raspberryfv.netbird.cloud")
        print("=" * 65)

    except Exception as e:
        print(f"\n[ERROR CRITICO] Ocurrió un error en el despliegue: {e}")
        sys.exit(1)
    finally:
        client.close()

if __name__ == "__main__":
    main()
