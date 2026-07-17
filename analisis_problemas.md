# Análisis de Problemas - Complejo FV

**Fecha:** 2026-07-16
**Base primaria:** complexivo-fv
**Base secundaria:** aula-4587b (compartida con otros grupos)

---

## Problema 1: Nuestra DB escribe en /puerta_fisica de la otra DB

**Archivo:** `main_control.py` (líneas 584-591)
**Gravedad:** ALTA

```python
# Actualizar el nodo compartido puerta_fisica en minúsculas
db.reference('puerta_fisica').update({
    "estado": "abierta" if puerta_abierta else "cerrada",
    "timestamp": time.time()
})
```

**Qué ocurre:** Cuando el sensor magnético detecta un cambio, nuestro backend escribe el estado en `/puerta_fisica` de **aula-4587b** (la base del otro grupo).

**Por qué es problema:**
- Sobreescribe el estado de puerta del otro grupo
- El otro grupo tiene su propio sensor magnético físico
- Crea confusión: ¿de qué aula es el sensor?
- El otro grupo podría ver datos incorrectos en su dashboard

**Estado actual en ambas bases:**
- complexivo-fv `/puerta_fisica`: `{"estado": "cerrada", "timestamp": 1784264989}`
- aula-4587b `/puerta_fisica`: `{"estado": "cerrada", "timestamp": 1784255545}`

**Solución:** Eliminar esa escritura. El sensor magnético es local de nuestra aula. No debería escribirse en la base del otro grupo a menos que sea un sensor físico compartido entre ambos sistemas.

---

## Problema 2: Nuestra DB escribe /accesos en ambas bases

**Archivo:** `main_control.py` (líneas 314-330, función `registrar_acceso_shared_db`)
**Gravedad:** ALTA

```python
def registrar_acceso_shared_db(uid, exitoso, metodo, motivo, perfil=None, identificador_usuario=""):
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
```

**Qué ocurre:** Cada acceso RFID se registra en DOS bases:
1. `/accesos` de complexivo-fv (correcto, es nuestra base)
2. `/accesos` de aula-4587b (problema)

**Por qué es problema:**
- El otro grupo YA tiene 296 registros de accesos con su propio formato
- Nuestros accesos se mezclan con los de ellos
- La estructura de datos es diferente (nuestros registros tienen campos que ellos no tienen y viceversa)
- Dificulta el análisis cruzado
- Puede romper dashboards del otro lado que esperan su propio formato

**Estado actual:**
- complexivo-fv `/accesos`: 8 registros (nuestros)
- aula-4587b `/accesos`: 296 registros (mezcla de ambos grupos)

**Solución:** Evaluar si realmente necesitamos escribir en aula-4587b. Si el propósito es solo **validar** tarjetas RFID del otro grupo, basta con LECTURA. No escritura.

---

## Problema 3: Estructura de accesos diferente en cada DB

**Gravedad:** MEDIA

**complexivo-fv `/accesos`** (formato del backend Python):
```json
{
  "exitoso": true,
  "metodo": "RFID:D395BE0C",
  "motivo": "RFID verificado de María Belén Toledo Illescas",
  "perfil": {"nombre": "María Belén Toledo Illescas", "rol": "admin"},
  "timestamp": 1784248216.8995,
  "fecha_hora": "2026-07-17 00:30:16",
  "identificador_usuario": "maria.toledo"
}
```

**aula-4587b `/accesos`** (formato del otro grupo):
```json
{
  "exitoso": true,
  "metodo": "CODIGO:1234",
  "motivo": "Código 1234",
  "timestamp": 1780897718.7280107
}
```

**Por qué es problema:**
- Los registros que escribimos en aula-4587b tienen campos extras (`perfil`, `fecha_hora`, `identificador_usuario`)
- El otro grupo no espera esos campos
- Si el otro grupo filtra o muestra accesos por tipo, nuestros registros podrían romper la lógica
- No hay un estándar compartido de estructura

---

## Problema 4: /tarjetas duplicado y con conflictos de permisos

**Gravedad:** ALTA

**Tarjetas en AMBAS bases:**

| UID | complexivo-fv | aula-4587b |
|-----|--------------|------------|
| D30A491C | Usuario de Prueba (rol: admin) | Usuario de Prueba (rol: admin) |
| D3344A1C | Mateo Perez (rol: **estudiante**) | Mateo Pérez (rol: **admin**) |
| D395BE0C | Mateo Jose Perez Portilla (rol: admin) | Mateo Jose Perez Portilla (rol: admin) |

**Por qué es problema:**

1. **Conflicto de permisos:** Para la tarjeta `D3344A1C`, nuestro sistema dice que es "estudiante" pero el otro grupo dice que es "admin". La misma persona tiene permisos diferentes según la base.

2. **El código busca primero en aula-4587b** (línea 359-368):
```python
# Buscar la tarjeta RFID en la DB COMPARTIDA (aula-4587b)
tarjeta = db.reference(f'tarjetas/{uid}', app=shared_app).get()
if tarjeta:
    print(f"[RFID] Tarjeta encontrada en DB compartida: {uid}")

# Fallback: buscar en nuestra DB
if not tarjeta:
    tarjeta = db.reference(f'tarjetas/{uid}').get()
```

3. **Resultado:** Si una tarjeta está en ambas, gana la del otro grupo. Mateo Pérez podría tener permisos de admin en nuestro sistema aunque nosotros le dimos permisos de estudiante.

