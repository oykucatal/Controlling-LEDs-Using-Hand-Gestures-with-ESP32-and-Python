// ==== ESP32 LED Web Server (5 LED) ====
// Pins: 27=thumb, 26=index, 25=middle, 33=ring, 32=pinky
#include <WiFi.h>
#include <ESPAsyncWebServer.h>

const char* ssid     = "Oyku";          // <-- 2.4 GHz SSID
const char* password = "1234567890";   // <-- şifre

// false -> PIN LOW  = LED ON  (sinking: LED anodu 3.3V'a, katodu GPIO'ya)
// true  -> PIN HIGH = LED ON  (sourcing: GPIO -> direnç -> LED anodu, katot GND)
const bool LED_ACTIVE_HIGH = false;   // devrene göre gerekirse true yap

const int PIN_THUMB  = 27;
const int PIN_INDEX  = 26;
const int PIN_MIDDLE = 25;
const int PIN_RING   = 33;
const int PIN_PINKY  = 32;

AsyncWebServer server(80);

inline void ledOn (int pin){ digitalWrite(pin, LED_ACTIVE_HIGH ? HIGH : LOW ); }
inline void ledOff(int pin){ digitalWrite(pin, LED_ACTIVE_HIGH ? LOW  : HIGH); }

void ledInit() {
  pinMode(PIN_THUMB,  OUTPUT);
  pinMode(PIN_INDEX,  OUTPUT);
  pinMode(PIN_MIDDLE, OUTPUT);
  pinMode(PIN_RING,   OUTPUT);
  pinMode(PIN_PINKY,  OUTPUT);
  // başlangıç: kapalı
  ledOff(PIN_THUMB); ledOff(PIN_INDEX); ledOff(PIN_MIDDLE); ledOff(PIN_RING); ledOff(PIN_PINKY);
}

void addLedRoute(const char* name, int pin) {
  String n(name), base = "/led/" + n;
  server.on((base + "/on").c_str(),  HTTP_GET, [pin, n](AsyncWebServerRequest* r){ ledOn(pin);  r->send(200,"text/plain", n + " ON");  });
  server.on((base + "/off").c_str(), HTTP_GET, [pin, n](AsyncWebServerRequest* r){ ledOff(pin); r->send(200,"text/plain", n + " OFF"); });
}

void setup() {
  Serial.begin(115200);
  delay(150);
  ledInit();

  WiFi.mode(WIFI_STA);
  WiFi.persistent(false);
  WiFi.setSleep(false);

  Serial.printf("Connecting to WiFi: %s\n", ssid);
  WiFi.begin(ssid, password);
  unsigned long t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 60000) { delay(500); Serial.print("."); }
  if (WiFi.status() != WL_CONNECTED) { Serial.println("\nFailed to connect to WiFi"); return; }

  Serial.println("\nConnected to WiFi");
  Serial.print("IP Address: "); Serial.println(WiFi.localIP());

  server.on("/command", HTTP_GET, [](AsyncWebServerRequest* r){ r->send(200,"text/plain","OK"); });

  addLedRoute("thumb",  PIN_THUMB);
  addLedRoute("index",  PIN_INDEX);
  addLedRoute("middle", PIN_MIDDLE);
  addLedRoute("ring",   PIN_RING);
  addLedRoute("pinky",  PIN_PINKY);

  // Basit web arayüzü (isteğe bağlı)
  server.on("/", HTTP_GET, [](AsyncWebServerRequest* r){
    String h = "<h2>ESP32 LED Control</h2>";
    auto btn=[&](const char* nm){
      h += String("<p>") + nm +
           " <button onclick=\"fetch('/led/"+String(nm)+"/on')\">ON</button> " +
           "<button onclick=\"fetch('/led/"+String(nm)+"/off')\">OFF</button></p>";
    };
    btn("thumb"); btn("index"); btn("middle"); btn("ring"); btn("pinky");
    r->send(200,"text/html",h);
  });

  server.begin();
  Serial.println("Server started");
}

void loop() {}
