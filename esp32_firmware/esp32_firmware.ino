#include <HTTPClient.h>
#include <WiFi.h>

// ═══════════════════════════════════════════════════════════════
//  CONFIGURACIÓN DE RED — Conexión al Hotspot de la Raspberry Pi
// ═══════════════════════════════════════════════════════════════
const char *ssid = "ESP32_MQTT_AP";
const char *password = "taipt_iot_2026";
const char *serverUrl = "http://10.42.0.1:5000/api/sensores";

// ═══════════════════════════════════════════════════════════════
//  CONFIGURACIÓN DE PINES
// ═══════════════════════════════════════════════════════════════
const int PIN_IR1 = 34; // Sensor IR ENTRADA (lado izquierdo del marco)
const int PIN_IR2 = 35; // Sensor IR SALIDA  (lado derecho del marco)
const int PIN_PIR = 27; // Sensor PIR HC-SR501 (arriba del marco)
const int PIN_LDR = 32; // Sensor LDR (divisor de tensión con resistencia 10kΩ)

// ═══════════════════════════════════════════════════════════════
//  CONSTANTES DE TIMING
// ═══════════════════════════════════════════════════════════════
const unsigned long TIMEOUT_FLUJO = 1500; // 1.5s máx entre cruce de sensores IR
const unsigned long DEBOUNCE_CRUCE =
    2000; // 2s debounce después de un cruce válido
const unsigned long INTERVALO_PIR = 10000; // 10s mínimo entre alertas PIR
const unsigned long INTERVALO_LUZ = 30000; // 30s entre reportes de nivel de luz
const unsigned long INTERVALO_RECON =
    5000; // 5s entre intentos de reconexión WiFi

// ═══════════════════════════════════════════════════════════════
//  VARIABLES DE ESTADO
// ═══════════════════════════════════════════════════════════════

// Sensores IR (conteo de personas)
int last_IR1 = HIGH;
int last_IR2 = HIGH;
unsigned long time_IR1_triggered = 0;
unsigned long time_IR2_triggered = 0;
unsigned long last_cruce_time = 0;
int personas_dentro = 0; // Contador local

// Sensor PIR
bool last_pir_state = LOW;
unsigned long last_pir_post = 0;

// Sensor LDR (luz)
unsigned long last_luz_report = 0;
int umbral_luz_baja =
    1500; // Valor ADC por debajo del cual se considera "oscuro"
int umbral_luz_alta =
    3000; // Valor ADC por encima del cual se considera "muy iluminado"

// WiFi reconexión
unsigned long last_recon_attempt = 0;
bool wifi_conectado = false;

// ═══════════════════════════════════════════════════════════════
//  SETUP
// ═══════════════════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);
  Serial.println("\n═══════════════════════════════════════");
  Serial.println("  ESP32 — Aula Inteligente v2.0");
  Serial.println("═══════════════════════════════════════\n");

  // Configurar pines de entrada
  pinMode(PIN_IR1, INPUT);
  pinMode(PIN_IR2, INPUT);
  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_LDR, INPUT); // Entrada analógica

  // Conectar a WiFi
  conectarWiFi();
}

// ═══════════════════════════════════════════════════════════════
//  LOOP PRINCIPAL
// ═══════════════════════════════════════════════════════════════
void loop() {
  unsigned long now = millis();

  // Verificar conexión WiFi
  if (WiFi.status() != WL_CONNECTED) {
    wifi_conectado = false;
    if (now - last_recon_attempt > INTERVALO_RECON) {
      Serial.println("[WiFi] Reconectando...");
      WiFi.disconnect();
      WiFi.reconnect();
      last_recon_attempt = now;
    }
    delay(100);
    return;
  }

  if (!wifi_conectado) {
    wifi_conectado = true;
    Serial.println("[WiFi] Reconectado!");
    Serial.print("[WiFi] IP: ");
    Serial.println(WiFi.localIP());
  }

  // Procesar sensores
  procesarFlujo();
  procesarPIR();
  procesarLuz();

  delay(50); // Estabilidad
}

// ═══════════════════════════════════════════════════════════════
//  COMUNICACIÓN — Enviar datos al servidor Flask en la RPi
// ═══════════════════════════════════════════════════════════════
void enviarPost(String evento) { enviarPost(evento, ""); }

void enviarPost(String evento, String extra) {
  HTTPClient http;
  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(5000); // 5s timeout

  String payload = "{\"evento\":\"" + evento + "\"";
  if (extra.length() > 0) {
    payload += "," + extra;
  }
  payload += "}";

  Serial.println("[HTTP] POST " + payload);

  int httpResponseCode = http.POST(payload);

  if (httpResponseCode > 0) {
    Serial.print("[HTTP] Response: ");
    Serial.println(httpResponseCode);
  } else {
    Serial.print("[HTTP] Error: ");
    Serial.println(httpResponseCode);
  }
  http.end();
}

// ═══════════════════════════════════════════════════════════════
//  SENSOR IR — Conteo de personas (Entrada/Salida)
// ═══════════════════════════════════════════════════════════════

