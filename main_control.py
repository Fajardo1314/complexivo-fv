import time
import datetime
import threading
import os
import subprocess
import json
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import credentials, db
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    print("[MOCK] paho-mqtt no encontrado. Control de foco via MQTT deshabilitado.")
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

# --- CONFIGURACIÓN FIREBASE (DUAL DATABASE) ---
# DB principal (complexivo-fv): hardware (aforo, PIR, foco, inventario)
# DB staging (new-conexion): puerta_fisica, accesos, codigos_unico (espejo del compañero)

OUR_DB_URL = "https://complexivo-fv-default-rtdb.firebaseio.com/"
STAGING_DB_URL = "https://new-conexion-default-rtdb.firebaseio.com/"

try:
    cred = credentials.Certificate('google-services.json')
    # App principal (nombres por defecto)
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {
            'databaseURL': OUR_DB_URL
        })
    print(f"[Firebase] DB principal conectada: {OUR_DB_URL}")
except Exception as e:
    print(f"[ERROR Firebase principal] Verifica google-services.json: {e}")

# App secundaria para staging (necesita nombre único)
staging_app = None
try:
    staging_app = firebase_admin.initialize_app(
        cred,
        {'databaseURL': STAGING_DB_URL},
        name='staging'
    )
    print(f"[Firebase] DB staging conectada: {STAGING_DB_URL}")
except Exception as e:
    print(f"[Firebase] DB staging no disponible (se omite): {e}")
    staging_app = None

# --- HELPERS DUAL-DATABASE ---
def db_primary():
    """Retorna referencia a la base de datos principal (complexivo-fv)."""
    return db

def db_staging():
    """Retorna referencia a la base de datos staging (new-conexion). Si no está disponible, usa la principal."""
    if staging_app:
        from firebase_admin import db as _db
        return _db.reference('', app=staging_app)
    return db

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

def actualizar_staging(path, datos):
    """Escribe datos en la base de datos staging (new-conexion)."""
    try:
        if staging_app:
            from firebase_admin import db as _db
            ref = _db.reference(path, app=staging_app)
            ref.update(datos)
            print(f"[Staging] {path} actualizado")
        else:
            # Fallback: escribir en DB principal si staging no está disponible
            db.reference(path).update(datos)
    except Exception as e:
        print(f"[Error Staging] {e}")

def push_staging(path, datos):
    """Push un nodo hijo en la base de datos staging (new-conexion)."""
    try:
        if staging_app:
            from firebase_admin import db as _db
            ref = _db.reference(path, app=staging_app)
            ref.push(datos)
            print(f"[Staging] push en {path}")
        else:
            db.reference(path).push(datos)
    except Exception as e:
        print(f"[Error Staging push] {e}")

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

            time.sleep(1)

