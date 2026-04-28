// =============================================================================
// max6675.h - Header für MAX6675 Thermoelement Sensor Bibliothek
// =============================================================================
// Diese Header-Datei deklariert die Klasse MAX6675 und ihre Methoden.
//
// Verwendung:
//   #include "max6675.h"
//   MAX6675 thermocouple(SCK_PIN, CS_PIN, SO_PIN);
//   float temp = thermocouple.readCelsius();
// =============================================================================

#ifndef MAX6675_H           // Include-Guard: Verhindert mehrfaches Einbinden
#define MAX6675_H

#include <Arduino.h>        // Arduino Kern-Funktionen (pinMode, digitalWrite, etc.)

// =============================================================================
// MAX6675 KLASSE
// =============================================================================
/**
 * Klasse zur Ansteuerung des MAX6675 Thermoelement-Sensors
 * 
 * Diese Klasse implementiert die SPI-ähnliche Kommunikation mit dem MAX6675
 * und bietet Methoden zum Auslesen der Temperatur.
 */
class MAX6675 {
  private:
    // =========================================================================
    // MEMBER-VARIABLEN (Pin-Nummern)
    // =========================================================================
    uint8_t cs_pin;         // Chip Select Pin (aktiv LOW)
    uint8_t sck_pin;        // Serial Clock Pin (Takt)
    uint8_t so_pin;         // Serial Out Pin (Daten vom Sensor)

  public:
    // =========================================================================
    // KONSTRUKTOR
    // =========================================================================
    /**
     * Konstruktor - initialisiert den Sensor mit den angegebenen Pins
     * 
     * @param cs   Chip Select Pin (verbinde mit D8/GPIO15)
     * @param sck  Serial Clock Pin (verbinde mit D7/GPIO13)
     * @param so   Serial Out Pin (verbinde mit D6/GPIO12)
     */
    MAX6675(uint8_t cs, uint8_t sck, uint8_t so);
    
    // =========================================================================
    // ÖFFENTLICHE METHODEN
    // =========================================================================
    
    /**
     * Liest die Temperatur in Grad Celsius
     * 
     * @return float Temperatur in °C, NAN bei Fehler (kein Thermoelement)
     */
    float readCelsius();
    
    /**
     * Liest die Temperatur in Grad Fahrenheit
     * 
     * @return float Temperatur in °F, NAN bei Fehler (kein Thermoelement)
     */
    float readFahrenheit();
    
    /**
     * Prüft ob das Thermoelement angeschlossen ist
     * 
     * @return true  wenn Thermoelement angeschlossen ist
     * @return false wenn kein Thermoelement erkannt wurde
     */
    bool isConnected();
};

#endif  // MAX6675_H