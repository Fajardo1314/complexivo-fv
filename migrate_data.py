import json
import os
import firebase_admin
from firebase_admin import credentials, db

# CONFIGURACION
BACKUP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data_base", "current_db_backup.json")
CRED_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "google-services.json")

# URL de las bases de datos
OLD_DB_URL = "https://complexivo-fv-default-rtdb.firebaseio.com"
NEW_DB_URL = "https://aula-4587b-default-rtdb.firebaseio.com"

# Nodos a omitir para no interferir con la base del otro proyecto
NODOS_A_OMITIR = ["puerta", "puerta_fisica"]

def cargar_credenciales():
    if not os.path.exists(CRED_PATH):
        raise FileNotFoundError(f"No se encontró el archivo de credenciales en {CRED_PATH}")
    with open(CRED_PATH, 'r') as f:
        return json.load(f)

def inicializar_firebase(project_id, db_url):
    # Limpiar app previa si existe
    if firebase_admin._apps:
        for app_name in list(firebase_admin._apps.keys()):
            app = firebase_admin._apps[app_name]
            firebase_admin.delete_app(app)
            
    cred = credentials.Certificate(CRED_PATH)
    firebase_admin.initialize_app(cred, {
        'databaseURL': db_url
    })

def fase1_backup():
    print("\n--- FASE 1: DESCARGA DE RESPALDO DESDE LA BASE VIEJA ---")
    try:
        cred_data = cargar_credenciales()
        project_id = cred_data.get("project_id")
        
        if project_id != "complexivo-fv":
            print(f"[ERROR] El archivo google-services.json actual es para el proyecto '{project_id}'.")
            print("Para la FASE 1, debes usar el google-services.json de 'complexivo-fv' para poder descargar los datos.")
            return False
            
        print(f"[INFO] Inicializando conexión con la base vieja ({project_id})...")
        inicializar_firebase(project_id, OLD_DB_URL)
        
        print("[INFO] Leyendo todos los nodos de la base de datos...")
        ref_raiz = db.reference("/")
        datos = ref_raiz.get()
        
        if not datos:
            print("[ADVERTENCIA] La base de datos está vacía.")
            datos = {}
            
        # Asegurarnos de que el directorio del backup exista
        os.makedirs(os.path.dirname(BACKUP_FILE), exist_ok=True)
        
        print(f"[INFO] Guardando respaldo en: {BACKUP_FILE}")
        with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)
            
        print("[OK] Fase 1 completada con éxito.")
        return True
    except Exception as e:
        print(f"[ERROR] Error durante la Fase 1: {e}")
        return False

def fase2_restore():
    print("\n--- FASE 2: CARGA DE DATOS A LA NUEVA BASE DE DATOS ---")
    try:
        if not os.path.exists(BACKUP_FILE):
            print(f"[ERROR] No se encontró el archivo de respaldo {BACKUP_FILE}.")
            print("Debes ejecutar primero la FASE 1 usando el google-services.json viejo.")
            return
            
        cred_data = cargar_credenciales()
        project_id = cred_data.get("project_id")
        
        if project_id != "aula-4587b":
            print(f"[ERROR] El archivo google-services.json actual es para el proyecto '{project_id}'.")
            print("Para la FASE 2, debes reemplazar google-services.json con el archivo del nuevo proyecto 'aula-4587b'.")
            return
            
        print(f"[INFO] Inicializando conexión con la base nueva ({project_id})...")
        inicializar_firebase(project_id, NEW_DB_URL)
        
        print(f"[INFO] Cargando datos desde el respaldo: {BACKUP_FILE}")
        with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
            datos = json.load(f)
            
        print("[INFO] Iniciando importación no destructiva...")
        for clave, valor in datos.items():
            if clave in NODOS_A_OMITIR:
                print(f" -> [OMITIDO] Nodo /{clave} (omitido para proteger la base del otro proyecto)")
                continue
                
            print(f" -> Migrando nodo: /{clave} ...")
            try:
                ref = db.reference(clave)
                ref.set(valor)
                print(f" -> [OK] Nodo /{clave} migrado.")
            except Exception as e:
                print(f" -> [ERROR] Error al migrar nodo /{clave}: {e}")
                
        print("\n=== MIGRACIÓN COMPLETADA EXITOSAMENTE ===")
        print("[INFO] Se omitieron los nodos compartidos 'puerta' y 'puerta_fisica' para evitar conflictos.")
    except Exception as e:
        print(f"[ERROR] Error durante la Fase 2: {e}")

def main():
    print("==================================================")
    print("      GESTOR DE MIGRACIÓN SMART STOCK")
    print("==================================================")
    print("1. Fase 1: Descargar respaldo de base de datos vieja (usa google-services.json viejo)")
    print("2. Fase 2: Cargar respaldo a base de datos nueva (usa google-services.json nuevo)")
    print("--------------------------------------------------")
    
    # Auto-detección de fase basada en el google-services.json actual
    try:
        cred_data = cargar_credenciales()
        project_id = cred_data.get("project_id")
        print(f"[Detección] google-services.json actual corresponde al proyecto: {project_id}")
        
        if project_id == "complexivo-fv":
            print("[Detección] Se ejecutará la FASE 1 de descarga.")
            fase1_backup()
        elif project_id == "aula-4587b":
            print("[Detección] Se ejecutará la FASE 2 de restauración.")
            fase2_restore()
        else:
            print("[ADVERTENCIA] Proyecto desconocido en google-services.json. Seleccione una opción manual.")
    except Exception as e:
        print(f"[ERROR] No se pudo leer google-services.json: {e}")

if __name__ == "__main__":
    main()
