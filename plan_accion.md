# Plan de Acción - Corrección de Problemas Complejo FV

**Fecha:** 2026-07-17
**Repo:** complexivo-fv (rama main)
**Archivo principal:** `main_control.py` (701 líneas)
**Base Firebase primaria:** complexivo-fv
**Base Firebase secundaria:** aula-4587b

---

## Regla General

**aula-4587b = SOLO LECTURA. NUNCA escritura.**

---

## Cambio 1: Eliminar escritura en puerta_fisica de aula-4587b

**Archivo:** `main_control.py`
**Línea:** 584-591 (dentro de `mqtt_sensor_relay()`, case `puerta_fisica/estado`)
**Función que lo contiene:** `mqtt_sensor_relay()` (líneas 518-617)
**Llamadores:** `main()` → thread daemon

**Código actual (ELIMINAR):**
```python
# Actualizar el nodo compartido puerta_fisica en minúsculas
try:
    db.reference('puerta_fisica').update({
        "estado": "abierta" if puerta_abierta else "cerrada",
        "timestamp": time.time()
    })
except Exception as e:
    print(f"[ERROR Shared puerta_fisica] {e}")
```

**Acción:** Eliminar este bloque completo (líneas 584-591).

**Verificación:** Después del cambio, `puerta_fisica` en aula-4587b solo cambiará cuando el otro grupo escriba. Nuestro backend ya NO tocará ese nodo.

---

## Cambio 2: Mantener escritura dual de accesos (NO CAMBIAR)

**Archivo:** `main_control.py`
**Función:** `registrar_acceso_shared_db()` (líneas 314-331)
**Llamadores:** `verificar_uid_en_nuestra_db()`, `registrar_permanencia_no_registrado()`

**Decisión:** Mantener la escritura en ambas bases. Cada base tiene su propio historial de accesos. No se requiere cambio.

**Estado:** OK - Sin cambios necesarios.

---

## Cambio 3: Solo lectura de aula-4587b en verificación RFID

**Archivo:** `main_control.py`
**Función:** `verificar_uid_en_nuestra_db()` (líneas 356-429)
**Llamadores:** `mqtt_sensor_relay()` (case `accesos`), `recibir_sensores()`, `registro_acceso_externo()`

**Código actual (líneas 359-368):**
```python
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
```

**Código actual (líneas 370-374):**
```python
# Fallback: buscar en nuestra DB
if not tarjeta:
    tarjeta = db.reference(f'tarjetas/{uid}').get()
    if tarjeta:
        print(f"[RFID] Tarjeta encontrada en nuestra DB: {uid}")
```

**Acción:** INVERTIR la prioridad. Primero buscar en NUESTRA DB, luego fallback a aula-4587b.

**Nuevo código:**
```python
# Buscar la tarjeta RFID en NUESTRA DB primero
tarjeta = None
try:
    tarjeta = db.reference(f'tarjetas/{uid}').get()
    if tarjeta:
        print(f"[RFID] Tarjeta encontrada en nuestra DB: {uid}")
except Exception as e:
    print(f"[RFID] Error leyendo nuestra DB: {e}")

# Fallback: buscar en la DB COMPARTIDA (aula-4587b) - SOLO LECTURA
if not tarjeta:
    try:
        shared_app = get_shared_db()
        if shared_app:
            tarjeta = db.reference(f'tarjetas/{uid}', app=shared_app).get()
            if tarjeta:
                print(f"[RFID] Tarjeta encontrada en DB compartida (fallback): {uid}")
    except Exception as e:
        print(f"[RFID] Error leyendo DB compartida: {e}")
```

**Verificación:** Nuestra DB tiene prioridad. Si una tarjeta está en ambas, se usan nuestros permisos.

---

## Cambio 4: Eliminar tarjetas duplicadas de nuestra DB

**Archivo:** Firebase (no código)
**Nodo:** `complexivo-fv/tarjetas`

**Tarjetas actuales en complexivo-fv:**
- `D30A491C` → Usuario de Prueba (admin) — DUPLICADA en aula-4587b
- `D3344A1C` → Mateo Perez (estudiante) — DUPLICADA en aula-4587b
- `D395BE0C` → Mateo Jose Perez Portilla (admin) — DUPLICADA en aula-4587b

**Acción:** NO eliminar de Firebase todavía. Primero verificar que el cambio 3 (inversión de prioridad) funciona correctamente. Después de confirmar, eliminar las duplicadas de nuestra DB.

**Paso 1 (ahora):** Aplicar cambio 3 y probar con una tarjeta duplicada.
**Paso 2 (después):** Eliminar `D30A491C`, `D3344A1C`, `D395BE0C` de `complexivo-fv/tarjetas`.

---

## Cambio 5: Migración a bcrypt (FUTURO)

