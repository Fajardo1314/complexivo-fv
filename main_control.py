import time
import datetime
import threading
import os
import subprocess
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, db

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    print("[MOCK] paho-mqtt no encontrado.")

try:
    import RPi.GPIO as GPIO
except ImportError:
    class MockGPIO:
        BCM = 'BCM'
        OUT = 'OUT'
        IN = 'IN'
        LOW = 'LOW'
        HIGH = 'HIGH'
        PUD_UP = 'PUD_UP'
        FALLING = 'FALLING'
        def setmode(self, mode): pass
        def setwarnings(self, flag): pass
        def setup(self, pin, mode, initial=None, pull_up_down=None): pass
        def output(self, pin, state): pass
        def add_event_detect(self, pin, edge, callback, bouncetime): pass
        def cleanup(self): pass
    GPIO = MockGPIO()
    print("[MOCK] RPi.GPIO no encontrado. Simulando hardware.")

try:
    from mfrc522 import SimpleMFRC522
except ImportError:
    class MockRFID:
        def read(self):
            time.sleep(10)
            return None, None
    SimpleMFRC522 = MockRFID

# PIN CONFIGURATION
PIN_RELE_CHAPA = 17
PIN_PULSADOR_SALIDA = 27

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(PIN_RELE_CHAPA, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(PIN_PULSADOR_SALIDA, GPIO.IN, pull_up_down=GPIO.PUD_UP)

try:
    reader = SimpleMFRC522()
except Exception as e:
    class MockRFIDFallback:
        def read(self):
            time.sleep(60)
            return None, None
    reader = MockRFIDFallback()

# FIREBASE CONFIGURATION
OUR_DB_URL = "https://complexivo-fv-default-rtdb.firebaseio.com/"
SHARED_DB_URL = "https://aula-4587b-default-rtdb.firebaseio.com/"

try:
    cred = credentials.Certificate('google-services.json')
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {
            'databaseURL': OUR_DB_URL
        })
    print(f"[Firebase] Nuestra DB (default): {OUR_DB_URL}")
except Exception as e:
    print(f"[ERROR Firebase] google-services.json: {e}")

# Firebase App para la base compartida (aula-4587b) - solo lectura RFID
try:
    shared_cred = credentials.Certificate('aula-4587b-firebase-adminsdk-fbsvc-7b1a51cecd.json')
    firebase_admin.initialize_app(shared_cred, {
        'databaseURL': SHARED_DB_URL
    }, name='sharedApp')
    print(f"[Firebase] DB compartida (RFID): {SHARED_DB_URL}")
except Exception as e:
    print(f"[WARNING] No se pudo conectar a DB compartida: {e}")

def get_shared_db():
    """Obtiene referencia a la DB compartida aula-4587b"""
    try:
        return firebase_admin.get_app('sharedApp')
    except ValueError:
        return None

# GLOBAL STATE
estado_actual = {
    "personas_dentro_actualmente": 0,
    "estado_chapa": "CERRADA",
    "alerta_pir": False,
    "ultimo_movimiento_ts": time.time(),
    "puerta_fisica_abierta": False
}

def actualizar_monitoreo(datos):
    try:
        ref = db.reference('monitoreo')
        ref.update(datos)
    except Exception as e:
        print(f"[Error Firebase] {e}")

def abrir_chapa(metodo_acceso="BOTON", usuario_name="Pulsador Salida"):
    """Abre la chapa electrica local y de la DB unificada por 5 segundos."""
    print(f"[CHAPA] Abriendo puerta... (Método: {metodo_acceso}, Responsable: {usuario_name})")
    estado_actual["estado_chapa"] = "ABIERTA"
    actualizar_monitoreo({"estado_chapa": "ABIERTA", "estado_puerta": "ABIERTA"})
    
    # Escribir en base unificada (aula-4587b) en el nodo compartido 'puerta'
    try:
        ref_puerta = db.reference('puerta')
        ref_puerta.update({
            "estado": "abierta",
            "metodo": metodo_acceso,
            "timestamp": time.time(),
            "ultimo_acceso": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "usuario_responsable": usuario_name
        })
    except Exception as e:
        print(f"[CHAPA Error Shared DB] {e}")
        
    GPIO.output(PIN_RELE_CHAPA, GPIO.HIGH)
    time.sleep(5)
    print("[CHAPA] Cerrando puerta...")
    GPIO.output(PIN_RELE_CHAPA, GPIO.LOW)
    estado_actual["estado_chapa"] = "CERRADA"
    actualizar_monitoreo({"estado_chapa": "CERRADA", "estado_puerta": "CERRADA"})
    try:
        db.reference('puerta/estado').set("cerrada")
    except Exception as e:
        print(f"[CHAPA Error Shared DB] {e}")

