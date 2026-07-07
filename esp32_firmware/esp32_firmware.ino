/*
 * ESP32 — Firmware Módulo de Sensores (Seguridad de Estante, PIR, Puerta y Luz)
 * Lógica actualizada: Sin Aforo, Sensores IR FC-51 adaptados como alarma de estantería.
 *
 * Pines:
 *   IR Casillero 1: GPIO 33 (INPUT_PULLUP)
 *   IR Casillero 2: GPIO 32 (INPUT_PULLUP)
 *   Magnético:      GPIO 13 (INPUT_PULLUP) — 100% independiente
 *   PIR:            GPIO 27 (INPUT)
 *   BH1750:         I2C SDA=21, SCL=22
 */

#include <BH1750.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <Wire.h>

// Prototipos de funciones
void conectarWiFi();
void conectarMQTT();
void publicar(const char *topic, String val);
void procesarCasilleros(unsigned long ahora);
void procesarPIR(unsigned long ahora);
void procesarPuerta(unsigned long ahora);
void procesarLuz(unsigned long ahora);

// ═══════════════════════════════════════════
//  CONFIGURACIÓN
// ═══════════════════════════════════════════
const char *WIFI_SSID = "ESP32_MQTT_AP";
const char *WIFI_PASSWORD = "taipt_iot_2026";
const char *MQTT_BROKER = "10.42.0.1";
const int MQTT_PORT = 1883;

// Topics MQTT
const char *TOPIC_CASILLERO1 = "sensor_ir/casillero1";
const char *TOPIC_CASILLERO2 = "sensor_ir/casillero2";
const char *TOPIC_PUERTA = "puerta_fisica/estado";
const char *TOPIC_PIR = "movimiento_pir";
const char *TOPIC_LUZ = "aula/luminosidad";

// Pines
const int PIN_IR1 = 33; // Casillero 1
const int PIN_IR2 = 32; // Casillero 2
const int PIN_PIR = 27; // PIR
const int PIN_MAG = 13; // Magnético (PULLUP)

// Configuración sensor magnético
// Cambiar a true si el sensor reporta invertido
const bool INVERTIR_MAGNETICO = false;

// ═══════════════════════════════════════════
//  CONSTANTES DE TIEMPO (ms)
// ═══════════════════════════════════════════
const unsigned long DEBOUNCE_IR = 200;      // Debounce para evitar alertas falsas por ruido en IR
const unsigned long DEBOUNCE_PIR = 5000;
const unsigned long DEBOUNCE_PUERTA = 1000;
const unsigned long INTERVALO_LUZ = 5000;
const unsigned long RECONECTAR_WIFI = 30000;
const unsigned long RECONECTAR_MQTT = 30000;

// ═══════════════════════════════════════════
//  ESTADO GLOBAL
// ═══════════════════════════════════════════
WiFiClient espClient;
PubSubClient mqttClient(espClient);
BH1750 lightMeter;

bool bh1750_ok = false;
bool last_pir = LOW;
unsigned long lastPir = 0;
int lastPuerta = -1;
unsigned long lastPuer = 0;
unsigned long lastLuz = 0;
unsigned long lastWifi = 0;
unsigned long lastMqtt = 0;
unsigned long lastReportePuerta = 0;  // Reporte periodico de diagnostico
const unsigned long REPORTE_PUERTA = 10000;  // Imprimir estado cada 10s


// Estado de los casilleros (FC-51 IR)
// Nota: LOW = Obstáculo detectado (Alerta / Mano cerca), HIGH = Seguro / Libre
int lastCasillero1 = -1;
int lastCasillero2 = -1;
unsigned long lastDebounceIR1 = 0;
unsigned long lastDebounceIR2 = 0;

// ═══════════════════════════════════════════
//  SETUP
// ═══════════════════════════════════════════
void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println("\n=== ESP32 Seguridad Estante + Sensores v5.0 ===\n");

  pinMode(PIN_IR1, INPUT_PULLUP);
  pinMode(PIN_IR2, INPUT_PULLUP);
  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_MAG, INPUT_PULLUP);

  Wire.begin(21, 22);
  delay(500);
  bh1750_ok = lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE);
  if (bh1750_ok) {
    Serial.println("[BH1750] OK");
    lightMeter.readLightLevel();
    delay(200);
  } else {
    Serial.println("[BH1750] No detectado");
  }

  conectarWiFi();
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setBufferSize(512);
  conectarMQTT();

  // Publicar estado inicial del sensor magnetico al arrancar
  delay(500);
  int estInicial = digitalRead(PIN_MAG);
  lastPuerta = estInicial;
  bool cerradaInicial = INVERTIR_MAGNETICO ? (estInicial == HIGH) : (estInicial == LOW);
  Serial.println("[PUERTA] Estado inicial GPIO 13 = " + String(estInicial) + " -> " + String(cerradaInicial ? "CERRADA" : "ABIERTA"));
  publicar(TOPIC_PUERTA, cerradaInicial ? "0" : "1");
}

// ═══════════════════════════════════════════
//  LOOP
// ═══════════════════════════════════════════
void loop() {
  unsigned long ahora = millis();

  // WiFi
  if (WiFi.status() != WL_CONNECTED && ahora - lastWifi > RECONECTAR_WIFI) {
    lastWifi = ahora;
    conectarWiFi();
  }

  // MQTT
  if (!mqttClient.connected() && ahora - lastMqtt > RECONECTAR_MQTT) {
    lastMqtt = ahora;
    conectarMQTT();
  }
  mqttClient.loop();

  // Procesamiento de Sensores
  procesarCasilleros(ahora);
  procesarPIR(ahora);
  procesarPuerta(ahora);
  procesarLuz(ahora);

  delay(20);
}