def registrar_acceso_docente(uid):
    ref_usuarios = db.reference('usuarios')
    usuario = ref_usuarios.child(uid).get()
    
    ahora_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if usuario:
        nombre = usuario.get('nombre', 'Docente Desconocido')
        rol = usuario.get('rol', 'Docente')
        
        # Si el UID existe, limpiamos el último UID no registrado
        actualizar_monitoreo({"ultimo_uid_no_registrado": None})
        
        if estado_actual["docente_encargado_uid"] == uid:
            # Salida del encargado
            print(f"[ACCESO] El docente {nombre} ({rol}) está SALIENDO.")
            
            # Calcular tiempo
            t_ingreso = datetime.datetime.strptime(estado_actual["hora_ingreso_encargado"], "%Y-%m-%d %H:%M:%S")
            t_salida = datetime.datetime.now()
            minutos = int((t_salida - t_ingreso).total_seconds() / 60)
            
            # Guardar histórico (DB principal)
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
                "saca_producto": False,
                "producto_extraido_id": ""
            })
            # Espejo en staging (new-conexion)
            push_staging("accesos", {
                "docente": nombre,
                "rol": rol,
                "metodo": "RFID",
                "metodo_acceso": "rfid",
                "codigo_usado": uid,
                "fecha_hora": ahora_str,
                "hora_ingreso": estado_actual["hora_ingreso_encargado"],
                "hora_salida": ahora_str,
                "tiempo_permanencia_min": minutos,
                "acompanantes_al_ingresar": estado_actual["personas_dentro_actualmente"],
                "exitoso": True
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
        return {"status": "authorized", "nombre": nombre, "rol": rol}
    else:
        print(f"[ACCESO DENEGADO] UID no registrado: {uid}")
        # Guardar último UID no registrado en Firebase para que el frontend despliegue el formulario
        actualizar_monitoreo({"ultimo_uid_no_registrado": uid})
        return {"status": "unregistered", "uid": uid}

def procesar_rfid(uid):
    registrar_acceso_docente(uid)

# --- SERVIDOR FLASK (HTTP POST) ---
app = Flask(__name__)

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'POST, GET, OPTIONS'
    return response

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
        
        # Registrar en base de datos con marca de tiempo
        db.reference('historial_flujo').push({
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "evento": "ingreso",
            "aforo_actual": estado_actual["personas_dentro_actualmente"]
        })
        
    elif evento == "salida":
        estado_actual["personas_dentro_actualmente"] = max(0, estado_actual["personas_dentro_actualmente"] - 1)
        print(f"[FLUJO] Salida. Total: {estado_actual['personas_dentro_actualmente']}")
        actualizar_monitoreo({"personas_dentro_actualmente": estado_actual["personas_dentro_actualmente"]})
        
        # Registrar en base de datos con marca de tiempo
        db.reference('historial_flujo').push({
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "evento": "salida",
            "aforo_actual": estado_actual["personas_dentro_actualmente"]
        })
        
    elif evento == "movimiento_detectado":
        # El sensor PIR solo debe registrar alertas si la puerta está estrictamente CERRADA
        if estado_actual["estado_chapa"] == "CERRADA":
            if estado_actual["personas_dentro_actualmente"] == 0:
                print("[ALERTA] ¡Movimiento detectado con aula vacía y puerta cerrada!")
                estado_actual["alerta_pir"] = True
                actualizar_monitoreo({"alerta_pir": True})
                
                # Guardar evento de alerta histórico
                db.reference('alertas_historicas').push({
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "mensaje": "Movimiento detectado con aula vacía y puerta cerrada."
                })
            else:
                print("[PIR] Movimiento detectado normal (aula ocupada).")
        else:
            print("[PIR] Alerta ignorada porque la puerta está ABIERTA.")
            
    elif evento == "estado_puerta":
        estado = data.get("estado", "CERRADA")  # "ABIERTA" o "CERRADA"
        estado_actual["estado_chapa"] = estado
        actualizar_monitoreo({"estado_chapa": estado})
        # Espejo en staging (new-conexion)
        actualizar_staging("puerta_fisica", {"estado": estado, "ultimo_cambio": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        actualizar_staging("puerta", {"estado": estado, "ultimo_cambio": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        print(f"[PUERTA] Estado del sensor magnético: {estado}")
        
    elif evento == "rfid_leido":
        uid = data.get("uid")
        result = registrar_acceso_docente(uid)
        return jsonify(result), 200
    
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
# ENDPOINTS DE INVENTARIO Y QR MÓVIL
# ────────────────────────────────────────────────────────────────────────────────────────

@app.route('/api/inventario', methods=['POST'])
def registrar_equipo():
    """Registra un equipo en inventario de forma segura y devuelve la URL del QR."""
    data = request.json
    if not data or 'id' not in data or 'nombre' not in data or 'stock' not in data:
        return jsonify({"error": "Faltan campos requeridos (id, nombre, stock)"}), 400
        
    id_prod = data.get("id").strip()
    nombre = data.get("nombre").strip()
    stock = int(data.get("stock", 0))
    categoria = data.get("categoria", "Laboratorio").strip()
    
    try:
        # Transacción segura: Inserción en Firebase
        ref = db.reference('inventario').child(id_prod)
        ref.set({
            "nombre_producto": nombre,
            "stock": stock,
            "categoria": categoria
        })
        
        # Devolver URL dinámica para el código QR
        server_ip = request.host  # Obtiene IP:Puerto actual
        qr_url = f"http://{server_ip}/dashboard/equipo/{id_prod}"
        
        return jsonify({
            "status": "success",
            "qr_url": qr_url,
            "message": "Equipo guardado en la base de datos."
        }), 200
        
    except Exception as e:
        print(f"[ERROR INVENTARIO] Falla en base de datos: {e}")
        return jsonify({"status": "error", "message": f"Error de inserción: {str(e)}"}), 500


@app.route('/dashboard/equipo/<id_equipo>', methods=['GET'])
def ver_equipo(id_equipo):
    """Muestra una interfaz móvil responsiva y elegante del equipo escaneado."""
    try:
        equipo = db.reference('inventario').child(id_equipo).get()
        if not equipo:
            return f"<h1>Equipo {id_equipo} no encontrado</h1>", 404
            
        nombre = equipo.get("nombre_producto", "Material Desconocido")
        stock = equipo.get("stock", 0)
        categoria = equipo.get("categoria", "Equipos")
        estado = equipo.get("estado", "Funcional")
        
        html_responsivo = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Inventario - {nombre}</title>
            <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
            <style>
                :root {{
                    --bg: #070a13;
                    --card-bg: rgba(13, 20, 38, 0.65);
                    --border: rgba(255, 255, 255, 0.08);
                    --primary: #3b82f6;
                    --accent: #8b5cf6;
                    --text: #f8fafc;
                    --text-muted: #94a3b8;
                    --success: #10b981;
                    --danger: #ef4444;
                }}
                body {{
                    background: radial-gradient(circle at 50% 50%, #1e1b4b 0%, #070a13 100%);
                    color: var(--text);
                    font-family: 'Outfit', sans-serif;
                    margin: 0;
                    padding: 20px;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    box-sizing: border-box;
                }}
                .mobile-card {{
                    background: var(--card-bg);
                    backdrop-filter: blur(20px);
                    -webkit-backdrop-filter: blur(20px);
                    border: 1px solid var(--border);
                    border-radius: 24px;
                    padding: 30px;
                    width: 100%;
                    max-width: 380px;
                    box-shadow: 0 15px 40px rgba(0,0,0,0.6);
                    text-align: center;
                }}
                .header-logo {{
                    font-size: 0.85rem;
                    text-transform: uppercase;
                    letter-spacing: 1.5px;
                    color: var(--primary);
                    margin-bottom: 25px;
                    font-weight: 800;
                }}
                h1 {{
                    font-size: 1.6rem;
                    font-weight: 800;
                    margin: 10px 0;
                    line-height: 1.2;
                }}
                .uid {{
                    font-family: monospace;
                    font-size: 0.85rem;
                    color: var(--accent);
                    background: rgba(139, 92, 246, 0.12);
                    border: 1px dashed rgba(139, 92, 246, 0.3);
                    padding: 4px 12px;
                    border-radius: 8px;
                    display: inline-block;
                    margin-bottom: 30px;
                }}
                .info-item {{
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 14px 0;
                    border-bottom: 1px solid var(--border);
                }}
                .info-item:last-child {{
                    border-bottom: none;
                }}
                .label {{
                    color: var(--text-muted);
                    font-size: 0.9rem;
                    font-weight: 500;
                }}
                .value {{
                    font-weight: 600;
                    font-size: 1rem;
                }}
                .badge {{
                    padding: 6px 14px;
                    border-radius: 20px;
                    font-size: 0.8rem;
                    font-weight: 700;
                }}
                .badge-green {{
                    background: rgba(16, 185, 129, 0.15);
                    color: var(--success);
                    border: 1px solid rgba(16, 185, 129, 0.3);
                }}
                .badge-red {{
                    background: rgba(239, 68, 68, 0.15);
                    color: var(--danger);
                    border: 1px solid rgba(239, 68, 68, 0.3);
                }}
            </style>
        </head>
        <body>
            <div class="mobile-card">
                <div class="header-logo">UCUENCA — MATERIAL IOT</div>
                <h1>{nombre}</h1>
                <div class="uid">{id_equipo}</div>
                
                <div class="info-item">
                    <span class="label">Categoría</span>
                    <span class="value" style="color:var(--primary);">{categoria}</span>
                </div>
                <div class="info-item">
                    <span class="label">Estado del Equipo</span>
                    <span class="value">
                        <span class="badge { 'badge-green' if estado == 'Funcional' else 'badge-red' }">
                            {estado}
                        </span>
                    </span>
                </div>
                <div class="info-item">
                    <span class="label">Disponibilidad</span>
                    <span class="value">
                        <span class="badge { 'badge-green' if stock > 0 else 'badge-red' }">
                            {stock} unidades
                        </span>
                    </span>
                </div>
            </div>
        </body>
        </html>
        """
        return html_responsivo, 200
    except Exception as e:
        return f"<h1>Error al cargar equipo: {str(e)}</h1>", 500


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
    
    # Registrar en la tabla compartida de accesos (DB principal)
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
    # Espejo en staging (new-conexion)
    push_staging("accesos", {
        "docente": nombre,
        "metodo": "CODIGO",
        "metodo_acceso": "teclado",
        "codigo_usado": codigo,
        "fecha_hora": ahora_str,
        "hora_ingreso": ahora_str,
        "hora_salida": None,
        "exitoso": True
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

# --- TUYA CLOUD API: Control del Interruptor Inteligente ---
TUYA_ACCESS_ID = "4cg753npk9gxtjwnqr7y"
TUYA_ACCESS_SECRET = "a5e813311035455eab6f92a8d7786ca0"
TUYA_DEVICE_ID = "eb98686bb984169ea7dgfq"
TUYA_ENDPOINT = "https://openapi.tuyaus.com"

tuya_api = None

def inicializar_tuya():
    """Inicializa la conexion con Tuya Cloud API."""
    global tuya_api
    try:
        from tuya_connector import TuyaOpenAPI
        tuya_api = TuyaOpenAPI(TUYA_ENDPOINT, TUYA_ACCESS_ID, TUYA_ACCESS_SECRET)
        tuya_api.connect()
        print("[Tuya] Conectado a Tuya Cloud API")

        # === DIAGNOSTICO: Consultar especificaciones y estado del dispositivo ===
        print("[Tuya] === DIAGNOSTICO DEL DISPOSITIVO ===")

        # 1. Consultar info basica del dispositivo
        info = tuya_api.get(f"/v1.0/devices/{TUYA_DEVICE_ID}")
        print(f"[Tuya] Device Info: {json.dumps(info, indent=2, default=str)}")

        # 2. Consultar estado actual (codigos de funcion disponibles)
        status = tuya_api.get(f"/v1.0/devices/{TUYA_DEVICE_ID}/status")
        print(f"[Tuya] Device Status: {json.dumps(status, indent=2, default=str)}")

        # 3. Consultar especificaciones del producto
        specs = tuya_api.get(f"/v1.0/devices/{TUYA_DEVICE_ID}/specification")
        print(f"[Tuya] Device Spec: {json.dumps(specs, indent=2, default=str)}")

        print("[Tuya] === FIN DIAGNOSTICO ===")

    except ImportError:
        print("[Tuya] tuya-connector-python no instalado. Control de foco deshabilitado.")
    except Exception as e:
        print(f"[Tuya Error] No se pudo conectar: {e}")
        tuya_api = None

def tuya_toggle_foco(encender):
    """Envia comando al interruptor inteligente Tuya para encender/apagar."""
    global tuya_api
    if tuya_api is None:
        print("[Tuya] API no inicializada. Reintentando...")
        inicializar_tuya()
    if tuya_api is None:
        print("[Tuya] No se pudo conectar. Comando ignorado.")
        return False

    estado_str = "ENCENDIDO" if encender else "APAGADO"

    # Probar multiples codigos de comando (varian segun modelo de interruptor)
    codigos_a_probar = ["switch_1", "switch", "master_switch"]

    for codigo in codigos_a_probar:
        try:
            commands = {"commands": [{"code": codigo, "value": encender}]}
            print(f"[Tuya] Intentando '{codigo}' = {encender} ...")
            response = tuya_api.post(f"/v1.0/devices/{TUYA_DEVICE_ID}/commands", commands)
            print(f"[Tuya] Respuesta '{codigo}': {json.dumps(response, default=str)}")

            if response.get("success"):
                print(f"[Tuya] EXITO: Interruptor -> {estado_str} (codigo: {codigo})")
                return True
            else:
                print(f"[Tuya] '{codigo}' fallo, probando siguiente...")

        except Exception as e:
            print(f"[Tuya Error] '{codigo}': {e}")
            continue

    # Si ninguno funciono, reiniciar conexion
    print("[Tuya] Todos los codigos fallaron. Reiniciando conexion...")
    tuya_api = None
    return False

# --- FIREBASE LISTENER: estado_foco → Tuya API ---
def firebase_foco_listener():
    """Escucha cambios en /estado_foco de Firebase y activa el interruptor Tuya."""
    print("[FOCO-LISTENER] Iniciando escucha de estado_foco en Firebase...")
    inicializar_tuya()
    last_value = None

    def callback(event):
        nonlocal last_value
        try:
            nuevo_estado = event.data
            if isinstance(nuevo_estado, str) and nuevo_estado != last_value:
                last_value = nuevo_estado
                val_upper = nuevo_estado.strip().upper()
                encender = val_upper in ("ENCENDIDO", "ON", "TRUE", "1")
                print(f"[FOCO-LISTENER] Firebase cambio: {nuevo_estado} -> Tuya {'ON' if encender else 'OFF'}")
                tuya_toggle_foco(encender)
        except Exception as e:
            print(f"[FOCO-LISTENER Error] {e}")

    try:
        ref = db.reference('estado_foco')
        ref.listen(callback)
    except Exception as e:
        print(f"[FOCO-LISTENER Error] No se pudo escuchar Firebase: {e}")

# --- MQTT SUBSCRIBER: Relay ESP32 → Firebase ---
# El ESP32 publica sus sensores via MQTT local. Este hilo los recibe
# y los sube a las bases de datos Firebase correspondientes.
def mqtt_sensor_relay():
    """Se suscribe a los topics MQTT del ESP32 y retransmite a Firebase."""
    if not MQTT_AVAILABLE:
        print("[MQTT-RELAY] paho-mqtt no disponible. Relay deshabilitado.")
        return

    def on_connect(client, userdata, flags, rc, properties=None):
        print(f"[MQTT-RELAY] Conectado al broker (rc={rc})")
        client.subscribe("movimiento_pir")
        client.subscribe("aforo")
        client.subscribe("puerta_fisica/estado")
        client.subscribe("accesos")
        print("[MQTT-RELAY] Suscrito a: movimiento_pir, aforo, puerta_fisica/estado, accesos")

    def on_message(client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8').strip()
        print(f"[MQTT-RELAY] Recibido: {topic} = {payload}")

        try:
            if topic == "movimiento_pir":
                # PIR → NUESTRA DB (complexivo-fv) en /monitoreo/movimiento_pir
                val = payload.lower() in ("true", "1")
                db.reference('monitoreo/movimiento_pir').set(val)
                print(f"  -> [Firebase OUR] /monitoreo/movimiento_pir = {val}")

            elif topic == "aforo":
                # Aforo → NUESTRA DB (complexivo-fv) en /monitoreo/aforo
                try:
                    payload_limpio = msg.payload.decode('utf-8').strip()
                    valor_numerico = int(payload_limpio)
                    db.reference('monitoreo/aforo').set(valor_numerico)
                    print(f"[DEBUG IR] Enviando aforo numérico a Firebase: {valor_numerico}")
                    print(f"  -> [Firebase OUR] /monitoreo/aforo = {valor_numerico} (OK)")
                except ValueError:
                    print(f"[ERROR IR] No se pudo convertir '{payload_limpio}' a entero")
                except Exception as e:
                    print(f"[ERROR IR] Fallo al enviar aforo a Firebase: {e}")

            elif topic == "puerta_fisica/estado":
                # Convertir a booleano: "1" o "true" → True, "0" o "false" → False
                puerta_abierta = payload.lower() in ("1", "true", "abierta")

                # NUESTRA DB (complexivo-fv): /monitoreo/puerta como BOOLEANO
                db.reference('monitoreo/puerta').set(puerta_abierta)
                print(f"  -> [Firebase OUR] /monitoreo/puerta = {puerta_abierta}")

                # COMPANION DB (new-conexion): /puerta_fisica/estado como STRING
                if staging_app:
                    from firebase_admin import db as _db
                    estado_str = "ABIERTA" if puerta_abierta else "CERRADA"
                    _db.reference('puerta_fisica/estado', app=staging_app).set(estado_str)
                print(f"  -> [Firebase COMPANION] /puerta_fisica/estado = {'ABIERTA' if puerta_abierta else 'CERRADA'}")

            elif topic == "accesos":
                # RFID UID → Validar contra /usuarios y registrar en /accesos de staging
                ahora_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                uid = payload

                # Buscar usuario en NUESTRA DB (complexivo-fv) donde están los usuarios
                usuario = db.reference(f'usuarios/{uid}').get()

                if usuario:
                    nombre = usuario.get('nombre', 'Desconocido')
                    rol = usuario.get('rol', 'Sin rol')
                    print(f"  -> [RFID] Autorizado: {nombre} ({rol})")

                    # Registrar en staging (new-conexion) /accesos
                    if staging_app:
                        from firebase_admin import db as _db
                        _db.reference('accesos', app=staging_app).push({
                            "uid": uid,
                            "docente": nombre,
                            "rol": rol,
                            "metodo": "RFID",
                            "fecha_hora": ahora_str,
                            "exitoso": True
                        })
                    print(f"  -> [Firebase COMPANION] /accesos += {nombre}")
                else:
                    print(f"  -> [RFID] UID NO registrado: {uid}")
                    # Registrar intento fallido en staging
                    if staging_app:
                        from firebase_admin import db as _db
                        _db.reference('accesos', app=staging_app).push({
                            "uid": uid,
                            "metodo": "RFID",
                            "fecha_hora": ahora_str,
                            "exitoso": False
                        })
                    # Notificar al dashboard del UID no registrado
                    db.reference('ultimo_uid_no_registrado').set(uid)

        except Exception as e:
            print(f"[MQTT-RELAY Error] {topic}: {e}")

    try:
        relay_client = mqtt.Client(client_id="rpi-sensor-relay",
                                   callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        relay_client.on_connect = on_connect
        relay_client.on_message = on_message
        # En Docker, usar nombre del contenedor; fuera de Docker, usar localhost
        mqtt_host = "mosquitto" if os.environ.get("DOCKER_CONTAINER") else "127.0.0.1"
        relay_client.connect(mqtt_host, 1883, 60)
        print(f"[MQTT-RELAY] Conectado a broker MQTT en {mqtt_host}:1883")
        print("[MQTT-RELAY] Iniciando loop de relay MQTT → Firebase...")
        relay_client.loop_forever()
    except Exception as e:
        print(f"[MQTT-RELAY Error] No se pudo conectar: {e}")

def main():
    try:
        # Iniciar hilo RFID
        t_rfid = threading.Thread(target=rfid_loop, daemon=True)
        t_rfid.start()

        # Iniciar hilo relay MQTT → Firebase (ESP32 sensors → nube)
        t_relay = threading.Thread(target=mqtt_sensor_relay, daemon=True)
        t_relay.start()

        # Iniciar hilo listener foco Firebase → Tuya API
        t_foco = threading.Thread(target=firebase_foco_listener, daemon=True)
        t_foco.start()
        
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
