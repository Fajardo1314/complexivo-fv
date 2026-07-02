/*
 * ESP32 — Firmware Aforo Bidireccional + Puerta Independiente
 * Máquina de estados estricta anti-ruido eléctrico.
 *
 * Pines:
 *   IR Exterior: GPIO 35 (INPUT)
 *   IR Interior: GPIO 32 (INPUT_PULLUP)
 *   Magnético:   GPIO 13 (INPUT_PULLUP) — 100% independiente
 *   PIR:         GPIO 27
 *   BH1750:      I2C SDA=21, SCL=22
 *
 * Algoritmo anti-fantasma:
 *   Estado IDLE → esperar que un sensor pase a LOW.
 *   Al activarse un sensor, se abre una ventana de 2000ms.
 *   Si el segundo sensor se activa DENTRO de la ventana → cruce válido.
 *   Si la ventana expira sin segundo sensor → se descarta (ruido).
 *   Tras cruce válido → bloqueo global de 1500ms.
 */

#include <BH1750.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <Wire.h>

// ═══════════════════════════════════════════
//  CONFIGURACIÓN
// ═══════════════════════════════════════════
const char *WIFI_SSID = "ESP32_MQTT_AP";
const char *WIFI_PASSWORD = "taipt_iot_2026";
const char *MQTT_BROKER = "10.42.0.1";
const int MQTT_PORT = 1883;

// Topics MQTT
const char *TOPIC_AFORO = "aforo";
const char *TOPIC_PUERTA = "puerta_fisica/estado";
const char *TOPIC_PIR = "movimiento_pir";
const char *TOPIC_LUZ = "aula/luminosidad";

// Pines
const int PIN_IR1 = 35; // Exterior
const int PIN_IR2 = 32; // Interior (PULLUP)
const int PIN_PIR = 27;
const int PIN_MAG = 13; // Magnético (PULLUP) — independiente

// ═══════════════════════════════════════════
//  CONSTANTES DE TIEMPO (ms)
// ═══════════════════════════════════════════
const unsigned long VENTANA_CRUCE = 2000;  // Ventana para segundo sensor
const unsigned long BLOQUEO_GLOBAL = 1500; // Debounce tras cruce válido
const unsigned long DEBOUNCE_PIR = 5000;
const unsigned long DEBOUNCE_PUERTA = 1000;
const unsigned long INTERVALO_LUZ = 5000;
const unsigned long RECONECTAR_WIFI = 30000;
const unsigned long RECONECTAR_MQTT = 30000;

// ═══════════════════════════════════════════
//  MÁQUINA DE ESTADOS — AFORO
// ═══════════════════════════════════════════
enum EstadoAforo {
  IDLE,         // Esperando primer sensor
  IR1_ACTIVADO, // IR1 (exterior) LOW, esperando IR2
  IR2_ACTIVADO  // IR2 (interior) LOW, esperando IR1
};

EstadoAforo estadoAforo = IDLE;
unsigned long tiempoActivacion = 0; // millis() cuando se activó primer sensor
unsigned long tiempoBloqueo = 0;    // millis() del último cruce válido

// ═══════════════════════════════════════════
//  ESTADO GLOBAL
// ═══════════════════════════════════════════
WiFiClient espClient;
PubSubClient mqttClient(espClient);
BH1750 lightMeter;

int contadorAforo = 0;
bool bh1750_ok = false;
bool last_pir = LOW;
unsigned long lastPir = 0;
int lastPuerta = -1;
unsigned long lastPuer = 0;
unsigned long lastLuz = 0;
unsigned long lastWifi = 0;
unsigned long lastMqtt = 0;
int lastIR1 = HIGH;
int lastIR2 = HIGH;

// ═══════════════════════════════════════════
//  SETUP
// ═══════════════════════════════════════════
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=== ESP32 Aforo v3.0 — Anti-Ruido ===\n");

  pinMode(PIN_IR1, INPUT);
  pinMode(PIN_IR2, INPUT_PULLUP);
  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_MAG, INPUT_PULLUP);

  Wire.begin(21, 22);
  bh1750_ok = lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE);
  if (bh1750_ok)
    Serial.println("[BH1750] OK");
  else
    Serial.println("[BH1750] No detectado");

  conectarWiFi();
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setBufferSize(512);
  conectarMQTT();
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

  // Sensores
  procesarAforo(ahora);
  procesarPIR(ahora);
  procesarPuerta(ahora);
  procesarLuz(ahora);

  delay(20);
}

