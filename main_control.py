import time
import datetime
import threading
import os
import subprocess
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, db
try:
    import RPi.GPIO as GPIO
except ImportError:
    # Fallback/Mock para pruebas en Windows
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
    print("[MOCK] RPi.GPIO no encontrado. Simulando hardware para PC.")

try:
    from mfrc522 import SimpleMFRC522
except ImportError:
    # Fallback/Mock for testing off-device
    class SimpleMFRC522:
        def read(self):
            time.sleep(10) # Simular espera larga
            return None, None
    print("[MOCK] mfrc522 no encontrado. Simulando lector RFID.")

# --- CONFIGURACIÓN DE PINES (RPi) ---
PIN_RELE_CHAPA = 17
PIN_PULSADOR_SALIDA = 27

# Configurar GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(PIN_RELE_CHAPA, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(PIN_PULSADOR_SALIDA, GPIO.IN, pull_up_down=GPIO.PUD_UP)

try:
    reader = SimpleMFRC522()
    print("[RFID] Lector RFID inicializado correctamente.")
except Exception as e:
    print(f"[WARNING] No se pudo inicializar RFID (hardware no disponible): {e}")
    print("[WARNING] El sistema seguira funcionando sin lectura RFID.")
    class MockRFIDFallback:
        def read(self):
            time.sleep(60)  # Espera larga para no consumir CPU
            return None, None
    reader = MockRFIDFallback()

# --- CONFIGURACIÓN FIREBASE ---
try:
    cred = credentials.Certificate('google-services.json')
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {
            'databaseURL': 'https://complexivo-fv-default-rtdb.firebaseio.com/'
        })
    print("[Firebase] Conectado exitosamente.")
except Exception as e:
    print(f"[ERROR Firebase] Verifica google-services.json: {e}")

# --- VARIABLES GLOBALES ---
estado_actual = {
    "personas_dentro_actualmente": 0,
    "estado_chapa": "CERRADA",
    "alerta_pir": False,
    "docente_encargado_uid": None,
    "hora_ingreso_encargado": None,
    "docente_nombre": None
}

# --- FUNCIONES DE CONTROL DE CHAPA ---
def abrir_chapa():
    if estado_actual["estado_chapa"] == "ABIERTA":
        return
        
    print("[CHAPA] Abriendo puerta...")
    estado_actual["estado_chapa"] = "ABIERTA"
    actualizar_monitoreo({"estado_chapa": "ABIERTA"})
    GPIO.output(PIN_RELE_CHAPA, GPIO.HIGH)
    
    # Mantener abierta 5 segundos
    time.sleep(5)
    
    print("[CHAPA] Cerrando puerta...")
    GPIO.output(PIN_RELE_CHAPA, GPIO.LOW)
    estado_actual["estado_chapa"] = "CERRADA"
    actualizar_monitoreo({"estado_chapa": "CERRADA"})

def boton_salida_callback(channel):
    print("[PULSADOR] Botón de salida presionado.")
    threading.Thread(target=abrir_chapa).start()

# Configurar interrupción para el botón
try:
    GPIO.add_event_detect(PIN_PULSADOR_SALIDA, GPIO.FALLING, callback=boton_salida_callback, bouncetime=500)
    print("[GPIO] Deteccion de flanco en pulsador configurada.")
except Exception as e:
    print(f"[WARNING] No se pudo configurar event_detect en GPIO {PIN_PULSADOR_SALIDA}: {e}")
    print("[WARNING] El pulsador fisico no funcionara, pero el sistema continua.")

# --- UTILIDADES FIREBASE ---
def actualizar_monitoreo(datos):
    try:
        ref = db.reference('monitoreo_tiempo_real')
        ref.update(datos)
    except Exception as e:
        print(f"[Error Firebase] {e}")

# Sincronizar estado inicial
actualizar_monitoreo({
    "personas_dentro_actualmente": estado_actual["personas_dentro_actualmente"],
    "estado_chapa": estado_actual["estado_chapa"],
    "alerta_pir": estado_actual["alerta_pir"]
})

# --- HILO RFID ---
def rfid_loop():
    print("[RFID] Escuchando tarjetas...")
    while True:
        try:
            uid_raw, text = reader.read()
            if uid_raw:
                uid = str(uid_raw)
                print(f"[RFID] Tarjeta leída: {uid}")
                procesar_rfid(uid)
                time.sleep(2) # Evitar lecturas múltiples seguidas
        except Exception as e:
            print(f"[RFID Error] {e}")
            time.sleep(1)