**Solución:** Decidir una fuente de verdad. O eliminamos las tarjetas duplicadas de aula-4587b (no我们应该 hacerlo, es la DB del otro grupo), o cambiamos la lógica para que NUESTRA base tenga prioridad sobre las tarjetas que YA existen en ambas.

---

## Problema 5: /usuarios con diferente formato de password

**Gravedad:** MEDIA

**complexivo-fv `/usuarios`** (texto plano):
```json
{
  "admin": {"password": "admin123", "rol": "admin"},
  "jomayra06": {"password": "jomayra2006", "rol": "docente"},
  "margarita13": {"password": "hola123", "rol": "admin"},
  "sam": {"password": "sam123", "rol": "estudiante"}
}
```

**aula-4587b `/usuarios`** (bcrypt):
```json
{
  "diego": {"password": "$2b$12$Nb5E2E3Yd5Ezvu.kQtOYY...", "rol": "admin"},
  "mateo~perez": {"password": "$2b$12$Js3YHqoA8iZri54pKUWcF...", "rol": "admin"}
}
```

**Por qué es problema:**
- Nuestro sistema compara passwords en texto plano (`user.password === p`)
- El otro grupo usa bcrypt (hash seguro)
- Si algún día se comparte lógica de login entre ambos sistemas, el nuestro es inseguro
- Las passwords están expuestas en Firebase Console y en los backups

**Solución a futuro:** Migrar a bcrypt en nuestra base. No es urgente para el functionality actual, pero es un riesgo de seguridad.

---

## Problema 6: /puerta duplicado - conflicto de estado

**Gravedad:** MEDIA

**complexivo-fv `/puerta`:**
```json
{
  "estado": "cerrada",
  "metodo": "RFID:D395BE0C",
  "timestamp": 1784248216.8995,
  "ultimo_acceso": "2026-07-17 00:30:16",
  "usuario_responsable": "María Belén Toledo Illescas"
}
```

**aula-4587b `/puerta`:**
```json
{
  "estado": "cerrada",
  "metodo": "web",
  "timestamp": 1784252751.3559837,
  "ultimo_acceso": "Mateo José Pérez Portilla",
  "usuario_responsable": "mateo.perez"
}
```

**Por qué es problema:**
- Ambas bases tienen `/puerta` con estados diferentes
- Nuestro backend escribe SOLO en complexivo-fv (correcto)
- Pero si el otro grupo lee su `/puerta`, podría ver nuestro estado como si fuera el de ellos
- No hay aislamiento real entre los dos sistemas

---

## Problema 7: Nodo /sistema sin uso claro

**Gravedad:** BAJA

**complexivo-fv `/sistema`:**
```json
{
  "comandos_servidor": "shutdown"
}
```

**Qué ocurre:** Este nodo tiene un valor estático de "shutdown". No se lee ni se escribe desde el código del backend ni del dashboard. Es un nodo muerto que probablemente se usó para pruebas iniciales del otro grupo.

**Solución:** Eliminar o documentar su propósito. Si se usa para comandos remotos, implementar la lógica correspondiente.

---

## Problema 8: Nuestro backend escribe en /puerta de aula-4587b

**Archivo:** `main_control.py` (líneas 122-132, función `abrir_chapa`)
**Gravedad:** ALTA

```python
# Escribir en base unificada (aula-4587b) en el nodo compartido 'puerta'
ref_puerta = db.reference('puerta')
ref_puerta.update({
    "estado": "abierta",
    "metodo": metodo_acceso,
    "timestamp": time.time(),
    "ultimo_acceso": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "usuario_responsable": usuario_name
})
```

**Qué ocurre:** Cuando abrimos NUESTRA chapa eléctrica, escribimos el estado en `/puerta` de complexivo-fv. Pero este código está usando la app por defecto (sin `app=shared_app`), así que ESCRIBE en complexivo-fv.

**El problema real:** La función `abrir_chapa` escribe en `/puerta` de complexivo-fv. Pero el otro grupo TAMBIÉN tiene `/puerta` en aula-4587b. Si nuestro backend lee `/puerta` de aula-4587b en algún momento (por ejemplo, en `firebase_puerta_listener`), podría confundir el estado de NUESTRA puerta con la de ellos.

**Estado actual:** No hay conflicto directo porque escribimos en different bases. Pero la semántica es confusa: ¿`/puerta` es nuestra o es compartida?

**Solución:** Si `/puerta` es solo nuestra, no debería existir en aula-4587b. Si es compartida, ambas bases deberían sincronizarse (que no es el caso actualmente).

---

## Resumen de acciones recomendadas

| # | Problema | Prioridad | Acción |
|---|----------|-----------|--------|
| 1 | Escritura en /puerta_fisica de aula-4587b | ALTA | Eliminar la línea que escribe en la DB del otro grupo |
| 2 | Escritura en /accesos de aula-4587b | ALTA | Evaluar si es necesario; si solo es validación, quitar escritura |
| 3 | Estructura de accesos diferente | MEDIA | Estandarizar o eliminar escritura cruzada |
| 4 | Tarjetas RFID duplicadas con permisos diferentes | ALTA | Decidir fuente de verdad; priorizar nuestra DB |
| 5 | Passwords en texto plano | MEDIA | Migrar a bcrypt (no urgente) |
| 6 | /puerta duplicado | MEDIA | Documentar que cada DB tiene su propio /puerta |
| 7 | Nodo /sistema muerto | BAJA | Eliminar o implementar |
| 8 | Semántica confusa de /puerta | ALTA | Aclarar ownership: ¿/puerta es nuestra o compartida? |
