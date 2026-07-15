# DIAGRAMA DE CONEXIONES - Smart Stock

## 1. ESQUEMA FISICO (Hardware)

```
╔══════════════════════════════════════════════════════════════════╗
║                    AULA / LABORATORIO                            ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  ┌─────────────────────────────────────────────────────────┐    ║
║  │                   ESP32 (NodeMCU-32S)                    │    ║
║  │                                                          │    ║
║  │  GPIO 33 ──── IR Casillero 1 (FC-51)                    │    ║
║  │  GPIO 32 ──── IR Casillero 2 (FC-51)                    │    ║
║  │  GPIO 27 ──── PIR (HC-SR501)                            │    ║
║  │  GPIO 13 ──── Magnetico (Reed Switch)                   │    ║
║  │  GPIO 21 ──── BH1750 SDA (I2C)                          │    ║
║  │  GPIO 22 ──── BH1750 SCL (I2C)                          │    ║
║  │                                                          │    ║
║  │  WiFi: ESP32_MQTT_AP / taipt_iot_2026                   │    ║
║  │  MQTT Broker: 10.42.0.1:1883                            │    ║
║  └─────────────────────────────────────────────────────────┘    ║
║                                                                  ║
║  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  ║
║  │  Casillero 1     │  │  Casillero 2     │  │   Puerta     │  ║
║  │  ┌────────────┐  │  │  ┌────────────┐  │  │  ┌────────┐ │  ║
║  │  │ FC-51 IR   │  │  │  │ FC-51 IR   │  │  │  │ Reed   │ │  ║
║  │  │ GPIO 33    │  │  │  │ GPIO 32    │  │  │  │ Switch │ │  ║
║  │  └────────────┘  │  │  └────────────┘  │  │  │GPIO 13 │ │  ║
║  └──────────────────┘  └──────────────────┘  │  └────────┘ │  ║
║                                               │  + Chapa    │  ║
║  ┌──────────────────┐  ┌──────────────────┐  │  GPIO 17    │  ║
║  │  PIR (HC-SR501)  │  │  BH1750 (I2C)   │  └──────────────┘  ║
║  │  GPIO 27         │  │  SDA=21 SCL=22  │                     ║
║  │  Deteccion       │  │  Luminosidad    │  ┌──────────────┐  ║
║  │  movimiento      │  │  (lux)          │  │  RPi GPIO    │  ║
║  └──────────────────┘  └──────────────────┘  │  GPIO 17=Chapa│ ║
║                                               │  GPIO 27=Btn │  ║
║                                               └──────────────┘  ║
╚══════════════════════════════════════════════════════════════════╝
```

## 2. ESQUEMA LOGICO (Comunicacion)

```
┌──────────────┐         WiFi AP          ┌──────────────────────┐
│              │  ESP32_MQTT_AP            │   Raspberry Pi 4B    │
│    ESP32     │ ──────────────────────►  │                      │
│  (Sensores)  │    MQTT (10.42.0.1:1883)  │  ┌────────────────┐  │
│              │                           │  │   Mosquitto    │  │
│  Topics:     │                           │  │   (Broker)     │  │
│  - aforo     │                           │  │   puerto 1883  │  │
│  - pir       │                           │  └───────┬────────┘  │
│  - puerta    │                           │          │           │
│  - luz       │                           │  ┌───────▼────────┐  │
│  - casilleros│                           │  │ backend-control │  │
└──────────────┘                           │  │  (Flask:5000)  │  │
                                           │  │                │  │
                                           │  │ - MQTT Relay   │  │
                                           │  │ - Tuya API     │  │
                                           │  │ - RFID Reader  │  │
                                           │  │ - Chapa GPIO   │  │
                                           │  └───────┬────────┘  │
                                           │          │           │
                                           │  ┌───────▼────────┐  │
                                           │  │ web-dashboard  │  │
                                           │  │  (Nginx:80)    │  │
                                           │  │  HTML/JS/CSS   │  │
                                           │  └────────────────┘  │
                                           └──────────┬───────────┘
                                                      │
                              ┌────────────────────────┼────────────────┐
                              │                        │                │
                    ┌─────────▼──────┐    ┌────────────▼───────┐  ┌────▼──────┐
                    │   Firebase     │    │   Tuya Cloud API   │  │ new-      │
                    │   (complexivo-fv)│   │   (Interruptor)    │  │ conexion  │
                    │                │    │                    │  │ (companion)│
                    │  /usuarios     │    │  switch_1 ON/OFF   │  │           │
                    │  /inventario   │    │                    │  │           │
                    │  /accesos      │    └────────────────────┘  └───────────┘
                    │  /monitoreo    │
                    │  /estado_foco  │
                    │  /alertas      │
                    └────────────────┘
```

