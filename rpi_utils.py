"""
rpi_utils.py — Utilidades para la Raspberry Pi
===============================================
Consolida diagnóstico, despliegue y mantenimiento en un solo archivo.

Uso:
    python rpi_utils.py diagnostico     # Info general del sistema
    python rpi_utils.py deploy          # Desplegar código a la Pi
    python rpi_utils.py nodered-restart # Reiniciar Node-RED
    python rpi_utils.py firebase-test   # Probar conexión Firebase
    python rpi_utils.py firebase-seed   # Sembrar datos iniciales
    python rpi_utils.py shell           # Sesión SSH interactiva
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))
from ssh_raspberry import RaspberrySSH


def cmd_diagnostico(rpi):
    """Diagnóstico completo del sistema."""
    comandos = [
        ("Sistema",        "uname -a"),
        ("Uptime",         "uptime -p 2>/dev/null || cat /proc/uptime"),
        ("Memoria",        "free -h"),
        ("Disco",          "df -h /"),
        ("CPU Temp",       "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo N/A"),
        ("Contenedores",   "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'"),
        ("Puertos",        "ss -tulpn | grep -E '(80|1880|5000)' | grep LISTEN"),
        ("Netbird IP",     "ip addr show wt0 2>/dev/null | grep 'inet ' || echo 'Sin Netbird'"),
        ("Firebase JSON",  "ls -la /home/user/proyecto_grado/google-services.json 2>/dev/null || echo 'No encontrado'"),
    ]
    print("\n" + "=" * 60)
    print("  DIAGNÓSTICO — Raspberry Pi")
    print("=" * 60)
    for nombre, cmd in comandos:
        print(f"\n▶ {nombre}")
        print("─" * 40)
        print(rpi.ejecutar(cmd) or "(sin salida)")


def cmd_deploy(rpi):
    """Desplegar archivos actualizados a la Pi y reiniciar contenedores."""
    base = os.path.dirname(__file__)
    
    archivos = [
        ("main_control.py",   "/home/user/proyecto_grado/main_control.py",
         "docker cp /home/user/proyecto_grado/main_control.py backend-control:/app/main_control.py"),
        ("web_dashboard/index.html", "/home/user/proyecto_grado/web_dashboard/index.html", None),
        ("web_dashboard/app.js",     "/home/user/proyecto_grado/web_dashboard/app.js", None),
        ("nodered_data/flows.json",  "/tmp/flows.json",
         "docker cp /tmp/flows.json nodered:/data/flows.json"),
        ("nginx.conf",        "/home/user/proyecto_grado/nginx.conf",
         "docker cp /home/user/proyecto_grado/nginx.conf web-dashboard:/etc/nginx/conf.d/default.conf"),
    ]
    
    print("\n" + "=" * 60)
    print("  DESPLEGANDO CÓDIGO A RASPBERRY PI")
    print("=" * 60)
    
    for local_rel, remote_path, post_cmd in archivos:
        local_path = os.path.join(base, local_rel)
        if not os.path.exists(local_path):
            print(f"\n⚠️  {local_rel} no encontrado, saltando...")
            continue
        print(f"\n[UP] {local_rel} → {remote_path}")
        rpi.subir_archivo(local_path, remote_path)
        if post_cmd:
            print(f"[CP] {post_cmd}")
            rpi.ejecutar(post_cmd)
    
    print("\n[RESTART] Reiniciando contenedores...")
    rpi.ejecutar("docker restart backend-control")
    time.sleep(5)
    rpi.ejecutar("docker restart nodered")
    time.sleep(5)
    rpi.ejecutar("docker exec web-dashboard nginx -s reload")
    time.sleep(2)
    
    print("\n[VERIFY] Estado:")
    print(rpi.ejecutar("docker ps --format 'table {{.Names}}\t{{.Status}}'"))
    print(f"\n[TEST] /status: {rpi.ejecutar('curl -s http://127.0.0.1:5000/status 2>&1')}")
    print(f"[TEST] /nodered/: {rpi.ejecutar('curl -s -o /dev/null -w HTTP_%{http_code} http://127.0.0.1/nodered/ 2>&1')}")
    print(f"[TEST] /nodered/api/ui/: {rpi.ejecutar('curl -s -o /dev/null -w HTTP_%{http_code} http://127.0.0.1/nodered/api/ui/ 2>&1')}")


def cmd_nodered_restart(rpi):
    """Reiniciar Node-RED."""
    print("[RESTART] Reiniciando Node-RED...")
    rpi.ejecutar("docker restart nodered")
    time.sleep(10)
    print(rpi.ejecutar("docker logs nodered --tail 10 2>&1"))


def cmd_firebase_test(rpi):
    """Probar conexión a Firebase desde el contenedor."""
    print("\n" + "=" * 60)
    print("  TEST FIREBASE")
    print("=" * 60)
    
    test_script = """