**Archivo:** `main_control.py` (login en dashboard JS) + Firebase
**Nodo:** `complexivo-fv/usuarios`

**Usuarios actuales (texto plano):**
- admin / admin123
- jomayra06 / jomayra2006
- margarita13 / hola123
- sam / sam123

**Acción diferida:** NO implementar ahora. Requiere:
1. Instalar `bcrypt` en el backend
2. Migrar passwords existentes
3. Cambiar lógica de login en `app.js` y `retiro.html`
4. Agregar bcrypt al `requirements.txt`

**Estado:** PENDIENTE - Implementar después de estabilizar los cambios 1-4.

---

## Cambio 6: Guardar usuario no identificado (NO CAMBIAR)

**Archivo:** `main_control.py`
**Función:** `registrar_permanencia_no_registrado()` (líneas 333-354)

**Decisión:** La lógica actual ya guarda "USUARIO NO REGISTRADO" cuando el UID no se encuentra. No se requiere cambio.

**Estado:** OK - Sin cambios necesarios.

---

## Cambio 7: Comandos shutdown/reboot (NO CAMBIAR)

**Archivo:** `main_control.py`
**Funciones:** `shutdown_raspberry()` (línea 664), `reboot_raspberry()` (línea 672)

**Decisión:** Mantener la funcionalidad actual. El nodo `/sistema/comandos_servidor` controla estos comandos. No se requiere cambio.

**Estado:** OK - Sin cambios necesarios.

---

## Cambio 8: Verificar que no hay más escrituras a aula-4587b

**Búsqueda en código:** Todas las llamadas a `get_shared_db()` y `db.reference(..., app=shared_app)`

**Funciones que usan shared_app:**
1. `get_shared_db()` — retorna la app de aula-4587b
2. `registrar_acceso_shared_db()` — ESCRIBE en /accesos (MANTENER)
3. `verificar_uid_en_nuestra_db()` — LEE de /tarjetas (MANTENER)
4. `registrar_permanencia_no_registrado()` — llama a `registrar_acceso_shared_db()` (MANTENER)

**Verificación:** Después del cambio 1, las únicas escrituras a aula-4587b serán en `/accesos` (que es intencional). No hay más escrituras.

---

## Estado de Ejecución

```
PASO 1 ✅ Cambio 1: Eliminar escritura puerta_fisica
  → Líneas 584-591 eliminadas
  → Sintaxis verificada: OK
  → Sin más escrituras a puerta_fisica en aula-4587b

PASO 2 ✅ Cambio 3: Invertir prioridad RFID
  → Líneas 359-374 reescritas
  → Sintaxis verificada: OK
  → Nuestra DB tiene prioridad, fallback a aula-4587b

PASO 3 ⏳ Verificar en Firebase
  → Pendiente de deploy a la Raspberry Pi

PASO 4 ⏳ Eliminar tarjetas duplicadas
  → Pendiente de confirmar paso 3

PASO 5 ⏳ Commit + push
  → Pendiente
```

---

## Orden de Ejecución

```
PASO 1: Aplicar Cambio 1 (Eliminar escritura puerta_fisica)
  → Archivo: main_control.py línea 584-591
  → Riesgo: BAJO (solo elimina escritura innecesaria)

PASO 2: Aplicar Cambio 3 (Invertir prioridad RFID)
  → Archivo: main_control.py línea 359-374
  → Riesgo: MEDIO (cambia flujo de validación RFID)
  → Requiere: Prueba con tarjeta duplicada

PASO 3: Verificar en Firebase que no hay escrituras rotas
  → Monitorear /puerta_fisica en aula-4587b
  → Probar tarjeta RFID que esté en ambas bases

PASO 4: Aplicar Cambio 4 (Eliminar tarjetas duplicadas)
  → Firebase Console o script Python
  → Solo después de confirmar paso 3

PASO 5: Commit y push
  → git add main_control.py
  → git commit -m "fix: solo lectura aula-4587b, invertir prioridad RFID"
  → git push
```

---

## Archivos Afectados

| Archivo | Cambios | Líneas |
|---------|---------|--------|
| main_control.py | Eliminar bloque puerta_fisica | 584-591 |
| main_control.py | Invertir prioridad RFID | 359-374 |

**Total de líneas modificadas:** ~25
**Archivos nuevos:** 0
**Dependencias nuevas:** 0

---

## Criterios de Verificación

- [ ] `puerta_fisica` en aula-4587b ya NO se actualiza desde nuestro backend
- [ ] Tarjeta duplicada (D3344A1C) usa permisos de NUESTRA DB
- [ ] Accesos siguen registrándose en ambas bases
- [ ] Sensor magnético sigue funcionando (escritura en complexivo-fv)
- [ ] Dashboard web no se ve afectado
- [ ] retiro.html sigue funcionando
