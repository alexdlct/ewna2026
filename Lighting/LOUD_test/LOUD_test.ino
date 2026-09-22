#include <Arduino_LED_Matrix.h>

Arduino_LED_Matrix matrix;

uint8_t allOn[104];

void setup() {

  matrix.begin();
  matrix.setGrayscaleBits(1);

  
  for (int i = 0; i < 104; i++) {
    allOn[i] = 1;
  }

  
  matrix.draw(allOn);

  
  delay(1000);

  
  matrix.clear();
}

void loop() {
  // 아무것도 하지 않음
}