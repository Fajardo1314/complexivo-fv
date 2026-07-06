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
    print("[MOCK] paho-mqtt no encontrado. Control de foco via MQTT deshabilitado.")
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
    print("[MOCK] RPi.GPIO no encontrado. Simulando hardware para PC.")

try:
    from mfrc522 import SimpleMFRC522
except ImportError:
    class SimpleMFRC522:
        def read(self):
            time.sleep(10)
            return None, None
    print("[MOCK] mfrc522 no encontrado. Simulando lector RFID.")

# ============================================================
#  CONFIGURACION DE PINES (RPi)
# ============================================================
PIN_RELE_CHAPA = 17
PIN_PULSADOR_SALIDA = 27

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
            time.sleep(60)
            return None, None
    reader = MockRFIDFallback()

# ============================================================
#  CONFIGURACION FIREBASE
# ============================================================
OUR_DB_URL = "https://complexivo-fv-default-rtdb.firebaseio.com/"

try:
    cred = credentials.Certificate('google-services.json')
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred, {
            'databaseURL': OUR_DB_URL
        })
    print(f"[Firebase] Conectado a: {OUR_DB_URL}")
except Exception as e:
    print(f"[ERROR Firebase] Verifica google-services.json: {e}")

# ============================================================
#  VARIABLES GLOBALES
# ============================================================
estado_actual = {
    "personas_dentro_actualmente": 0,
    "estado_chapa": "CERRADA",
    "alerta_pir": False,
    "docente_encargado_uid": None,
    "hora_ingreso_encargado": None,
    "docente_nombre": None
}

# ============================================================
#  UTILIDADES FIREBASE
# ============================================================
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

# ============================================================
#  FUNCIONES DE CONTROL DE CHAPA (PUERTA)
# ============================================================
_chapa_lock = threading.Lock()

def abrir_chapa():
    """Abre la chapa electrica por 5 segundos y la cierra."""
    with _chapa_lock:
        if estado_actual["estado_chapa"] == "ABIERTA":
            return
        print("[CHAPA] Abriendo puerta...")
        estado_actual["estado_chapa"] = "ABIERTA"
        actualizar_monitoreo({"estado_chapa": "ABIERTA"})
        GPIO.output(PIN_RELE_CHAPA, GPIO.HIGH)
        time.sleep(5)
        print("[CHAPA] Cerrando puerta...")
        GPIO.output(PIN_RELE_CHAPA, GPIO.LOW)
        estado_actual["estado_chapa"] = "CERRADA"
        actualizar_monitoreo({"estado_chapa": "CERRADA"})

def boton_salida_callback(channel):
    print("[PULSADOR] Boton de salida presionado.")
    threading.Thread(target=abrir_chapa, daemon=True).start()

try:
    GPIO.add_event_detect(PIN_PULSADOR_SALIDA, GPIO.FALLING, callback=boton_salida_callback, bouncetime=500)
    print("[GPIO] Deteccion de flanco en pulsador configurada.")
except Exception as e:
    print(f"[WARNING] No se pudo configurar event_detect en GPIO {PIN_PULSADOR_SALIDA}: {e}")

# ============================================================
#  FUNCIONES DE ACCESO RFID
# ============================================================
def registrar_acceso_docente(uid):
    """Valida UID contra Firebase /usuarios, registra acceso y abre puerta."""
    ref_usuarios = db.reference('usuarios')
    usuario = ref_usuarios.child(uid).get()
    ahora_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if usuario:
        nombre = usuario.get('nombre', 'Docente Desconocido')
        rol = usuario.get('rol', 'Docente')
        actualizar_monitoreo({"ultimo_uid_no_registrado": None})

        if estado_actual["docente_encargado_uid"] == uid:
            # Salida del encargado
            print(f"[ACCESO] El docente {nombre} ({rol}) esta SALIENDO.")
            t_ingreso = datetime.datetime.strptime(estado_actual["hora_ingreso_encargado"], "%Y-%m-%d %H:%M:%S")
            t_salida = datetime.datetime.now()
            minutos = int((t_salida - t_ingreso).total_seconds() / 60)
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
        threading.Thread(target=abrir_chapa, daemon=True).start()
        return {"status": "authorized", "nombre": nombre, "rol": rol}
    else:
        print(f"[ACCESO DENEGADO] UID no registrado: {uid}")
        actualizar_monitoreo({"ultimo_uid_no_registrado": uid})
        return {"status": "unregistered", "uid": uid}

