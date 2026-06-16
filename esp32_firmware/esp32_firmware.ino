#include <SPI.h>
#include <MFRC522.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClient.h>
#include <PubSubClient.h>

// ═══════════════════════════════════════════════════════════════
//  1. CONFIGURACIÓN DE RED & BROKER (RASPBERRY PI AP)
// ═══════════════════════════════════════════════════════════════
const char* WIFI_SSID     = "Smart_Stock";                      
const char* WIFI_PASSWORD = "TAIPT_M4a";                         

// IP fija de la Raspberry Pi actuando como Hotspot
const char* RASPBERRY_IP  = "10.42.0.1"; 

// endpoints locales
const char* BACKEND_URL   = "http://10.42.0.1:5000/api/sensores";
const char* MQTT_BROKER   = "10.42.0.1";
const int   MQTT_PORT     = 1883;

// ═══════════════════════════════════════════════════════════════
//  2. CONFIGURACIÓN DE FIREBASE DIRECTO
// ═══════════════════════════════════════════════════════════════
// Reemplaza con la URL de tu Realtime Database (ej: "tu-proyecto.firebaseio.com")
const char* FIREBASE_HOST = "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40complexivo-fv.iam.gserviceaccount.com"; 

// ═══════════════════════════════════════════════════════════════
//  3. CONFIGURACIÓN DE PINES & CLIENTES
// ═══════════════════════════════════════════════════════════════
const int PIN_IR1 = 34;       
const int PIN_IR2 = 35;       
const int PIN_PIR = 27;       
const int PIN_MAGNETICO = 13; 

#define SS_PIN    5           
#define RST_PIN   22          

MFRC522 rfid(SS_PIN, RST_PIN);
WiFiClient espClient;
PubSubClient mqttClient(espClient);

// Constantes de tiempo
const unsigned long TIMEOUT_FLUJO = 1500;
const unsigned long DEBOUNCE_CRUCE = 2000;
const unsigned long INTERVALO_PIR = 5000;
const unsigned long INTERVALO_PUERTA = 1000;

// Variables de estado
int last_IR1 = HIGH;
int last_IR2 = HIGH;
unsigned long time_IR1_triggered = 0;
unsigned long time_IR2_triggered = 0;
unsigned long last_cruce_time = 0;
bool last_pir_state = LOW;
unsigned long last_pir_post = 0;
int ultimo_estado_puerta = -1; 
unsigned long ultimo_tiempo_puerta = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n═══════════════════════════════════════");
  Serial.println("  ESP32 — MULTI-CONEXIÓN (MQTT + FIREBASE)");
  Serial.println("═══════════════════════════════════════\n");

  pinMode(PIN_IR1, INPUT);
  pinMode(PIN_IR2, INPUT);
  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_MAGNETICO, INPUT_PULLUP);

  SPI.begin();
  rfid.PCD_Init();
  Serial.println("[SISTEMA] RFID Inicializado.");

  conectarWiFi();
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    conectarWiFi();
  }
  
  if (!mqttClient.connected()) {
    reconectarMQTT();
  }
  mqttClient.loop();

  procesarFlujo();
  procesarPIR();
  procesarRFID();
  procesarPuerta();

  delay(50);
}

void conectarWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.print("[WIFI] Conectando a Hotspot: ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 20) {
    delay(500);
    Serial.print(".");
    retries++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WIFI] [OK] Conectado con IP: " + WiFi.localIP().toString());
  } else {
    Serial.println("\n[WIFI] [ERROR] No se pudo conectar al Hotspot.");
  }
}

void reconectarMQTT() {
  int retries = 0;
  while (!mqttClient.connected() && retries < 3) {
    Serial.print("[MQTT] Intentando conexión al Broker RPi...");
    String clientId = "ESP32Client-" + String(random(0, 1000));
    if (mqttClient.connect(clientId.c_str())) {
      Serial.println("[OK]");
    } else {
      Serial.print("falló, rc=");
      Serial.print(mqttClient.state());
      Serial.println(" reintentando en 2 segundos...");
      delay(2000);
      retries++;
    }
  }
}