void procesarFlujo() {
  int current_IR1 = digitalRead(PIN_IR1);
  int current_IR2 = digitalRead(PIN_IR2);
  unsigned long currentTime = millis();

  // No procesar si estamos en período de debounce
  if (currentTime - last_cruce_time < DEBOUNCE_CRUCE) {
    last_IR1 = current_IR1;
    last_IR2 = current_IR2;
    return;
  }

  // Detectar flanco de bajada (obstáculo detectado: HIGH → LOW)
  if (current_IR1 == LOW && last_IR1 == HIGH) {
    time_IR1_triggered = currentTime;
    Serial.println("[IR] IR1 activado (lado izquierdo)");
  }
  if (current_IR2 == LOW && last_IR2 == HIGH) {
    time_IR2_triggered = currentTime;
    Serial.println("[IR] IR2 activado (lado derecho)");
  }

  // ── INGRESO: IR1 primero → IR2 después ──
  if (time_IR1_triggered > 0 && time_IR2_triggered > time_IR1_triggered) {
    if (time_IR2_triggered - time_IR1_triggered < TIMEOUT_FLUJO) {
      personas_dentro++;
      Serial.print("[FLUJO] INGRESO detectado. Personas: ");
      Serial.println(personas_dentro);
      enviarPost("ingreso");
      last_cruce_time = currentTime;
    }
    time_IR1_triggered = 0;
    time_IR2_triggered = 0;
  }
  // ── SALIDA: IR2 primero → IR1 después ──
  else if (time_IR2_triggered > 0 && time_IR1_triggered > time_IR2_triggered) {
    if (time_IR1_triggered - time_IR2_triggered < TIMEOUT_FLUJO) {
      personas_dentro = max(0, personas_dentro - 1);
      Serial.print("[FLUJO] SALIDA detectada. Personas: ");
      Serial.println(personas_dentro);
      enviarPost("salida");
      last_cruce_time = currentTime;
    }
    time_IR1_triggered = 0;
    time_IR2_triggered = 0;
  }

  // Limpiar si expira el timeout
  if (time_IR1_triggered > 0 &&
      (currentTime - time_IR1_triggered > TIMEOUT_FLUJO)) {
    time_IR1_triggered = 0;
  }
  if (time_IR2_triggered > 0 &&
      (currentTime - time_IR2_triggered > TIMEOUT_FLUJO)) {
    time_IR2_triggered = 0;
  }

  last_IR1 = current_IR1;
  last_IR2 = current_IR2;
}

// ═══════════════════════════════════════════════════════════════
//  SENSOR PIR — Detección de movimiento
// ═══════════════════════════════════════════════════════════════

void procesarPIR() {
  bool pir_state = digitalRead(PIN_PIR) == HIGH;
  unsigned long currentTime = millis();

  if (pir_state && !last_pir_state) {
    if (currentTime - last_pir_post > INTERVALO_PIR) {
      Serial.println("[PIR] 🚨 Movimiento detectado!");
      enviarPost("movimiento_detectado");
      last_pir_post = currentTime;
    }
  }
  last_pir_state = pir_state;
}

// ═══════════════════════════════════════════════════════════════
//  SENSOR LDR — Monitoreo de luz ambiente
// ═══════════════════════════════════════════════════════════════

void procesarLuz() {
  unsigned long currentTime = millis();

  if (currentTime - last_luz_report < INTERVALO_LUZ) {
    return; // No es tiempo de reportar aún
  }

  int valor_ldr = analogRead(PIN_LDR);

  // Clasificar el nivel de luz
  String nivel;
  if (valor_ldr < 500) {
    nivel = "OSCURO";
  } else if (valor_ldr < 1500) {
    nivel = "Poca luz";
  } else if (valor_ldr < 3000) {
    nivel = "Normal";
  } else {
    nivel = "Brillante";
  }

  Serial.print("[LDR] Valor: ");
  Serial.print(valor_ldr);
  Serial.print(" — Nivel: ");
  Serial.println(nivel);

  // Enviar al servidor
  enviarPost("nivel_luz", "\"valor_ldr\":" + String(valor_ldr) +
                              ",\"nivel_luz\":\"" + nivel + "\"");

  last_luz_report = currentTime;
}

// ═══════════════════════════════════════════════════════════════
//  WiFi — Conexión al Hotspot de la Raspberry Pi
// ═══════════════════════════════════════════════════════════════
void conectarWiFi() {
  Serial.print("[WiFi] Conectando a ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int intentos = 0;
  while (WiFi.status() != WL_CONNECTED && intentos < 30) {
    delay(500);
    Serial.print(".");
    intentos++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    wifi_conectado = true;
    Serial.println("\n[WiFi] Conectado!");
    Serial.print("[WiFi] IP del ESP32: ");
    Serial.println(WiFi.localIP());
    Serial.print("[WiFi] Gateway (RPi): ");
    Serial.println(WiFi.gatewayIP());
    Serial.print("[WiFi] Servidor: ");
    Serial.println(serverUrl);
  } else {
    wifi_conectado = false;
    Serial.println("\n[WiFi] No se pudo conectar. Reintentará en el loop.");
  }
}