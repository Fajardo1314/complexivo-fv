"""
credentials.py
==============
Credenciales y configuracion centralizada del sistema Smart Stock.

     ADVERTENCIA DE SEGURIDAD:
    - NO subir este archivo a repositorios publicos (Git, GitHub, etc.)
    - Anadir 'credentials.py' al archivo .gitignore
    - Para produccion, usar variables de entorno o un gestor de secretos.
"""

# -----------------------------------------------------------
# RASPBERRY PI 4B - Acceso SSH
# -----------------------------------------------------------

SSH_HOST     = "raspberryfv"             # NetBird IP
SSH_USER     = "user"
SSH_PASSWORD = "taipt"
SSH_PORT     = 22

SSH_HOST_LOCAL = "192.168.18.251"           # IP local LAN

# -----------------------------------------------------------
# NETBIRD VPN
# -----------------------------------------------------------

NETBIRD_SETUP_KEY = "AD8D21D2-4620-45FE-8AB7-D171F6E8FE18"
NETBIRD_FQDN      = "raspberryfv.nb"
NETBIRD_IFACE     = "wt0"

# -----------------------------------------------------------
# WIFI HOTSPOT (para ESP32)
# -----------------------------------------------------------

AP_SSID        = "ESP32_MQTT_AP"
AP_PASSWORD    = "taipt_iot_2026"
AP_GATEWAY_IP  = "10.42.0.1"   # IP de la Raspberry en la red del AP

# -----------------------------------------------------------
# MQTT (Mosquitto Broker)
# -----------------------------------------------------------

MQTT_HOST      = AP_GATEWAY_IP   # Broker en la red del AP
MQTT_PORT      = 1883
MQTT_USER      = None            # Sin autenticacion (allow_anonymous true)
MQTT_PASSWORD  = None

# -----------------------------------------------------------
# FIREBASE
# -----------------------------------------------------------

FIREBASE_EMAIL        = "margaritafajardo1@hotmail.com"
FIREBASE_PROJECT      = "complexivo-fv"
FIREBASE_DATABASE_URL = "https://complexivo-fv-default-rtdb.firebaseio.com"
FIREBASE_KEY_FILE     = "google-services.json"

# -----------------------------------------------------------
# GMAIL SMTP (para envio de correos OTP y notificaciones)
# -----------------------------------------------------------

SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587
SMTP_USER     = "smartstock97@gmail.com"
SMTP_PASSWORD = "F@jardo123"

# -----------------------------------------------------------
# ESP32 FIRMWARE - Configuracion de red
# -----------------------------------------------------------

ESP32_WIFI_SSID     = AP_SSID
ESP32_WIFI_PASSWORD = AP_PASSWORD
ESP32_MQTT_BROKER   = AP_GATEWAY_IP