// ═══════════════════════════════════════════
//  CONEXIONES
// ═══════════════════════════════════════════
void conectarWiFi() {
  if (WiFi.status() == WL_CONNECTED)
    return;
  WiFi.disconnect(true);
  delay(100);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int r = 0;
  while (WiFi.status() != WL_CONNECTED && r < 30) {
    delay(500);
    r++;
  }
  if (WiFi.status() == WL_CONNECTED)
    Serial.println("[WiFi] OK: " + WiFi.localIP().toString());
}

void conectarMQTT() {
  if (mqttClient.connected() || WiFi.status() != WL_CONNECTED)
    return;
  String cid = "ESP32-" + String(random(0, 9999));
  if (mqttClient.connect(cid.c_str()))
    Serial.println("[MQTT] OK");
  else
    Serial.println("[MQTT] FALLO rc=" + String(mqttClient.state()));
}

void publicar(const char *topic, String val) {
  if (mqttClient.connected()) {
    mqttClient.publish(topic, val.c_str());
    Serial.println("[PUB] " + String(topic) + " = " + val);
  }
}

// ═══════════════════════════════════════════
//  PROCESAMIENTO DE ESTANTERÍA SEGURA (IR)
// ═══════════════════════════════════════════
void procesarCasilleros(unsigned long ahora) {
  int lectura1 = digitalRead(PIN_IR1);
  int lectura2 = digitalRead(PIN_IR2);

  // Casillero 1 (IR 1)
  if (lectura1 != lastCasillero1) {
    if (ahora - lastDebounceIR1 > DEBOUNCE_IR) {
      lastCasillero1 = lectura1;
      // LOW = Objeto detectado (Alerta = true), HIGH = Seguro = false
      bool alerta = (lectura1 == LOW);
      publicar(TOPIC_CASILLERO1, alerta ? "true" : "false");
      Serial.println("[ESTANTE] Casillero 1: " + String(alerta ? "ALERTA" : "SEGURO"));
      lastDebounceIR1 = ahora;
    }
  }

  // Casillero 2 (IR 2)
  if (lectura2 != lastCasillero2) {
    if (ahora - lastDebounceIR2 > DEBOUNCE_IR) {
      lastCasillero2 = lectura2;
      bool alerta = (lectura2 == LOW);
      publicar(TOPIC_CASILLERO2, alerta ? "true" : "false");
      Serial.println("[ESTANTE] Casillero 2: " + String(alerta ? "ALERTA" : "SEGURO"));
      lastDebounceIR2 = ahora;
    }
  }
}

// ═══════════════════════════════════════════
//  PIR
// ═══════════════════════════════════════════
void procesarPIR(unsigned long ahora) {
  bool pir = digitalRead(PIN_PIR) == HIGH;

  if (pir && !last_pir && ahora - lastPir > DEBOUNCE_PIR) {
    publicar(TOPIC_PIR, "true");
    lastPir = ahora;
  }

  if (!pir && last_pir && ahora - lastPir > 2000) {
    publicar(TOPIC_PIR, "false");
  }

  last_pir = pir;
}

// ═══════════════════════════════════════════
//  PUERTA MAGNÉTICA
//  Sensor NC: cerrada = LOW, abierta = HIGH  (INVERTIR_MAGNETICO = false)
//  Sensor NO: cerrada = HIGH, abierta = LOW  (INVERTIR_MAGNETICO = true)
// ═══════════════════════════════════════════
void procesarPuerta(unsigned long ahora) {
  int est = digitalRead(PIN_MAG);

  // Reporte de diagnostico periodico en Serial Monitor
  if (ahora - lastReportePuerta > REPORTE_PUERTA) {
    lastReportePuerta = ahora;
    bool cerradaDiag = INVERTIR_MAGNETICO ? (est == HIGH) : (est == LOW);
    Serial.println("[PUERTA-DIAG] GPIO13=" + String(est) +
                   " -> " + String(cerradaDiag ? "CERRADA" : "ABIERTA") +
                   " | INVERTIR=" + String(INVERTIR_MAGNETICO ? "true" : "false"));
  }

  // Solo publicar si cambio el estado Y paso el debounce
  if (est != lastPuerta && ahora - lastPuer > DEBOUNCE_PUERTA) {
    bool cerrada = INVERTIR_MAGNETICO ? (est == HIGH) : (est == LOW);
    publicar(TOPIC_PUERTA, cerrada ? "0" : "1");
    Serial.println("[PUERTA] Cambio detectado: GPIO13=" + String(est) +
                   " -> " + String(cerrada ? "CERRADA" : "ABIERTA"));
    lastPuerta = est;
    lastPuer = ahora;
  }
}


// ═══════════════════════════════════════════
//  BH1750 LUZ
// ═══════════════════════════════════════════
void procesarLuz(unsigned long ahora) {
  if (!bh1750_ok || ahora - lastLuz < INTERVALO_LUZ)
    return;
  float lux = lightMeter.readLightLevel();
  if (lux > 0)
    publicar(TOPIC_LUZ, String(lux, 1));
  lastLuz = ahora;
}