def boton_salida_callback(channel):
    print("[PULSADOR] Boton de salida presionado.")
    threading.Thread(target=abrir_chapa, args=("BOTON", "Pulsador Salida"), daemon=True).start()

try:
    GPIO.add_event_detect(PIN_PULSADOR_SALIDA, GPIO.FALLING, callback=boton_salida_callback, bouncetime=500)
except Exception as e:
    print(f"[WARNING] Event_detect error: {e}")

# TUYA SMART SWITCH CONTROL
TUYA_ACCESS_ID = "4cg753npk9gxtjwnqr7y"
TUYA_ACCESS_SECRET = "a5e813311035455eab6f92a8d7786ca0"
TUYA_DEVICE_ID = "eb98686bb984169ea7dgfq"
TUYA_ENDPOINT = "https://openapi.tuyaus.com"

tuya_api = None

def inicializar_tuya():
    global tuya_api
    try:
        from tuya_connector import TuyaOpenAPI
        tuya_api = TuyaOpenAPI(TUYA_ENDPOINT, TUYA_ACCESS_ID, TUYA_ACCESS_SECRET)
        tuya_api.connect()
    except Exception as e:
        print(f"[Tuya Error] {e}")
        tuya_api = None

def tuya_toggle_foco(encender):
    global tuya_api
    if tuya_api is None:
        inicializar_tuya()
    if tuya_api is None:
        return False
    codigos = ["switch_1", "switch", "master_switch"]
    for codigo in codigos:
        try:
            commands = {"commands": [{"code": codigo, "value": encender}]}
            response = tuya_api.post(f"/v1.0/devices/{TUYA_DEVICE_ID}/commands", commands)
            if response.get("success"):
                print(f"[Tuya] Foco -> {'ON' if encender else 'OFF'}")
                return True
        except:
            continue
    tuya_api = None
    return False

# HORARIO Y LOGICA DE ILUMINACION
def _es_horario_iluminacion():
    try:
        horario = db.reference('configuracion/horario_iluminacion').get()
        if not horario:
            horario = {"inicio": "06:30", "fin": "22:00"}
        
        ahora = datetime.datetime.now().time()
        
        h_ini, m_ini = map(int, horario.get("inicio", "06:30").split(":"))
        h_fin, m_fin = map(int, horario.get("fin", "22:00").split(":"))
        
        inicio = datetime.time(h_ini, m_ini)
        fin = datetime.time(h_fin, m_fin)
        return inicio <= ahora < fin
    except Exception as e:
        print(f"[Horario LDR Error] {e}")
        return datetime.time(6, 30) <= datetime.datetime.now().time() < datetime.time(22, 0)

# THREAD FOR FOCO LISTENER
def firebase_foco_listener():
    print("[FOCO-LISTENER] Iniciando escucha...")
    inicializar_tuya()
    last_value = None

    def callback(event):
        nonlocal last_value
        try:
            nuevo_estado = event.data
            if nuevo_estado != last_value:
                last_value = nuevo_estado
                
                # Validar horario
                if not _es_horario_iluminacion() and nuevo_estado == "ENCENDIDO":
                    print("[FOCO-LISTENER] Intento de encendido fuera de horario denegado.")
                    db.reference('estado_foco').set("APAGADO")
                    return
                
                encender = nuevo_estado == "ENCENDIDO"
                tuya_toggle_foco(encender)
        except Exception as e:
            print(f"[FOCO-LISTENER Error] {e}")

    try:
        ref = db.reference('estado_foco')
        ref.listen(callback)
    except Exception as e:
        print(f"[FOCO-LISTENER Error] {e}")

