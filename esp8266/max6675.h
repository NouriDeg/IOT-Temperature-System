// max6675.h
#ifndef MAX6675_H
#define MAX6675_H

#include <Arduino.h>

class MAX6675 {
private:
    uint8_t cs_pin;
    uint8_t sck_pin;
    uint8_t so_pin;
    
public:
    MAX6675(uint8_t cs, uint8_t sck, uint8_t so);
    float readCelsius();
    float readFahrenheit();
    bool isConnected();
};

#endif