// max6675.cpp
#include "max6675.h"

MAX6675::MAX6675(uint8_t cs, uint8_t sck, uint8_t so) {
    cs_pin = cs;
    sck_pin = sck;
    so_pin = so;
    
    pinMode(cs_pin, OUTPUT);
    pinMode(sck_pin, OUTPUT);
    pinMode(so_pin, INPUT);
    
    digitalWrite(cs_pin, HIGH);
    digitalWrite(sck_pin, LOW);
}

float MAX6675::readCelsius() {
    digitalWrite(cs_pin, LOW);
    delayMicroseconds(10);
    
    uint16_t value = 0;
    for (int i = 0; i < 16; i++) {
        digitalWrite(sck_pin, LOW);
        delayMicroseconds(1);
        digitalWrite(sck_pin, HIGH);
        delayMicroseconds(1);
        value = (value << 1) | digitalRead(so_pin);
    }
    
    digitalWrite(cs_pin, HIGH);
    
    // Fehlerprüfung (Bit 2 = 1 bedeutet kein Thermoelement)
    if (value & 0x4) {
        return NAN;
    }
    
    return (value >> 3) * 0.25;
}

float MAX6675::readFahrenheit() {
    return readCelsius() * 9.0 / 5.0 + 32.0;
}

bool MAX6675::isConnected() {
    digitalWrite(cs_pin, LOW);
    delayMicroseconds(10);
    
    uint16_t value = 0;
    for (int i = 0; i < 16; i++) {
        digitalWrite(sck_pin, LOW);
        delayMicroseconds(1);
        digitalWrite(sck_pin, HIGH);
        delayMicroseconds(1);
        value = (value << 1) | digitalRead(so_pin);
    }
    
    digitalWrite(cs_pin, HIGH);
    
    return !(value & 0x4);
}