# THREAD: SINCRONIZADOR DE ESTADO REAL DEL SWITCH TUYA
# Lee el estado fisico real del interruptor Tuya cada 3 segundos.
# Si el switch fue cambiado manualmente (desde el interruptor fisico),
# actualiza Firebase para que el Dashboard refleje el estado correcto.
def tuya_estado_sincronizador():
    global tuya_api
    print("[TUYA-SYNC] Iniciando sincronizador bidireccional del switch fisico...")
    inicializar_tuya()
    last_estado_tuya = None
    codigos_switch = ["switch_1", "switch", "master_switch"]

    while True:
        try:
            if tuya_api is None:
                inicializar_tuya()
                time.sleep(5)
                continue

            # Consultar estado real del dispositivo desde la nube de Tuya
            response = tuya_api.get(f"/v1.0/devices/{TUYA_DEVICE_ID}/status")
            if not response.get("success"):
                time.sleep(5)
                continue

            # Buscar el switch principal en la respuesta
            estado_tuya = None
            for item in response.get("result", []):
                if item.get("code") in codigos_switch:
                    estado_tuya = item.get("value")
                    break

            if estado_tuya is None:
                time.sleep(3)
                continue

            estado_str = "ENCENDIDO" if estado_tuya else "APAGADO"

            # Solo actualizar Firebase si el estado cambio fisicamente
            if estado_str != last_estado_tuya:
                last_estado_tuya = estado_str
                # Leer el estado actual en Firebase para evitar loop de escritura
                estado_firebase = db.reference('estado_foco').get()
                if estado_firebase != estado_str:
                    print(f"[TUYA-SYNC] Estado fisico del switch cambio a {estado_str}. Actualizando Firebase.")
                    db.reference('estado_foco').set(estado_str)
        except Exception as e:
            print(f"[TUYA-SYNC Error] {e}")
            tuya_api = None  # Forzar reconexion en la siguiente iteracion
        time.sleep(3)


# MQTT SENSOR RELAY
mqtt_pub_client = None

def registrar_acceso_shared_db(uid, exitoso, metodo, motivo, perfil=None, identificador_usuario=""):
    """Registra un acceso en la DB compartida aula-4587b con la estructura estandar."""
    try:
        shared_app = get_shared_db()
        if shared_app:
            shared_db = db.reference('accesos', app=shared_app)
            shared_db.push({
                "exitoso": exitoso,
                "fecha_hora": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "identificador_usuario": identificador_usuario,
                "metodo": metodo,
                "motivo": motivo,
                "perfil": perfil or {},
                "timestamp": time.time()
            })
            print(f"[SHARED-DB] Acceso registrado en aula-4587b: {motivo}")
    except Exception as e:
        print(f"[SHARED-DB Error] {e}")

def registrar_permanencia_no_registrado(uid):
    ahora_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.reference('monitoreo/permanencia').set({
        "activo": True,
        "inicio": ahora_str,
        "usuario": "USUARIO NO REGISTRADO",
        "uid": uid
    })
    
    # Registrar en accesos (nuestra DB con estructura de aula-4587b)
    db.reference('accesos').push({
        "exitoso": False,
        "fecha_hora": ahora_str,
        "identificador_usuario": "",
        "metodo": f"RFID:{uid}",
        "motivo": "Tarjeta no registrada",
        "perfil": {},
        "timestamp": time.time()
    })
    
    # Tambien registrar en la DB compartida
    registrar_acceso_shared_db(uid, False, f"RFID:{uid}", "Tarjeta no registrada")