// ═══════════════════════════════════════════
//  CONEXIÓN
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
//  AFORO BIDIRECCIONAL — MÁQUINA DE ESTADOS
// ═══════════════════════════════════════════
/*
 *  Diagrama de estados:
 *
 *       ┌──────────────────────────────────────────┐
 *       │                                          │
 *       ▼                                          │
 *    ┌──────┐   IR1=LOW    ┌────────────┐   IR2=LOW  ┌─────────────┐
 *    │ IDLE │─────────────→│ IR1_ACTIV  │──────────→│ ENTRADA +1  │──┐
 *    └──────┘              └────────────┘           └─────────────┘  │
 *       │                       │ timeout 2s                         │
 *       │                       ▼                                    │
 *       │                  ┌──────────┐                              │
 *       │                  │ CANCELAR │──→ IDLE                      │
 *       │                  └──────────┘                              │
 *       │   IR2=LOW    ┌────────────┐   IR1=LOW  ┌─────────────┐   │
 *       └─────────────→│ IR2_ACTIV  │──────────→│ SALIDA  -1  │───┘
 *                      └────────────┘           └─────────────┘  │
 *                           │ timeout 2s        bloqueo 1500ms   │
 *                           ▼                                    │
 *                      ┌──────────┐                              │
 *                      │ CANCELAR │──→ IDLE                      │
 *                      └──────────┘──────────────────────────────┘
 */
void procesarAforo(unsigned long ahora) {
  // Bloqueo global: no procesar tras cruce válido
  if (ahora - tiempoBloqueo < BLOQUEO_GLOBAL) {
    lastIR1 = digitalRead(PIN_IR1);
    lastIR2 = digitalRead(PIN_IR2);
    return;
  }

  int ir1 = digitalRead(PIN_IR1);
  int ir2 = digitalRead(PIN_IR2);

  switch (estadoAforo) {
  case IDLE:
    // Detectar flanco descendente en IR1 (exterior)
    if (ir1 == LOW && lastIR1 == HIGH) {
      estadoAforo = IR1_ACTIVADO;
      tiempoActivacion = ahora;
      Serial.println("[AFORO] IR1 activado → esperando IR2...");
    }
    // Detectar flanco descendente en IR2 (interior)
    else if (ir2 == LOW && lastIR2 == HIGH) {
      estadoAforo = IR2_ACTIVADO;
      tiempoActivacion = ahora;
      Serial.println("[AFORO] IR2 activado → esperando IR1...");
    }
    break;

  case IR1_ACTIVADO:
    // ¿Se activó IR2 dentro de la ventana?
    if (ir2 == LOW && lastIR2 == HIGH) {
      // ENTRADA válida
      contadorAforo++;
      Serial.println("[AFORO] ✅ ENTRADA +" + String(contadorAforo));
      publicar(TOPIC_AFORO, String(contadorAforo));
      estadoAforo = IDLE;
      tiempoBloqueo = ahora;
    }
    // Timeout: cancelar
    else if (ahora - tiempoActivacion > VENTANA_CRUCE) {
      Serial.println("[AFORO] Timeout IR1 → cancelado (ruido)");
      estadoAforo = IDLE;
    }
    break;

  case IR2_ACTIVADO:
    // ¿Se activó IR1 dentro de la ventana?
    if (ir1 == LOW && lastIR1 == HIGH) {
      // SALIDA válida
      contadorAforo--;
      if (contadorAforo < 0)
        contadorAforo = 0;
      Serial.println("[AFORO] ✅ SALIDA " + String(contadorAforo));
      publicar(TOPIC_AFORO, String(contadorAforo));
      estadoAforo = IDLE;
      tiempoBloqueo = ahora;
    }
    // Timeout: cancelar
    else if (ahora - tiempoActivacion > VENTANA_CRUCE) {
      Serial.println("[AFORO] Timeout IR2 → cancelado (ruido)");
      estadoAforo = IDLE;
    }
    break;
  }

  lastIR1 = ir1;
  lastIR2 = ir2;
}

// ═══════════════════════════════════════════
//  PIR — Independiente de todo
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
//  PUERTA MAGNÉTICA — 100% Independiente
// ═══════════════════════════════════════════
void procesarPuerta(unsigned long ahora) {
  if (ahora - lastPuer < DEBOUNCE_PUERTA)
    return;
  int est = digitalRead(PIN_MAG);
  if (est != lastPuerta) {
    publicar(TOPIC_PUERTA, est == LOW ? "0" : "1");
    Serial.println("[PUERTA] " + String(est == LOW ? "CERRADA" : "ABIERTA"));
    lastPuerta = est;
  }
  lastPuer = ahora;
}

// ═══════════════════════════════════════════
//  BH1750 LUZ — Aislado
// ═══════════════════════════════════════════
void procesarLuz(unsigned long ahora) {
  if (!bh1750_ok || ahora - lastLuz < INTERVALO_LUZ)
    return;
  float lux = lightMeter.readLightLevel();
  if (lux >= 0)
    publicar(TOPIC_LUZ, String(lux, 1));
  lastLuz = ahora;
}