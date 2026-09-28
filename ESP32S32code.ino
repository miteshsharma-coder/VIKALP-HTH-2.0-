#include <DHT.h>

#define SOIL_PIN 5
#define DHT_PIN 6
#define DHT_TYPE DHT11

// Soil calibration values
#define SOIL_DRY 4101
#define SOIL_WET 1100

DHT dht(DHT_PIN, DHT_TYPE);

void setup() {
  Serial.begin(115200);
  delay(1000);

  dht.begin();

  Serial.println();
  Serial.println("======================================");
  Serial.println("       VIKALP ENVIRONMENT MONITOR");
  Serial.println("       ESP32-S3");
  Serial.println("======================================");
}

void loop() {

  // Read soil moisture
  int soilADC = analogRead(SOIL_PIN);

  // Convert ADC to percentage
  int moisturePercent = map(
    soilADC,
    SOIL_DRY,
    SOIL_WET,
    0,
    100
  );

  moisturePercent = constrain(moisturePercent, 0, 100);

  // Read DHT11
  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();

  Serial.println();
  Serial.println("----------- SENSOR DATA --------------");

  Serial.print("Soil ADC         : ");
  Serial.println(soilADC);

  Serial.print("Soil Moisture    : ");
  Serial.print(moisturePercent);
  Serial.println(" %");

  // Soil status
  if (moisturePercent <= 30) {
    Serial.println("Soil Status      : DRY");
  }
  else if (moisturePercent <= 70) {
    Serial.println("Soil Status      : MOIST");
  }
  else {
    Serial.println("Soil Status      : WET");
  }

  // DHT11
  if (isnan(temperature) || isnan(humidity)) {

    Serial.println("Temperature      : ERROR");
    Serial.println("Humidity         : ERROR");

  } else {

    Serial.print("Temperature      : ");
    Serial.print(temperature);
    Serial.println(" °C");

    Serial.print("Humidity         : ");
    Serial.print(humidity);
    Serial.println(" %");
  }

  Serial.println("--------------------------------------");

  delay(2000);
}