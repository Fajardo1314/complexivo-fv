# Análisis de Problemas y Soluciones - Complejo FV

**Fecha:** 2026-07-17
**Base primaria:** complexivo-fv
**Base secundaria:** aula-4587b (compartida con otros grupos)

---

## 1. Sensor Magnético de Puerta

**Problema:** Cada grupo tiene un sensor diferente para verificar el estado de la puerta. Nuestro sensor magnético no funciona correctamente, pero el del otro grupo sí.

**Solución:** Usar el estado de puerta del otro grupo (`aula-4587b/puerta_fisica`) para evitar inconvenientes. Solo LECTURA, no escritura en su DB.

**Cambios en `main_control.py`:**
- Eliminar la escritura en `puerta_fisica` de aula-4587b
- Leer el estado de puerta de `aula-4587b/puerta_fisica` como fallback

---

## 2. Accesos en 2 Bases de Datos

**Problema:** Los accesos se escriben en ambas bases. Cada grupo tiene configuraciones diferentes:
- Ellos: acceso por teclado + RFID + apertura por web
- Nosotros: acceso por RFID + apertura por web

**Solución:** Mantener la escritura en ambas bases porque es la misma lógica con configuraciones diferentes. Cada base tiene su propio historial de accesos.

---

## 3. Lógica del Otro Grupo

**Problema:** El otro grupo tiene su proyecto terminado y no podemos cambiar su lógica.

**Solución:** Quedarse con la lógica del otro grupo. Solo LECTURA de su DB para:
- Tarjetas RFID compartidas
- Estado de puerta (`puerta_fisica`)

---

## 4. Tarjetas RFID Duplicadas

**Problema:** Tarjetas duplicadas en ambas bases con permisos diferentes.

**Solución:** Eliminar tarjetas duplicadas de nuestra DB. Si una tarjeta ya está registrada en aula-4587b, marcarla como "registrada en otro proyecto" en nuestra DB.

---

## 5. Migración a bcrypt

**Problema:** Las passwords están en texto plano en nuestra DB.

**Solución:** Migrar a bcrypt para seguridad. Usar la misma estructura que el otro grupo: `$2b$12$...`

---

## 6. Usuario No Identificado

**Problema:** No podemos juntar el aspecto de la puerta con el otro grupo.

**Solución:** Guardar usuario no identificado en nuestra DB cuando no se pueda determinar la identidad.

---

## 7. Comandos de Servidor

**Problema:** El nodo `/sistema/comandos_servidor` controla shutdown y restart de la Raspberry Pi.

**Solución:** Mantener la funcionalidad actual. El comando "shutdown" apaga la Raspberry, "reboot" la reinicia.

---

## 8. Solo Lectura a la DB del Otro Grupo

**Problema:** No debemos modificar la DB del otro grupo.

**Solución:** Solo lectura de:
- `aula-4587b/tarjetas` (para validar RFID)
- `aula-4587b/puerta_fisica` (para estado de puerta)

NUNCA escritura a aula-4587b.

---

## Resumen de Cambios

| # | Cambio | Archivo | Estado |
|---|--------|---------|--------|
| 1 | Eliminar escritura en puerta_fisica de aula-4587b | main_control.py | Pendiente |
| 2 | Mantener escritura dual de accesos | main_control.py | OK |
| 3 | Solo lectura de aula-4587b | main_control.py | Pendiente |
| 4 | Eliminar tarjetas duplicadas | main_control.py | Pendiente |
| 5 | Migrar a bcrypt | main_control.py | Pendiente |
| 6 | Guardar usuario no identificado | main_control.py | OK |
| 7 | Comandos shutdown/reboot | main_control.py | OK |
| 8 | Solo lectura de aula-4587b | main_control.py | Pendiente |