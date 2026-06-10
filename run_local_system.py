import os
import sys
import json
import time
import urllib.request
import webbrowser
import threading
import subprocess
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer

# --- CONFIGURACIÓN ---
PORT = 8000
BACKEND_URL = "http://127.0.0.1:5000"
FIREBASE_MONITOR_URL = "https://complexivo-fv-default-rtdb.firebaseio.com/monitoreo_tiempo_real.json"
DEFAULT_COM_PORT = "COM6"  # Especificado en tu documentacion de hardware

BANNER = """
============================================================
  [*] SISTEMA DE CONTROL LOCAL - PROYECTO DE GRADO
============================================================
"""

# Intentar importar serial para la conexión física del ESP32
try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False

def post_to_backend(event_data):
    """Envía un evento al backend Flask (puerto 5000) para que procese la lógica de negocio."""
    try:
        req_data = json.dumps(event_data).encode('utf-8')
        req = urllib.request.Request(
            f"{BACKEND_URL}/api/sensores",
            data=req_data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            resultado = json.loads(response.read().decode())
            return True, resultado
    except Exception as e:
        print(f"  [ERROR Backend] No se pudo enviar al Flask: {e}")
        print(f"  [INFO] ¿Está corriendo el backend en {BACKEND_URL}?")
        return False, {}

def patch_firebase(data):
    """Envia actualizaciones de estado DIRECTAMENTE a Firebase (fallback/compatibilidad)."""
    try:
        req_data = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(
            FIREBASE_MONITOR_URL,
            data=req_data,
            headers={'Content-Type': 'application/json'},
            method='PATCH'
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status == 200
    except Exception as e:
        print(f"  [ERROR Firebase] No se pudo enviar a Firebase: {e}")
        return False

# --- SERVIDOR WEB LOCAL ---
class CustomHTTPRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Evitar problemas de caché durante el desarrollo
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

def start_web_server():
    """Inicia un servidor HTTP local para servir el Dashboard sin problemas de CORS."""
    web_dir = os.path.join(os.path.dirname(__file__), 'web_dashboard')
    os.chdir(web_dir)
    
    # Permitir reutilizar el puerto inmediatamente
    TCPServer.allow_reuse_address = True
    with TCPServer(("", PORT), CustomHTTPRequestHandler) as httpd:
        print(f"[WEB SERVER] Dashboard activo en http://localhost:{PORT}")
        httpd.serve_forever()

# --- MODO 1: SIMULADOR MANUAL ---
def run_manual_simulator():
    print("\n" + "="*50)
    print("  MODO 1: SIMULADOR MANUAL POR TECLADO ACTIVO")
    print("  (Eventos enviados al Backend Flask -> Firebase)")
    print("="*50)
    
    while True:
        print("\nComandos disponibles:")
        print("  [1] Abrir Puerta  (Sensor Magnetico -> ABIERTA)")
        print("  [2] Cerrar Puerta (Sensor Magnetico -> CERRADA)")
        print("  [3] Movimiento PIR detectado")
        print("  [4] Limpiar alerta PIR")
        print("  [5] Entrada de Persona (+1 aforo)")
        print("  [6] Salida de Persona  (-1 aforo)")
        print("  [7] [!] CASO DE INTRUSION (Puerta Cerrada + Movimiento)")
        print("  [8] Simular tarjeta RFID (UID personalizado)")
        print("  [q] Volver al menu principal / Salir")
        
        opcion = input("\nSelecciona una opcion: ").strip().lower()
        if opcion == 'q':
            break

        elif opcion == '1':
            ok, res = post_to_backend({"evento": "estado_puerta", "estado": "ABIERTA"})
            if ok:
                print("-> [OK] Puerta ABIERTA -> Backend -> Firebase.")
            else:
                print("-> [!]  Fallback: enviando directo a Firebase...")
                patch_firebase({"estado_chapa": "ABIERTA"})

        elif opcion == '2':
            ok, res = post_to_backend({"evento": "estado_puerta", "estado": "CERRADA"})
            if ok:
                print("-> [OK] Puerta CERRADA -> Backend -> Firebase.")
            else:
                print("-> [!]  Fallback: enviando directo a Firebase...")
                patch_firebase({"estado_chapa": "CERRADA"})

        elif opcion == '3':
            ok, res = post_to_backend({"evento": "movimiento_detectado"})
            if ok:
                print("-> [OK] Movimiento PIR enviado al Backend (valida estado puerta).")
            else:
                print("-> [!]  Fallback: enviando directo a Firebase...")
                patch_firebase({"alerta_pir": True})

        elif opcion == '4':
            patch_firebase({"alerta_pir": False})
            print("-> [OK] Alerta PIR limpiada directamente en Firebase.")

        elif opcion == '5':
            ok, res = post_to_backend({"evento": "ingreso"})
            if ok:
                print("-> [OK] Ingreso registrado -> Backend proceso el aforo.")
            else:
                print("-> [!]  Fallback directo a Firebase no disponible para aforo.")

        elif opcion == '6':
            ok, res = post_to_backend({"evento": "salida"})
            if ok:
                print("-> [OK] Salida registrada -> Backend proceso el aforo.")
            else:
                print("-> [!]  Fallback directo a Firebase no disponible para aforo.")

        elif opcion == '7':
            print("-> [!] Enviando caso de intrusion critica...")
            ok1, _ = post_to_backend({"evento": "estado_puerta", "estado": "CERRADA"})
            time.sleep(0.3)
            ok2, _ = post_to_backend({"evento": "movimiento_detectado"})
            if ok1 and ok2:
                print("-> [OK] Escenario de intrusion enviado al Backend.")
            else:
                patch_firebase({"estado_chapa": "CERRADA", "alerta_pir": True})

        elif opcion == '8':
            uid = input("  Escribe el UID de la tarjeta RFID a simular: ").strip()
            if uid:
                ok, res = post_to_backend({"evento": "rfid_leido", "uid": uid})
                if ok:
                    estado = res.get('status', '?')
                    nombre = res.get('nombre', '')
                    if estado == 'authorized':
                        print(f"-> [OK] Tarjeta autorizada: {nombre}")
                    elif estado == 'unregistered':
                        print(f"-> [!]  UID no registrado ({uid}). Revisa el panel de Docentes en el Dashboard.")
                    else:
                        print(f"-> Respuesta: {res}")
                else:
                    print("-> [!]  No se pudo conectar al backend.")
            else:
                print("-> UID vacio, ignorado.")

# --- MODO 2: PUENTE SERIAL (ESP32 FÍSICO POR USB) ---
def parse_and_send_serial_line(line, state):
    """Parsea la salida Serial del ESP32 y actualiza Firebase en consecuencia."""
    line = line.strip()
    if not line:
        return

    print(f"[ESP32 Serial] {line}")

    # 1. Parsear Sensor Magnético / Puerta
    if "[PUERTA] Estado: CERRADA" in line:
        patch_firebase({"estado_chapa": "CERRADA"})
        print("  >> Firebase Actualizado: Puerta CERRADA")
    elif "[PUERTA] Estado: ABIERTA" in line:
        patch_firebase({"estado_chapa": "ABIERTA"})
        print("  >> Firebase Actualizado: Puerta ABIERTA")

    # 2. Parsear Movimiento PIR
    elif "[PIR] Alerta" in line or "Movimiento detectado" in line:
        patch_firebase({"alerta_pir": True})
        print("  >> Firebase Actualizado: Movimiento Detectado (PIR)")
        # Programar limpieza automática de la alerta PIR en 6 segundos
        state['pir_timer'] = time.time() + 6.0
        state['pir_active'] = True

    # 3. Parsear Conteo de Personas
    elif "[CONTEO] Personas" in line:
        try:
            parts = line.split(":")
            if len(parts) > 1:
                val = int(parts[1].strip())
                patch_firebase({"personas_dentro_actualmente": val})
                print(f"  >> Firebase Actualizado: Aforo = {val}")
        except Exception as e:
            print(f"  [ERROR Conteo] No se pudo parsear aforo de la línea: {e}")

    # 4. Parsear UID de Tarjeta RFID
    elif "[RFID] Tarjeta Detectada" in line or "UID:" in line:
        try:
            parts = line.split("UID:")
            if len(parts) > 1:
                uid = parts[1].strip()
                patch_firebase({"ultimo_uid_rfid": uid})
                print(f"  >> Firebase Actualizado: Tarjeta RFID UID = {uid}")
        except Exception as e:
            print(f"  [ERROR RFID] No se pudo extraer UID: {e}")

def run_serial_bridge():
    if not SERIAL_AVAILABLE:
        print("\n[ERROR] La librería 'pyserial' no está instalada.")
        print("Por favor instálala ejecutando: pip install pyserial")
        return

    ports = list(serial.tools.list_ports.comports())
    print("\nPuertos COM disponibles:")
    for p in ports:
        print(f"  - {p.device}: {p.description}")
        
    port_name = input(f"\nEscribe el puerto COM del ESP32 [{DEFAULT_COM_PORT}]: ").strip()
    if not port_name:
        port_name = DEFAULT_COM_PORT

    try:
        ser = serial.Serial(port_name, 115200, timeout=1)
        print(f"\n[OK] Conectado a {port_name} a 115200 baudios.")
        print("Escuchando datos del ESP32 y reenviándolos a Firebase...")
        print("Presiona Ctrl+C para detener el puente serial.\n")
        
        state = {'pir_active': False, 'pir_timer': 0}
        
        while True:
            # Leer línea del puerto serial
            if ser.in_waiting > 0:
                try:
                    line = ser.readline().decode('utf-8', errors='replace')
                    parse_and_send_serial_line(line, state)
                except Exception as e:
                    print(f"[ERROR de Lectura Serial]: {e}")
            
            # Limpiar alerta de movimiento por tiempo
            if state['pir_active'] and time.time() > state['pir_timer']:
                patch_firebase({"alerta_pir": False})
                print("  >> Firebase Actualizado: Alerta PIR restablecida a seguro.")
                state['pir_active'] = False
                
            time.sleep(0.05)
            
    except serial.SerialException as e:
        print(f"\n[ERROR] No se pudo abrir el puerto {port_name}: {e}")
        print("Verifica que el ESP32 esté conectado correctamente y que el puerto COM no esté en uso por el monitor de Arduino IDE.")
    except KeyboardInterrupt:
        print("\nPuente serial detenido por el usuario.")

# --- INICIO ---
def main():
    print(BANNER)
    
    # 1. Iniciar Backend Flask (main_control.py) en segundo plano
    backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main_control.py")
    print(f"[SISTEMA] Iniciando Backend Flask en segundo plano: {backend_path}")
    try:
        backend_process = subprocess.Popen(
            [sys.executable, backend_path],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception as e:
        print(f"[SISTEMA] [ERROR] No se pudo iniciar el backend: {e}")
        backend_process = None
    
    # 2. Iniciar servidor web local en segundo plano
    server_thread = threading.Thread(target=start_web_server, daemon=True)
    server_thread.start()
    
    # Esperar un momento a que el servidor web y backend levanten
    time.sleep(2.0)
    
    # 3. Abrir el dashboard en el navegador por defecto
    url = f"http://localhost:{PORT}/index.html"
    print(f"[SISTEMA] Abriendo el navegador web en: {url}")
    webbrowser.open(url)
    
    # 4. Menú de ejecución del sistema
    try:
        while True:
            print("\n" + "="*50)
            print("   COMO DESEAS CONTROLAR EL SISTEMA LOCAL?")
            print("="*50)
            print("  [1] Ejecutar SIMULADOR por teclado (Pruebas manuales rapidas)")
            print("  [2] Ejecutar PUENTE SERIAL (Conectar ESP32 real por cable USB)")
            print("  [q] Salir de todo el sistema")
            
            sel = input("\nElige una opcion: ").strip().lower()
            if sel == 'q':
                print("Deteniendo servicios y saliendo...")
                break
            elif sel == '1':
                run_manual_simulator()
            elif sel == '2':
                run_serial_bridge()
    finally:
        # Detener el backend al salir
        if backend_process:
            print("[SISTEMA] Cerrando backend en segundo plano...")
            backend_process.terminate()
            backend_process.wait()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nCerrando todo el sistema local.")
        sys.exit(0)
