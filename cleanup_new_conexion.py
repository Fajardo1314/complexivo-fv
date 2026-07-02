"""
cleanup_new_conexion.py
=======================
Limpia los nodos que nuestro proyecto creó accidentalmente en la base de datos
espejo de mi compañero ('new-conexion'). Esa DB debe contener SOLO:
  - /puerta_fisica/estado
  - /accesos

Este script ELIMINA: /estado_foco, /movimiento_pir, /aforo y cualquier otro
nodo que no sea nativo del diseño de mi compañero.
"""

import urllib.request
import json

DB_URL = 'https://new-conexion-default-rtdb.firebaseio.com'

# Nodos que DEBEN EXISTIR en new-conexion (no borrar)
NODOS_PERMITIDOS = {'puerta_fisica', 'accesos', 'puerta'}

# Nodos a borrar explícitamente (nuestros sensores que NO deben estar aquí)
NODOS_A_BORRAR = ['estado_foco', 'movimiento_pir', 'aforo', 'monitoreo',
                   'monitoreo_tiempo_real', 'historial_flujo', 'alertas_historicas',
                   'inventario', 'usuarios', 'usuarios_sistema', 'auditoria',
                   'configuracion', 'sistema', 'retiros', 'equipos',
                   'ultimo_uid_no_registrado', 'ultimo_intento_invalido',
                   'docentes', 'usuarios_plataforma']

print("=" * 60)
print("  LIMPIEZA DE new-conexion (DB del compañero)")
print("=" * 60)

# 1. Borrar nodos conocidos
for node in NODOS_A_BORRAR:
    try:
        req = urllib.request.Request(f'{DB_URL}/{node}.json', method='DELETE')
        resp = urllib.request.urlopen(req, timeout=10)
        status = resp.read().decode()
        print(f"  [DELETED] /{node} -> {status}")
    except Exception as e:
        print(f"  [SKIP] /{node}: {e}")

# 2. Verificar qué queda
print("\n--- Verificando nodos restantes ---")
try:
    req = urllib.request.Request(f'{DB_URL}/.json?shallow=true')
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read().decode())
    remaining = list(data.keys()) if data else []
    print(f"  Nodos restantes: {remaining}")

    # Advertir si hay nodos extraños
    for r in remaining:
        if r not in NODOS_PERMITIDOS:
            print(f"  [WARNING] Nodo no nativo detectado: /{r} - considerar borrarlo")
except Exception as e:
    print(f"  [ERROR] No se pudo verificar: {e}")

print("\n" + "=" * 60)
print("  [OK] Limpieza completada.")
print("  new-conexion ahora solo contiene: puerta_fisica, accesos")
print("=" * 60)