#include <Arduino_LED_Matrix.h>

Arduino_LED_Matrix matrix;

const int ROWS = 8;
const int COLS = 13;

uint8_t frame[104];

/*
left arrow
right arrow
voice
water
danger sign
lightning
shatter
skull
CO 
SOS
*/

/*
animateLeft
animateRight
animateVoice
animateWater
animateDanger
animateLightning
animateShatter
animateSkull
animateCO
animateSOS

*/


// ============================================================
// LEFT ARROW
// ============================================================

uint8_t arrow_left[104] = {
  0,0,0,1,1,0,0,0,0,0,0,0,0,
  0,0,1,1,0,0,0,0,0,0,0,0,0,
  0,1,1,0,0,0,0,0,0,0,0,0,0,
  1,1,1,1,1,1,1,1,1,1,1,1,1,
  1,1,1,1,1,1,1,1,1,1,1,1,1,
  0,1,1,0,0,0,0,0,0,0,0,0,0,
  0,0,1,1,0,0,0,0,0,0,0,0,0,
  0,0,0,1,1,0,0,0,0,0,0,0,0
};


// ============================================================
// RIGHT ARROW
// ============================================================

uint8_t arrow_right[104] = {
  0,0,0,0,0,0,0,0,1,1,0,0,0,
  0,0,0,0,0,0,0,0,0,1,1,0,0,
  0,0,0,0,0,0,0,0,0,0,1,1,0,
  1,1,1,1,1,1,1,1,1,1,1,1,1,
  1,1,1,1,1,1,1,1,1,1,1,1,1,
  0,0,0,0,0,0,0,0,0,0,1,1,0,
  0,0,0,0,0,0,0,0,0,1,1,0,0,
  0,0,0,0,0,0,0,0,1,1,0,0,0
};


// ============================================================
// HUMAN VOICE
// ============================================================

uint8_t voice1[104] = {
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,1,0,1,0,1,0,0,0,0,
  0,0,1,0,1,0,1,0,1,0,1,0,0,
  0,0,1,0,1,0,1,0,1,0,1,0,0,
  0,0,0,0,1,0,1,0,1,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0
};

uint8_t voice2[104] = {
  0,0,0,0,1,0,1,0,1,0,0,0,0,
  0,0,1,0,1,0,1,0,1,0,1,0,0,
  1,0,1,0,1,0,1,0,1,0,1,0,1,
  1,0,1,0,1,0,1,0,1,0,1,0,1,
  1,0,1,0,1,0,1,0,1,0,1,0,1,
  1,0,1,0,1,0,1,0,1,0,1,0,1,
  0,0,1,0,1,0,1,0,1,0,1,0,0,
  0,0,0,0,1,0,1,0,1,0,0,0,0
};


// ============================================================
// WATER
// ============================================================

uint8_t water1[104] = {
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,1,1,1,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0
};

uint8_t water2[104] = {
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,1,1,1,0,0,0,0,0,
  0,0,0,0,0,1,1,1,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0
};

uint8_t water3[104] = {
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,1,1,1,0,0,0,0,0,
  0,0,0,0,1,1,1,1,1,0,0,0,0,
  0,0,0,0,1,1,1,1,1,0,0,0,0,
  0,0,0,0,0,1,1,1,0,0,0,0,0
};


// ============================================================
// DANGER SIGN
// ============================================================

uint8_t danger_sign[104] = {
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,1,0,1,0,0,0,0,0,
  0,0,0,0,1,0,1,0,1,0,0,0,0,
  0,0,0,1,0,0,1,0,0,1,0,0,0,
  0,0,1,0,0,0,1,0,0,0,1,0,0,
  0,1,0,0,0,0,0,0,0,0,0,1,0,
  1,0,0,0,0,0,1,0,0,0,0,0,1,
  1,1,1,1,1,1,1,1,1,1,1,1,1
};


// ============================================================
// LIGHTNING
// ============================================================

uint8_t lightning_symbol[104] = {
  0,0,0,0,0,0,1,1,1,0,0,0,0,
  0,0,0,0,0,1,1,1,0,0,0,0,0,
  0,0,0,0,1,1,1,0,0,0,0,0,0,
  0,0,0,1,1,1,1,1,1,1,0,0,0,
  0,0,0,0,0,0,1,1,1,0,0,0,0,
  0,0,0,0,0,1,1,1,0,0,0,0,0,
  0,0,0,0,1,1,1,0,0,0,0,0,0,
  0,0,0,1,1,0,0,0,0,0,0,0,0
};