import json, sys
sys.path.insert(0, '/app')
try:
    import firebase_admin
    from firebase_admin import credentials, db
    for app_name in list(firebase_admin._apps.keys()):
        firebase_admin.delete_app(firebase_admin._apps[app_name])
    cred = credentials.Certificate('/app/google-services.json')
    firebase_admin.initialize_app(cred, {'databaseURL': 'https://complexivo-fv-default-rtdb.firebaseio.com/'})
    data = db.reference('monitoreo_tiempo_real').get()
    print(f'[OK] Firebase conectado! Datos: {data}')
except Exception as e:
    print(f'[ERROR] {type(e).__name__}: {e}')
"""
    local_path = os.path.join(os.path.dirname(__file__), '_tmp_test.py')
    with open(local_path, 'w') as f:
        f.write(test_script)
    rpi.subir_archivo(local_path, '/tmp/_tmp_test.py')
    rpi.ejecutar("docker cp /tmp/_tmp_test.py backend-control:/app/_tmp_test.py")
    print(rpi.ejecutar("docker exec backend-control python3 /app/_tmp_test.py 2>&1", timeout=30))
    os.remove(local_path)


def cmd_firebase_seed(rpi):
    """Sembrar datos iniciales en Firebase."""
    print("\n" + "=" * 60)
    print("  SEED FIREBASE — Datos iniciales")
    print("=" * 60)
    
    seed_script = """
import json, sys
sys.path.insert(0, '/app')
try:
    import firebase_admin
    from firebase_admin import credentials, db
    for app_name in list(firebase_admin._apps.keys()):
        firebase_admin.delete_app(firebase_admin._apps[app_name])
    cred = credentials.Certificate('/app/google-services.json')
    firebase_admin.initialize_app(cred, {'databaseURL': 'https://complexivo-fv-default-rtdb.firebaseio.com/'})
    
    db.reference('monitoreo_tiempo_real').set({
        'personas_dentro_actualmente': 0,
        'estado_chapa': 'CERRADA',
        'alerta_pir': False,
        'estado_foco': 'APAGADO'
    })
    print('[OK] monitoreo_tiempo_real')
    
    db.reference('usuarios').set({
        '12345678': {'nombre': 'Ing. Esteban Bravo', 'rol': 'Tecnico de Laboratorio'},
        '238472910': {'nombre': 'Dr. Marcelo Vasquez', 'rol': 'Docente de Electronica'}
    })
    print('[OK] usuarios')
    
    db.reference('inventario').set({
        'QR_OSCILOSCOPIO_1': {'nombre_producto': 'Osciloscopio Digital Rigol DS1054Z', 'stock': 4},
        'QR_MULTIMETRO_2': {'nombre_producto': 'Multimetro Digital Fluke 115', 'stock': 12}
    })
    print('[OK] inventario')
    
    print('[SUCCESS] Datos semilla creados!')
except Exception as e:
    print(f'[ERROR] {type(e).__name__}: {e}')
"""
    local_path = os.path.join(os.path.dirname(__file__), '_tmp_seed.py')
    with open(local_path, 'w') as f:
        f.write(seed_script)
    rpi.subir_archivo(local_path, '/tmp/_tmp_seed.py')
    rpi.ejecutar("docker cp /tmp/_tmp_seed.py backend-control:/app/_tmp_seed.py")
    print(rpi.ejecutar("docker exec backend-control python3 /app/_tmp_seed.py 2>&1", timeout=30))
    os.remove(local_path)


def cmd_shell(rpi):
    """Sesión SSH interactiva."""
    from ssh_raspberry import sesion_interactiva
    sesion_interactiva(rpi)


COMANDOS = {
    "diagnostico":      ("Info general del sistema",        cmd_diagnostico),
    "deploy":           ("Desplegar código a la Pi",        cmd_deploy),
    "nodered-restart":  ("Reiniciar Node-RED",              cmd_nodered_restart),
    "firebase-test":    ("Probar conexión Firebase",        cmd_firebase_test),
    "firebase-seed":    ("Sembrar datos iniciales",         cmd_firebase_seed),
    "shell":            ("Sesión SSH interactiva",          cmd_shell),
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMANDOS:
        print("\n╔══════════════════════════════════════════╗")
        print("║   rpi_utils.py — Utilidades RPi          ║")
        print("╚══════════════════════════════════════════╝")
        print("\nComandos disponibles:")
        for cmd, (desc, _) in COMANDOS.items():
            print(f"  python rpi_utils.py {cmd:<20s} # {desc}")
        sys.exit(1)
    
    cmd_name = sys.argv[1]
    _, func = COMANDOS[cmd_name]
    
    with RaspberrySSH() as rpi:
        func(rpi)


if __name__ == "__main__":
    main()