def verificar_uid_en_nuestra_db(uid):
    ahora_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Buscar la tarjeta RFID en la DB COMPARTIDA (aula-4587b)
    tarjeta = None
    try:
        shared_app = get_shared_db()
        if shared_app:
            tarjeta = db.reference(f'tarjetas/{uid}', app=shared_app).get()
            if tarjeta:
                print(f"[RFID] Tarjeta encontrada en DB compartida: {uid}")
    except Exception as e:
        print(f"[RFID] Error leyendo DB compartida: {e}")
    
    # Fallback: buscar en nuestra DB
    if not tarjeta:
        tarjeta = db.reference(f'tarjetas/{uid}').get()
        if tarjeta:
            print(f"[RFID] Tarjeta encontrada en nuestra DB: {uid}")
    
    if tarjeta and tarjeta.get('activa', False):
        nombre = tarjeta.get('nombre', 'Sin nombre')
        rol = tarjeta.get('rol', 'Docente')
        propietario = tarjeta.get('propietario', '')
        print(f"[RFID] Tarjeta autorizada: {nombre} (UID: {uid}, Propietario: {propietario}, Rol: {rol})")
        
        # Registrar permanencia
        db.reference('monitoreo/permanencia').set({
            "activo": True,
            "inicio": ahora_str,
            "usuario": nombre,
            "uid": uid,
            "propietario": propietario
        })
        
        # Registrar en accesos (nuestra DB con estructura de aula-4587b)
        perfil = {"nombre": nombre, "rol": rol}
        db.reference('accesos').push({
            "exitoso": True,
            "fecha_hora": ahora_str,
            "identificador_usuario": propietario,
            "metodo": f"RFID:{uid}",
            "motivo": f"RFID verificado de {nombre}",
            "perfil": perfil,
            "timestamp": time.time()
        })
        
        # Tambien registrar en la DB compartida
        registrar_acceso_shared_db(uid, True, f"RFID:{uid}", f"RFID verificado de {nombre}", perfil, propietario)
        
        # Abrir la chapa remota y local
        threading.Thread(target=abrir_chapa, args=(f"RFID:{uid}", nombre), daemon=True).start()
    elif tarjeta and not tarjeta.get('activa', False):
        nombre = tarjeta.get('nombre', 'Desconocido')
        print(f"[RFID] Tarjeta INACTIVA: {uid} ({nombre})")
        db.reference('monitoreo/permanencia').set({
            "activo": True,
            "inicio": ahora_str,
            "usuario": nombre,
            "uid": uid
        })
        db.reference('accesos').push({
            "exitoso": False,
            "fecha_hora": ahora_str,
            "identificador_usuario": "",
            "metodo": f"RFID:{uid}",
            "motivo": f"Tarjeta inactiva: {nombre}",
            "perfil": {"nombre": nombre, "rol": tarjeta.get('rol', '')},
            "timestamp": time.time()
        })
        registrar_acceso_shared_db(uid, False, f"RFID:{uid}", f"Tarjeta inactiva: {nombre}")
    else:
        print(f"[RFID] UID NO registrado: {uid}. Guardando log como no registrado.")
        registrar_permanencia_no_registrado(uid)

# BACKGROUND THREAD FOR MONITORING UNIFIED DB REMOTE DOOR COMMANDS
def firebase_puerta_listener():
    print("[PUERTA-LISTENER] Iniciando escucha de cambios en puerta/estado...")
    
    def callback(event):
        try:
            nuevo_estado = event.data
            if nuevo_estado == "abierta":
                # Validar si chapa esta cerrada actualmente para evitar bucles de retroalimentación
                if estado_actual["estado_chapa"] == "CERRADA":
                    print("[PUERTA-LISTENER] Detectado cambio remoto a 'abierta'. Activando chapa...")
                    # Obtener los metadatos de la apertura remota
                    metodo = db.reference('puerta/metodo').get() or "RFID/Remoto"
                    usr = db.reference('puerta/usuario_responsable').get() or "Sistema Externo"
                    threading.Thread(target=abrir_chapa, args=(metodo, usr), daemon=True).start()
        except Exception as e:
            print(f"[PUERTA-LISTENER Error] {e}")
            
    try:
        ref = db.reference('puerta/estado')
        ref.listen(callback)
    except Exception as e:
        print(f"[PUERTA-LISTENER Error] {e}")

# THREAD FOR AUTO SHUTOFF TIMER OF LIGHTS
def luces_temporizador_monitor():
    while True:
        try:
            # Obtener tiempo de encendido configurado
            temp_config = db.reference('configuracion/tiempo_encendido_luces').get()
            if not temp_config:
                temp_config = {"valor": 10, "unidad": "minutos"}
            
            valor = float(temp_config.get("valor", 10))
            unidad = temp_config.get("unidad", "minutos")
            
            segundos_limite = valor * 60 if unidad == "minutos" else valor * 3600
            
            estado_foco = db.reference('estado_foco').get()
            if estado_foco == "ENCENDIDO":
                # Si no hay movimiento en los ultimos 'segundos_limite' segundos, apagar luces
                inactivo_desde = time.time() - estado_actual["ultimo_movimiento_ts"]
                if inactivo_desde >= segundos_limite:
                    print(f"[TEMPORIZADOR] Inactividad superada ({inactivo_desde:.1f}s >= {segundos_limite}s). Apagando foco.")
                    db.reference('estado_foco').set("APAGADO")
        except Exception as e:
            print(f"[TEMPORIZADOR Error] {e}")
        time.sleep(10)