// ============================================================
// SHATTER
// ============================================================

uint8_t shatter1[104] = {
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,1,1,1,0,0,0,0,0,
  0,0,0,0,0,1,1,1,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0,
  0,0,0,0,0,0,0,0,0,0,0,0,0
};

uint8_t shatter2[104] = {
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,1,0,0,0,1,0,0,0,1,0,0,
  0,0,0,1,0,1,1,1,0,1,0,0,0,
  0,0,0,1,1,1,1,1,1,1,0,0,0,
  0,0,1,0,0,0,1,0,0,0,1,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0,
  0,0,0,0,0,0,1,0,0,0,0,0,0
};

uint8_t shatter3[104] = {
  1,0,0,0,0,0,1,0,0,0,0,0,1,
  0,1,0,0,0,0,1,0,0,0,0,1,0,
  0,0,1,0,0,0,1,0,0,0,1,0,0,
  0,0,0,1,0,1,1,1,0,1,0,0,0,
  1,1,1,1,1,1,1,1,1,1,1,1,1,
  0,0,0,1,0,1,1,1,0,1,0,0,0,
  0,0,1,0,0,0,1,0,0,0,1,0,0,
  0,1,0,0,0,0,1,0,0,0,0,1,0
};


// ============================================================
// SKULL
// ============================================================

uint8_t skull[104] = {
  0,0,0,1,1,1,1,1,1,1,0,0,0,
  0,0,1,1,1,1,1,1,1,1,1,0,0,
  0,1,1,1,0,0,1,0,0,1,1,1,0,
  0,1,1,1,0,0,1,0,0,1,1,1,0,
  0,1,1,1,1,1,1,1,1,1,1,1,0,
  0,0,1,1,0,1,0,1,0,1,1,0,0,
  0,0,0,1,1,1,1,1,1,1,0,0,0,
  0,0,0,1,0,1,0,1,0,1,0,0,0
};


// ============================================================
// CO
// ============================================================

uint8_t CO[104] = {
  0,1,1,1,0,0,0,1,1,1,1,0,0,
  1,0,0,0,0,0,1,0,0,0,0,1,0,
  1,0,0,0,0,0,1,0,0,0,0,1,0,
  1,0,0,0,0,0,1,0,0,0,0,1,0,
  1,0,0,0,0,0,1,0,0,0,0,1,0,
  1,0,0,0,0,0,1,0,0,0,0,1,0,
  1,0,0,0,0,0,1,0,0,0,0,1,0,
  0,1,1,1,0,0,0,1,1,1,1,0,0
};


// ============================================================
// SOS
// ============================================================

uint8_t SOS[104] = {
  0,1,1,0,0,1,1,1,0,0,1,1,0,
  1,0,0,0,1,0,0,0,1,1,0,0,0,
  1,0,0,0,1,0,0,0,1,1,0,0,0,
  0,1,0,0,1,0,0,0,1,0,1,0,0,
  0,0,1,0,1,0,0,0,1,0,0,1,0,
  0,0,1,0,1,0,0,0,1,0,0,1,0,
  0,0,1,0,1,0,0,0,1,0,0,1,0,
  1,1,0,0,0,1,1,1,0,1,1,0,0
};


// ============================================================
// ARROW DRAWING
// ============================================================

void drawLeftShifted(int offset) {

  for (int i = 0; i < 104; i++) {
    frame[i] = 0;
  }

  for (int row = 0; row < ROWS; row++) {

    for (int col = 0; col < COLS; col++) {

      int newCol = col - offset;

      if (newCol >= 0 && newCol < COLS) {

        frame[row * COLS + newCol] =
          arrow_left[row * COLS + col];
      }
    }
  }

  matrix.draw(frame);
}


void drawRightShifted(int offset) {

  for (int i = 0; i < 104; i++) {
    frame[i] = 0;
  }

  for (int row = 0; row < ROWS; row++) {

    for (int col = 0; col < COLS; col++) {

      int newCol = col + offset;

      if (newCol >= 0 && newCol < COLS) {

        frame[row * COLS + newCol] =
          arrow_right[row * COLS + col];
      }
    }
  }

  matrix.draw(frame);
}


