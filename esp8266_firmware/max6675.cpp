// =============================================================================
// MAX6675.cpp - Bibliothek für MAX6675 Thermoelement Sensor
// =============================================================================
// Dieser Code implementiert die Treiber-Funktionen für den MAX6675 Chip,
// der ein K-Type Thermoelement ausliest.
//
// Hardware: MAX6675 Modul mit K-Type Thermoelement
// Pins:     CS (Chip Select), SCK (Clock), SO (Serial Out)
//
// Funktionen:
// - readCelsius()   : Temperatur in Celsius lesen
// - readFahrenheit(): Temperatur in Fahrenheit lesen
// - isConnected()   : Prüft ob Thermoelement angeschlossen ist
//
// Autor:  Nouri Deg. 
// IoT Temperature Monitoring System
// Datum:   24.04.2026 
// Version: 1.0
// =============================================================================

#include "max6675.h"          // Einbinden der Header-Datei

// =============================================================================
// KONSTRUKTOR
// =============================================================================
/**
 * Initialisiert den MAX6675 Sensor mit den angegebenen Pins
 * 
 * @param cs  Chip Select Pin (aktiv LOW) - Wählt den Chip aus
 * @param sck Serial Clock Pin - Takt für die Datenübertragung
 * @param so  Serial Out Pin - Datenleitung vom Sensor zum ESP8266
 * 
 * Der Konstruktor speichert die Pin-Nummern und konfiguriert die Pins:
 * - CS und SCK als Ausgänge (ESP8266 steuert sie)
 * - SO als Eingang (ESP8266 liest Daten vom Sensor)
 * - Initialisiert CS auf HIGH (Chip nicht ausgewählt)
 * - Initialisiert SCK auf LOW (Clock im Ruhezustand)
 */
MAX6675::MAX6675(uint8_t cs, uint8_t sck, uint8_t so) {
    // Pin-Nummern in Member-Variablen speichern
    cs_pin = cs;
    sck_pin = sck;
    so_pin = so;
    
    // Pins konfigurieren
    pinMode(cs_pin, OUTPUT);      // CS = Chip Select (Ausgang)
    pinMode(sck_pin, OUTPUT);     // SCK = Serial Clock (Ausgang)
    pinMode(so_pin, INPUT);       // SO = Serial Out (Eingang)
    
    // Initialzustand der Ausgänge setzen
    digitalWrite(cs_pin, HIGH);   // CS HIGH = Chip deaktiviert
    digitalWrite(sck_pin, LOW);   // SCK LOW = Clock im Ruhezustand
}

// =============================================================================
// TEMPERATUR IN CELSIUS LESEN (KERN-FUNKTION)
// =============================================================================
/**
 * Liest die aktuelle Temperatur vom MAX6675 Sensor in Grad Celsius
 * 
 * Der MAX6675 sendet 16 Datenbits:
 * - Bit 15-3: Temperaturwert (12 Bit, 0.25°C Auflösung)
 * - Bit 2:    Fehlerflag (1 = Thermoelement nicht angeschlossen/nicht verbunden)
 * - Bit 1-0:  Nicht genutzt (immer 0)
 * 
 * Datenübertragungs-Protokoll (SPI ähnlich):
 * 1. CS auf LOW setzen (aktiviert den Chip)
 * 2. 16 Taktimpulse senden (SCK toggeln)
 * 3. Während der Taktimpulse wird jedes Bit von SO gelesen
 * 4. CS auf HIGH setzen (deaktiviert den Chip)
 * 
 * @return float Temperatur in Celsius, NAN bei Fehler (kein Thermoelement)
 */
