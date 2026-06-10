#include <SPI.h>
#include <MFRC522.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>

// ═══════════════════════════════════════════════════════════════
//  CONFIGURACIÓN WIFI & FIREBASE (Ajustar a tu entorno)
// ═══════════════════════════════════════════════════════════════
const char* WIFI_SSID     = "Tu_Nombre_de_WiFi";
const char* WIFI_PASSWORD = "Tu_Contrasena_de_WiFi";

// URL base de tu Realtime Database en Firebase
const char* FIREBASE_HOST = "https://complexivo-fv-default-rtdb.firebaseio.com/monitoreo_tiempo_real.json";

// ═══════════════════════════════════════════════════════════════
//  CONFIGURACIÓN DE PINES (Mapeados a tu ESP32)
// ═══════════════════════════════════════════════════════════════
const int PIN_IR1 = 34;       // Sensor IR ENTRADA
const int PIN_IR2 = 35;       // Sensor IR SALIDA
const int PIN_PIR = 27;       // Sensor PIR HC-SR501
const int PIN_MAGNETICO = 13; // Sensor magnético de puerta

// Pines para el Lector RFID RC522
#define SS_PIN    5           // SDA
#define RST_PIN   22          // RST

MFRC522 rfid(SS_PIN, RST_PIN);

// ═══════════════════════════════════════════════════════════════
//  CONSTANTES DE TIMING
// ═══════════════════════════════════════════════════════════════
const unsigned long TIMEOUT_FLUJO = 1500;    // 1.5s máx entre cruce de sensores IR
const unsigned long DEBOUNCE_CRUCE = 2000;   // 2s debounce después de un cruce válido
const unsigned long INTERVALO_PIR = 5000;    // 5s mínimo entre alertas PIR
const unsigned long INTERVALO_PUERTA = 1000;  // 1s entre lecturas del estado de la puerta

// ═══════════════════════════════════════════════════════════════
//  VARIABLES DE ESTADO
// ═══════════════════════════════════════════════════════════════
int last_IR1 = HIGH;
int last_IR2 = HIGH;
unsigned long time_IR1_triggered = 0;
unsigned long time_IR2_triggered = 0;
unsigned long last_cruce_time = 0;
int personas_dentro = 0; 

bool last_pir_state = LOW;
unsigned long last_pir_post = 0;
unsigned long pir_trigger_time = 0;
bool pir_alert_active = false;

int ultimo_estado_puerta = -1; 
unsigned long ultimo_tiempo_puerta = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n═══════════════════════════════════════");
  Serial.println("  ESP32 — WIFI & FIREBASE (Monitoreo)");
  Serial.println("═══════════════════════════════════════\n");

  // Configurar pines
  pinMode(PIN_IR1, INPUT);
  pinMode(PIN_IR2, INPUT);
  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_MAGNETICO, INPUT_PULLUP);

  // Inicializar RFID
  SPI.begin();
  rfid.PCD_Init();
  Serial.println("[SISTEMA] RFID Inicializado.");

  // Conectar a Wi-Fi
  conectarWiFi();
}

void loop() {
  // Mantener la conexión WiFi activa
  if (WiFi.status() != WL_CONNECTED) {
    conectarWiFi();
  }

  procesarFlujo();
  procesarPIR();
  procesarRFID();
  procesarPuerta();

  // Limpiar alerta PIR después de 6 segundos de inactividad
  if (pir_alert_active && (millis() - pir_trigger_time > 6000)) {
    Serial.println("[PIR] Limpiando alerta por inactividad...");
    if (patchFirebase("{\"alerta_pir\": false}")) {
      pir_alert_active = false;
    }
  }

  delay(50);
}

// ═══════════════════════════════════════════════════════════════
//  CONEXIÓN WIFI
// ═══════════════════════════════════════════════════════════════
void conectarWiFi() {
  Serial.print("[WIFI] Conectando a ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int reintentos = 0;
  while (WiFi.status() != WL_CONNECTED && reintentos < 20) {
    delay(500);
    Serial.print(".");
    reintentos++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n[WIFI] [OK] Conectado exitosamente.");
    Serial.print("[WIFI] Dirección IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n[WIFI] [ERROR] No se pudo conectar a la red WiFi.");
  }
}

// ═══════════════════════════════════════════════════════════════
//  ENVÍO DE DATOS A FIREBASE (PATCH REST API)
// ═══════════════════════════════════════════════════════════════
bool patchFirebase(String jsonPayload) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[FIREBASE] [ERROR] Sin conexión WiFi.");
    return false;
  }

  WiFiClientSecure client;
  client.setInsecure(); // Omitir validación de certificado SSL para simplicidad
  
  HTTPClient http;
  http.begin(client, FIREBASE_HOST);
  http.addHeader("Content-Type", "application/json");

  Serial.print("[FIREBASE] Enviando PATCH: ");
  Serial.println(jsonPayload);

  int httpCode = http.PATCH(jsonPayload);

  if (httpCode > 0) {
    Serial.print("[FIREBASE] Respuesta HTTP: ");
    Serial.println(httpCode);
    if (httpCode == HTTP_CODE_OK) {
      http.end();
      return true;
    }
  } else {
    Serial.print("[FIREBASE] Fallo en la solicitud. Error: ");
    Serial.println(http.errorToString(httpCode).c_str());
  }
  
  http.end();
  return false;
}

