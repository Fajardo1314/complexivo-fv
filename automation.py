import asyncio
import schedule
import time
import datetime
try:
    import RPi.GPIO as GPIO
except ImportError:
    class MockGPIO:
        BCM = 'BCM'
        IN = 'IN'
        OUT = 'OUT'
        @staticmethod
        def setmode(mode):
            pass
        @staticmethod
        def setwarnings(flag):
            pass
        @staticmethod
        def setup(pin, mode):
            pass
        @staticmethod
        def input(pin):
            return 0
    GPIO = MockGPIO
from kasa import Discover, SmartBulb
import firebase_admin
from firebase_admin import credentials, db

# --- CONFIGURACIÓN DE PINES (RPi) ---
PIN_LDR_DIGITAL = 22 # Lectura de día (0) o noche (1) mediante divisor resistivo o comparador

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(PIN_LDR_DIGITAL, GPIO.IN)

# --- CONFIGURACIÓN FIREBASE ---
try:
    cred = credentials.Certificate('google-services.json')
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://complexivo-fv-default-rtdb.firebaseio.com/'
        })
except:
    pass

# Variables
bulb_ip = None

def actualizar_estado_foco(estado_str):
    try:
        db.reference('monitoreo_tiempo_real').update({"estado_foco": estado_str})
    except:
        pass

async def discover_bulb():
    global bulb_ip
    print("[AUTO] Buscando dispositivos TP-Link Kasa en la red...")
    devices = await Discover.discover()
    for ip, dev in devices.items():
        if dev.is_bulb:
            print(f"[AUTO] Foco encontrado: {dev.alias} en {ip}")
            bulb_ip = ip
            return ip
    print("[AUTO] No se encontró ningún foco TP-Link.")
    return None

async def turn_on_bulb():
    if not bulb_ip: return
    try:
        bulb = SmartBulb(bulb_ip)
        await bulb.update()
        if not bulb.is_on:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Encendiendo luces de forma automática...")
            await bulb.turn_on()
            actualizar_estado_foco("ENCENDIDO")
    except Exception as e:
        print(f"[Error Foco] {e}")

async def turn_off_bulb():
    if not bulb_ip: return
    try:
        bulb = SmartBulb(bulb_ip)
        await bulb.update()
        if bulb.is_on:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Apagando luces de forma automática...")
            await bulb.turn_off()
            actualizar_estado_foco("APAGADO")
    except Exception as e:
        print(f"[Error Foco] {e}")

# Funciones de Envoltura Síncrona
def job_encender():
    asyncio.run(turn_on_bulb())

def job_apagar():
    asyncio.run(turn_off_bulb())

def check_ldr_status():
    # Retorna True si detecta "Noche/Oscuridad", False si detecta "Día/Luz"
    # Ajustar según si el módulo entrega 1 o 0 con luz
    # Asumiremos que HIGH (1) = Oscuridad
    return GPIO.input(PIN_LDR_DIGITAL) == GPIO.HIGH

def validacion_continua():
    """
    Se ejecuta frecuentemente.
    - Si es de día (LDR = Luz) -> Apaga el foco.
    - Si es después de las 17:00 y antes de las 23:00, y el LDR = Oscuridad -> Enciende el foco.
    """
    ahora = datetime.datetime.now().time()
    es_oscuro = check_ldr_status()
    
    if not es_oscuro:
        # Hay suficiente luz natural
        job_apagar()
    else:
        # Está oscuro
        hora_17 = datetime.time(17, 0)
        hora_23 = datetime.time(23, 0)
        if hora_17 <= ahora < hora_23:
            job_encender()

# Programación Horaria Fija
schedule.every().day.at("23:00").do(job_apagar)    # Apagado forzoso preventivo
schedule.every().day.at("06:00").do(job_encender)  # Encendido programado matutino

# Programación Dinámica
schedule.every(2).minutes.do(validacion_continua)

def main():
    try:
        # Buscar el foco al iniciar
        asyncio.run(discover_bulb())
        
        print("[AUTO] Módulo de Automatización Inteligente Iniciado.")
        
        while True:
            schedule.run_pending()
            time.sleep(1)
            
    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()
