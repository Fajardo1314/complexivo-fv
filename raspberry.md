# Configuración de Servidor, Red y Hardware - Proyecto de Grado 🚀

Este documento detalla la configuración del sistema operativo de la Raspberry Pi 4B (con Arch Linux/EndeavourOS), la red VPN de Netbird, el Punto de Acceso (Access Point), la configuración de Firebase y las conexiones del microcontrolador ESP32 NodeMCU-32S.

> [!IMPORTANT]
> **Las credenciales se encuentran en un archivo separado:** [`credentials.py`](file:///c:/Users/ASUS/Documents/complexivo/Proyecto_grado/credentials.py)  
> **Cliente SSH en Python:** [`ssh_raspberry.py`](file:///c:/Users/ASUS/Documents/complexivo/Proyecto_grado/ssh_raspberry.py)  
> ⚠️ Añade `credentials.py` a tu `.gitignore` para no subir claves al repositorio.

---

## 🖥️ 1. Raspberry Pi 4B - Información General y Sistema

Se extrajo la información directamente del sistema operativo alojado en la Raspberry Pi 4B:

*   **Sistema Operativo (Distro):** EndeavourOS ARM (basada en Arch Linux) 🦅
*   **Versión del Kernel:** `Linux raspberryfv 6.18.32-2-rpi #1 SMP PREEMPT Fri May 22 17:11:05 UTC 2026 aarch64 GNU/Linux`
*   **Arquitectura:** `aarch64` (ARM 64-bit)
*   **Nombre de Host (Hostname):** `raspberryfv`
*   **Acceso SSH local:** Ver variables `SSH_HOST`, `SSH_USER`, `SSH_PASSWORD` en [`credentials.py`](file:///c:/Users/ASUS/Documents/complexivo/Proyecto_grado/credentials.py)
    *   **Comando rápido:** `ssh user@raspberryfv.nb`
    *   **Cliente Python:** ejecutar [`ssh_raspberry.py`](file:///c:/Users/ASUS/Documents/complexivo/Proyecto_grado/ssh_raspberry.py)

---

## 🌐 2. Conexión VPN - Netbird

La Raspberry Pi está configurada dentro de una red privada mallada gestionada por **Netbird**, lo que permite acceder a ella de forma remota y segura desde cualquier lugar sin abrir puertos en el router.

*   **Cliente NetBird:** versión `0.71.4` (Daemon y CLI)
*   **Interfaz de Red:** `wt0` (túnel WireGuard)
*   **Setup Key (Red Activa):** `AD8D21D2-4620-45FE-8AB7-D171F6E8FE18`
*   **Nombre de Dominio (FQDN):** `raspberryfv.nb` (zona personalizada .nb en Netbird)
*   **Servicio de Control:** `netbird.service` (habilitado y corriendo activamente)

> [!NOTE]
> Puedes acceder por SSH a la Raspberry Pi usando su IP de Netbird desde tu computadora (siempre que tu computadora también esté conectada a la misma red de Netbird). Verifica la IP actual con `netbird status` tras la reconexión.

### 🔄 Cambiar de Red (Setup Key):

> [!CAUTION]
> Si accedes por SSH a través de la IP VPN de Netbird, **perderás la sesión** al ejecutar `netbird down`. Asegúrate de tener acceso local o por IP física de red local antes de proceder.

```bash
# 1. Desconectar de la red Netbird actual
sudo netbird down

# 2. Reconectarse con el nuevo Setup Key (nueva red)
sudo netbird up --setup-key AD8D21D2-4620-45FE-8AB7-D171F6E8FE18

# 3. Verificar el nuevo estado y obtener la nueva IP VPN
netbird status
```

### Comandos Útiles de Netbird:
```bash
# Verificar el estado de la conexión VPN
netbird status

# Iniciar / Detener el servicio daemon
sudo systemctl start netbird
sudo systemctl stop netbird
```

---

## 📶 3. Configuración del Punto de Acceso (Access Point) en la Raspberry Pi

Para comunicar el ESP32 con la Raspberry Pi a través de MQTT de forma local, la Raspberry Pi actúa como un enrutador inalámbrico emitiendo un punto de acceso (Access Point).

### Credenciales de la Red Wifi:
Ver variables `AP_SSID`, `AP_PASSWORD`, `AP_GATEWAY_IP` en [`credentials.py`](file:///c:/Users/ASUS/Documents/complexivo/Proyecto_grado/credentials.py)

*   **SSID:** `ESP32_MQTT_AP`
*   **IP Gateway / Broker:** `10.42.0.1`

### ¿Cómo está implementado?
El Access Point está gestionado nativamente por **NetworkManager** mediante un perfil de conexión inalámbrico compartido. 

```bash
# Ver las conexiones activas
nmcli con

# Ver el estado de los dispositivos
nmcli dev
```

> [!IMPORTANT]
> NetworkManager utiliza internamente un rango de red dinámico asignado a `wlan0` con la dirección fija `10.42.0.1` e inicia un servicio interno de DHCP (`dnsmasq` o similar embebido) para entregarle direcciones IP en la subred `10.42.0.x` al ESP32 y a cualquier otro dispositivo que se conecte.

### Comandos de Control para el Hotspot:
```bash
# Encender el Punto de Acceso (si se encuentra apagado)
sudo nmcli connection up Hotspot

# Apagar el Punto de Acceso
sudo nmcli connection down Hotspot

# Asegurar que se levante automáticamente al iniciar la Raspberry Pi
sudo nmcli connection modify Hotspot connection.autoconnect yes

# Si por alguna razón se elimina y necesitas recrearlo:
sudo nmcli device wifi hotspot ifname wlan0 ssid ESP32_MQTT_AP password taipt_iot_2026
```

---

## 🔌 4. Configuración del Broker MQTT (Mosquitto)

> [!WARNING]
> Durante la auditoría del sistema se detectó que **no hay un broker MQTT (Mosquitto) instalado** ni puertos escuchando en el `1883` en la Raspberry Pi. Para que [gestor_aulas.py](file:///c:/Users/User/OneDrive/Desktop/Proyecto_grado/backend/gestor_aulas.py) y el ESP32 puedan conectarse, debes configurar el broker siguiendo estos pasos:

### 1. Instalar Mosquitto en Arch Linux ARM:
```bash
sudo pacman -Syu mosquitto
```

### 2. Configurar Acceso Externo (Crucial para el ESP32):
Por defecto, Mosquitto v2.0+ solo escucha en `localhost` (127.0.0.1) y deniega conexiones anónimas. Debes editar su archivo de configuración para permitir conexiones desde la red del ESP32 (`10.42.0.x`).
Edita el archivo `/etc/mosquitto/mosquitto.conf`:
```bash
sudo nano /etc/mosquitto/mosquitto.conf
```
Añade las siguientes líneas al final del archivo:
```ini
# Escuchar en todas las interfaces (0.0.0.0) en el puerto estándar MQTT
listener 1883 0.0.0.0

# Permitir conexiones sin usuario y contraseña (para propósitos de desarrollo)
allow_anonymous true
```

### 3. Iniciar e Habilitar el Servicio:
```bash
# Iniciar y hacer que inicie automáticamente con el sistema
sudo systemctl enable --now mosquitto

# Verificar que está activo y escuchando en el puerto 1883
ss -tulpn | grep 1883
```

---

## 🔥 5. Cuentas e Integración con Firebase

El sistema centraliza las lecturas de los sensores en tiempo real y gestiona los accesos a través de Firebase Realtime Database.

Ver variables `FIREBASE_EMAIL`, `FIREBASE_PROJECT`, `FIREBASE_DATABASE_URL` en [`credentials.py`](file:///c:/Users/ASUS/Documents/complexivo/Proyecto_grado/credentials.py)

*   **Proyecto:** `proyecto-grado`
*   **URL de la Base de Datos:** `https://proyecto-grado-default-rtdb.firebaseio.com/`

### Configuración del Backend (Python en RPi):
El backend utiliza las credenciales de la cuenta de servicio de Firebase para autenticarse de manera segura con permisos de administración.
*   **Archivo Requerido:** Debe descargarse un archivo de llave privada JSON desde la Consola Firebase (`Configuración del Proyecto -> Cuentas de Servicio -> Generar nueva clave privada`).
*   **Ubicación:** Debe renombrarse a `google-services.json` y colocarse en el directorio [backend/](file:///c:/Users/User/OneDrive/Desktop/Proyecto_grado/backend/).
*   **Carga del certificado:** Definida en [gestor_aulas.py](file:///c:/Users/User/OneDrive/Desktop/Proyecto_grado/backend/gestor_aulas.py#L7-L16).

### Configuración del Dashboard Web:
Ubicado en [web_dashboard/app.js](file:///c:/Users/User/OneDrive/Desktop/Proyecto_grado/web_dashboard/app.js#L4-L14). Configurado con:
```javascript
const firebaseConfig = {
    databaseURL: "https://proyecto-grado-default-rtdb.firebaseio.com/",
    // Opcionalmente agregar apiKey y projectId si configuras autenticación o storage
};
```

---

## 🧠 6. Configuración de Hardware - ESP32 NodeMCU-32S (38 Pines)

El microcontrolador principal es un **ESP32 NodeMCU-32S (38 pines)**. Al conectarse a la computadora por USB, se registra en el puerto **COM6** utilizando el chip de comunicación serial **Silicon Labs CP210x USB to UART Bridge**.

### Características Técnicas del NodeMCU-32S (38 Pines):
*   **Microcontrolador:** ESP-WROOM-32 (Tensilica Dual Core 32-bit LX6 a 240 MHz).
*   **Memoria:** 520 KB SRAM, 4 MB de memoria Flash externa.
*   **Conectividad:** Wi-Fi 802.11 b/g/n (2.4 GHz) y Bluetooth v4.2 BR/EDR y BLE.
*   **Pines Físicos:** 38 pines distribuidos en dos hileras de 19 pines.

### 📋 Diagrama de Pines (Layout de 38 Pines)

```text
                     ---[ ANTENA WIFI ]---
           3.3V  [01]                     [38]  GND
       EN (RST)  [02]                     [37]  TX0 (GPIO1)
    VP (GPIO36)  [03]                     [36]  RX0 (GPIO3)
    VN (GPIO39)  [04]                     [35]  GPIO22 (SCL)
  G34 (GPIO34)*  [05]                     [34]  GPIO21 (SDA)
  G35 (GPIO35)*  [06]                     [33]  GPIO19 (VSPI MISO)
    G32 (GPIO32)  [07]                     [32]  GPIO18 (VSPI SCK)
    G33 (GPIO33)  [08]                     [31]  GPIO5  (VSPI CS)
    G25 (GPIO25)  [09]                     [30]  GPIO17 (TX2)
    G26 (GPIO26)  [10]                     [29]  GPIO16 (RX2)
    G27 (GPIO27)  [11]                     [28]  GPIO4  (Touch0)
    G14 (GPIO14)  [12]                     [27]  GPIO2  (LED Integrado)
    G12 (GPIO12)  [13]                     [26]  GPIO15 (HSPI CS)
    G13 (GPIO13)  [14]                     [25]  GPIO8  (SD1)*
            GND  [15]                     [24]  GPIO7  (SD0)*
     GPIO9 (SD2) [16]                     [23]  GPIO6  (CLK)*
    GPIO10 (SD3) [17]                     [22]  GPIO23 (VSPI MOSI)
   GPIO11 (CMD)* [18]                     [21]  GND
       5V (VIN)  [19]                     [20]  GND
                     ---------------------
                   * Nota: Pines marcados con asterisco tienen funciones especiales
                     o restricciones (GPIO 34-39 son de entrada exclusivamente).
```

---

### 🔌 Conexión de Sensores y Módulos al ESP32

A continuación se detalla la asignación de pines y diagramas de conexión para cada uno de los sensores requeridos por el sistema.

| Sensor / Módulo | Pin del Módulo | Pin en ESP32 (GPIO) | Tipo de Pin | Descripción / Notas |
| :--- | :--- | :--- | :--- | :--- |
| **Lector RFID (RC522)** | **VCC** | **3.3V** | Alimentación | **¡CUIDADO!** No conectar a 5V o dañará el RC522. |
| *(Comunicación SPI)* | **GND** | **GND** | Tierra | Tierra de referencia común. |
| | **MISO** | **GPIO 19** | SPI MISO | Bus de datos SPI - Master Input Slave Output. |
| | **MOSI** | **GPIO 23** | SPI MOSI | Bus de datos SPI - Master Output Slave Input. |
| | **SCK** | **GPIO 18** | SPI SCK | Reloj de bus SPI. |
| | **SDA (SS)** | **GPIO 5** | Salida Digital | Selector de esclavo / Chip Select para SPI. |
| | **RST** | **GPIO 22** | Salida Digital | Línea de reinicio del lector RFID. |
| | **IRQ** | *No Conectado* | N/A | No se requiere para esta implementación. |
| **Sensor PIR (HC-SR501)**| **VCC** | **5V (VIN)** | Alimentación | El módulo requiere 5V para alimentar su regulador integrado. |
| *(Detección de Presencia)*| **GND** | **GND** | Tierra | Tierra de referencia común. |
| | **OUT** | **GPIO 27** | Entrada Digital| Envía señal HIGH (3.3V) al detectar movimiento. |
| **Sensor IR 1 - Entrada** | **VCC** | **3.3V o 5V** | Alimentación | Alimentación de la barrera IR o TCRT5000. |
| *(Contador de personas IN)*| **GND** | **GND** | Tierra | Tierra de referencia común. |
| | **OUT** | **GPIO 34** | Entrada Digital| **Pin sólo entrada**. Cambia de estado al interrumpirse. |
| **Sensor IR 2 - Salida** | **VCC** | **3.3V o 5V** | Alimentación | Alimentación de la barrera IR o TCRT5000. |
| *(Contador de personas OUT)*| **GND** | **GND** | Tierra | Tierra de referencia común. |
| | **OUT** | **GPIO 35** | Entrada Digital| **Pin sólo entrada**. Cambia de estado al interrumpirse. |
| **Sensor LDR (Opcional)**| **VCC** | **3.3V** | Alimentación | Extremo del sensor LDR. |
| *(Luz Ambiental)* | **OUT (Señal)**| **GPIO 32** | Entrada Analóg.| Punto medio del divisor de tensión (LDR y R 10kΩ). |
| | **GND** | **GND** | Tierra | Extremo libre de la resistencia de 10kΩ. |
| **Relé Chapa Eléctrica** | **VCC** | **5V** | Alimentación | Alimentación de la bobina del relevador. |
| *(Controlador de Puerta)*| **GND** | **GND** | Tierra | Tierra de referencia común. |
| | **IN** | **GPIO 26** | Salida Digital | Envía señal para abrir el cerrojo eléctrico. |

---

### ⚠️ Consideraciones de Hardware Importantes:
1.  **Pines de Entrada Únicamente (GPIO 34 y 35):** Estos dos pines elegidos para las barreras infrarrojas (IR) no disponen de resistencias de pull-up internas en el chip ESP32. Sin embargo, los módulos comerciales TCRT5000/infrarrojos de barrera ya integran sus propias resistencias en la placa del sensor, por lo que se pueden conectar directamente sin problema.
2.  **Alimentación del Lector RFID:** El chip RC522 es estrictamente de **3.3V**. Conectarlo a la línea de 5V quemará el circuito integrado del lector. Asegura realizar la conexión al pin `3.3V` del ESP32.
3.  **Tierra Común (GND):** Asegúrate de que las tierras de todos los componentes (ESP32, Sensores, Lector, Fuente del Relé) estén interconectadas físicamente para evitar lecturas erráticas y ruidos en la señal.
