import asyncio
import schedule
import time
import datetime
from kasa import Discover, SmartBulb
import json
from firebase_admin import credentials, db
import firebase_admin

# --- CONFIGURACIÓN FIREBASE (OPCIONAL AQUÍ PARA LEER LUZ) ---
try:
    cred = credentials.Certificate('google-services.json')
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://complexivo-fv-default-rtdb.firebaseio.com/'
        })
except:
    pass

bulb_ip = None  # Se descubrirá automáticamente
UMBRAL_LUZ_SUFICIENTE = 2500  # Ajustar según las lecturas del LDR

async def discover_bulb():
    global bulb_ip
    print("Buscando dispositivos TP-Link Kasa en la red...")
    devices = await Discover.discover()
    for ip, dev in devices.items():
        if dev.is_bulb:
            print(f"Foco encontrado: {dev.alias} en {ip}")
            bulb_ip = ip
            return ip
    print("No se encontró ningún foco TP-Link.")
    return None

async def turn_on_bulb():
    if not bulb_ip: return
    try:
        bulb = SmartBulb(bulb_ip)
        await bulb.update()
        if not bulb.is_on:
            print(f"[{datetime.datetime.now()}] Encendiendo luces...")
            await bulb.turn_on()
    except Exception as e:
        print(f"Error encendiendo foco: {e}")

async def turn_off_bulb():
    if not bulb_ip: return
    try:
        bulb = SmartBulb(bulb_ip)
        await bulb.update()
        if bulb.is_on:
            print(f"[{datetime.datetime.now()}] Apagando luces...")
            await bulb.turn_off()
    except Exception as e:
        print(f"Error apagando foco: {e}")

# Funciones Wrappers para Schedule
def job_encender_tarde():
    asyncio.run(turn_on_bulb())

def job_apagar_noche():
    asyncio.run(turn_off_bulb())

def job_encender_manana():
    asyncio.run(turn_on_bulb())

def verificar_luz_ambiental():
    try:
        ref_estado = db.reference('estado_actual')
        estado = ref_estado.get()
        if estado and 'luz_ambiental' in estado:
            luz = estado['luz_ambiental']
            print(f"Luz ambiental actual: {luz}")
            # Si hay suficiente luz natural (LDR lee valores altos cuando hay oscuridad o al revés según el divisor de tensión)
            # Asumiendo LDR disminuye resistencia con luz, y lectura analógica aumenta con luz
            if luz > UMBRAL_LUZ_SUFICIENTE:
                print("Luz suficiente detectada. Apagando foco.")
                asyncio.run(turn_off_bulb())
    except Exception as e:
        pass

# Programación de Horarios
schedule.every().day.at("17:00").do(job_encender_tarde)
schedule.every().day.at("23:00").do(job_apagar_noche)
schedule.every().day.at("06:00").do(job_encender_manana)

# Verificar luz ambiental periódicamente durante el día (ej: cada 5 minutos)
schedule.every(5).minutes.do(verificar_luz_ambiental)

if __name__ == "__main__":
    # Descubrir inicial
    asyncio.run(discover_bulb())
    
    print("Servicio de Control TP-Link iniciado.")
    print("Horarios programados: ON 17:00, OFF 23:00, ON 06:00, OFF Automático por LDR")
    
    while True:
        schedule.run_pending()
        time.sleep(1)
