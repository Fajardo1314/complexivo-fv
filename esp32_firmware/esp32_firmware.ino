/*
 * ESP32 - Firmware MQTT-Only
 * Arquitectura: Publica TODOS los sensores via MQTT local a la RPi.
 * La RPi se encarga de subir los datos a Firebase.
 * Sin Firebase directo, sin actuadores locales.
 *
 * Sensores: PIR, Infrarrojo (aforo), Magnetico (puerta), RFID
 */

#include <MFRC522.h>
#include <PubSubClient.h>
#include <SPI.h>
#include <WiFi.h>
#include <WiFiClient.h>

// === RED ===
const char *WIFI_SSID = "ESP32_MQTT_AP";
const char *WIFI_PASSWORD = "taipt_iot_2026";

// === MQTT (Raspberry Pi - broker local) ===
const char *MQTT_BROKER = "10.42.0.1";
const int MQTT_PORT = 1883;
const char *TOPIC_PIR = "movimiento_pir";
const char *TOPIC_AFORO = "aforo";
const char *TOPIC_PUERTA = "puerta_fisica/estado";
const char *TOPIC_RFID = "accesos";

// === Pines ===
const int PIN_IR1 = 34;
const int PIN_IR2 = 35;
const int PIN_PIR = 27;
const int PIN_MAGNETICO = 13;
#define SS_PIN 5
#define RST_PIN 22

// === Tiempos ===
const unsigned long TIMEOUT_FLUJO = 1500;
const unsigned long DEBOUNCE_CRUCE = 2000;
const unsigned long INTERVALO_PIR = 5000;
const unsigned long INTERVALO_PUERTA = 1000;
const unsigned long INTERVALO_RECONEXION = 30000;
const unsigned long INTERVALO_RECONEXION_WIFI = 30000;

// === Estado global ===
MFRC522 rfid(SS_PIN, RST_PIN);
WiFiClient espClient;
PubSubClient mqttClient(espClient);

int contadorAforo = 0;
int last_IR1 = HIGH, last_IR2 = HIGH;
unsigned long time_IR1_triggered = 0, time_IR2_triggered = 0;
unsigned long last_cruce_time = 0;
bool last_pir_state = LOW;
unsigned long last_pir_post = 0;
int ultimo_estado_puerta = -1;
unsigned long ultimo_tiempo_puerta = 0;
unsigned long ultimo_intento_mqtt = 0;
unsigned long ultimo_intento_wifi = 0;

// ============================================================
//  SETUP
// ============================================================
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=== ESP32 MQTT-Only (RPi handles Firebase) ===\n");

  pinMode(PIN_IR1, INPUT);
  pinMode(PIN_IR2, INPUT);
  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_MAGNETICO, INPUT_PULLUP);

  SPI.begin();
  rfid.PCD_Init();
  Serial.println("[RFID] Inicializado.");

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
  procesarRFID();
  procesarPuerta();

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
  } else {
    Serial.print(" FALLO rc=");
    Serial.println(mqttClient.state());
  }
}

// ============================================================
//  MQTT: PUBLICAR DATO (solo MQTT, sin Firebase)
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
//  SENSOR: PIR
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
//  SENSOR: INFRARROJO DOBLE (AFORO)
// ============================================================
void procesarFlujo() {
  int ir1 = digitalRead(PIN_IR1);
  int ir2 = digitalRead(PIN_IR2);
  unsigned long now = millis();

  if (now - last_cruce_time < DEBOUNCE_CRUCE) {
    last_IR1 = ir1;
    last_IR2 = ir2;
    return;
  }

  if (ir1 == LOW && last_IR1 == HIGH)
    time_IR1_triggered = now;
  if (ir2 == LOW && last_IR2 == HIGH)
    time_IR2_triggered = now;

  if (time_IR1_triggered > 0 && time_IR2_triggered > time_IR1_triggered) {
    if (time_IR2_triggered - time_IR1_triggered < TIMEOUT_FLUJO) {
      contadorAforo++;
      enviarMQTTInt(TOPIC_AFORO, contadorAforo);
      last_cruce_time = now;
    }
    time_IR1_triggered = 0;
    time_IR2_triggered = 0;
  } else if (time_IR2_triggered > 0 &&
             time_IR1_triggered > time_IR2_triggered) {
    if (time_IR1_triggered - time_IR2_triggered < TIMEOUT_FLUJO) {
      contadorAforo--;
      if (contadorAforo < 0)
        contadorAforo = 0;
      enviarMQTTInt(TOPIC_AFORO, contadorAforo);
      last_cruce_time = now;
    }
    time_IR1_triggered = 0;
    time_IR2_triggered = 0;
  }

  if (time_IR1_triggered > 0 && now - time_IR1_triggered > TIMEOUT_FLUJO)
    time_IR1_triggered = 0;
  if (time_IR2_triggered > 0 && now - time_IR2_triggered > TIMEOUT_FLUJO)
    time_IR2_triggered = 0;

  last_IR1 = ir1;
  last_IR2 = ir2;
}

// ============================================================
//  SENSOR: PUERTA MAGNETICA
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
//  SENSOR: RFID
// ============================================================
void procesarRFID() {
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial())
    return;

  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10)
      uid += "0";
    uid += String(rfid.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();
  enviarMQTT(TOPIC_RFID, uid);
  rfid.PICC_HaltA();
}