def procesar_rfid(uid):
    registrar_acceso_docente(uid)

def rfid_loop():
    print("[RFID] Escuchando tarjetas...")
    while True:
        try:
            uid_raw, text = reader.read()
            if uid_raw:
                uid = str(uid_raw)
                print(f"[RFID] Tarjeta leida: {uid}")
                procesar_rfid(uid)
                time.sleep(2)
        except Exception as e:
            print(f"[RFID Error] {e}")
            time.sleep(1)

# ============================================================
#  SERVIDOR FLASK
# ============================================================
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

    if evento == "rfid_leido":
        uid = data.get("uid")
        result = registrar_acceso_docente(uid)
        return jsonify(result), 200

    elif evento == "nivel_luz":
        valor_ldr = data.get("valor_ldr", 0)
        nivel_luz = data.get("nivel_luz", "N/A")
        print(f"[LDR] Luz: {valor_ldr} ({nivel_luz})")
        actualizar_monitoreo({"valor_ldr": valor_ldr, "nivel_luz": nivel_luz})

    return jsonify({"status": "ok"}), 200


# ============================================================
#  ENDPOINT: REGISTRO DE ACCESO DESDE NEW-CONEXION
#  El otro grupo (new-conexion) envia codigos aqui para
#  que nosotros validemos y abramos la puerta.
# ============================================================
@app.route('/api/registro_acceso', methods=['POST'])
def registro_acceso_externo():
    """
    Endpoint para que new-conexion envie codigos de tarjeta validados.
    POST con: {"codigo": "UID_TARJETA", "nombre": "Prof. Juan", "accion": "ingreso|salida"}
    """
    data = request.json
    if not data:
        return jsonify({"error": "No JSON"}), 400

    codigo = data.get("codigo", "")
    nombre = data.get("nombre", "Usuario Externo")
    accion = data.get("accion", "ingreso")
    ahora_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print(f"[NEW-CONEXION] Acceso recibido: {nombre} (codigo: {codigo}, accion: {accion})")

    if accion == "ingreso":
        # Registrar ingreso
        ref_accesos = db.reference('accesos')
        ref_accesos.push({
            "docente": nombre,
            "metodo_acceso": "new-conexion",
            "codigo_usado": codigo,
            "hora_ingreso": ahora_str,
            "hora_salida": None,
            "tiempo_permanencia_min": 0,
            "acompanantes_al_ingresar": estado_actual["personas_dentro_actualmente"],
            "saca_producto": False,
            "producto_extraido_id": ""
        })
        # Abrir la puerta
        threading.Thread(target=abrir_chapa, daemon=True).start()
        print(f"[NEW-CONEXION] Puerta abierta para {nombre}")
        return jsonify({"status": "ok", "mensaje": f"Acceso concedido a {nombre}"}), 200

    elif accion == "salida":
        # Buscar ultimo acceso sin salida
        ref_accesos = db.reference('accesos')
        accesos = ref_accesos.order_by_child('docente').equal_to(nombre).get()
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
        return jsonify({"status": "ok", "mensaje": f"Salida registrada para {nombre}"}), 200

    return jsonify({"error": "Accion no valida"}), 400


