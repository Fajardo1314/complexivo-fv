/*
 * ESP32 - Firmware MQTT-Only (Sin RFID, Anti-Bloqueo, Candado IR)
 * Arquitectura: Publica sensores via MQTT local a la RPi.
 * La RPi se encarga de subir los datos a Firebase.
 *
 * Sensores activos:
 *   - PIR (GPIO 27)
 *   - IR Aforo (GPIO 32) - INPUT_PULLUP, candado booleano + debounce
 *   - Magnetico Puerta (GPIO 13)
 *   - BH1750 Luxometro (I2C: SDA=21, SCL=22) - Aislado
 *
 * RFID ELIMINADO.
 */

#include <BH1750.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <Wire.h>

// === RED ===
const char *WIFI_SSID = "ESP32_MQTT_AP";
const char *WIFI_PASSWORD = "taipt_iot_2026";

// === MQTT ===
const char *MQTT_BROKER = "10.42.0.1";
const int MQTT_PORT = 1883;
const char *TOPIC_PIR = "movimiento_pir";
const char *TOPIC_AFORO = "aforo";
const char *TOPIC_PUERTA = "puerta_fisica/estado";
const char *TOPIC_LUZ = "aula/luminosidad";

// === Pines ===
const int PIN_IR = 32;
const int PIN_PIR = 27;
const int PIN_MAGNETICO = 13;

// === BH1750 ===
BH1750 lightMeter;
bool bh1750_ok = false;
bool bh1750_error_logged = false;
unsigned long lastLuzRead = 0;
const unsigned long INTERVALO_LUZ = 5000;

// === Tiempos ===
const unsigned long DEBOUNCE_IR = 1000;
const unsigned long INTERVALO_PIR = 5000;
const unsigned long INTERVALO_PUERTA = 1000;
const unsigned long INTERVALO_RECONEXION = 30000;
const unsigned long INTERVALO_RECONEXION_WIFI = 30000;

// === Estado global ===
WiFiClient espClient;
PubSubClient mqttClient(espClient);

int contadorAforo = 0;
bool last_pir_state = LOW;
unsigned long last_pir_post = 0;
int ultimo_estado_puerta = -1;
unsigned long ultimo_tiempo_puerta = 0;
unsigned long ultimo_intento_mqtt = 0;
unsigned long ultimo_intento_wifi = 0;

// === Estado IR con confirmacion por tiempo ===
// El pin debe permanecer LOW por 200ms continuos para confirmar cruce real
bool ir_en_espera = false;
bool ir_detectando = false;
unsigned long irTiempoDeteccion = 0;
unsigned long irUltimoConteo = 0;
const unsigned long IR_CONFIRMACION = 200; // 200ms LOW continuo = cruce real

// ============================================================
//  SETUP
// ============================================================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=== ESP32 MQTT-Only (Sin RFID, Candado IR) ===\n");

  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_MAGNETICO, INPUT_PULLUP);
  pinMode(PIN_IR, INPUT_PULLUP);
  Serial.println("[IR] GPIO 32 configurado con INPUT_PULLUP.");

  Wire.begin(21, 22);
  delay(100);
  bh1750_ok = lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE);
  if (bh1750_ok) {
    Serial.println("[BH1750] Luxometro inicializado.");
  } else {
    Serial.println("[BH1750] No detectado. Lecturas deshabilitadas.");
  }

  conectarWiFi();
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setBufferSize(512);
  intentarConexionMQTT();
}

// ============================================================
//  LOOP
// ============================================================
void loop() {
  verificarWiFi();

  if (!mqttClient.connected()) {
    unsigned long ahora = millis();
    if (ahora - ultimo_intento_mqtt >= INTERVALO_RECONEXION) {
      intentarConexionMQTT();
      ultimo_intento_mqtt = ahora;
    }
  }
  mqttClient.loop();

  procesarFlujo();
  procesarPIR();
  procesarPuerta();
  procesarLuz();

  delay(50);
}

// ============================================================
//  WIFI
// ============================================================
void conectarWiFi() {
  if (WiFi.status() == WL_CONNECTED)
    return;
  if (WiFi.status() == WL_IDLE_STATUS)
    return;

  WiFi.disconnect(true);
  delay(100);
  WiFi.mode(WIFI_STA);

  Serial.print("[WiFi] Conectando a: ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 30) {
    delay(500);
    Serial.print(".");
    retries++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WiFi] Conectado. IP: " + WiFi.localIP().toString());
  } else {
    Serial.println("\n[WiFi] No se pudo conectar. Reintentando en 30s...");
    WiFi.disconnect(true);
  }
}

void verificarWiFi() {
  if (WiFi.status() == WL_CONNECTED)
    return;
  unsigned long ahora = millis();
  if (ahora - ultimo_intento_wifi >= INTERVALO_RECONEXION_WIFI) {
    ultimo_intento_wifi = ahora;
    conectarWiFi();
  }
}

