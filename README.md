# Proyecto Grado - Gestión Inteligente de Aulas

Este repositorio contiene todo el código para el sistema integral de gestión de aulas, accesos, inventario e iluminación inteligente.

## 🗂️ Estructura del Proyecto

* **`esp32_firmware/`**: Código C++ para el microcontrolador ESP32-S3 / NodeMCU-32S. Maneja sensores IR, PIR, tarjeta RFID RC522, LDR y chapa eléctrica.
* **`backend/`**: Scripts de Python para ejecutarse en la Raspberry Pi. Actúa como el cerebro central sincronizando MQTT y Firebase, además de controlar el foco TP-Link.
* **`web_dashboard/`**: Panel de control web estético con Glassmorphism. Muestra el inventario, genera QRs y muestra gráficos en tiempo real.

---

## 🔥 Paso 1: Configurar la Base de Datos Firebase

Como se trata de un sistema conectado a la nube, necesitas crear el proyecto en Firebase con tu cuenta (`margaritafajardo1@hotmail.com`):

1. Ve a [Firebase Console](https://console.firebase.google.com/) e inicia sesión con tu correo.
2. Haz clic en **"Agregar proyecto"** y nómbralo `proyecto-grado`.
3. Ve a la sección **"Realtime Database"** en el menú izquierdo y haz clic en **"Crear base de datos"**. 
4. Iníciala en **Modo de Prueba** (para evitar problemas de permisos de escritura iniciales).
5. Ve a "Configuración del Proyecto" (engranaje arriba a la izquierda) -> "Cuentas de Servicio" -> **"Generar nueva clave privada"**.
6. Descarga el archivo JSON, renómbralo a `google-services.json` y guárdalo dentro de la carpeta `backend/`.
7. En esa misma página de Configuración General, añade una **App Web** `</>`. Te dará un objeto `firebaseConfig` con tu `apiKey` y URL. Copia y pega esos datos en el archivo `web_dashboard/app.js` (línea 5).

---

## ⚡ Paso 2: Subir el Código al ESP32

1. Abre `esp32_firmware/esp32_firmware.ino` con el Arduino IDE.
2. Asegúrate de instalar las librerías:
   * `PubSubClient` (por Nick O'Leary)
   * `MFRC522` (por GithubCommunity)
3. Conecta tu ESP32 al puerto COM6 y sube el código.

---

## 🧠 Paso 3: Ejecutar el Backend en la Raspberry Pi

En la terminal de la Raspberry Pi, instala las dependencias e inicia los servicios:

```bash
# Instalar librerías de Python
pip install -r backend/requirements.txt

# Ejecutar el gestor principal (Terminal 1)
python backend/gestor_aulas.py

# Ejecutar el control de luces (Terminal 2)
python backend/control_tplink.py
```

---

## 🌐 Paso 4: Abrir el Dashboard Web

Simplemente haz doble clic en el archivo `web_dashboard/index.html` para abrirlo en tu navegador. Si deseas publicarlo en WordPress, puedes:
1. Subir la carpeta a tu servidor por FTP.
2. Utilizar un plugin de "Insert HTML/JS" para embeber el código, o un "Iframe" apuntando a los archivos alojados.
