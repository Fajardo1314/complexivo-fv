import json
import urllib.request
import time
import sys

# URL base de tu Realtime Database en Firebase
FIREBASE_URL = "https://complexivo-fv-default-rtdb.firebaseio.com/monitoreo_tiempo_real.json"

BANNER = """
============================================================
  🚀 SIMULADOR LOCAL ESP32 - PROYECTO DE GRADO
  Actualiza en tiempo real Firebase Realtime Database
============================================================
"""

def patch_firebase(data):
    """Realiza una petición PATCH a Firebase Realtime Database usando urllib."""
    try:
        req_data = json.dumps(data).encode('utf-8')
        req = urllib.request.Request(
            FIREBASE_URL, 
            data=req_data, 
            headers={'Content-Type': 'application/json'},
            method='PATCH'
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                print(f"[OK] Firebase actualizado con éxito: {data}")
                return True
            else:
                print(f"[ERROR] Código de estado de Firebase: {response.status}")
                return False
    except Exception as e:
        print(f"[ERROR] No se pudo conectar a Firebase: {e}")
        return False

def show_menu():
    print("\nSelecciona un caso de prueba o cambio de estado:")
    print("  [1] Abrir Puerta (estado_chapa = ABIERTA)")
    print("  [2] Cerrar Puerta (estado_chapa = CERRADA)")
    print("  [3] Detectar Movimiento (alerta_pir = True)")
    print("  [4] Limpiar Alerta de Movimiento (alerta_pir = False)")
    print("  [5] Incrementar Personas (+1)")
    print("  [6] Decrementar Personas (-1, mín 0)")
    print("  [7] CASO DE INTRUSIÓN CRÍTICA (Puerta Cerrada + Movimiento)")
    print("  [8] Encender Foco (estado_foco = ENCENDIDO)")
    print("  [9] Apagar Foco (estado_foco = APAGADO)")
    print("  [q] Salir")

def main():
    print(BANNER)
    print(f"Apuntando a: {FIREBASE_URL}\n")
    
    # Inicializar estado local de personas (por defecto aforo 0)
    personas = 0
    
    while True:
        show_menu()
        opcion = input("\nOpción: ").strip().lower()
        
        if opcion == 'q':
            print("Saliendo del simulador...")
            break
        elif opcion == '1':
            patch_firebase({"estado_chapa": "ABIERTA"})
        elif opcion == '2':
            patch_firebase({"estado_chapa": "CERRADA"})
        elif opcion == '3':
            patch_firebase({"alerta_pir": True})
        elif opcion == '4':
            patch_firebase({"alerta_pir": False})
        elif opcion == '5':
            personas += 1
            patch_firebase({"personas_dentro_actualmente": personas})
        elif opcion == '6':
            personas = max(0, personas - 1)
            patch_firebase({"personas_dentro_actualmente": personas})
        elif opcion == '7':
            print("\n🚨 Enviando estado de intrusión (Puerta Cerrada + Movimiento)...")
            patch_firebase({
                "estado_chapa": "CERRADA",
                "alerta_pir": True
            })
        elif opcion == '8':
            patch_firebase({"estado_foco": "ENCENDIDO"})
        elif opcion == '9':
            patch_firebase({"estado_foco": "APAGADO"})
        else:
            print("Opción no válida. Inténtalo de nuevo.")

if __name__ == "__main__":
    main()