# ============================================================
#  ENDPOINT: ACCESO POR TECLADO (otro grupo)
# ============================================================
@app.route('/api/acceso_teclado', methods=['POST'])
def acceso_teclado():
    data = request.json
    if not data:
        return jsonify({"error": "No JSON"}), 400
    codigo = data.get("codigo", "")
    nombre = data.get("nombre", "Usuario Teclado")
    ahora_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[TECLADO] Acceso por teclado: {nombre} (codigo: {codigo})")
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
    threading.Thread(target=abrir_chapa, daemon=True).start()
    return jsonify({"status": "ok", "mensaje": f"Acceso concedido a {nombre}"}), 200


@app.route('/api/acceso_teclado/salida', methods=['POST'])
def salida_teclado():
    data = request.json
    if not data:
        return jsonify({"error": "No JSON"}), 400
    codigo = data.get("codigo", "")
    nombre = data.get("nombre", "Usuario Teclado")
    ahora_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[TECLADO] Salida por teclado: {nombre}")
    ref_accesos = db.reference('accesos')
    accesos = ref_accesos.order_by_child('docente').equal_to(nombre).get()
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
    return jsonify({"status": "ok"}), 200


# ============================================================
#  ENDPOINT: ENVIAR CORREO (usado por el dashboard web)
# ============================================================
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "smartstock97@gmail.com"
SMTP_PASS = "F@jardo123"