## 3. TOPICS MQTT

```
ESP32 Publica ──────────────────────────────────────────────► Mosquitto
┌─────────────────────────┬──────────────────────────────────────────┐
│ Topic                   │ Contenido                                │
├─────────────────────────┼──────────────────────────────────────────┤
│ sensor_ir/casillero1    │ "true" (alerta) / "false" (seguro)       │
│ sensor_ir/casillero2    │ "true" (alerta) / "false" (seguro)       │
│ movimiento_pir          │ "true" / "false"                         │
│ puerta_fisica/estado    │ "0" (cerrada) / "1" (abierta)            │
│ aula/luminosidad        │ "83.5" (lux float)                       │
└─────────────────────────┴──────────────────────────────────────────┘

Backend Suscribe ◄────────────────────────────────────────── Mosquitto
Backend → Firebase:
┌─────────────────────────┬──────────────────────────────────────────┐
│ MQTT Topic              │ Firebase Path                            │
├─────────────────────────┼──────────────────────────────────────────┤
│ sensor_ir/casillero1    │ /monitoreo/casillero1 = "ALERTA"/"SEGURO"│
│ sensor_ir/casillero2    │ /monitoreo/casillero2 = "ALERTA"/"SEGURO"│
│ movimiento_pir          │ /monitoreo/movimiento_pir = true/false   │
│ puerta_fisica/estado    │ /monitoreo/puerta = true/false           │
│                         │ /monitoreo/estado_puerta = "ABIERTA"/"CERRADA" │
│ aula/luminosidad        │ /monitoreo/lux_actual = 83.5             │
│ accesos                 │ /accesos/ (push registro)                │
└─────────────────────────┴──────────────────────────────────────────┘

Backend ← Firebase (listeners):
┌─────────────────────────┬──────────────────────────────────────────┐
│ Firebase Path           │ Accion                                   │
├─────────────────────────┼──────────────────────────────────────────┤
│ /estado_foco            │ → Tuya Cloud API (ON/OFF interruptor)    │
│ /configuracion/horario  │ Control horario iluminacion 6:30-22:00   │
│ /configuracion/umbral   │ Umbral luxes para encendido automatico   │
└─────────────────────────┴──────────────────────────────────────────┘
```

## 4. LOGICA DE ILUMINACION

```
┌─────────────────────────────────────────────────────────────┐
│                 CONTROL DE ILUMINACION                       │
│                                                              │
│  BH1750 (lux) ──► ¿Es horario? (6:30-22:00)                 │
│                      │           │                           │
│                     SI           NO → Apagar, no controlar   │
│                      │                                        │
│              ¿lux < umbral?                                   │
│              /            \                                   │
│            SI              NO                                │
│             │               │                                │
│    ¿Hay movimiento?    ¿lux > umbral x3?                     │
│    (PIR=true)           (histéresis)                          │
│      /      \            /       \                            │
│    SI        NO        SI         NO                         │
│     │         │         │          │                         │
│  ENCENDER  NO hacer  APAGAR    mantener                      │
│             nada                                               │
│                                                              │
│  Cooldown: 60 segundos entre cambios                         │
│  Minimo encendido: 5 minutos (via timer backend)             │
│  Maximo encendido: 14 horas (via timer backend)              │
│  Fuera horario: Solo manual con aprobacion dashboard         │
└─────────────────────────────────────────────────────────────┘
```

## 5. LOGICA DE ACCESOS

