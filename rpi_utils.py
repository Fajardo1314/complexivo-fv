"""
rpi_utils.py — Utilidades para la Raspberry Pi
===============================================
Uso:
    python rpi_utils.py diagnostico     # Info general del sistema
    python rpi_utils.py deploy          # Desplegar código a la Pi
    python rpi_utils.py nodered-restart # Reiniciar Node-RED
    python rpi_utils.py firebase-test   # Probar conexión Firebase
    python rpi_utils.py firebase-seed   # Sembrar datos iniciales
    python rpi_utils.py hotspot-on      # Activar WiFi hotspot ESP32
    python rpi_utils.py hotspot-off     # Desactivar WiFi hotspot
    python rpi_utils.py shell           # Sesión SSH interactiva
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
from ssh_raspberry import RaspberrySSH


def cmd_diagnostico(rpi):
    comandos = [
        ("Sistema",      "uname -a"),
        ("Uptime",       "uptime -p 2>/dev/null || cat /proc/uptime"),
        ("Memoria",      "free -h"),
        ("Disco",        "df -h /"),
        ("CPU Temp",     "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo N/A"),
        ("Contenedores", "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'"),
        ("Puertos",      "ss -tulpn | grep -E '(80|1880|5000)' | grep LISTEN"),
        ("Netbird IP",   "ip addr show wt0 2>/dev/null | grep 'inet ' || echo Sin_Netbird"),
        ("WiFi AP",      "nmcli dev status | grep wlan0"),
        ("Firebase",     "ls -la /home/user/proyecto_grado/google-services.json 2>/dev/null || echo No_encontrado"),
    ]
    for nombre, cmd in comandos:
        print(f"\n▶ {nombre}")
        print("─" * 40)
        print(rpi.ejecutar(cmd) or "(sin salida)")


def cmd_deploy(rpi):
    base = os.path.dirname(__file__)
    archivos = [
        ("main_control.py",          "/home/user/proyecto_grado/main_control.py",          "docker cp /home/user/proyecto_grado/main_control.py backend-control:/app/main_control.py"),
        ("web_dashboard/index.html", "/home/user/proyecto_grado/web_dashboard/index.html", None),
        ("web_dashboard/app.js",     "/home/user/proyecto_grado/web_dashboard/app.js",     None),
        ("nodered_data/flows.json",  "/tmp/flows.json",                                     "docker cp /tmp/flows.json nodered:/data/flows.json"),
        ("nginx.conf",               "/home/user/proyecto_grado/nginx.conf",                "docker cp /home/user/proyecto_grado/nginx.conf web-dashboard:/etc/nginx/conf.d/default.conf"),
    ]
    for local_rel, remote, post in archivos:
        lp = os.path.join(base, local_rel)
        if not os.path.exists(lp): continue
        rpi.subir_archivo(lp, remote)
        if post: rpi.ejecutar(post)
    rpi.ejecutar("docker restart backend-control")
    time.sleep(5)
    rpi.ejecutar("docker restart nodered")
    time.sleep(5)
    rpi.ejecutar("docker exec web-dashboard nginx -s reload")
    print(rpi.ejecutar("docker ps --format 'table {{.Names}}\t{{.Status}}'"))


def cmd_nodered_restart(rpi):
    rpi.ejecutar("docker restart nodered")
    time.sleep(10)
    print(rpi.ejecutar("docker logs nodered --tail 10 2>&1"))


def cmd_firebase_test(rpi):
    s = "import sys; sys.path.insert(0,'/app'); import firebase_admin; from firebase_admin import credentials, db; [firebase_admin.delete_app(firebase_admin._apps[k]) for k in list(firebase_admin._apps.keys())]; firebase_admin.initialize_app(credentials.Certificate('/app/google-services.json'),{'databaseURL':'https://complexivo-fv-default-rtdb.firebaseio.com/'}); print('[OK]', db.reference('monitoreo_tiempo_real').get())"
    rpi.ejecutar(f"docker exec backend-control python3 -c \"{s}\" 2>&1", timeout=30)


def cmd_firebase_seed(rpi):
    s = """import sys; sys.path.insert(0,'/app')
import firebase_admin; from firebase_admin import credentials, db
[firebase_admin.delete_app(firebase_admin._apps[k]) for k in list(firebase_admin._apps.keys())]
firebase_admin.initialize_app(credentials.Certificate('/app/google-services.json'),{'databaseURL':'https://complexivo-fv-default-rtdb.firebaseio.com/'})
db.reference('monitoreo_tiempo_real').set({'personas_dentro_actualmente':0,'estado_chapa':'CERRADA','alerta_pir':False,'estado_foco':'APAGADO'})
db.reference('usuarios').set({'12345678':{'nombre':'Ing. Esteban Bravo','rol':'Tecnico de Laboratorio'},'238472910':{'nombre':'Dr. Marcelo Vasquez','rol':'Docente de Electronica'}})
db.reference('inventario').set({'QR_OSCILOSCOPIO_1':{'nombre_producto':'Osciloscopio Digital Rigol DS1054Z','stock':4},'QR_MULTIMETRO_2':{'nombre_producto':'Multimetro Digital Fluke 115','stock':12}})
print('[OK] Seed completado')"""
    f = os.path.join(os.path.dirname(__file__), '_t.py')
    with open(f, 'w') as fh: fh.write(s)
    rpi.subir_archivo(f, '/tmp/_t.py')
    rpi.ejecutar("docker cp /tmp/_t.py backend-control:/app/_t.py")
    print(rpi.ejecutar("docker exec backend-control python3 /app/_t.py 2>&1", timeout=30))
    os.remove(f)


def cmd_hotspot_on(rpi):
    rpi.ejecutar_sudo("nmcli connection modify Hotspot connection.autoconnect yes")
    rpi.ejecutar_sudo("nmcli connection up Hotspot")
    time.sleep(3)
    print(rpi.ejecutar("ip addr show wlan0 2>/dev/null | grep 'inet '"))
    print(rpi.ejecutar("curl -s http://10.42.0.1:5000/status 2>&1 || echo 'Flask no accesible'"))


def cmd_hotspot_off(rpi):
    rpi.ejecutar_sudo("nmcli connection down Hotspot")
    print("Hotspot desactivado.")


def cmd_shell(rpi):
    from ssh_raspberry import sesion_interactiva
    sesion_interactiva(rpi)


COMANDOS = {
    "diagnostico": cmd_diagnostico, "deploy": cmd_deploy,
    "nodered-restart": cmd_nodered_restart, "firebase-test": cmd_firebase_test,
    "firebase-seed": cmd_firebase_seed, "hotspot-on": cmd_hotspot_on,
    "hotspot-off": cmd_hotspot_off, "shell": cmd_shell,
}

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMANDOS:
        print("\n  rpi_utils.py — Utilidades RPi\n")
        for c in COMANDOS: print(f"    python rpi_utils.py {c}")
        sys.exit(1)
    with RaspberrySSH() as rpi:
        COMANDOS[sys.argv[1]](rpi)

if __name__ == "__main__":
    main()