// ============================================================
// ARROW ANIMATIONS
// ============================================================

void animateLeft() {

  for (int offset = 0; offset <= 13; offset++) {

    drawLeftShifted(offset);

    delay(70);
  }

  matrix.clear();
}


void animateRight() {

  for (int offset = 0; offset <= 13; offset++) {

    drawRightShifted(offset);

    delay(70);
  }

  matrix.clear();
}


// ============================================================
// OTHER ANIMATIONS
// ============================================================

void animateVoice() {

  for (int i = 0; i < 4; i++) {

    matrix.draw(voice1);
    delay(180);

    matrix.draw(voice2);
    delay(180);
  }

  matrix.clear();
}


void animateWater() {

  matrix.draw(water1);
  delay(180);

  matrix.draw(water2);
  delay(180);

  matrix.draw(water3);
  delay(350);

  matrix.clear();
}


void animateDanger() {

  for (int i = 0; i < 4; i++) {

    matrix.draw(danger_sign);
    delay(200);

    matrix.clear();
    delay(120);
  }
}

void animateLightning() {

  for (int i = 0; i < 4; i++) {

    matrix.draw(lightning_symbol);
    delay(70);

    matrix.clear();
    delay(60);
  }

  matrix.draw(lightning_symbol);
  delay(300);

  matrix.clear();
}


void animateShatter() {

  matrix.draw(shatter1);
  delay(130);

  matrix.draw(shatter2);
  delay(130);

  matrix.draw(shatter3);
  delay(500);

  matrix.clear();
}


void animateSkull() {

  for (int i = 0; i < 3; i++) {

    matrix.draw(skull);
    delay(300);

    matrix.clear();
    delay(120);
  }

  matrix.draw(skull);
  delay(500);

  matrix.clear();
}


void animateCO() {

  for (int i = 0; i < 4; i++) {

    matrix.draw(CO);
    delay(250);

    matrix.clear();
    delay(150);
  }
}


void animateSOS() {

  for (int i = 0; i < 6; i++) {

    matrix.draw(SOS);
    delay(180);

    matrix.clear();
    delay(120);
  }

  matrix.draw(SOS);
  delay(500);

  matrix.clear();
}


// ============================================================
// COMMAND HANDLER
// ============================================================

/*
command types:
left
right
voice
water
danger
lightning
shatter
skull
co
sos
clear
*/

void handleCommand(String command) {

  command.trim();
  command.toLowerCase();


  if (command == "left") {

    Serial.println("LEFT");
    animateLeft();

  }

  else if (command == "right") {

    Serial.println("RIGHT");
    animateRight();

  }

  else if (command == "voice") {

    Serial.println("VOICE");
    animateVoice();

  }

  else if (command == "water") {

    Serial.println("WATER");
    animateWater();

  }

  else if (command == "danger") {

    Serial.println("DANGER");
    animateDanger();

  }

  else if (command == "lightning") {

    Serial.println("LIGHTNING");
    animateLightning();

  }

  else if (command == "shatter") {

    Serial.println("SHATTER");
    animateShatter();

  }

  else if (command == "skull") {

    Serial.println("SKULL");
    animateSkull();

  }

  else if (command == "co") {

    Serial.println("CO");
    animateCO();

  }

  else if (command == "sos") {

    Serial.println("SOS");
    animateSOS();

  }

  else if (command == "clear") {

    Serial.println("CLEAR");
    matrix.clear();

  }

  else {

    Serial.print("Unknown command: ");
    Serial.println(command);

  }
}


// ============================================================
// SETUP
// ============================================================

void setup() {

  Serial.begin(115200);

  matrix.begin();
  matrix.setGrayscaleBits(1);
  matrix.clear();

  Serial.println();
  Serial.println("============================");
  Serial.println(" UNO Q LED MATRIX READY");
  Serial.println("============================");

  Serial.println("Commands:");
  Serial.println("left");
  Serial.println("right");
  Serial.println("voice");
  Serial.println("water");
  Serial.println("danger");
  Serial.println("lightning");
  Serial.println("shatter");
  Serial.println("skull");
  Serial.println("co");
  Serial.println("sos");
  Serial.println("clear");
  Serial.println();
}


// ============================================================
// LOOP
// ============================================================

void loop() {

  if (Serial.available() > 0) {

    String command = Serial.readStringUntil('\n');

    handleCommand(command);

  }
}