def procesar_rfid(uid):
    ref_usuarios = db.reference('usuarios')
    usuario = ref_usuarios.child(uid).get()
    
    ahora_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if usuario:
        nombre = usuario.get('nombre', 'Docente Desconocido')
        rol = usuario.get('rol', 'Docente')
        
        if estado_actual["docente_encargado_uid"] == uid:
            # Salida del encargado
            print(f"[ACCESO] El docente {nombre} ({rol}) está SALIENDO.")
            
            # Calcular tiempo
            t_ingreso = datetime.datetime.strptime(estado_actual["hora_ingreso_encargado"], "%Y-%m-%d %H:%M:%S")
            t_salida = datetime.datetime.now()
            minutos = int((t_salida - t_ingreso).total_seconds() / 60)
            
            # Guardar histórico
            ref_accesos = db.reference('accesos')
            ref_accesos.push({
                "docente": nombre,
                "rol": rol,
                "metodo_acceso": "rfid",
                "codigo_usado": uid,
                "hora_ingreso": estado_actual["hora_ingreso_encargado"],
                "hora_salida": ahora_str,
                "tiempo_permanencia_min": minutos,
                "acompanantes_al_ingresar": estado_actual["personas_dentro_actualmente"],
                "saca_producto": False, # Por defecto
                "producto_extraido_id": ""
            })
            
            # Resetear estado
            estado_actual["docente_encargado_uid"] = None
            estado_actual["hora_ingreso_encargado"] = None
            estado_actual["docente_nombre"] = None
            
        else:
            # Ingreso de un nuevo encargado
            print(f"[ACCESO] El docente {nombre} ({rol}) ha INGRESADO.")
            estado_actual["docente_encargado_uid"] = uid
            estado_actual["hora_ingreso_encargado"] = ahora_str
            estado_actual["docente_nombre"] = nombre
            
        # Abrir la puerta en ambos casos
        threading.Thread(target=abrir_chapa).start()
    else:
        print(f"[ACCESO DENEGADO] UID no registrado: {uid}")

# --- SERVIDOR FLASK (HTTP POST) ---
app = Flask(__name__)

@app.route('/api/sensores', methods=['POST'])
def recibir_sensores():
    data = request.json
    if not data:
        return jsonify({"error": "No JSON"}), 400
        
    evento = data.get("evento")
    
    if evento == "ingreso":
        estado_actual["personas_dentro_actualmente"] += 1
        print(f"[FLUJO] Ingreso. Total: {estado_actual['personas_dentro_actualmente']}")
        actualizar_monitoreo({"personas_dentro_actualmente": estado_actual["personas_dentro_actualmente"]})
        
    elif evento == "salida":
        estado_actual["personas_dentro_actualmente"] = max(0, estado_actual["personas_dentro_actualmente"] - 1)
        print(f"[FLUJO] Salida. Total: {estado_actual['personas_dentro_actualmente']}")
        actualizar_monitoreo({"personas_dentro_actualmente": estado_actual["personas_dentro_actualmente"]})
        
    elif evento == "movimiento_detectado":
        if estado_actual["personas_dentro_actualmente"] == 0:
            print("[ALERTA] ¡Movimiento detectado con aula vacía!")
            estado_actual["alerta_pir"] = True
            actualizar_monitoreo({"alerta_pir": True})
            
            # Guardar evento de alerta histórico
            db.reference('alertas_historicas').push({
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "mensaje": "Movimiento detectado con aula vacía."
            })
        else:
            print("[PIR] Movimiento detectado normal.")
    
    elif evento == "nivel_luz":
        valor_ldr = data.get("valor_ldr", 0)
        nivel_luz = data.get("nivel_luz", "N/A")
        print(f"[LDR] Luz: {valor_ldr} ({nivel_luz})")
        actualizar_monitoreo({
            "valor_ldr": valor_ldr,
            "nivel_luz": nivel_luz
        })
            
    return jsonify({"status": "ok"}), 200


# ────────────────────────────────────────────────────────────────────────────────────────
# ENDPOINT DE ACCESO POR TECLADO (para el otro grupo que usa teclado numérico)
# ────────────────────────────────────────────────────────────────────────────────────────

@app.route('/api/acceso_teclado', methods=['POST'])
def acceso_teclado():
    """
    Endpoint para registrar accesos por teclado numérico.
    El otro grupo envía POST con: {"codigo": "1234", "nombre": "Prof. Juan"}
    """
    data = request.json
    if not data:
        return jsonify({"error": "No JSON"}), 400
    
    codigo = data.get("codigo", "")
    nombre = data.get("nombre", "Usuario Teclado")
    ahora_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"[TECLADO] Acceso por teclado: {nombre} (código: {codigo})")
    
    # Registrar en la tabla compartida de accesos
    ref_accesos = db.reference('accesos')
    ref_accesos.push({
        "docente": nombre,
        "metodo_acceso": "teclado",
        "codigo_usado": codigo,
        "hora_ingreso": ahora_str,
        "hora_salida": None,
        "tiempo_permanencia_min": 0,
        "acompanantes_al_ingresar": estado_actual["personas_dentro_actualmente"],
        "saca_producto": False,
        "producto_extraido_id": ""
    })
    
    # Abrir la puerta
    threading.Thread(target=abrir_chapa).start()
    
    return jsonify({"status": "ok", "mensaje": f"Acceso concedido a {nombre}"}), 200


