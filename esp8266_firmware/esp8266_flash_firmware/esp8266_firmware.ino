#include <ESP8266WiFi.h>         // WLAN-Funktionen für ESP8266
#include <WiFiClientSecure.h>    // TLS/SSL für sichere MQTT Verbindung
//#include <PubSubClient.h>        // MQTT Client für Nachrichtenaustausch
// #include <ArduinoJson.h>         // JSON Parsing für MQTT Nachrichten
// #include <max6675.h>             // MAX6675 Thermoelement Sensor Bibliothek
#include <EEPROM.h>              // Persistente Speicherung (Credentials bleiben erhalten)
#include <ArduinoOTA.h>          // Over-the-Air Updates via WLAN
#include <Adafruit_SleepyDog.h>  // Watchdog Timer (verhindert System-Freezes)
#define EEPROM_SIZE         4096        // EEPROM-Größe: 4 KB
#define PROVISIONED_FLAG_ADDR 0         // Adresse für Provisionierungs-Flag (1 Byte)
#define MQTT_BROKER_ADDR    50          // Startadresse für Broker-IP (max. 50 Bytes)
#define MQTT_PORT_ADDR      120         // Adresse für Broker-Port (2 Bytes)
#define MQTT_USER_ADDR      124         // Startadresse für Benutzername (max. 32 Bytes)
#define MQTT_PASS_ADDR      160     
void setup() {
  Serial.begin(115200);
  delay(1000);

  // ============================================
  // 🔥 EEPROM ZURÜCKSETZEN (NUR EINMAL!)
  // ============================================
  EEPROM.begin(EEPROM_SIZE);
  EEPROM.write(PROVISIONED_FLAG_ADDR, 0);  // Provisionierungs-Flag löschen
  EEPROM.commit();
  EEPROM.end();
  Serial.println("✅ EEPROM zurückgesetzt! Neustart...");
  delay(3000);
  ESP.restart();
  // ============================================

  // ... Rest vom setup
}
// ============================================================================
// LOOP
// ============================================================================
void loop() {
  

  static unsigned long lastSensor = 0;
  if (millis() - lastSensor > 5000) {
    lastSensor = millis();
   
  }

  delay(10);
}