# THREAD FOR STAY COUNTER INACTIVITY CHECK
def permanencia_inactividad_monitor():
    while True:
        try:
            perm = db.reference('monitoreo/permanencia').get()
            if perm and perm.get('activo'):
                # Si la puerta esta cerrada y no hay movimiento en los ultimos 5 minutos (300 segundos), detener conteo
                if not estado_actual["puerta_fisica_abierta"]:
                    inactivo_desde = time.time() - estado_actual["ultimo_movimiento_ts"]
                    if inactivo_desde >= 300:
                        print("[PERMANENCIA] No hay movimiento en los ultimos 5 min con puerta cerrada. Deteniendo conteo.")
                        # Marcar salida en el historico de accesos
                        uid = perm.get('uid')
                        nombre = perm.get('usuario', 'USUARIO NO REGISTRADO')
                        ahora_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        ref_accesos = db.reference('accesos')
                        accesos = ref_accesos.order_by_child('codigo_usado').equal_to(uid).get()
                        if accesos:
                            for key, acc in reversed(list(accesos.items())):
                                if acc.get('hora_salida') is None:
                                    t_ingreso = datetime.datetime.strptime(acc['hora_ingreso'], "%Y-%m-%d %H:%M:%S")
                                    minutos = int((datetime.datetime.now() - t_ingreso).total_seconds() / 60)
                                    ref_accesos.child(key).update({
                                        "hora_salida": ahora_str,
                                        "tiempo_permanencia_min": minutos
                                    })
                                    break
                        db.reference('monitoreo/permanencia/activo').set(False)
        except Exception as e:
            print(f"[PERMANENCIA MONITOR Error] {e}")
        time.sleep(10)