float MAX6675::readCelsius() {
    // =========================================================================
    // 1. SENSOR AKTIVIEREN (CS = LOW)
    // =========================================================================
    digitalWrite(cs_pin, LOW);          // Chip Select aktivieren
    delayMicroseconds(10);              // Kurze Wartezeit für Sensor-Stabilisierung
    
    // =========================================================================
    // 2. 16 BITS VOM SENSOR LESEN
    // =========================================================================
    uint16_t value = 0;                 // 16-Bit Variable für die Sensor-Daten
    
    // Für jeden der 16 Bits...
    for (int i = 0; i < 16; i++) {
        // Taktimpuls erzeugen: LOW -> HIGH
        digitalWrite(sck_pin, LOW);     // Clock auf LOW
        delayMicroseconds(1);           // Kurze Pause für Signal-Stabilisierung
        
        digitalWrite(sck_pin, HIGH);    // Clock auf HIGH (steigende Flanke)
        delayMicroseconds(1);           // Kurze Pause für Signal-Stabilisierung
        
        // Datenbit lesen und in 'value' speichern
        // (value << 1) = Bits nach links schieben (Platz für neues Bit)
        // | digitalRead(so_pin) = Neues Bit an das Ende anhängen
        value = (value << 1) | digitalRead(so_pin);
    }
    
    // =========================================================================
    // 3. SENSOR DEAKTIVIEREN (CS = HIGH)
    // =========================================================================
    digitalWrite(cs_pin, HIGH);         // Chip Select deaktivieren
    
    // =========================================================================
    // 4. FEHLERPRÜFUNG
    // =========================================================================
    // Bit 2 (Wert 0x4) zeigt an, ob das Thermoelement angeschlossen ist
    // Wenn Bit 2 = 1 -> Kein Thermoelement erkannt
    if (value & 0x4) {
        return NAN;                     // "Not a Number" = Fehler signalisieren
    }
    
    // =========================================================================
    // 5. TEMPERATUR BZW. WERT BEREICHNEN
    // =========================================================================
    // Der Temperaturwert steht in Bits 15-3 (12 Bit)
    // >> 3 = Bits um 3 Stellen nach rechts schieben (Bit 2-0 entfernen)
    // * 0.25 = Jeder Schritt entspricht 0.25°C Auflösung
    // Beispiel: Wert 1000 -> 1000 * 0.25 = 250.0°C
    return (value >> 3) * 0.25;
}

// =============================================================================
// TEMPERATUR IN FAHRENHEIT LESEN
// =============================================================================
/**
 * Liest die aktuelle Temperatur in Grad Fahrenheit
 * 
 * Umrechnungsformel: °F = (°C * 9/5) + 32
 * 
 * @return float Temperatur in Fahrenheit, NAN bei Fehler
 */
float MAX6675::readFahrenheit() {
    // Celsius lesen und in Fahrenheit umrechnen
    // 9.0 / 5.0 = 1.8 (Umrechnungsfaktor)
    // + 32.0 = Offset für Fahrenheit-Skala
    return readCelsius() * 9.0 / 5.0 + 32.0;
}

// =============================================================================
// VERBINDUNGSSTATUS PRÜFEN
// =============================================================================
/**
 * Prüft ob das Thermoelement korrekt angeschlossen ist
 * 
 * Diese Funktion führt eine Lesung durch und prüft das Fehler-Bit.
 * Im Gegensatz zu readCelsius() wird hier NUR geprüft, ob das
 * Thermoelement angeschlossen ist - die Temperatur wird ignoriert.
 * 
 * @return true  = Thermoelement ist angeschlossen
 * @return false = Thermoelement ist nicht angeschlossen oder defekt
 */
bool MAX6675::isConnected() {
    // =========================================================================
    // 1. SENSOR AKTIVIEREN
    // =========================================================================
    digitalWrite(cs_pin, LOW);          // Chip Select aktivieren
    delayMicroseconds(10);              // Kurze Wartezeit
    
    // =========================================================================
    // 2. 16 BITS VOM SENSOR LESEN (gleicher Vorgang wie bei readCelsius)
    // =========================================================================
    uint16_t value = 0;                 // 16-Bit Variable für die Sensor-Daten
    
    for (int i = 0; i < 16; i++) {
        digitalWrite(sck_pin, LOW);     // Clock LOW
        delayMicroseconds(1);
        digitalWrite(sck_pin, HIGH);    // Clock HIGH
        delayMicroseconds(1);
        value = (value << 1) | digitalRead(so_pin);
    }
    
    // =========================================================================
    // 3. SENSOR DEAKTIVIEREN
    // =========================================================================
    digitalWrite(cs_pin, HIGH);         // Chip Select deaktivieren
    
    // =========================================================================
    // 4. VERBINDUNG PRÜFEN
    // =========================================================================
    // Wenn Bit 2 = 1 -> kein Thermoelement angeschlossen
    //  !(value & 0x4) invertiert die Aussage:
    // - Bei Fehler (Bit 2 = 1) -> !(1) = false
    // - Bei OK (Bit 2 = 0)    -> !(0) = true
    return !(value & 0x4);
}