// ═══════════════════════════════════════════════════════════════
//  LÓGICA SENSOR MAGNÉTICO — Estado de la Puerta
// ═══════════════════════════════════════════════════════════════
void procesarPuerta() {
  unsigned long tiempoActual = millis();
  if (tiempoActual - ultimo_tiempo_puerta < INTERVALO_PUERTA) return;

  int estadoActualPuerta = digitalRead(PIN_MAGNETICO);

  if (estadoActualPuerta != ultimo_estado_puerta) {
    String payload = "";
    if (estadoActualPuerta == LOW) {
      Serial.println("[PUERTA] Estado: CERRADA");
      payload = "{\"estado_chapa\": \"CERRADA\"}";
    } else {
      Serial.println("[PUERTA] Estado: ABIERTA");
      payload = "{\"estado_chapa\": \"ABIERTA\"}";
    }
    
    patchFirebase(payload);
    ultimo_estado_puerta = estadoActualPuerta;
  }
  ultimo_tiempo_puerta = tiempoActual;
}

// ═══════════════════════════════════════════════════════════════
//  LÓGICA SENSOR RFID
// ═══════════════════════════════════════════════════════════════
void procesarRFID() {
  if (!rfid.PICC_IsNewCardPresent()) return;
  if (!rfid.PICC_ReadCardSerial()) return;

  String uidStr = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if(rfid.uid.uidByte[i] < 0x10) uidStr += "0";
    uidStr += String(rfid.uid.uidByte[i], HEX);
  }
  uidStr.toUpperCase();
  
  Serial.println("[RFID] Tarjeta Detectada -> UID: " + uidStr);
  
  // Registrar el UID de la tarjeta en Firebase
  patchFirebase("{\"ultimo_uid_rfid\": \"" + uidStr + "\"}");

  rfid.PICC_HaltA();
}

// ═══════════════════════════════════════════════════════════════
//  LÓGICA SENSOR IR — Conteo de personas
// ═══════════════════════════════════════════════════════════════
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
    Serial.println("[IR] Sensor 1 (IN) interrumpido");
  }
  if (current_IR2 == LOW && last_IR2 == HIGH) {
    time_IR2_triggered = currentTime;
    Serial.println("[IR] Sensor 2 (OUT) interrupted");
  }

  if (time_IR1_triggered > 0 && time_IR2_triggered > time_IR1_triggered) {
    if (time_IR2_triggered - time_IR1_triggered < TIMEOUT_FLUJO) {
      personas_dentro++;
      Serial.println("\n--> [INGRESO DETECTADO] -->");
      Serial.print("[CONTEO] Personas: ");
      Serial.println(personas_dentro);
      
      patchFirebase("{\"personas_dentro_actualmente\": " + String(personas_dentro) + "}");
      last_cruce_time = currentTime;
    }
    time_IR1_triggered = 0;
    time_IR2_triggered = 0;
  }
  else if (time_IR2_triggered > 0 && time_IR1_triggered > time_IR2_triggered) {
    if (time_IR1_triggered - time_IR2_triggered < TIMEOUT_FLUJO) {
      personas_dentro = max(0, personas_dentro - 1);
      Serial.println("\n<-- [SALIDA DETECTADA] <--");
      Serial.print("[CONTEO] Personas: ");
      Serial.println(personas_dentro);
      
      patchFirebase("{\"personas_dentro_actualmente\": " + String(personas_dentro) + "}");
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

// ═══════════════════════════════════════════════════════════════
//  LÓGICA SENSOR PIR — Detección de movimiento
// ═══════════════════════════════════════════════════════════════
void procesarPIR() {
  bool pir_state = digitalRead(PIN_PIR) == HIGH;
  unsigned long currentTime = millis();

  if (pir_state && !last_pir_state) {
    if (currentTime - last_pir_post > INTERVALO_PIR) {
      Serial.println("[PIR] Alerta: Movimiento detectado en el aula.");
      
      if (patchFirebase("{\"alerta_pir\": true}")) {
        pir_alert_active = true;
        pir_trigger_time = currentTime;
      }
      last_pir_post = currentTime;
    }
  }
  last_pir_state = pir_state;
}