@app.route('/api/acceso_teclado/salida', methods=['POST'])
def salida_teclado():
    """
    Endpoint para registrar salidas por teclado.
    POST con: {"codigo": "1234", "nombre": "Prof. Juan"}
    """
    data = request.json
    if not data:
        return jsonify({"error": "No JSON"}), 400
    
    codigo = data.get("codigo", "")
    nombre = data.get("nombre", "Usuario Teclado")
    ahora_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"[TECLADO] Salida por teclado: {nombre}")
    
    # Buscar el último acceso de este usuario por teclado y actualizar hora de salida
    ref_accesos = db.reference('accesos')
    accesos = ref_accesos.order_by_child('docente').equal_to(nombre).get()
    
    if accesos:
        # Encontrar el último registro sin salida
        for key, acc in reversed(list(accesos.items())):
            if acc.get('hora_salida') is None:
                t_ingreso = datetime.datetime.strptime(acc['hora_ingreso'], "%Y-%m-%d %H:%M:%S")
                t_salida = datetime.datetime.now()
                minutos = int((t_salida - t_ingreso).total_seconds() / 60)
                
                ref_accesos.child(key).update({
                    "hora_salida": ahora_str,
                    "tiempo_permanencia_min": minutos
                })
                break
    
    return jsonify({"status": "ok"}), 200


# ────────────────────────────────────────────────────────────────────────────────────────
# ENDPOINTS DE CONTROL DEL SISTEMA (usados por Node-RED Dashboard)
# ────────────────────────────────────────────────────────────────────────────────────────

@app.route('/status', methods=['GET'])
def system_status():
    """Devuelve el estado actual del sistema. Usado por Node-RED para monitoreo."""
    try:
        # Uptime del sistema (con fallback si no existe el comando)
        uptime = 'N/A'
        try:
            result = subprocess.run(['uptime', '-p'], capture_output=True, text=True, timeout=5)
            uptime = result.stdout.strip() if result.returncode == 0 else 'N/A'
        except FileNotFoundError:
            try:
                with open('/proc/uptime', 'r') as f:
                    uptime_seconds = float(f.readline().split()[0])
                    hours = int(uptime_seconds // 3600)
                    minutes = int((uptime_seconds % 3600) // 60)
                    uptime = f"up {hours}h {minutes}m"
            except Exception:
                uptime = 'N/A'
        
        # Temperatura de la CPU (disponible en Raspberry Pi)
        temp_celsius = None
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp_raw = int(f.read().strip())
                temp_celsius = round(temp_raw / 1000.0, 1)
        except Exception:
            pass
        
        return jsonify({
            'status': 'online',
            'uptime': uptime,
            'cpu_temp_celsius': temp_celsius,
            'personas_dentro': estado_actual['personas_dentro_actualmente'],
            'estado_chapa': estado_actual['estado_chapa'],
            'alerta_pir': estado_actual['alerta_pir'],
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/shutdown', methods=['POST'])
def shutdown_raspberry():
    """Apaga la Raspberry Pi de forma segura. Llamado desde el dashboard de Node-RED."""
    print("[SISTEMA] ⚠️  Solicitud de APAGADO recibida desde Node-RED Dashboard.")
    try:
        # Programar el apagado con 3 segundos de retardo para que la respuesta HTTP pueda enviarse
        subprocess.Popen(['sudo', 'shutdown', '-h', '+0'],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        return jsonify({
            'status': 'shutting_down',
            'message': 'Raspberry Pi se apagará en breve.',
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }), 200
    except Exception as e:
        print(f"[ERROR SHUTDOWN] {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/reboot', methods=['POST'])
def reboot_raspberry():
    """Reinicia la Raspberry Pi de forma segura. Llamado desde el dashboard de Node-RED."""
    print("[SISTEMA] 🔄 Solicitud de REINICIO recibida desde Node-RED Dashboard.")
    try:
        subprocess.Popen(['sudo', 'reboot'],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        return jsonify({
            'status': 'rebooting',
            'message': 'Raspberry Pi se reiniciará en breve.',
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }), 200
    except Exception as e:
        print(f"[ERROR REBOOT] {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def main():
    try:
        # Iniciar hilo RFID
        t_rfid = threading.Thread(target=rfid_loop, daemon=True)
        t_rfid.start()
        
        # Iniciar Flask (host=0.0.0.0 permite conexiones externas desde la red local)
        print("[FLASK] Iniciando servidor en puerto 5000...")
        app.run(host='0.0.0.0', port=5000, use_reloader=False)
        
    except KeyboardInterrupt:
        pass
    finally:
        print("\n[CLEANUP] Limpiando GPIO...")
        GPIO.cleanup()

if __name__ == "__main__":
    main()
