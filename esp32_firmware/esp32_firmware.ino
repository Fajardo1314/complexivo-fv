#include <WiFi.h>
#include <HTTPClient.h>

// --- CONFIGURACIÓN DE RED ---
const char* ssid = "ESP32_MQTT_AP";
const char* password = "taipt_iot_2026";
const char* serverUrl = "http://10.42.0.1:5000/api/sensores";

// --- CONFIGURACIÓN DE PINES ---
const int PIN_IR1 = 34; // Sensor de Entrada
const int PIN_IR2 = 35; // Sensor de Salida
const int PIN_PIR = 27; // Sensor de Movimiento

// --- VARIABLES DE ESTADO ---
int last_IR1 = HIGH; // Asumimos HIGH = Sin obstáculo (depende del módulo)
int last_IR2 = HIGH;
unsigned long time_IR1_triggered = 0;
unsigned long time_IR2_triggered = 0;
const unsigned long TIMEOUT_FLUJO = 1500; // 1.5 seg máximo entre cruzar ambos sensores

bool last_pir_state = LOW;
unsigned long last_pir_post = 0;

void setup() {
  Serial.begin(115200);
  
  // Configurar Pines
  pinMode(PIN_IR1, INPUT);
  pinMode(PIN_IR2, INPUT);
  pinMode(PIN_PIR, INPUT);

  // Conectar a Wi-Fi
  Serial.println();
  Serial.print("Conectando a ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("");
  Serial.println("Wi-Fi conectado.");
  Serial.print("Dirección IP: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  if(WiFi.status() == WL_CONNECTED) {
    procesarFlujo();
    procesarPIR();
  } else {
    // Intentar reconectar si se pierde
    WiFi.disconnect();
    WiFi.reconnect();
    delay(1000);
  }
  delay(50); // Pequeño retraso para estabilidad
}

void enviarPost(String evento) {
  HTTPClient http;
  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/json");
  
  String payload = "{\"evento\":\"" + evento + "\"}";
  int httpResponseCode = http.POST(payload);
  
  if (httpResponseCode > 0) {
    Serial.print("HTTP Response code: ");
    Serial.println(httpResponseCode);
  } else {
    Serial.print("Error code: ");
    Serial.println(httpResponseCode);
  }
  http.end();
}

void procesarFlujo() {
  int current_IR1 = digitalRead(PIN_IR1);
  int current_IR2 = digitalRead(PIN_IR2);
  unsigned long currentTime = millis();

  // Detectar flanco de bajada (obstáculo detectado)
  if (current_IR1 == LOW && last_IR1 == HIGH) {
    time_IR1_triggered = currentTime;
    Serial.println("IR1 Activado");
  }
  if (current_IR2 == LOW && last_IR2 == HIGH) {
    time_IR2_triggered = currentTime;
    Serial.println("IR2 Activado");
  }

  // Evaluar secuencia de Entrada: IR1 primero, luego IR2
  if (time_IR1_triggered > 0 && time_IR2_triggered > time_IR1_triggered) {
    if (time_IR2_triggered - time_IR1_triggered < TIMEOUT_FLUJO) {
      Serial.println("=> Ingreso detectado");
      enviarPost("ingreso");
      delay(1000); // Debounce fuerte tras un cruce
    }
    time_IR1_triggered = 0;
    time_IR2_triggered = 0;
  }
  
  // Evaluar secuencia de Salida: IR2 primero, luego IR1
  else if (time_IR2_triggered > 0 && time_IR1_triggered > time_IR2_triggered) {
    if (time_IR1_triggered - time_IR2_triggered < TIMEOUT_FLUJO) {
      Serial.println("=> Salida detectada");
      enviarPost("salida");
      delay(1000); // Debounce fuerte tras un cruce
    }
    time_IR1_triggered = 0;
    time_IR2_triggered = 0;
  }

  // Limpiar si expira el timeout
  if (time_IR1_triggered > 0 && (currentTime - time_IR1_triggered > TIMEOUT_FLUJO)) {
    time_IR1_triggered = 0;
  }
  if (time_IR2_triggered > 0 && (currentTime - time_IR2_triggered > TIMEOUT_FLUJO)) {
    time_IR2_triggered = 0;
  }

  last_IR1 = current_IR1;
  last_IR2 = current_IR2;
}

void procesarPIR() {
  bool pir_state = digitalRead(PIN_PIR) == HIGH;
  unsigned long currentTime = millis();

  // Enviar alerta si detecta movimiento y han pasado más de 10 seg desde el último post
  if (pir_state && !last_pir_state) {
    if (currentTime - last_pir_post > 10000) {
      Serial.println("Movimiento detectado!");
      enviarPost("movimiento_detectado");
      last_pir_post = currentTime;
    }
  }
  last_pir_state = pir_state;
}
