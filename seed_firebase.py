"""
seed_firebase.py
================
Crea/verifica nodos semilla en AMBAS bases de datos Firebase:
  - complexivo-fv (NUESTRA DB): aforo, movimiento_pir, estado_foco, usuario test
  - new-conexion (COMPANION DB): puerta_fisica/estado, accesos
"""

import urllib.request
import json

OUR_DB = "https://complexivo-fv-default-rtdb.firebaseio.com"
COMPANION_DB = "https://new-conexion-default-rtdb.firebaseio.com"

def firebase_put(url, path, data):
    """PUT directo a Firebase via REST API (sin SDK)."""
    full_url = f"{url}/{path}.json"
    body = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(full_url, data=body, method='PUT')
    req.add_header('Content-Type', 'application/json')
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        result = resp.read().decode()
        print(f"  [OK] PUT {path} -> {result}")
        return True
    except Exception as e:
        print(f"  [ERROR] PUT {path}: {e}")
        return False

def firebase_get(url, path):
    """GET directo a Firebase via REST API."""
    full_url = f"{url}/{path}.json"
    try:
        req = urllib.request.Request(full_url)
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read().decode())
    except Exception as e:
        print(f"  [ERROR] GET {path}: {e}")
        return None

print("=" * 60)
print("  SEED FIREBASE - Nodos semilla en ambas DBs")
print("=" * 60)

# ─────────────────────────────────────────────
# 1. NUESTRA DB (complexivo-fv)
# ─────────────────────────────────────────────
print("\n--- complexivo-fv (NUESTRA DB) ---")

# aforo
firebase_put(OUR_DB, "aforo", 0)

# movimiento_pir
firebase_put(OUR_DB, "movimiento_pir", False)

# estado_foco
firebase_put(OUR_DB, "estado_foco", "APAGADO")

# usuario de prueba RFID
print("\n  Verificando usuario de prueba RFID '1065B011'...")
existing = firebase_get(OUR_DB, "usuarios/1065B011")
if existing is None or existing == "null":
    firebase_put(OUR_DB, "usuarios/1065B011", {
        "nombre": "Docente Test",
        "rol": "docente",
        "estado": "activo",
        "uid": "1065B011"
    })
else:
    print(f"  [SKIP] Usuario 1065B011 ya existe: {existing}")

# ─────────────────────────────────────────────
# 2. COMPANION DB (new-conexion)
# ─────────────────────────────────────────────
print("\n--- new-conexion (COMPANION DB) ---")

# puerta_fisica/estado
firebase_put(COMPANION_DB, "puerta_fisica/estado", "cerrada")

# accesos (objeto vacío)
firebase_put(COMPANION_DB, "accesos", {})

# Verificar que no haya nodos extra
print("\n  Verificando nodos en new-conexion...")
req = urllib.request.Request(f"{COMPANION_DB}/.json?shallow=true")
resp = urllib.request.urlopen(req, timeout=15)
data = json.loads(resp.read().decode())
remaining = list(data.keys()) if data else []
print(f"  Nodos en new-conexion: {remaining}")

ALLOWED = {'puerta_fisica', 'accesos', 'puerta', 'codigos_unico'}
for r in remaining:
    if r not in ALLOWED:
        print(f"  [WARNING] Nodo no nativo: /{r}")

print("\n" + "=" * 60)
print("  [OK] Nodos semilla creados/verificados en ambas DBs.")
print("=" * 60)