@app.route('/send-otp', methods=['POST'])
def send_otp():
    """Genera un codigo OTP de 6 digitos, lo guarda en Firebase y lo envia por correo."""
    import random
    data = request.json
    if not data or 'correo' not in data:
        return jsonify({"error": "Falta campo 'correo'"}), 400

    correo = data['correo']
    codigo = str(random.randint(100000, 999999))

    # Guardar OTP en Firebase con expiracion de 5 minutos
    import time as _time
    db.reference('otp_temp').set({
        "codigo": codigo,
        "correo": correo,
        "expira_en": int(_time.time()) + 300,  # 5 minutos
        "usado": False
    })

    # Enviar por correo
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SMTP_USER
        msg["To"] = correo
        msg["Subject"] = "Smart Stock - Codigo de Verificacion"
        body = f"Tu codigo de verificacion es: {codigo}\n\nEste codigo expira en 5 minutos.\n\nNo compartas este codigo con nadie."
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, correo, msg.as_string())

        print(f"[OTP] Codigo enviado a: {correo}")
        return jsonify({"ok": True, "message": "OTP enviado"}), 200
    except Exception as e:
        print(f"[OTP Error] {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    """Verifica el codigo OTP ingresado por el usuario."""
    import time as _time
    data = request.json
    if not data or 'codigo' not in data:
        return jsonify({"error": "Falta campo 'codigo'"}), 400

    codigo_ingresado = str(data['codigo']).strip()
    otp_data = db.reference('otp_temp').get()

    if not otp_data:
        return jsonify({"valido": False, "error": "No hay OTP pendiente"}), 400

    if otp_data.get('usado'):
        return jsonify({"valido": False, "error": "OTP ya utilizado"}), 400

    if int(_time.time()) > otp_data.get('expira_en', 0):
        return jsonify({"valido": False, "error": "OTP expirado"}), 400

    if codigo_ingresado == str(otp_data.get('codigo', '')):
        db.reference('otp_temp').update({"usado": True})
        print("[OTP] Verificacion exitosa")
        return jsonify({"valido": True}), 200
    else:
        return jsonify({"valido": False, "error": "Codigo incorrecto"}), 400


@app.route('/ultimo-rfid', methods=['GET'])
def ultimo_rfid():
    """Devuelve el ultimo UID RFID leido no registrado (usado por dashboard para asignar tarjetas)."""
    uid = db.reference('monitoreo_tiempo_real/ultimo_uid_no_registrado').get()
    return jsonify({"uid": uid}), 200


@app.route('/api/send-email', methods=['POST', 'OPTIONS'])
def send_email():
    """Envia correos electronicos via SMTP. Usado por el dashboard para OTP y notificaciones."""
    if request.method == 'OPTIONS':
        response = jsonify({"ok": True})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response, 200

    data = request.json
    if not data:
        return jsonify({"error": "No JSON"}), 400

    to_addr = data.get("to", "")
    subject = data.get("subject", "Smart Stock - Notificacion")
    body_text = data.get("body", "")

    if not to_addr:
        return jsonify({"error": "Falta campo 'to'"}), 400

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = SMTP_USER
        msg["To"] = to_addr
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_addr, msg.as_string())

        print(f"[Email] Correo enviado a: {to_addr}")
        return jsonify({"ok": True, "message": "Correo enviado"}), 200
    except smtplib.SMTPAuthenticationError as e:
        print(f"[Email] Error de autenticacion SMTP: {e}")
        return jsonify({"error": "Error de autenticacion SMTP"}), 500
    except Exception as e:
        print(f"[Email] Error al enviar correo: {e}")
        return jsonify({"error": str(e)}), 500


# ============================================================
#  ENDPOINTS DE INVENTARIO
# ============================================================
@app.route('/api/inventario', methods=['POST'])
def registrar_equipo():
    data = request.json
    if not data or 'id' not in data or 'nombre' not in data or 'stock' not in data:
        return jsonify({"error": "Faltan campos requeridos (id, nombre, stock)"}), 400
    id_prod = data.get("id").strip()
    nombre = data.get("nombre").strip()
    stock = int(data.get("stock", 0))
    categoria = data.get("categoria", "Laboratorio").strip()
    marca = data.get("marca", "").strip()
    descripcion = data.get("descripcion", "").strip()
    try:
        ref = db.reference('inventario').child(id_prod)
        ref.set({
            "nombre_producto": nombre,
            "stock": stock,
            "categoria": categoria,
            "marca": marca,
            "descripcion": descripcion
        })
        server_ip = request.host
        qr_url = f"http://{server_ip}/retiro.html?id={id_prod}"
        return jsonify({"status": "success", "qr_url": qr_url, "message": "Equipo guardado."}), 200
    except Exception as e:
        print(f"[ERROR INVENTARIO] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/dashboard/equipo/<id_equipo>', methods=['GET'])
def ver_equipo(id_equipo):
    """Muestra interfaz movil del equipo escaneado (redirect a retiro.html)."""
    try:
        equipo = db.reference('inventario').child(id_equipo).get()
        if not equipo:
            return f"<h1>Equipo {id_equipo} no encontrado</h1>", 404
        nombre = equipo.get("nombre_producto", "Material Desconocido")
        stock = equipo.get("stock", 0)
        categoria = equipo.get("categoria", "Equipos")
        estado = equipo.get("estado", "Funcional")
        marca = equipo.get("marca", "")
        descripcion = equipo.get("descripcion", "")

        html_responsivo = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Inventario - {nombre}</title>
            <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
            <style>
                :root {{ --bg: #070a13; --card-bg: rgba(13, 20, 38, 0.65); --border: rgba(255,255,255,0.08); --primary: #3b82f6; --accent: #8b5cf6; --text: #f8fafc; --text-muted: #94a3b8; --success: #10b981; --danger: #ef4444; }}
                body {{ background: radial-gradient(circle at 50% 50%, #1e1b4b 0%, #070a13 100%); color: var(--text); font-family: 'Outfit', sans-serif; margin: 0; padding: 20px; display: flex; justify-content: center; align-items: center; min-height: 100vh; box-sizing: border-box; }}
                .mobile-card {{ background: var(--card-bg); backdrop-filter: blur(20px); border: 1px solid var(--border); border-radius: 24px; padding: 30px; width: 100%; max-width: 380px; box-shadow: 0 15px 40px rgba(0,0,0,0.6); text-align: center; }}
                .header-logo {{ font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1.5px; color: var(--primary); margin-bottom: 25px; font-weight: 800; }}
                h1 {{ font-size: 1.6rem; font-weight: 800; margin: 10px 0; }}
                .uid {{ font-family: monospace; font-size: 0.85rem; color: var(--accent); background: rgba(139,92,246,0.12); border: 1px dashed rgba(139,92,246,0.3); padding: 4px 12px; border-radius: 8px; display: inline-block; margin-bottom: 30px; }}
                .info-item {{ display: flex; justify-content: space-between; align-items: center; padding: 14px 0; border-bottom: 1px solid var(--border); }}
                .info-item:last-child {{ border-bottom: none; }}
                .label {{ color: var(--text-muted); font-size: 0.9rem; }}
                .value {{ font-weight: 600; font-size: 1rem; }}
                .badge {{ padding: 6px 14px; border-radius: 20px; font-size: 0.8rem; font-weight: 700; }}
                .badge-green {{ background: rgba(16,185,129,0.15); color: var(--success); border: 1px solid rgba(16,185,129,0.3); }}
                .badge-red {{ background: rgba(239,68,68,0.15); color: var(--danger); border: 1px solid rgba(239,68,68,0.3); }}
                .desc {{ color: var(--text-muted); font-size: 0.85rem; margin: 10px 0; line-height: 1.5; }}
            </style>
        </head>
        <body>
            <div class="mobile-card">
                <div class="header-logo">UCUENCA - MATERIAL IOT</div>
                <h1>{nombre}</h1>
                <div class="uid">{id_equipo}</div>
                {"<p class='desc'><strong>Marca:</strong> " + marca + "</p>" if marca else ""}
                {"<p class='desc'>" + descripcion + "</p>" if descripcion else ""}
                <div class="info-item"><span class="label">Categoria</span><span class="value" style="color:var(--primary);">{categoria}</span></div>
                <div class="info-item"><span class="label">Estado</span><span class="value"><span class="badge {'badge-green' if estado == 'Funcional' else 'badge-red'}">{estado}</span></span></div>
                <div class="info-item"><span class="label">Disponibilidad</span><span class="value"><span class="badge {'badge-green' if stock > 0 else 'badge-red'}">{stock} unidades</span></span></div>
                <a href="/" style="display:block;margin-top:20px;color:var(--primary);text-decoration:none;font-weight:600;">Ir al Dashboard</a>
            </div>
        </body>
        </html>
        """
        return html_responsivo, 200
    except Exception as e:
        return f"<h1>Error: {str(e)}</h1>", 500


# ============================================================
#  ENDPOINTS DE CONTROL DEL SISTEMA
# ============================================================
@app.route('/status', methods=['GET'])
def system_status():
    try:
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
        temp_celsius = None
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp_celsius = round(int(f.read().strip()) / 1000.0, 1)
        except Exception:
            pass
        return jsonify({
            'status': 'online', 'uptime': uptime, 'cpu_temp_celsius': temp_celsius,
            'personas_dentro': estado_actual['personas_dentro_actualmente'],
            'estado_chapa': estado_actual['estado_chapa'],
            'alerta_pir': estado_actual['alerta_pir'],
            'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/shutdown', methods=['POST'])
def shutdown_raspberry():
    print("[SISTEMA] Solicitud de APAGADO recibida.")
    try:
        subprocess.Popen(['sudo', 'shutdown', '-h', '+0'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return jsonify({'status': 'shutting_down', 'message': 'Raspberry Pi se apagara en breve.'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/reboot', methods=['POST'])
def reboot_raspberry():
    print("[SISTEMA] Solicitud de REINICIO recibida.")
    try:
        subprocess.Popen(['sudo', 'reboot'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return jsonify({'status': 'rebooting', 'message': 'Raspberry Pi se reiniciara en breve.'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ============================================================
#  TUYA CLOUD API: Control del Interruptor Inteligente
# ============================================================
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
        print("[Tuya] Conectado a Tuya Cloud API")
        # Diagnostico
        status = tuya_api.get(f"/v1.0/devices/{TUYA_DEVICE_ID}/status")
        print(f"[Tuya] Device Status: {json.dumps(status, default=str)}")
    except ImportError:
        print("[Tuya] tuya-connector-python no instalado.")
    except Exception as e:
        print(f"[Tuya Error] No se pudo conectar: {e}")
        tuya_api = None

def tuya_toggle_foco(encender):
    global tuya_api
    if tuya_api is None:
        inicializar_tuya()
    if tuya_api is None:
        return False
    estado_str = "ENCENDIDO" if encender else "APAGADO"
    codigos = ["switch_1", "switch", "master_switch"]
    for codigo in codigos:
        try:
            commands = {"commands": [{"code": codigo, "value": encender}]}
            response = tuya_api.post(f"/v1.0/devices/{TUYA_DEVICE_ID}/commands", commands)
            if response.get("success"):
                print(f"[Tuya] Interruptor -> {estado_str} (codigo: {codigo})")
                return True
        except Exception as e:
            print(f"[Tuya Error] '{codigo}': {e}")
            continue
    tuya_api = None
    return False


# ============================================================
#  FIREBASE LISTENER: estado_foco -> Tuya API
#  UNICO canal de control de iluminacion
# ============================================================
def firebase_foco_listener():
    """Escucha /estado_foco en Firebase y envia comando al interruptor Tuya."""
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
                print(f"[FOCO-LISTENER] Firebase: {nuevo_estado} -> Tuya {'ON' if encender else 'OFF'}")
                tuya_toggle_foco(encender)
        except Exception as e:
            print(f"[FOCO-LISTENER Error] {e}")

    try:
        ref = db.reference('estado_foco')
        ref.listen(callback)
    except Exception as e:
        print(f"[FOCO-LISTENER Error] {e}")


# ============================================================
#  MQTT RELAY: ESP32 -> Firebase
#  UNICA fuente de datos de sensores
# ============================================================
mqtt_pub_client = None

# Variables para histéresis de iluminación (evitar parpadeo)
_luz_estado_actual = None  # "ENCENDIDO" o "APAGADO"
_luz_ultimo_cambio = 0     # timestamp del último cambio
_LUZ_COOLDOWN = 60         # segundos mínimo entre cambios

def _es_horario_luces():
    """Retorna True si estamos en horario de operacion de luces (6:30 - 22:00)."""
    ahora = datetime.datetime.now().time()
    inicio = datetime.time(6, 30)
    fin = datetime.time(22, 0)
    return inicio <= ahora < fin

def mqtt_sensor_relay():
    global mqtt_pub_client
    if not MQTT_AVAILABLE:
        print("[MQTT-RELAY] paho-mqtt no disponible.")
        return

    def on_connect(client, userdata, flags, rc, properties=None):
        print(f"[MQTT-RELAY] Conectado al broker (rc={rc})")
        client.subscribe("movimiento_pir")
        client.subscribe("aforo")
        client.subscribe("puerta_fisica/estado")
        client.subscribe("accesos")
        client.subscribe("aula/luminosidad")
        print("[MQTT-RELAY] Suscrito a: movimiento_pir, aforo, puerta_fisica/estado, accesos, aula/luminosidad")

        # Resetear estado de puerta a CERRADA por defecto al reconectar
        # (el ESP32 solo envia cuando cambia, el valor en Firebase puede estar desactualizado)
        db.reference('monitoreo/puerta').set(False)
        db.reference('monitoreo/estado_puerta').set("CERRADA")
        estado_actual["estado_chapa"] = "CERRADA"
        print("[MQTT-RELAY] Estado puerta reseteado a CERRADA por defecto")

    def on_message(client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8').strip()
        print(f"[MQTT-RELAY] Recibido: {topic} = {payload}")

        try:
            # ── PIR ──────────────────────────────────────────
            if topic == "movimiento_pir":
                val = payload.lower() in ("true", "1")
                db.reference('monitoreo/movimiento_pir').set(val)

                # Registrar alerta si aforo==0 y puerta cerrada
                if val:
                    aforo = estado_actual.get("personas_dentro_actualmente", 0)
                    puerta = estado_actual.get("estado_chapa", "CERRADA")
                    if aforo == 0 and puerta == "CERRADA":
                        ahora_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        db.reference('alertas_historicas').push({
                            "timestamp": ahora_str,
                            "tipo": "intrusion",
                            "mensaje": "Movimiento detectado con aula vacia y puerta cerrada.",
                            "aforo": aforo,
                            "puerta": puerta
                        })
                        print("[ALERTA] Intrusion detectada! Registrada en alertas_historicas.")

            # ── AFORO ────────────────────────────────────────
            elif topic == "aforo":
                try:
                    valor_numerico = int(payload)
                    if valor_numerico < 0:
                        valor_numerico = 0
                    db.reference('monitoreo/aforo').set(valor_numerico)
                    # Actualizar estado local para PIR
                    estado_actual["personas_dentro_actualmente"] = valor_numerico
                    print(f"[AFORO] {valor_numerico} personas")
                except ValueError:
                    print(f"[ERROR IR] Payload no numerico: '{payload}'")

            # ── PUERTA MAGNETICA ─────────────────────────────
            elif topic == "puerta_fisica/estado":
                puerta_abierta = payload.lower() in ("1", "true", "abierta")
                db.reference('monitoreo/puerta').set(puerta_abierta)
                estado_str = "ABIERTA" if puerta_abierta else "CERRADA"
                db.reference('monitoreo/estado_puerta').set(estado_str)
                estado_actual["estado_chapa"] = estado_str
                print(f"[PUERTA] {estado_str}")

            # ── RFID ACCESOS ─────────────────────────────────
            elif topic == "accesos":
                uid = payload
                usuario = db.reference(f'usuarios/{uid}').get()
                ahora_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if usuario:
                    nombre = usuario.get('nombre', 'Desconocido')
                    rol = usuario.get('rol', 'Sin rol')
                    print(f"[RFID] Autorizado: {nombre} ({rol})")

                    # Registrar en /accesos
                    ref_accesos = db.reference('accesos')
                    ref_accesos.push({
                        "docente": nombre,
                        "rol": rol,
                        "metodo_acceso": "rfid",
                        "codigo_usado": uid,
                        "hora_ingreso": ahora_str,
                        "hora_salida": None,
                        "tiempo_permanencia_min": 0,
                        "acompanantes_al_ingresar": estado_actual.get("personas_dentro_actualmente", 0),
                        "saca_producto": False,
                        "producto_extraido_id": ""
                    })

                    # Abrir la puerta
                    threading.Thread(target=abrir_chapa, daemon=True).start()
                    print(f"[RFID] Puerta abierta para {nombre}")
                else:
                    print(f"[RFID] UID NO registrado: {uid}")
                    db.reference('monitoreo_tiempo_real').update({"ultimo_uid_no_registrado": uid})

            # ── LUMINOSIDAD (BH1750) con HISTERESIS ──────────
            elif topic == "aula/luminosidad":
                global _luz_estado_actual, _luz_ultimo_cambio
                try:
                    lux_actual = float(payload)
                except (ValueError, TypeError):
                    print(f"[LUZ] Payload invalido: '{payload}'")
                    return

                # Ignorar lecturas de 0.0 (sensor desconectado o error)
                if lux_actual <= 0:
                    print(f"[LUZ] Lectura 0.0 ignorada (posible sensor desconectado)")
                    return

                # Leer umbral base desde Firebase (default 70)
                umbral_base = 70
                try:
                    raw = db.reference('configuracion/umbral_luxes').get()
                    if raw is not None and float(raw) > 0:
                        umbral_base = float(raw)
                except Exception:
                    pass

                # HISTERESIS: dos umbrales para evitar parpadeo
                # Umbral bajo: encender si lux < umbral_bajo
                # Umbral alto: apagar si lux > umbral_alto (mas alto para ignorar luz artificial)
                UMBRAL_BAJO = umbral_base
                UMBRAL_ALTO = umbral_base * 3  # 3x mas alto para ignorar la luz del foco

                # Guardar lectura actual
                db.reference('monitoreo/lux_actual').set(round(lux_actual, 1))

                # Verificar horario de operacion (6:30 - 22:00)
                if not _es_horario_luces():
                    if _luz_estado_actual != "APAGADO":
                        db.reference('monitoreo/estado_luces').set(0)
                        db.reference('estado_foco').set("APAGADO")
                        _luz_estado_actual = "APAGADO"
                    print(f"[LUZ] Fuera de horario ({datetime.datetime.now().strftime('%H:%M')}). Sin control automatico.")
                    return

                # Verificar cooldown (60 seg minimo entre cambios)
                ahora_ts = int(time.time())
                if ahora_ts - _luz_ultimo_cambio < _LUZ_COOLDOWN:
                    print(f"[LUZ] Cooldown activo ({_LUZ_COOLDOWN - (ahora_ts - _luz_ultimo_cambio)}s restantes). Lux={lux_actual}")
                    return

                # Evaluar con histéresis
                nuevo_estado = None
                if lux_actual < UMBRAL_BAJO and _luz_estado_actual != "ENCENDIDO":
                    nuevo_estado = "ENCENDIDO"
                    print(f"[LUZ] Poca luz ({lux_actual} < {UMBRAL_BAJO}). Encendiendo.")
                elif lux_actual > UMBRAL_ALTO and _luz_estado_actual != "APAGADO":
                    nuevo_estado = "APAGADO"
                    print(f"[LUZ] Luz suficiente ({lux_actual} > {UMBRAL_ALTO}). Apagando.")
                elif _luz_estado_actual is None:
                    # Primera lectura: decidir estado inicial
                    nuevo_estado = "ENCENDIDO" if lux_actual < UMBRAL_BAJO else "APAGADO"
                    print(f"[LUZ] Estado inicial: {nuevo_estado} (lux={lux_actual})")

                if nuevo_estado:
                    _luz_estado_actual = nuevo_estado
                    _luz_ultimo_cambio = ahora_ts
                    es_on = nuevo_estado == "ENCENDIDO"
                    db.reference('monitoreo/estado_luces').set(1 if es_on else 0)
                    db.reference('estado_foco').set(nuevo_estado)
                    print(f"[LUZ] >>> Estado cambiado a {nuevo_estado}. Cooldown {_LUZ_COOLDOWN}s.")

        except Exception as e:
            print(f"[MQTT-RELAY Error] {topic}: {e}")

    try:
        relay_client = mqtt.Client(client_id="rpi-sensor-relay",
                                   callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        relay_client.on_connect = on_connect
        relay_client.on_message = on_message
        mqtt_host = "mosquitto" if os.environ.get("DOCKER_CONTAINER") else "127.0.0.1"
        relay_client.connect(mqtt_host, 1883, 60)
        mqtt_pub_client = relay_client
        print(f"[MQTT-RELAY] Conectado a broker MQTT en {mqtt_host}:1883")
        relay_client.loop_forever()
    except Exception as e:
        print(f"[MQTT-RELAY Error] No se pudo conectar: {e}")


# ============================================================
#  MAIN
# ============================================================
def main():
    try:
        t_rfid = threading.Thread(target=rfid_loop, daemon=True)
        t_rfid.start()

        t_relay = threading.Thread(target=mqtt_sensor_relay, daemon=True)
        t_relay.start()

        t_foco = threading.Thread(target=firebase_foco_listener, daemon=True)
        t_foco.start()

        print("[FLASK] Iniciando servidor en puerto 5000...")
        app.run(host='0.0.0.0', port=5000, use_reloader=False)

    except KeyboardInterrupt:
        pass
    finally:
        print("\n[CLEANUP] Limpiando GPIO...")
        GPIO.cleanup()

if __name__ == "__main__":
    main()