// ============================================================
//  MQTT - CONEXION
// ============================================================
void intentarConexionMQTT() {
  if (mqttClient.connected() || WiFi.status() != WL_CONNECTED)
    return;
  Serial.print("[MQTT] Conectando...");
  String cid = "ESP32-" + String(random(0, 9999));
  if (mqttClient.connect(cid.c_str())) {
    Serial.println(" OK");
    mqttClient.publish("aforo", "0");
    Serial.println("[MQTT] Test publish: aforo = 0");
  } else {
    Serial.print(" FALLO rc=");
    Serial.println(mqttClient.state());
  }
}

// ============================================================
//  MQTT: PUBLICAR DATO
// ============================================================
void enviarMQTT(String topic, String valor) {
  Serial.println("[MQTT] " + topic + " = " + valor);
  if (mqttClient.connected()) {
    mqttClient.publish(topic.c_str(), valor.c_str());
    Serial.println("  -> [MQTT] OK");
  } else {
    Serial.println("  -> [MQTT] SKIP (no conectado)");
  }
}

void enviarMQTTInt(String topic, int valor) {
  enviarMQTT(topic, String(valor));
}

// ============================================================
//  SENSOR: PIR (GPIO 27) - INTACTO
// ============================================================
void procesarPIR() {
  bool pir = digitalRead(PIN_PIR) == HIGH;
  unsigned long now = millis();
  int puerta = digitalRead(PIN_MAGNETICO);
  bool puertaCerrada = (puerta == LOW);

  if (!puertaCerrada || contadorAforo > 0) {
    last_pir_state = LOW;
    return;
  }

  if (pir && !last_pir_state && now - last_pir_post > INTERVALO_PIR) {
    enviarMQTT(TOPIC_PIR, "true");
    last_pir_post = now;
  }
  if (!pir && last_pir_state && now - last_pir_post > 2000) {
    enviarMQTT(TOPIC_PIR, "false");
  }
  last_pir_state = pir;
}

// ============================================================
//  SENSOR: INFRARROJO (AFORO) - CONFIRMACION POR TIEMPO
// ============================================================
// GPIO 32 con INPUT_PULLUP. Reposo = HIGH.
// Logica anti-ruido en 3 pasos:
//   1. Pin baja a LOW → iniciar temporizador de confirmacion
//   2. Si el pin permanece LOW por 200ms seguidos → cruce REAL confirmado
//   3. Contar +1, activar candado, esperar a que el pin vuelva a HIGH
// Esto elimina TODOS los picos de ruido menores a 200ms.
// ============================================================
void procesarFlujo() {
  int irActual = digitalRead(PIN_IR);
  unsigned long now = millis();

  // FASE 1: Candado activo - esperar a que el pin vuelva a HIGH
  if (ir_en_espera) {
    if (irActual == HIGH) {
      ir_en_espera = false;
      ir_detectando = false;
      Serial.println("[IR] Liberado. Listo.");
    }
    return;
  }

  // FASE 2: Pin bajo - iniciar o continuar confirmacion
  if (irActual == LOW) {
    if (!ir_detectando) {
      // Primera vez que vemos LOW - iniciar temporizador
      ir_detectando = true;
      irTiempoDeteccion = now;
    } else if (now - irTiempoDeteccion >= IR_CONFIRMACION) {
      // 200ms continuos en LOW - CRUCE REAL CONFIRMADO
      if (now - irUltimoConteo >= DEBOUNCE_IR) {
        contadorAforo++;
        irUltimoConteo = now;
        ir_en_espera = true;
        ir_detectando = false;
        Serial.println("[IR] CRUCE CONFIRMADO. Aforo: " +
                       String(contadorAforo));
        enviarMQTTInt(TOPIC_AFORO, contadorAforo);
      }
    }
    // Si no paso la confirmacion aun, seguir esperando
  } else {
    // Pin volvio a HIGH antes de 200ms - era ruido, cancelar
    ir_detectando = false;
  }
}

// ============================================================
//  SENSOR: PUERTA MAGNETICA (GPIO 13) - INTACTO
// ============================================================
void procesarPuerta() {
  unsigned long now = millis();
  if (now - ultimo_tiempo_puerta < INTERVALO_PUERTA)
    return;

  int estado = digitalRead(PIN_MAGNETICO);
  if (estado != ultimo_estado_puerta) {
    enviarMQTT(TOPIC_PUERTA, estado == LOW ? "0" : "1");
    ultimo_estado_puerta = estado;
  }
  ultimo_tiempo_puerta = now;
}

// ============================================================
//  SENSOR: BH1750 LUXOMETRO - AISLADO, NO BLOQUEANTE
// ============================================================
void procesarLuz() {
  if (!bh1750_ok)
    return;

  unsigned long now = millis();
  if (now - lastLuzRead < INTERVALO_LUZ)
    return;
  lastLuzRead = now;

  float lux = lightMeter.readLightLevel();
  if (lux < 0) {
    if (!bh1750_error_logged) {
      Serial.println("[BH1750] Error de lectura. Desactivando luxometro.");
      bh1750_error_logged = true;
    }
    bh1750_ok = false;
    return;
  }

  enviarMQTTInt(TOPIC_LUZ, (int)lux);
}