// ═══════════════════════════════════════════════════════════════
//  DESPACHADOR DE DATOS CENTRALIZADO (HTTP + MQTT + FIREBASE)
// ═══════════════════════════════════════════════════════════════
void registrarEventoGlobal(String evento, String jsonClaveValor) {
  // Construcción del Payload JSON estándar
  String payload = "{\"evento\":\"" + evento + "\"";
  if (jsonClaveValor.length() > 0) {
    payload += "," + jsonClaveValor;
  }
  payload += "}";

  Serial.println("\n[PROCESANDO EVENTO] " + evento);

  // 1. Envío Local por MQTT a la Raspberry Pi
  if (mqttClient.connected()) {
    String topic = "proyecto/aula/" + evento;
    mqttClient.publish(topic.c_str(), payload.c_str());
    Serial.println("[MQTT] Publicado en: " + topic);
  }

  // 2. Envío Local por HTTP POST a tu Flask
  if (WiFi.status() == WL_CONNECTED) {
    WiFiClient client;
    HTTPClient http;
    http.begin(client, BACKEND_URL);
    http.addHeader("Content-Type", "application/json");
    int httpCode = http.POST(payload);
    http.end();
    Serial.println("[HTTP Flask] Código Respuesta: " + String(httpCode));
  }

  // 3. Envío Directo a la Nube de Firebase (REST API)
  if (WiFi.status() == WL_CONNECTED) {
    WiFiClient fbClient;
    HTTPClient fbHttp;
    // Envía una marca de tiempo con el evento a la colección "historico"
    String urlFirebase = "http://" + String(FIREBASE_HOST) + "/historico.json";
    fbHttp.begin(fbClient, urlFirebase);
    fbHttp.addHeader("Content-Type", "application/json");
    int fbCode = fbHttp.POST(payload);
    fbHttp.end();
    Serial.println("[FIREBASE DIRECTO] Código Respuesta: " + String(fbCode));
  }
}

void procesarPuerta() {
  unsigned long tiempoActual = millis();
  if (tiempoActual - ultimo_tiempo_puerta < INTERVALO_PUERTA) return;

  int estadoActualPuerta = digitalRead(PIN_MAGNETICO);
  if (estadoActualPuerta != ultimo_estado_puerta) {
    String estadoStr = (estadoActualPuerta == LOW) ? "CERRADA" : "ABIERTA";
    registrarEventoGlobal("estado_puerta", "\"estado\":\"" + estadoStr + "\"");
    ultimo_estado_puerta = estadoActualPuerta;
  }
  ultimo_tiempo_puerta = tiempoActual;
}

void procesarRFID() {
  if (!rfid.PICC_IsNewCardPresent()) return;
  if (!rfid.PICC_ReadCardSerial()) return;

  String uidStr = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if(rfid.uid.uidByte[i] < 0x10) uidStr += "0";
    uidStr += String(rfid.uid.uidByte[i], HEX);
  }
  uidStr.toUpperCase();
  
  registrarEventoGlobal("rfid_leido", "\"uid\":\"" + uidStr + "\"");
  rfid.PICC_HaltA();
}

void procesarFlujo() {
  int current_IR1 = digitalRead(PIN_IR1);
  int current_IR2 = digitalRead(PIN_IR2);
  unsigned long currentTime = millis();

  if (currentTime - last_cruce_time < DEBOUNCE_CRUCE) {
    last_IR1 = current_IR1;
    last_IR2 = current_IR2;
    return;
  }

  if (current_IR1 == LOW && last_IR1 == HIGH) {
    time_IR1_triggered = currentTime;
    Serial.println("[IR] Sensor 1 (IN) activo");
  }
  if (current_IR2 == LOW && last_IR2 == HIGH) {
    time_IR2_triggered = currentTime;
    Serial.println("[IR] Sensor 2 (OUT) activo");
  }

  if (time_IR1_triggered > 0 && time_IR2_triggered > time_IR1_triggered) {
    if (time_IR2_triggered - time_IR1_triggered < TIMEOUT_FLUJO) {
      registrarEventoGlobal("ingreso", "");
      last_cruce_time = currentTime;
    }
    time_IR1_triggered = 0;
    time_IR2_triggered = 0;
  }
  else if (time_IR2_triggered > 0 && time_IR1_triggered > time_IR2_triggered) {
    if (time_IR1_triggered - time_IR2_triggered < TIMEOUT_FLUJO) {
      registrarEventoGlobal("salida", "");
      last_cruce_time = currentTime;
    }
    time_IR1_triggered = 0;
    time_IR2_triggered = 0;
  }

  if (time_IR1_triggered > 0 && (currentTime - time_IR1_triggered > TIMEOUT_FLUJO)) time_IR1_triggered = 0;
  if (time_IR2_triggered > 0 && (currentTime - time_IR2_triggered > TIMEOUT_FLUJO)) time_IR2_triggered = 0;

  last_IR1 = current_IR1;
  last_IR2 = current_IR2;
}

void procesarPIR() {
  bool pir_state = digitalRead(PIN_PIR) == HIGH;
  unsigned long currentTime = millis();
  int estadoPuerta = digitalRead(PIN_MAGNETICO);

  if (pir_state && !last_pir_state) {
    if (estadoPuerta == LOW) {
      if (currentTime - last_pir_post > INTERVALO_PIR) {
        registrarEventoGlobal("movimiento_detectado", "");
        last_pir_post = currentTime;
      }
    }
  }
  last_pir_state = pir_state;
}