def mqtt_sensor_relay():
    global mqtt_pub_client
    if not MQTT_AVAILABLE:
        return

    def on_connect(client, userdata, flags, rc, properties=None):
        print(f"[MQTT-RELAY] Conectado (rc={rc})")
        client.subscribe("movimiento_pir")
        client.subscribe("sensor_ir/casillero1")
        client.subscribe("sensor_ir/casillero2")
        client.subscribe("puerta_fisica/estado")
        client.subscribe("accesos")
        client.subscribe("aula/luminosidad")

    def on_message(client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8').strip()
        
        try:
            # PIR MOTION SENSOR
            if topic == "movimiento_pir":
                val = payload.lower() in ("true", "1")
                db.reference('monitoreo/movimiento_pir').set(val)
                if val:
                    estado_actual["ultimo_movimiento_ts"] = time.time()
                    
                    # Logica de encendido de luces
                    if _es_horario_iluminacion():
                        # Solo encender si lux < 100
                        lux_actual = db.reference('monitoreo/lux_actual').get()
                        if lux_actual is not None and float(lux_actual) < 100:
                            estado_foco = db.reference('estado_foco').get()
                            if estado_foco != "ENCENDIDO":
                                print(f"[PIR] Movimiento detectado con baja luminosidad ({lux_actual} lux). Encendiendo foco.")
                                db.reference('estado_foco').set("ENCENDIDO")
                    else:
                        # Fuera de horario: Alerta de movimiento nocturna
                        db.reference('monitoreo/alerta_pir_nocturna').set(True)

            # SHELF SECURITY WIDGETS (CASILLEROS)
            elif topic == "sensor_ir/casillero1":
                val = payload.lower() in ("true", "1")
                db.reference('monitoreo/casillero1').set("ALERTA" if val else "SEGURO")
                if val:
                    # Si no esta en modo seguro, disparar alerta general
                    modo_seguro = db.reference('monitoreo/modo_seguro_estante').get()
                    if not modo_seguro:
                        db.reference('monitoreo/alerta_estante').set("Alguien tocó materiales no permitidos en Casillero 1")

            elif topic == "sensor_ir/casillero2":
                val = payload.lower() in ("true", "1")
                db.reference('monitoreo/casillero2').set("ALERTA" if val else "SEGURO")
                if val:
                    modo_seguro = db.reference('monitoreo/modo_seguro_estante').get()
                    if not modo_seguro:
                        db.reference('monitoreo/alerta_estante').set("Alguien tocó materiales no permitidos en Casillero 2")

            # MAGNETIC DOOR SENSOR
            elif topic == "puerta_fisica/estado":
                puerta_abierta = payload.lower() in ("1", "true", "abierta")
                db.reference('monitoreo/puerta').set(puerta_abierta)
                estado_str = "ABIERTA" if puerta_abierta else "CERRADA"
                db.reference('monitoreo/estado_puerta').set(estado_str)
                estado_actual["puerta_fisica_abierta"] = puerta_abierta
                print(f"[PUERTA MAGNETIC] {estado_str}")
                
                # Actualizar el nodo compartido puerta_fisica en minúsculas
                try:
                    db.reference('puerta_fisica').update({
                        "estado": "abierta" if puerta_abierta else "cerrada",
                        "timestamp": time.time()
                    })
                except Exception as e:
                    print(f"[ERROR Shared puerta_fisica] {e}")

            # RFID TOPIC DIRECT FROM HARDWARE
            elif topic == "accesos":
                verificar_uid_en_nuestra_db(payload)

            # LUX SENSOR (BH1750)
            elif topic == "aula/luminosidad":
                try:
                    lux_actual = float(payload)
                    db.reference('monitoreo/lux_actual').set(round(lux_actual, 1))
                except:
                    pass

        except Exception as e:
            print(f"[MQTT Error] {topic}: {e}")

    try:
        relay_client = mqtt.Client(client_id="rpi-sensor-relay", callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        relay_client.on_connect = on_connect
        relay_client.on_message = on_message
        mqtt_host = "mosquitto" if os.environ.get("DOCKER_CONTAINER") else "127.0.0.1"
        relay_client.connect(mqtt_host, 1883, 60)
        mqtt_pub_client = relay_client
        relay_client.loop_forever()
    except Exception as e:
        print(f"[MQTT Connection Error] {e}")

app = Flask(__name__)

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
    return response

# FLASK ENDPOINTS
@app.route('/api/sensores', methods=['POST'])
def recibir_sensores():
    data = request.json
    if not data:
        return jsonify({"error": "No JSON"}), 400
    evento = data.get("evento")
    if evento == "rfid_leido":
        uid = data.get("uid")
        verificar_uid_en_nuestra_db(uid)
    return jsonify({"status": "ok"}), 200

@app.route('/api/registro_acceso', methods=['POST'])
def registro_acceso_externo():
    data = request.json
    if not data:
        return jsonify({"error": "No JSON"}), 400
    codigo = data.get("codigo", "")
    verificar_uid_en_nuestra_db(codigo)
    return jsonify({"status": "ok"}), 200

@app.route('/api/abrir_puerta', methods=['POST'])
def abrir_puerta_api():
    threading.Thread(target=abrir_chapa, daemon=True).start()
    return jsonify({"status": "ok", "mensaje": "Comando enviado para abrir la puerta."}), 200

@app.route('/status', methods=['GET'])
def system_status():
    return jsonify({
        'status': 'online',
        'personas_dentro': estado_actual['personas_dentro_actualmente'],
        'estado_chapa': estado_actual['estado_chapa'],
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }), 200

@app.route('/shutdown', methods=['POST'])
def shutdown_raspberry():
    try:
        subprocess.Popen(['sudo', 'shutdown', '-h', '+0'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return jsonify({'status': 'shutting_down'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/reboot', methods=['POST'])
def reboot_raspberry():
    try:
        subprocess.Popen(['sudo', 'reboot'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return jsonify({'status': 'rebooting'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

SMTP_USER = "smartstock97@gmail.com"
SMTP_PASS = "F@jardo123"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

def main():
    try:
        # Listening threads
        threading.Thread(target=firebase_puerta_listener, daemon=True).start()
        threading.Thread(target=luces_temporizador_monitor, daemon=True).start()
        threading.Thread(target=permanencia_inactividad_monitor, daemon=True).start()
        threading.Thread(target=mqtt_sensor_relay, daemon=True).start()
        threading.Thread(target=firebase_foco_listener, daemon=True).start()
        threading.Thread(target=tuya_estado_sincronizador, daemon=True).start()
        app.run(host='0.0.0.0', port=5000, use_reloader=False)
    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()