```
┌─────────────────────────────────────────────────────────────┐
│                    FLUJO DE ACCESOS                          │
│                                                              │
│  ┌──────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │ RFID     │────►│ ESP32 lee    │────►│ MQTT topic   │    │
│  │ Tarjeta  │     │ UID          │     │ "accesos"    │    │
│  └──────────┘     └──────────────┘     └──────┬───────┘    │
│                                                │             │
│  ┌──────────┐     ┌──────────────┐             │             │
│  │ Teclado  │────►│ new-conexion │────► HTTP POST             │
│  │ Codigo   │     │ valida       │     /api/registro_acceso   │
│  └──────────┘     └──────────────┘             │             │
│                                                ▼             │
│                                    ┌───────────────────┐     │
│                                    │ Backend verifica  │     │
│                                    │ UID en Firebase   │     │
│                                    │ /usuarios/{uid}   │     │
│                                    └─────────┬─────────┘     │
│                                              │               │
│                               ┌──────────────┴─────────────┐ │
│                               │                            │ │
│                          ENCONTRADO                   NO ENCONTRADO │
│                               │                            │ │
│                    Registrar en /accesos         Log "no registrado"│
│                    Abrir chapa (GPIO 17)                         │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

## 6. PINES GPIO RASPBERRY PI

```
┌────────────────────────────────────────────────┐
│           Raspberry Pi 4B - GPIO Map           │
├────────────┬───────────────────────────────────┤
│ GPIO 17    │ Rele Chapa Electrica (OUTPUT)     │
│ GPIO 27    │ Pulsador Salida (INPUT, PUD_UP)   │
│ SPI 0.0    │ RFID MFRC522 (lector tarjetas)    │
│ wlan0      │ WiFi AP (10.42.0.1)               │
│ eth0       │ Red LAN / NetBird VPN             │
├────────────┼───────────────────────────────────┤
│ Docker     │                                     │
│ :5000      │ backend-control (Flask)             │
│ :80        │ web-dashboard (Nginx)               │
│ :1883      │ mosquitto (MQTT Broker)             │
└────────────┴───────────────────────────────────┘
```

## 7. PINES ESP32

```
┌────────────────────────────────────────────────┐
│              ESP32 NodeMCU-32S                 │
├────────────┬───────────────────────────────────┤
│ GPIO 33    │ IR Casillero 1 (INPUT_PULLUP)     │
│ GPIO 32    │ IR Casillero 2 (INPUT_PULLUP)     │
│ GPIO 27    │ PIR HC-SR501 (INPUT)              │
│ GPIO 13    │ Reed Switch Magnetico (INPUT_PULLUP)│
│ GPIO 21    │ BH1750 SDA (I2C)                  │
│ GPIO 22    │ BH1750 SCL (I2C)                  │
├────────────┼───────────────────────────────────┤
│ WiFi       │ ESP32_MQTT_AP / taipt_iot_2026    │
│ MQTT       │ 10.42.0.1:1883                    │
└────────────┴───────────────────────────────────┘
```

## 8. ESTADO ACTUAL Y PENDIENTES

### Funcionando:
- [x] Backend-control (Flask + MQTT + Tuya)
- [x] Web-dashboard (Nginx)
- [x] Mosquitto (Broker MQTT)
- [x] Firebase conectado
- [x] Tuya Cloud API conectada
- [x] Exportacion PDF de QR
- [x] Login sin OTP (acceso directo)
- [x] Inventario con Marca/Descripcion
- [x] Retiro.html con autenticacion

### Pendiente (requiere cambio en RPi):
- [ ] **SSID WiFi**: Cambiar de `Smart_Stock` a `ESP32_MQTT_AP` para que el ESP32 se conecte
  - Comando: `sudo nmcli con modify Hotspot-1 802-11-wireless.ssid ESP32_MQTT_AP`
  - Luego: `sudo nmcli con down Hotspot-1 && sudo nmcli con up Hotspot-1`

### Pendiente (requiere verificar fisicamente):
- [ ] Sensor magnetico: verificar si `INVERTIR_MAGNETICO` necesita ser `true` o `false`
- [ ] BH1750: verificar que el sensor lee valores correctos (no 0.0)
- [ ] Distancia sensores IR: ajustar segun tamano de casilleros